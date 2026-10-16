import json
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

from project_continuity_kit.cli import main
from project_continuity_kit.core import analyze, verify_bundle, write_bundle


def test_bundle_retains_custom_scope(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "keep.txt").write_text("included")
    (root / "private-cache").mkdir()
    (root / "private-cache" / "first.txt").write_text("synthetic")
    report = analyze({"root": str(root), "exclude": ["private-cache"]})
    bundle = tmp_path / "bundle.zip"
    write_bundle(report, bundle)
    (root / "private-cache" / "first.txt").write_text("changed synthetic")
    (root / "private-cache" / "second.txt").write_text("added synthetic")
    assert verify_bundle(bundle, root)["matches"] is True
    (root / "keep.txt").write_text("changed included")
    assert verify_bundle(bundle, root)["changes"]["changed"] == ["keep.txt"]


@pytest.mark.parametrize(
    "policy",
    [
        None,
        {},
        {"version": 2, "excluded_names": [], "environment_files": "exclude-dotenv-except-example"},
        {
            "version": True,
            "excluded_names": [],
            "environment_files": "exclude-dotenv-except-example",
        },
        {
            "version": 1,
            "excluded_names": "bad",
            "environment_files": "exclude-dotenv-except-example",
        },
        {
            "version": 1,
            "excluded_names": ["../private"],
            "environment_files": "exclude-dotenv-except-example",
        },
    ],
)
def test_malformed_scope_fails_without_output(policy, tmp_path, capsys):
    root = tmp_path / "source"
    root.mkdir()
    report = analyze({"root": str(root)})
    report["scan_scope"] = policy
    bundle = tmp_path / "invalid.zip"
    with ZipFile(bundle, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("continuity.json", json.dumps(report))
    output = tmp_path / "report.json"
    assert main(["--verify-bundle", str(bundle), "--root", str(root), "--output", str(output)]) == 2
    assert not output.exists()
    assert not capsys.readouterr().out


def test_legacy_scope_and_deterministic_value_free_bundle(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "cache").mkdir()
    (root / "cache" / "secret.txt").write_text("SYNTHETIC-VALUE")
    report = analyze({"root": str(root), "exclude": ["cache"]})
    first, second = tmp_path / "first.zip", tmp_path / "second.zip"
    write_bundle(report, first)
    write_bundle(report, second)
    assert first.read_bytes() == second.read_bytes()
    with ZipFile(first) as archive:
        assert b"SYNTHETIC-VALUE" not in archive.read("continuity.json")
    del report["scan_scope"]
    legacy = tmp_path / "legacy.zip"
    write_bundle(report, legacy)
    verified = verify_bundle(legacy, root)
    assert verified["matches"] and verified["scan_scope_source"] == "legacy-privacy"
    del report["privacy"]
    defaults = tmp_path / "defaults.zip"
    write_bundle(report, defaults)
    result = verify_bundle(defaults, root)
    assert result["scan_scope_source"] == "legacy-defaults"
    assert result["changes"]["added"] == ["cache/secret.txt"]
