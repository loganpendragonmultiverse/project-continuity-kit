from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .core import analyze, render_json, render_markdown, verify_bundle, write_bundle


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a redacted, verifiable continuity package.")
    parser.add_argument("input", nargs="?", type=Path, help="UTF-8 JSON input file")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--bundle", type=Path, help="write a deterministic continuity ZIP")
    parser.add_argument(
        "--verify-bundle", type=Path, help="compare an existing bundle with a repository"
    )
    parser.add_argument("--root", type=Path, help="repository root used with --verify-bundle")
    args = parser.parse_args(argv)
    try:
        if args.verify_bundle:
            if not args.root:
                raise ValueError("--verify-bundle requires --root")
            report = verify_bundle(args.verify_bundle, args.root)
        else:
            if not args.input:
                raise ValueError("provide an input specification or --verify-bundle")
            data = json.loads(args.input.read_text(encoding="utf-8"))
            report = analyze(data)
        rendered = render_json(report) if args.format == "json" else render_markdown(report)
        if args.output:
            if args.output.exists():
                raise ValueError(f"output already exists: {args.output}")
            args.output.write_text(rendered, encoding="utf-8")
        else:
            sys.stdout.write(rendered)
        if args.bundle and not args.verify_bundle:
            write_bundle(report, args.bundle)
    except (OSError, UnicodeError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0
