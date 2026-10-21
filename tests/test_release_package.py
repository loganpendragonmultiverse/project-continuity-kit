"""Tiny release fixtures verify refusal before existing checksums change."""

from __future__ import annotations

import importlib.util
import io
import tarfile
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location(
    "release_package", Path(__file__).resolve().parents[1] / "tools/release_package.py"
)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)
PROJECT = {"name": "sample-tool", "version": "1.2.3", "requires-python": ">=3.10"}
IDENTITY = {"Name": "sample-tool", "Version": "1.2.3", "Requires-Python": ">=3.10"}
STEM = "sample_tool-1.2.3"


def metadata(fields: dict[str, str]) -> bytes:
    return (
        "Metadata-Version: 2.4\n"
        + "".join(f"{key}: {value}\n" for key, value in fields.items())
        + "\n"
    ).encode()


def payloads(root: Path, kind: str = "", raw: bytes = b"") -> None:
    output = root / "dist"
    output.mkdir(exist_ok=True)
    with zipfile.ZipFile(output / (STEM + "-py3-none-any.whl"), "w") as archive:
        archive.writestr(
            STEM + ".dist-info/METADATA", raw if kind == "wheel" else metadata(IDENTITY)
        )
    data = raw if kind == "sdist" else metadata(IDENTITY)
    with tarfile.open(output / (STEM + ".tar.gz"), "w:gz") as archive:
        member = tarfile.TarInfo(STEM + "/PKG-INFO")
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))


def test_valid_release(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_REF_TYPE", "tag")
    monkeypatch.setenv("GITHUB_REF_NAME", "v1.2.3")
    payloads(tmp_path)
    rows = release.write_checksums(tmp_path, PROJECT, '__version__ = "1.2.3"').splitlines()
    assert len(rows) == 2
    assert {row.split("  ")[1] for row in rows} == {STEM + ".tar.gz", STEM + "-py3-none-any.whl"}
    assert all(len(row.split("  ")[0]) == 64 for row in rows)


@pytest.mark.parametrize("field", ["Name", "Version", "Requires-Python"])
@pytest.mark.parametrize("problem", ["missing", "different", "duplicate"])
@pytest.mark.parametrize("kind", ["wheel", "sdist"])
def test_built_identity_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str, problem: str, kind: str
) -> None:
    monkeypatch.delenv("GITHUB_REF_TYPE", raising=False)
    fields = dict(IDENTITY)
    if problem == "missing":
        del fields[field]
    elif problem == "different":
        fields[field] = "other"
    raw = metadata(fields)
    if problem == "duplicate":
        raw = raw.rstrip(b"\n") + f"\n{field}: {fields[field]}\n\n".encode()
    payloads(tmp_path, kind, raw)
    checksum = tmp_path / "dist/SHA256SUMS"
    checksum.write_text("preserved")
    with pytest.raises(ValueError, match="metadata"):
        release.write_checksums(tmp_path, PROJECT, '__version__ = "1.2.3"')
    assert checksum.read_text() == "preserved"


@pytest.mark.parametrize(
    "source", ['__version__ = "0.0.0"', '__version__ = "1.2.3"\n__version__ = "1.2.3"', "other = 1"]
)
def test_runtime_refusal(source: str) -> None:
    with pytest.raises(ValueError, match="Runtime/package"):
        release.validate_runtime(source, "1.2.3")


@pytest.mark.parametrize("problem", ["tag", "extra", "missing"])
def test_tag_and_payload_refusal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, problem: str
) -> None:
    payloads(tmp_path)
    checksum = tmp_path / "dist/SHA256SUMS"
    checksum.write_text("preserved")
    monkeypatch.delenv("GITHUB_REF_TYPE", raising=False)
    if problem == "tag":
        monkeypatch.setenv("GITHUB_REF_TYPE", "tag")
        monkeypatch.setenv("GITHUB_REF_NAME", "v0.0.0")
    elif problem == "extra":
        (tmp_path / "dist/unexpected.txt").write_text("extra")
    else:
        (tmp_path / "dist" / (STEM + ".tar.gz")).rename(tmp_path / "outside.tar.gz")
    with pytest.raises(ValueError):
        release.write_checksums(tmp_path, PROJECT, '__version__ = "1.2.3"')
    assert checksum.read_text() == "preserved"
