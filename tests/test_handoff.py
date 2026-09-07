import json
from pathlib import Path

import pytest

from project_continuity_kit.cli import main
from project_continuity_kit.core import analyze
from project_continuity_kit.handoff import render_html, validate_spec


@pytest.mark.parametrize(
    "change,field",
    [
        ({"root": 4}, "root"),
        ({"required_files": ["../secret"]}, "required_files"),
        ({"required_artifacts": ["C:/outside/*"]}, "required_artifacts"),
        ({"sections": {"operations": False}}, "sections.operations"),
        ({"recovery_checklist": [None]}, "recovery_checklist"),
        ({"recovery_checklist": [""]}, "step"),
        ({"recovery_checklist": [{"step": "ok", "status": 1}]}, "status"),
        ({"recovery_checklist": [{}]}, "step"),
        ({"recovery_checklist": [{"id": "a", "step": "x"}, {"id": "a", "step": "y"}]}, "id"),
        ({"owners": {"operations": []}}, "owners"),
        ({"previous": []}, "previous"),
        ({"previous": {"files": [None]}}, "previous.files"),
        ({"previous": {"files": [{"path": "a", "sha256": "a"}] * 2}}, "duplicated"),
    ],
)
def test_field_specific_validation(change: dict, field: str) -> None:
    with pytest.raises((TypeError, ValueError), match=field):
        validate_spec({"root": ".", **change})


def test_handoff_evidence_ownership_changes_and_cli(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "README.md").write_text("Original", encoding="utf-8")
    spec = {
        "root": str(root),
        "owners": {"operations": "A <B>"},
        "sections": {"operations": ["assertion", {"secret": "never show"}]},
        "recovery_checklist": [
            {"step": "Inspect <source>", "status": "verified", "evidence": "README.md"},
            "Review manually",
        ],
    }
    before = analyze(spec)
    (root / "README.md").write_text("Changed", encoding="utf-8")
    after = analyze({**spec, "previous": before})
    assert after["changes"]["changed"] == ["README.md"]
    assert after["ownership"]["assigned"] == 1
    assert after["recovery_drill"]["arbitrary_commands_executed"] is False
    html = render_html(after)
    assert 'href="#file-0"' in html
    assert "A &lt;B&gt;" in html and "<source>" not in html
    assert "never show" not in html
    assert "Unverified human assertions" in html
    source, target = tmp_path / "input.json", tmp_path / "handoff.html"
    source.write_text(json.dumps(spec), encoding="utf-8")
    assert main([str(source), "--format", "html", "--output", str(target)]) == 0
    assert "Observed files" in target.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="owners keys"):
        analyze({"root": str(root), "owners": {"unknown": "owner"}})
