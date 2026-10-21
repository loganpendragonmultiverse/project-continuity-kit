import json
import os
from pathlib import Path

import pytest

from project_continuity_kit import filesystem as fs
from project_continuity_kit.cli import main
from project_continuity_kit.core import analyze, verify_bundle, write_bundle


@pytest.mark.parametrize("position", ["root", "ancestor", "file", "directory"])
def test_symlinks_cannot_read_outside_selected_scope(tmp_path, position):
    root = tmp_path / "source"
    root.mkdir()
    (root / "real").mkdir()
    (root / "real/data.txt").write_text("synthetic")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "private.txt").write_text("synthetic outside")
    link = tmp_path / "root-link" if position in {"root", "ancestor"} else root / "linked"
    target = (
        root
        if position in {"root", "ancestor"}
        else outside / "private.txt"
        if position == "file"
        else outside
    )
    try:
        link.symlink_to(target, target_is_directory=position != "file")
    except OSError:
        pytest.skip("Actual symlink creation unavailable; not native acceptance")
    selected = link if position == "root" else link / "real" if position == "ancestor" else root
    with pytest.raises(ValueError, match="symlink|junction|reparse"):
        analyze({"root": str(selected)})
    assert (outside / "private.txt").read_text() == "synthetic outside"


@pytest.mark.parametrize(
    "field", ["max_files", "max_entries", "max_file_bytes", "max_total_bytes", "max_depth"]
)
@pytest.mark.parametrize("bad", [True, 0, -1, "2", 1.5, 10**12])
def test_scan_budget_types_and_caps(field, bad):
    policy = fs.limits()
    policy[field] = bad
    with pytest.raises(ValueError, match="scan_limits"):
        fs.limits(policy)


@pytest.mark.parametrize("value", [[], {}, {"version": True}])
def test_scan_budget_shape_is_versioned(value):
    with pytest.raises(ValueError, match="scan_limits"):
        fs.limits(value)


@pytest.mark.parametrize(
    "budget", ["max_files", "max_entries", "max_file_bytes", "max_total_bytes", "max_depth"]
)
def test_exhausted_budget_never_emits_a_partial_match(tmp_path, budget):
    root = tmp_path / "source"
    root.mkdir()
    (root / "one").write_bytes(b"aa")
    (root / "two").write_bytes(b"bb")
    (root / "nested/deeper").mkdir(parents=True)
    policy = fs.limits()
    policy[budget] = 1
    with pytest.raises(ValueError, match="budget"):
        analyze({"root": str(root), "scan_limits": policy})


def test_exact_file_budget_empty_files_and_recorded_limits_roundtrip(tmp_path):
    root = tmp_path / "source"
    root.mkdir()
    (root / "a").write_bytes(b"1234")
    (root / "empty").write_bytes(b"")
    policy = fs.limits()
    policy.update(max_file_bytes=4, max_total_bytes=4)
    report = analyze({"root": str(root), "scan_limits": policy})
    assert report["scan_complete"] and report["total_bytes"] == 4
    bundle = tmp_path / "bundle.zip"
    write_bundle(report, bundle)
    assert verify_bundle(bundle, root)["scan_limits"] == policy
    (root / "a").write_bytes(b"12345")
    with pytest.raises(ValueError, match="budget"):
        verify_bundle(bundle, root)


def test_changed_file_aborts_observation(tmp_path):
    file = tmp_path / "a"
    file.write_bytes(b"abc")
    iterator = fs.chunks(file, 10)
    assert next(iterator) == b"abc"
    file.write_bytes(b"changed")
    with pytest.raises(ValueError, match="changed|inconsistent"):
        list(iterator)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO fixture")
def test_special_file_is_refused_before_open(tmp_path):
    os.mkfifo(tmp_path / "pipe")
    with pytest.raises(ValueError, match="regular"):
        analyze({"root": str(tmp_path)})


def test_scan_error_is_actionable_and_writes_no_outputs(tmp_path, monkeypatch, capsys):
    root = tmp_path / "source"
    root.mkdir()
    spec = tmp_path / "input.json"
    spec.write_text(json.dumps({"root": str(root)}))
    original = fs.os.scandir

    def denied(path):
        if Path(path) == root:
            raise PermissionError("synthetic denied scan")
        return original(path)

    monkeypatch.setattr(fs.os, "scandir", denied)
    output, bundle = tmp_path / "report.json", tmp_path / "bundle.zip"
    assert main([str(spec), "--output", str(output), "--bundle", str(bundle)]) == 2
    assert not output.exists() and not bundle.exists()
    assert "denied" in capsys.readouterr().err


