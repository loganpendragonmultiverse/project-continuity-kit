import stat
import struct
import zipfile

import pytest

from project_continuity_kit import bundle_io
from project_continuity_kit.core import (
    analyze,
    verify_bundle,
    write_bundle,
)


def sample(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "README.md").write_text("hello")
    return root, analyze({"root": str(root)})


def rewrite(path, change):
    with zipfile.ZipFile(path) as archive:
        contents = {name: archive.read(name) for name in archive.namelist()}
    change(contents)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, content in contents.items():
            archive.writestr(name, content)


@pytest.mark.parametrize(
    "value", [b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":1e999}', b"[" * 2000 + b"]" * 2000]
)
def test_strict_json(value):
    with pytest.raises(ValueError):
        bundle_io.json_bytes(value)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.update(project="other"),
        lambda r: r.update(schema_version=True),
        lambda r: r.update(scan_complete=False),
        lambda r: r["files"].append(dict(r["files"][0])),
        lambda r: r["files"][0].update(path="../outside"),
        lambda r: r["files"][0].update(bytes=True),
        lambda r: r["files"][0].update(sha256="bad"),
        lambda r: r.update(manifest_sha256="0" * 64),
        lambda r: r.update(file_count=True),
        lambda r: r.update(total_bytes=-1),
        lambda r: r.update(signals={"docs": [42]}),
        lambda r: r.update(scan_limits={**r["scan_limits"], "max_files": 1}, files=r["files"] * 2),
    ],
)
def test_invalid_manifest_never_creates_bundle(tmp_path, mutation):
    root, report = sample(tmp_path)
    mutation(report)
    target = tmp_path / "handoff.zip"
    with pytest.raises(ValueError):
        write_bundle(report, target)
    assert not target.exists()
    assert (root / "README.md").read_text() == "hello"


def test_verify_record_and_legacy_privacy_validation(tmp_path):
    root, report = sample(tmp_path)
    target = tmp_path / "handoff.zip"
    write_bundle(report, target)
    rewrite(target, lambda c: c.update({"VERIFY.txt": b"different"}))
    with pytest.raises(ValueError, match="verification record"):
        verify_bundle(target, root)
    report.pop("scan_scope")
    report["privacy"] = []
    legacy = tmp_path / "legacy.zip"
    write_bundle(report, legacy)
    with pytest.raises(ValueError, match="privacy"):
        verify_bundle(legacy, root)
    with pytest.raises(ValueError, match="root"):
        verify_bundle(legacy, root / "README.md")


@pytest.mark.parametrize("kind", ["missing", "unknown", "duplicate", "special", "unsupported"])
def test_member_inventory_is_exact(tmp_path, kind):
    root, report = sample(tmp_path)
    target = tmp_path / "handoff.zip"
    write_bundle(report, target)
    if kind in {"missing", "unknown"}:
        rewrite(
            target,
            lambda c: c.pop("VERIFY.txt") if kind == "missing" else c.update({"extra": b"x"}),
        )
    else:
        with zipfile.ZipFile(target) as archive:
            contents = {name: archive.read(name) for name in archive.namelist()}
        with zipfile.ZipFile(target, "w") as archive:
            for name, content in contents.items():
                info = zipfile.ZipInfo(name)
                if name == "VERIFY.txt" and kind == "special":
                    info.external_attr = (stat.S_IFLNK | 0o777) << 16
                if name == "VERIFY.txt" and kind == "unsupported":
                    info.compress_type = zipfile.ZIP_BZIP2
                archive.writestr(info, content)
            if kind == "duplicate":
                archive.writestr("VERIFY.txt", b"duplicate")
    with pytest.raises(ValueError):
        verify_bundle(target, root)


