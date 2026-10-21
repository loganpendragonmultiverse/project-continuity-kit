from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from zipfile import BadZipFile

from .bundle_io import json_bytes
from .core import (
    DEFAULT_EXCLUDES,
    analyze,
    render_json,
    render_markdown,
    verify_bundle,
    write_bundle,
)
from .filesystem import chunks, no_links
from .handoff import render_html, validate_spec


def _destination(path: Path, root: Path, excluded: set[str]) -> Path:
    target = no_links(path).resolve()
    if target.exists() or target.is_symlink():
        raise ValueError(f"output already exists: {path}")
    if target == root or root in target.parents:
        parts = target.relative_to(root).parts
        if not any(
            part in excluded or part.startswith(".env.") and part != ".env.example"
            for part in parts
        ):
            raise ValueError(
                "Outputs must be outside the scanned root or under an excluded path component"
            )
    return target


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a redacted, verifiable continuity package.")
    parser.add_argument("input", nargs="?", type=Path, help="UTF-8 JSON input file")
    parser.add_argument("--format", choices=("markdown", "json", "html"), default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bundle", type=Path, help="write a deterministic continuity ZIP")
    parser.add_argument(
        "--verify-bundle", type=Path, help="compare an existing bundle with a repository"
    )
    parser.add_argument("--root", type=Path, help="repository root used with --verify-bundle")
    args = parser.parse_args(argv)
    try:
        if args.verify_bundle:
            if args.input or args.bundle:
                raise ValueError("Choose generation or bundle verification, not both")
            if not args.root:
                raise ValueError("--verify-bundle requires --root")
            report = verify_bundle(args.verify_bundle, args.root)
            root = no_links(args.root).resolve()
            excluded = set(report["scan_scope"]["excluded_names"])
        else:
            if not args.input:
                raise ValueError("provide an input specification or --verify-bundle")
            if args.root:
                raise ValueError("--root is only used with --verify-bundle")
            data = json_bytes(b"".join(chunks(args.input, 1024 * 1024)))
            validate_spec(data)
            root = no_links(Path(data["root"])).resolve()
            excluded = DEFAULT_EXCLUDES | set(data.get("exclude", []))
            report = None
        output = _destination(args.output, root, excluded) if args.output else None
        bundle = _destination(args.bundle, root, excluded) if args.bundle else None
        if output is not None and output == bundle:
            raise ValueError("Report and bundle outputs must be distinct")
        if report is None:
            report = analyze(data)
        rendered = (
            render_html(report)
            if args.format == "html"
            else render_json(report)
            if args.format == "json"
            else render_markdown(report)
            if not args.verify_bundle
            else render_json(report)
        )
        if bundle:
            write_bundle(report, bundle)
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            no_links(output)
            with output.open("x", encoding="utf-8") as stream:
                stream.write(rendered)
        else:
            sys.stdout.write(rendered)
    except (
        OSError,
        UnicodeError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
        BadZipFile,
        EOFError,
    ) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
