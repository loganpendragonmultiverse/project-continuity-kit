import json
from pathlib import Path
from zipfile import ZipFile

import pytest

from project_continuity_kit.cli import main
from project_continuity_kit.core import (
    analyze,
    render_json,
    render_markdown,
    verify_bundle,
    write_bundle,
)


def complete_input(root: Path) -> dict:
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text("name: CI", encoding="utf-8")
    (root / "pyproject.toml").write_text("[project]", encoding="utf-8")
    (root / ".env.example").write_text("TOKEN=replace", encoding="utf-8")
    (root / "README.md").write_text("Run pytest to verify recovery.", encoding="utf-8")
    return {
        "root": str(root),
        "sections": {
            name: {"summary": name, "api_token": "hide"}
            for name in (
                "architecture",
                "operations",
                "dependencies",
                "deployment",
                "recovery",
                "handoff",
            )
        },
        "recovery_checklist": [
            {"step": "Restore backup", "status": "verified", "evidence": "test-1"}
        ],
        "redact": ["private-name"],
        "required_commands": ["python"],
        "required_files": ["pyproject.toml"],
        "required_artifacts": ["README.md"],
        "required_environment": ["TOKEN"],
        "documented_commands": ["pytest"],
    }


def test_complete_package_is_ready_and_redacted(tmp_path):
    data = complete_input(tmp_path)
    report = analyze(data)
    assert report["ready_for_handoff"] is True
    assert report["sections"]["deployment"]["api_token"] == "[REDACTED]"
    assert report["signals"]["ci_workflows"] == [".github/workflows/ci.yml"]
    assert report["privacy"]["source_contents_included"] is False
    assert report["manifest_sha256"] in render_markdown(report)
    assert '"schema_version": 3' in render_json(report)
    assert report["recovery_drill"]["ready"] is True
    assert report["privacy"]["recovery_commands_executed"] is False


def test_gaps_exclusions_and_previous_diff(tmp_path):
    (tmp_path / "keep.txt").write_text("new", encoding="utf-8")
    (tmp_path / "skip.tmp").write_text("skip", encoding="utf-8")
    (tmp_path / ".env.secret").write_text("secret", encoding="utf-8")
    old = {"files": [{"path": "keep.txt", "sha256": "old"}, {"path": "gone.txt", "sha256": "x"}]}
    report = analyze({"root": str(tmp_path), "exclude": ["skip.tmp"], "previous": old})
    assert report["ready_for_handoff"] is False
    assert report["changes"]["changed"] == ["keep.txt"]
    assert report["changes"]["removed"] == ["gone.txt"]
    assert [item["path"] for item in report["files"]] == ["keep.txt"]


def test_bundle_is_deterministic_and_safe(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    report = analyze(complete_input(source))
    bundle = tmp_path / "continuity.zip"
    write_bundle(report, bundle)
    with ZipFile(bundle) as archive:
        assert archive.namelist() == ["continuity.json", "HANDOFF.md", "VERIFY.txt"]
        assert b"source_contents_included" in archive.read("continuity.json")
    with pytest.raises(ValueError, match="already exists"):
        write_bundle(report, bundle)


def test_bundle_verification_detects_repository_drift(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    report = analyze(complete_input(source))
    bundle = tmp_path / "continuity.zip"
    write_bundle(report, bundle)
    matching = verify_bundle(bundle, source)
    assert matching["matches"] is True
    (source / "new.txt").write_text("new", encoding="utf-8")
    drift = verify_bundle(bundle, source)
    assert drift["matches"] is False
    assert drift["changes"]["added"] == ["new.txt"]


@pytest.mark.parametrize(
    "data,message",
    [
        ({}, "root is required"),
        ({"root": "missing"}, "existing directory"),
        ({"root": ".", "exclude": "bad"}, "exclude must be a list"),
        ({"root": ".", "redact": [""]}, "redact must contain"),
        ({"root": ".", "sections": []}, "sections must be an object"),
        ({"root": ".", "recovery_checklist": "bad"}, "checklist must be a list"),
        ({"root": ".", "required_files": [""]}, "required_files must contain"),
        (
            {"root": ".", "recovery_checklist": [{"step": "x", "status": "done"}]},
            "status is invalid",
        ),
    ],
)
def test_invalid_inputs(data, message):
    with pytest.raises((TypeError, ValueError), match=message):
        analyze(data)


def test_cli_writes_report_and_bundle_without_overwrite(tmp_path, capsys):
    source = tmp_path / "source"
    source.mkdir()
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(complete_input(source)), encoding="utf-8")
    bundle = tmp_path / "bundle.zip"
    assert main([str(input_path), "--format", "json", "--bundle", str(bundle)]) == 0
    assert json.loads(capsys.readouterr().out)["project"] == "project-continuity-kit"
    output = tmp_path / "report.md"
    assert main([str(input_path), "--output", str(output)]) == 0
    assert output.exists()
    assert main([str(input_path), "--output", str(output)]) == 2
    assert main(["--verify-bundle", str(bundle), "--root", str(source), "--format", "json"]) == 0
    assert json.loads(capsys.readouterr().out)["matches"] is True
    assert main(["--verify-bundle", str(bundle)]) == 2