@pytest.mark.parametrize(
    "mutation", ["no_end", "disk", "offset", "count", "central_signature", "central_lengths"]
)
def test_bounded_directory_parsing(tmp_path, mutation):
    root, report = sample(tmp_path)
    target = tmp_path / "handoff.zip"
    write_bundle(report, target)
    raw = bytearray(target.read_bytes())
    end = raw.rfind(b"PK\x05\x06")
    directory = raw.find(b"PK\x01\x02")
    if mutation == "no_end":
        raw = raw[:end]
    elif mutation == "disk":
        struct.pack_into("<H", raw, end + 4, 1)
    elif mutation == "offset":
        struct.pack_into("<L", raw, end + 16, 0)
    elif mutation == "count":
        struct.pack_into("<HH", raw, end + 8, 3, 3)
    elif mutation == "central_signature":
        raw[directory] = 0
    else:
        struct.pack_into("<H", raw, directory + 28, 65535)
    target.write_bytes(raw)
    with pytest.raises(ValueError):
        verify_bundle(target, root)


@pytest.mark.parametrize("mutation", ["deflate", "underdeclared", "crc", "trailing", "incomplete"])
def test_complete_compressed_stream_required(tmp_path, mutation):
    root, report = sample(tmp_path)
    target = tmp_path / "handoff.zip"
    write_bundle(report, target)
    raw = bytearray(target.read_bytes())
    central = raw.find(b"PK\x01\x02")
    namesize, extrasize = struct.unpack_from("<HH", raw, 26)
    start = 30 + namesize + extrasize
    compressed = struct.unpack_from("<L", raw, central + 20)[0]
    if mutation == "deflate":
        raw[start] = 255
    elif mutation == "underdeclared":
        struct.pack_into("<L", raw, central + 24, 1)
    elif mutation == "crc":
        struct.pack_into("<L", raw, central + 16, 0)
    elif mutation == "trailing":
        # A complete empty stream followed by the original compressed member.
        raw[start : start + 2] = b"\x03\x00"
    else:
        struct.pack_into("<L", raw, central + 20, compressed - 1)
        struct.pack_into("<L", raw, 18, compressed - 1)
    target.write_bytes(raw)
    with pytest.raises((ValueError, zipfile.BadZipFile)):
        verify_bundle(target, root)


def test_render_and_read_limits_are_enforced(tmp_path, monkeypatch):
    root, report = sample(tmp_path)
    monkeypatch.setattr("project_continuity_kit.core.MAX_MEMBER_BYTES", 1)
    with pytest.raises(ValueError, match="Rendered"):
        write_bundle(report, tmp_path / "large.zip")
    target = tmp_path / "valid.zip"
    monkeypatch.undo()
    write_bundle(report, target)
    monkeypatch.setattr(bundle_io, "MAX_MEMBER_BYTES", 1)
    with pytest.raises(ValueError, match="size limit"):
        verify_bundle(target, root)


@pytest.mark.parametrize(
    "value",
    [float("inf"), float("nan"), {"nested": float("-inf")}, {1: "nonstring"}, {"tuple": (1, 2)}],
)
def test_direct_api_refuses_non_json_notes(tmp_path, value):
    root = tmp_path / "source"
    root.mkdir()
    with pytest.raises(ValueError, match="JSON"):
        analyze({"root": str(root), "sections": {"architecture": value}})


def test_bundle_json_exponent_overflow_is_refused(tmp_path):
    root, report = sample(tmp_path)
    target = tmp_path / "handoff.zip"
    write_bundle(report, target)
    rewrite(
        target,
        lambda c: c.update(
            {
                "continuity.json": c["continuity.json"].replace(
                    b'"schema_version": 3', b'"schema_version": 1e999'
                )
            }
        ),
    )
    with pytest.raises(ValueError, match="finite"):
        verify_bundle(target, root)


def test_zip64_locator_is_explicitly_refused():
    raw = b"PK\x06\x07" + b"\0" * 16 + struct.pack("<4s4H2LH", b"PK\x05\x06", 0, 0, 1, 1, 0, 20, 0)
    with pytest.raises(ValueError, match="ZIP64"):
        bundle_io._directory_guard(raw)
