"""Validate tagged distribution identity before writing two-payload checksums."""

from __future__ import annotations

import ast
import hashlib
import os
import stat
import tarfile
import zipfile
from email.parser import BytesParser
from pathlib import Path

RUNTIME_MODULE = "project_continuity_kit"
MAX_METADATA = 4 * 1024 * 1024


def validate_metadata(raw: bytes, identity: dict[str, str]) -> None:
    if len(raw) > MAX_METADATA:
        raise ValueError("Built metadata exceeds limit")
    message = BytesParser().parsebytes(raw)
    for field, value in identity.items():
        if message.get_all(field, []) != [value]:
            raise ValueError(f"Built metadata {field} disagrees with project")


def validate_runtime(source: str, version: str) -> None:
    versions = [
        ast.literal_eval(node.value)
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign)
        and any(isinstance(name, ast.Name) and name.id == "__version__" for name in node.targets)
    ]
    if versions != [version]:
        raise ValueError("Runtime/package versions disagree")


def validate_distribution(path: Path, identity: dict[str, str], stem: str) -> None:
    if path.suffix == ".whl":
        with zipfile.ZipFile(path) as archive:
            members = [
                entry for entry in archive.infolist() if entry.filename.endswith("/METADATA")
            ]
            if len(members) != 1 or members[0].filename != stem + ".dist-info/METADATA":
                raise ValueError("Wheel metadata path/count disagrees")
            member = members[0]
            if member.is_dir() or stat.S_ISLNK(member.external_attr >> 16) or member.flag_bits & 1:
                raise ValueError("Wheel metadata must be regular and unencrypted")
            if member.file_size > MAX_METADATA:
                raise ValueError("Built metadata exceeds limit")
            validate_metadata(archive.read(member), identity)
    else:
        with tarfile.open(path, "r:gz") as archive:
            members = [entry for entry in archive.getmembers() if entry.name == stem + "/PKG-INFO"]
            if len(members) != 1 or not members[0].isfile():
                raise ValueError("Source metadata path/count/type disagrees")
            if members[0].size > MAX_METADATA:
                raise ValueError("Built metadata exceeds limit")
            handle = archive.extractfile(members[0])
            if handle is None:
                raise ValueError("Source metadata unavailable")
            with handle:
                validate_metadata(handle.read(MAX_METADATA + 1), identity)


def write_checksums(root: Path, project: dict[str, str], source: str) -> str:
    name, version, floor = project["name"], project["version"], project["requires-python"]
    if not all(isinstance(value, str) and value for value in (name, version, floor)):
        raise ValueError("Release identity must contain nonempty strings")
    validate_runtime(source, version)
    if (
        os.environ.get("GITHUB_REF_TYPE") == "tag"
        and os.environ.get("GITHUB_REF_NAME") != "v" + version
    ):
        raise ValueError("Tag/package versions disagree")
    output = root / "dist"
    stem = name.replace("-", "_") + "-" + version
    expected = {stem + "-py3-none-any.whl", stem + ".tar.gz"}
    if {file.name for file in output.iterdir()} - {"SHA256SUMS"} != expected:
        raise ValueError("Expected exactly the current wheel and source distribution")
    identity = {"Name": name, "Version": version, "Requires-Python": floor}
    rows = []
    for filename in sorted(expected):
        file = output / filename
        if file.is_symlink() or not stat.S_ISREG(file.stat().st_mode):
            raise ValueError("Distributions must be regular files")
        validate_distribution(file, identity, stem)
        digest = hashlib.sha256()
        with file.open("rb") as handle:
            for block in iter(lambda: handle.read(65536), b""):
                digest.update(block)
        rows.append(digest.hexdigest() + "  " + filename + "\n")
    checksum = output / "SHA256SUMS"
    if checksum.is_symlink() or (checksum.exists() and not checksum.is_file()):
        raise ValueError("Checksum output must be a regular file")
    result = "".join(rows)
    checksum.write_text(result, encoding="utf-8")
    return result


def main() -> None:
    # Only this packaging entry point requires Python 3.11+; validators support 3.10.
    import tomllib

    root = Path(__file__).resolve().parents[1]
    project = tomllib.loads((root / "pyproject.toml").read_text("utf-8"))["project"]
    source = (root / "src" / RUNTIME_MODULE / "__init__.py").read_text("utf-8")
    print(write_checksums(root, project, source), end="")


if __name__ == "__main__":
    main()
