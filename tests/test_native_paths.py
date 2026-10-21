"""Actual OS link fixtures; focused Windows acceptance requires zero skips."""

import subprocess
import sys

import pytest

from project_continuity_kit.core import analyze, verify_bundle, write_bundle


@pytest.mark.skipif(sys.platform != "win32", reason="actual Windows junction fixture")
@pytest.mark.parametrize("position", ["root", "ancestor", "included", "bundle"])
def test_windows_junction_refusal(tmp_path, position):
    source = tmp_path / "source"
    source.mkdir()
    file = source / "README.md"
    file.write_bytes(b"source evidence")
    bundle = tmp_path / "bundle.zip"
    write_bundle(analyze({"root": str(source)}), bundle)
    before = file.read_bytes(), bundle.read_bytes()
    link = (source / "linked") if position == "included" else tmp_path / "junction"
    destination = source if position in {"root", "included"} else tmp_path / "outside"
    if destination != source:
        destination.mkdir()
        (destination / "child").mkdir()
        (destination / "bundle.zip").write_bytes(bundle.read_bytes())
    created = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(destination)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert created.returncode == 0, created.stdout + created.stderr
    assert link.lstat().st_file_attributes & 0x400
    with pytest.raises(ValueError, match="reparse"):
        if position == "bundle":
            verify_bundle(link / "bundle.zip", source)
        else:
            analyze(
                {
                    "root": str(
                        link / "child"
                        if position == "ancestor"
                        else link
                        if position == "root"
                        else source
                    )
                }
            )
    assert (file.read_bytes(), bundle.read_bytes()) == before


@pytest.mark.parametrize("position", ["root", "ancestor", "included", "bundle"])
def test_real_symlink_refusal(tmp_path, position):
    source = tmp_path / "source"
    source.mkdir()
    original = source / "README.md"
    original.write_bytes(b"source evidence")
    bundle = tmp_path / "bundle.zip"
    write_bundle(analyze({"root": str(source)}), bundle)
    before = original.read_bytes(), bundle.read_bytes()
    link = source / "linked" if position == "included" else tmp_path / "link"
    try:
        link.symlink_to(
            bundle if position == "bundle" else source, target_is_directory=position != "bundle"
        )
    except OSError as error:
        pytest.skip(f"actual symlink capability unavailable: {error}")
    with pytest.raises(ValueError, match="symlink"):
        if position == "bundle":
            verify_bundle(link, source)
        else:
            analyze(
                {
                    "root": str(
                        link / "child"
                        if position == "ancestor"
                        else link
                        if position == "root"
                        else source
                    )
                }
            )
    assert (original.read_bytes(), bundle.read_bytes()) == before