def test_excluded_artifacts_docs_and_examples_cannot_satisfy_observations(tmp_path):
    (tmp_path / ".env").write_text("SYNTHETIC=fixture")
    (tmp_path / ".env.example").write_text("EXAMPLE=value")
    (tmp_path / "README.md").write_text("synthetic command")
    report = analyze(
        {
            "root": str(tmp_path),
            "exclude": ["README.md", ".env.example"],
            "required_artifacts": [".env"],
            "documented_commands": ["synthetic command"],
            "required_environment": ["EXAMPLE"],
        }
    )
    assert report["file_count"] == 0
    assert all(not check["passed"] for check in report["recovery_drill"]["checks"])


@pytest.mark.parametrize(
    "path,pattern,expected",
    [
        ("a.py", "*.py", True),
        ("dir/a.py", "*.py", False),
        ("dir/a.py", "**/*.py", True),
        ("a.py", "**/*.py", True),
        ("a/b/c", "a/**", True),
        ("a/b/c", "a/?/c", True),
        ("a/b/c", "a/[x]/c", False),
    ],
)
def test_artifact_globs_match_included_components(path, pattern, expected):
    assert fs.artifact_matches(path, pattern) is expected


def test_owner_and_checklist_notes_are_redacted(tmp_path):
    report = analyze(
        {
            "root": str(tmp_path),
            "redact": ["PRIVATE"],
            "owners": {"operations": "PRIVATE owner"},
            "recovery_checklist": [
                {"step": "PRIVATE procedure", "status": "verified", "evidence": "PRIVATE notes"}
            ],
        }
    )
    assert "PRIVATE" not in json.dumps(report)
    assert report["ownership"]["assigned"] == 1
    assert report["recovery_checklist"][0]["status"] == "verified"
    bundle = tmp_path.parent / (tmp_path.name + ".zip")
    write_bundle(report, bundle)
    assert verify_bundle(bundle, tmp_path)["matches"]


def test_document_observation_is_bounded_and_bound_to_scan(tmp_path, monkeypatch):
    (tmp_path / "README.md").write_bytes(b"abcdefgh")
    monkeypatch.setattr(fs, "MAX_OBSERVATION_BYTES", 4)
    with pytest.raises(ValueError, match="budget"):
        analyze({"root": str(tmp_path), "documented_commands": ["a"]})
    monkeypatch.setattr(fs, "MAX_OBSERVATION_BYTES", 20)
    files = fs.scan(tmp_path, set(), fs.limits())
    (tmp_path / "README.md").write_text("changed")
    with pytest.raises(ValueError, match="changed"):
        fs.observed_text(tmp_path, "README.md", files)


def test_cli_excluded_output_location_does_not_immediately_drift(tmp_path, capsys):
    root = tmp_path / "source"
    root.mkdir()
    (root / "a").write_text("data")
    spec = tmp_path / "input.json"
    spec.write_text(json.dumps({"root": str(root)}))
    bundle = root / "build/package.zip"
    output = root / "build/report.json"
    assert (
        main([str(spec), "--format", "json", "--output", str(output), "--bundle", str(bundle)]) == 0
    )
    assert verify_bundle(bundle, root)["matches"]
    assert main([str(spec), "--output", str(root / "self.json")]) == 2
    assert not (root / "self.json").exists()


def test_output_collisions_are_preflighted_and_raced_file_is_preserved(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    spec = tmp_path / "input.json"
    spec.write_text(json.dumps({"root": str(root)}))
    target = tmp_path / "target"
    assert main([str(spec), "--output", str(target), "--bundle", str(target)]) == 2
    assert not target.exists()
    target.write_text("sentinel")
    assert main([str(spec), "--bundle", str(target), "--output", str(tmp_path / "new-report")]) == 2
    assert not (tmp_path / "new-report").exists() and target.read_text() == "sentinel"
    raced = tmp_path / "raced"
    original = Path.open

    def race(path, mode="r", *args, **kwargs):
        if path == raced and mode == "x":
            with original(path, "w") as output:
                output.write("raced sentinel")
        return original(path, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", race)
    assert main([str(spec), "--output", str(raced)]) == 2
    assert raced.read_text() == "raced sentinel"


def test_stat_api_ctime_representations_do_not_fake_changes(tmp_path, monkeypatch):
    from types import SimpleNamespace

    from project_continuity_kit import filesystem

    source = tmp_path / "file.txt"
    source.write_bytes(b"unchanged evidence")
    original = filesystem.os.fstat

    def descriptor_stat(fd):
        value = original(fd)
        return SimpleNamespace(
            st_mode=value.st_mode,
            st_dev=value.st_dev,
            st_ino=value.st_ino,
            st_size=value.st_size,
            st_mtime_ns=value.st_mtime_ns,
            st_ctime_ns=value.st_ctime_ns + 1,
        )

    monkeypatch.setattr(filesystem.os, "fstat", descriptor_stat)
    assert b"".join(filesystem.chunks(source, 100)) == b"unchanged evidence"
