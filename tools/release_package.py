"""Checksum exactly the two tagged Python distributions; never publishes."""

from __future__ import annotations

import ast
import hashlib
import os
from pathlib import Path

import tomllib


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    version = tomllib.loads((root / "pyproject.toml").read_text())["project"]["version"]
    module = ast.parse((root / "src/project_continuity_kit/__init__.py").read_text())
    versions = [
        ast.literal_eval(node.value)
        for node in module.body
        if isinstance(node, ast.Assign)
        and any(isinstance(name, ast.Name) and name.id == "__version__" for name in node.targets)
    ]
    if versions != [version]:
        raise SystemExit("Runtime/package versions disagree")
    if (
        os.environ.get("GITHUB_REF_TYPE") == "tag"
        and os.environ.get("GITHUB_REF_NAME") != "v" + version
    ):
        raise SystemExit("Tag and package versions disagree")
    output = root / "dist"
    expected = {
        f"project_continuity_kit-{version}-py3-none-any.whl",
        f"project_continuity_kit-{version}.tar.gz",
    }
    actual = {file.name for file in output.iterdir()}
    if actual - {"SHA256SUMS"} != expected:
        raise SystemExit("Expected exactly current wheel and source distribution")
    rows = []
    for name in sorted(expected):
        file = output / name
        if file.is_symlink() or not file.is_file():
            raise SystemExit("Distributions must be regular files")
        digest = hashlib.sha256()
        with file.open("rb") as handle:
            for block in iter(lambda: handle.read(65536), b""):
                digest.update(block)
        rows.append(digest.hexdigest() + "  " + name + "\n")
    checksum = output / "SHA256SUMS"
    if checksum.is_symlink():
        raise SystemExit("Checksum output must not be a symbolic link")
    checksum.write_text("".join(rows), encoding="utf-8")
    print("".join(rows), end="")


if __name__ == "__main__":
    main()
