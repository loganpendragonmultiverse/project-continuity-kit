"""Bounded, complete-or-error local file observations; no recovery execution."""

from __future__ import annotations

import fnmatch
import hashlib
import os
import stat
from collections.abc import Iterator
from functools import cache
from pathlib import Path
from typing import Any

MAX_FILES = 20000
MAX_ENTRIES = 50000
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_DEPTH = 32
MAX_OBSERVATION_BYTES = 1024 * 1024


def no_links(path: Path) -> Path:
    lexical = path.expanduser().absolute()
    for node in (lexical, *lexical.parents):
        try:
            metadata = node.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & 0x400:
            raise ValueError("Selected paths must not use symlinks, junctions or reparse points")
    return lexical


def limits(value: Any = None) -> dict[str, int]:
    maximum = {
        "max_files": MAX_FILES,
        "max_entries": MAX_ENTRIES,
        "max_file_bytes": MAX_FILE_BYTES,
        "max_total_bytes": MAX_TOTAL_BYTES,
        "max_depth": MAX_DEPTH,
    }
    if value is None:
        return {"version": 1, **maximum}
    if not isinstance(value, dict) or set(value) != {"version", *maximum}:
        raise ValueError("scan_limits must contain the complete versioned budget policy")
    if type(value["version"]) is not int or value["version"] != 1:
        raise ValueError("unsupported scan_limits version")
    for key, cap in maximum.items():
        if type(value[key]) is not int or not 0 < value[key] <= cap:
            raise ValueError(f"scan_limits.{key} must be a positive integer at most {cap}")
    return dict(value)


def chunks(path: Path, budget: int) -> Iterator[bytes]:
    path = no_links(path)
    initial = path.lstat()
    if not stat.S_ISREG(initial.st_mode):
        raise ValueError(f"Only regular files can be observed: {path.name}")
    if initial.st_size > budget:
        raise ValueError(f"File exceeds observation budget: {path.name}")
    count = 0
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    with os.fdopen(os.open(path, flags), "rb") as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or (before.st_dev, before.st_ino) != (
            initial.st_dev,
            initial.st_ino,
        ):
            raise ValueError("File changed before observation")
        while True:
            block = handle.read(min(65536, budget - count + 1))
            if not block:
                break
            count += len(block)
            if count > budget:
                raise ValueError(f"File exceeds observation budget: {path.name}")
            yield block
        after = os.fstat(handle.fileno())
    current = path.lstat()

    def fields(item: os.stat_result) -> tuple[int, int, int, int, int]:
        return (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)

    if (
        fields(before) != fields(after)
        or fields(initial) != fields(current)
        or count != after.st_size
        or count != initial.st_size
    ):
        raise ValueError(f"File changed or reported an inconsistent extent: {path.name}")


def scan(root: Path, excluded: set[str], policy: dict[str, int]) -> list[dict[str, Any]]:
    root = no_links(root)
    if not root.is_dir():
        raise ValueError("root must be an existing directory")
    entries = total = 0
    files: list[dict[str, Any]] = []
    stack = [(root, 0)]
    while stack:
        directory, depth = stack.pop()
        if depth > policy["max_depth"]:
            raise ValueError("Directory exceeds scan depth budget")
        children = []
        with os.scandir(directory) as iterator:
            for child in iterator:
                entries += 1
                if entries > policy["max_entries"]:
                    raise ValueError("Directory exceeds scan entry budget")
                if (
                    child.name in excluded
                    or child.name.startswith(".env.")
                    and child.name != ".env.example"
                ):
                    continue
                children.append(Path(child.path))
        for path in sorted(children, key=lambda item: item.name):
            metadata = no_links(path).lstat()
            if stat.S_ISDIR(metadata.st_mode):
                stack.append((path, depth + 1))
                continue
            if len(files) >= policy["max_files"]:
                raise ValueError("Directory exceeds scan file budget")
            digest = hashlib.sha256()
            count = 0
            for block in chunks(
                path, min(policy["max_file_bytes"], policy["max_total_bytes"] - total)
            ):
                count += len(block)
                digest.update(block)
            total += count
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "bytes": count,
                    "sha256": digest.hexdigest(),
                }
            )
    return sorted(files, key=lambda item: item["path"])


def observed_text(root: Path, name: str, files: list[dict[str, Any]]) -> str:
    record = next((item for item in files if item["path"] == name), None)
    if record is None:
        return ""
    content = b"".join(chunks(root / name, MAX_OBSERVATION_BYTES))
    if hashlib.sha256(content).hexdigest() != record["sha256"]:
        raise ValueError("Observed documentation changed after scanning")
    return content.decode("utf-8", errors="replace")


def artifact_matches(path: str, pattern: str) -> bool:
    """Glob path components over the included inventory, without traversing disk."""
    names, patterns = tuple(path.split("/")), tuple(pattern.replace("\\", "/").split("/"))

    @cache
    def match(i: int, j: int) -> bool:
        if j == len(patterns):
            return i == len(names)
        if patterns[j] == "**":
            return match(i, j + 1) or i < len(names) and match(i + 1, j)
        return i < len(names) and fnmatch.fnmatchcase(names[i], patterns[j]) and match(i + 1, j + 1)

    return match(0, 0)
