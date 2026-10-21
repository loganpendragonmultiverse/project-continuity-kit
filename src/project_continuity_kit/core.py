from __future__ import annotations

import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .bundle_io import MAX_BUNDLE_BYTES, MAX_MEMBER_BYTES, json_bytes, read_bundle, validate_json
from .filesystem import artifact_matches, limits, no_links, observed_text, scan
from .handoff import render_html, validate_spec

PROJECT = "project-continuity-kit"
VERSION = 3
SECTIONS = ("architecture", "operations", "dependencies", "deployment", "recovery", "handoff")
DEFAULT_EXCLUDES = {".git", ".env", ".venv", "node_modules", "dist", "build", "__pycache__"}
SENSITIVE_KEY = re.compile(r"(?:password|secret|token|api[_-]?key|private[_-]?key)", re.IGNORECASE)


def _require(data: dict[str, Any], key: str) -> Any:
    value = data.get(key)
    if value is None or value == "" or value == []:
        raise ValueError(f"{key} is required")
    return value


def _redact(value: Any, terms: tuple[str, ...], key: str = "") -> Any:
    if key and SENSITIVE_KEY.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _redact(v, terms, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item, terms) for item in value]
    if isinstance(value, str):
        result = value
        for term in terms:
            result = result.replace(term, "[REDACTED]")
        return result
    return value


def _signals(paths: list[str]) -> dict[str, list[str]]:
    rules = {
        "dependency_manifests": {
            "pyproject.toml",
            "requirements.txt",
            "package.json",
            "composer.json",
        },
        "lockfiles": {"package-lock.json", "poetry.lock", "uv.lock", "composer.lock"},
        "environment_examples": {".env.example", ".env.sample", "example.env"},
        "operations_docs": {"readme.md", "development.md", "runbook.md", "operations.md"},
        "recovery_docs": {"recovery.md", "backup.md", "disaster-recovery.md"},
    }
    result = {
        name: [path for path in paths if Path(path).name.lower() in names]
        for name, names in rules.items()
    }
    result["ci_workflows"] = [path for path in paths if path.startswith(".github/workflows/")]
    result["containers"] = [
        path
        for path in paths
        if Path(path).name.lower() in {"dockerfile", "compose.yml", "docker-compose.yml"}
    ]
    return result


def _changes(files: list[dict[str, Any]], previous: dict[str, Any] | None) -> dict[str, list[str]]:
    if previous is None:
        return {"added": [], "removed": [], "changed": [], "unchanged": []}
    old = {item["path"]: item["sha256"] for item in previous.get("files", [])}
    current = {item["path"]: item["sha256"] for item in files}
    return {
        "added": sorted(current.keys() - old.keys()),
        "removed": sorted(old.keys() - current.keys()),
        "changed": sorted(
            path for path in current.keys() & old.keys() if current[path] != old[path]
        ),
        "unchanged": sorted(
            path for path in current.keys() & old.keys() if current[path] == old[path]
        ),
    }


def _string_list(data: dict[str, Any], key: str) -> list[str]:
    value = data.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value):
        raise ValueError(f"{key} must contain non-empty strings")
    return value


def _declared_environment(root: Path, files: list[dict[str, Any]]) -> set[str]:
    declared: set[str] = set()
    for name in (".env.example", ".env.sample", "example.env"):
        for line in observed_text(root, name, files).splitlines():
            candidate = line.strip()
            if candidate and not candidate.startswith("#") and "=" in candidate:
                declared.add(candidate.split("=", 1)[0].strip())
    return declared


def _recovery_drill(
    root: Path, data: dict[str, Any], files: list[dict[str, Any]]
) -> dict[str, Any]:
    required_commands = _string_list(data, "required_commands")
    required_files = _string_list(data, "required_files")
    required_artifacts = _string_list(data, "required_artifacts")
    required_environment = _string_list(data, "required_environment")
    documented_commands = _string_list(data, "documented_commands")
    paths = [item["path"] for item in files]
    declared = _declared_environment(root, files) if required_environment else set()
    docs = [root / name for name in ("README.md", "DEVELOPMENT.md", "OPERATIONS.md", "RECOVERY.md")]
    documentation = (
        "\n".join(observed_text(root, path.name, files) for path in docs)
        if documented_commands
        else ""
    )
    checks: list[dict[str, Any]] = []
    checks += [
        {
            "kind": "command_available",
            "subject": command,
            "passed": shutil.which(command) is not None,
        }
        for command in required_commands
    ]
    checks += [
        {"kind": "file_present", "subject": name, "passed": name in paths}
        for name in required_files
    ]
    checks += [
        {
            "kind": "artifact_present",
            "subject": pattern,
            "passed": any(artifact_matches(path, pattern) for path in paths),
        }
        for pattern in required_artifacts
    ]
    checks += [
        {"kind": "environment_declared", "subject": name, "passed": name in declared}
        for name in required_environment
    ]
    checks += [
        {
            "kind": "command_documented",
            "subject": command,
            "passed": command.casefold() in documentation.casefold(),
        }
        for command in documented_commands
    ]
    failed = [check for check in checks if not check["passed"]]
    return {
        "mode": "non-executing-observation",
        "checks": checks,
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "ready": bool(checks) and not failed,
        "arbitrary_commands_executed": False,
    }


def _validated_scope(value: Any) -> list[str]:
    if not isinstance(value, dict) or set(value) != {
        "version",
        "excluded_names",
        "environment_files",
    }:
        raise ValueError("scan_scope must be a versioned scan-scope object")
    if (
        type(value["version"]) is not int
        or value["version"] != 1
        or value["environment_files"] != "exclude-dotenv-except-example"
    ):
        raise ValueError("unsupported scan_scope policy")
    names = value["excluded_names"]
    if not isinstance(names, list) or any(
        not isinstance(name, str)
        or not name
        or name in {".", ".."}
        or any(c in name for c in "/\\:")
        for name in names
    ):
        raise ValueError("scan_scope excluded_names must contain path component names")
    if names != sorted(set(names)) or not DEFAULT_EXCLUDES.issubset(names):
        raise ValueError("scan_scope excluded_names must be sorted, unique and include defaults")
    return names


def _scope(names: list[str]) -> dict[str, Any]:
    return {
        "version": 1,
        "excluded_names": names,
        "environment_files": "exclude-dotenv-except-example",
    }


def _continuity(data: dict[str, Any]) -> dict[str, Any]:
    root = no_links(Path(_require(data, "root"))).resolve()
    if not root.is_dir():
        raise ValueError("root must be an existing directory")
    extra_excludes = data.get("exclude", [])
    if not isinstance(extra_excludes, list):
        raise TypeError("exclude must be a list")
    excluded = DEFAULT_EXCLUDES | set(extra_excludes)
    scan_scope = _scope(sorted(excluded))
    _validated_scope(scan_scope)
    scan_limits = limits(data.get("scan_limits"))
    files = scan(root, excluded, scan_limits)
    terms_raw = data.get("redact", [])
    if not isinstance(terms_raw, list) or any(
        not isinstance(term, str) or not term for term in terms_raw
    ):
        raise ValueError("redact must contain non-empty strings")
    sections_raw = data.get("sections", data.get("notes", {}))
    if not isinstance(sections_raw, dict):
        raise TypeError("sections must be an object")
    sections = {name: _redact(sections_raw.get(name, {}), tuple(terms_raw)) for name in SECTIONS}
    owners = _redact(data.get("owners", {}), tuple(terms_raw))
    if set(owners) - set(SECTIONS):
        raise ValueError("owners keys must be continuity section names")
    checklist_raw = data.get("recovery_checklist", [])
    if not isinstance(checklist_raw, list):
        raise TypeError("recovery_checklist must be a list")
    checklist: list[dict[str, str]] = []
    for index, item in enumerate(checklist_raw, 1):
        record = (
            {"step": str(item), "status": "unverified"} if isinstance(item, str) else dict(item)
        )
        if record.get("status", "unverified") not in {"unverified", "verified", "blocked"}:
            raise ValueError("recovery checklist status is invalid")
        checklist.append(
            {
                "id": str(record.get("id", f"REC-{index}")),
                "step": str(_redact(_require(record, "step"), tuple(terms_raw))),
                "status": str(record.get("status", "unverified")),
                "evidence": str(_redact(record.get("evidence", ""), tuple(terms_raw))),
            }
        )
    paths = [item["path"] for item in files]
    signals = _signals(paths)
    drill = _recovery_drill(root, data, files)
    gaps = [f"missing {name} continuity notes" for name in SECTIONS if not sections[name]]
    if not signals["dependency_manifests"]:
        gaps.append("no dependency manifest observed")
    if not signals["ci_workflows"]:
        gaps.append("no CI workflow observed")
    if not checklist or any(item["status"] != "verified" for item in checklist):
        gaps.append("recovery checklist is not fully verified")
    if drill["checks"] and not drill["ready"]:
        gaps.append("recovery drill has failed observations")
    digest_input = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {
        "root": root.name,
        "scan_scope": scan_scope,
        "scan_limits": scan_limits,
        "scan_complete": True,
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "manifest_sha256": hashlib.sha256(digest_input).hexdigest(),
        "files": files,
        "signals": signals,
        "sections": sections,
        "evidence_boundary": {
            "observed": "File hashes, sizes, paths and non-executing checks from this run",
            "asserted": "Sections, owners and checklist statuses are human assertions, not independently verified recovery evidence",
        },
        "ownership": {
            "by_section": {name: owners.get(name, "") for name in SECTIONS},
            "assigned": sum(bool(owners.get(name)) for name in SECTIONS),
            "total": len(SECTIONS),
        },
        "recovery_checklist": checklist,
        "recovery_drill": drill,
        "changes": _changes(files, data.get("previous")),
        "gaps": gaps,
        "ready_for_handoff": not gaps,
        "privacy": {
            "source_contents_included": False,
            "excluded_names": sorted(excluded),
            "redaction_terms_applied": len(terms_raw),
            "environment_values_read": False,
            "recovery_commands_executed": False,
        },
    }


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    validate_json(data)
    validate_spec(data)
    return {"schema_version": VERSION, "project": PROJECT, **_continuity(data)}


def render_json(report: dict[str, Any]) -> str:
    validate_json(report)
    return json.dumps(report, indent=2, ensure_ascii=False) + "\n"


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Project Continuity Kit", "", f"Manifest: `{report['manifest_sha256']}`", ""]
    lines += [
        "## Handoff readiness",
        "",
        "Ready" if report["ready_for_handoff"] else "Needs review",
        "",
    ]
    lines += ["## Continuity gaps", ""]
    lines += [f"- {gap}" for gap in report["gaps"]] or ["- None"]
    lines += ["", "## Structured report", "", f"```json\n{render_json(report).rstrip()}\n```", ""]
    return "\n".join(lines)


def _validate_bundle_report(report: Any) -> None:
    if (
        not isinstance(report, dict)
        or report.get("project") != PROJECT
        or not isinstance(report.get("files"), list)
    ):
        raise ValueError("bundle is not a Project Continuity Kit package")
    if "schema_version" in report and (
        type(report["schema_version"]) is not int or report["schema_version"] not in {1, 2, 3}
    ):
        raise ValueError("unsupported continuity report schema")
    if report.get("scan_complete", True) is not True:
        raise ValueError("An incomplete recorded scan cannot establish a bundle match")
    policy = limits(report.get("scan_limits"))
    names = set()
    total = 0
    if len(report["files"]) > policy["max_files"]:
        raise ValueError("recorded file count exceeds scan limits")
    for item in report["files"]:
        if (
            not isinstance(item, dict)
            or not isinstance(item.get("path"), str)
            or not item["path"]
            or item["path"] in names
        ):
            raise ValueError("recorded file paths must be nonempty and unique")
        name = item["path"]
        if (
            name.startswith(("/", "\\"))
            or ":" in name
            or any(part in {"", ".", ".."} for part in name.replace("\\", "/").split("/"))
        ):
            raise ValueError("recorded file paths must stay relative to root")
        if type(item.get("bytes")) is not int or not 0 <= item["bytes"] <= policy["max_file_bytes"]:
            raise ValueError("recorded file sizes must be bounded integers")
        if not isinstance(item.get("sha256"), str) or not re.fullmatch(
            "[0-9a-f]{64}", item["sha256"]
        ):
            raise ValueError("recorded files require lowercase SHA-256")
        total += item["bytes"]
        names.add(name)
    expected = hashlib.sha256(
        json.dumps(report["files"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if report.get("manifest_sha256") != expected or total > policy["max_total_bytes"]:
        raise ValueError("recorded manifest fingerprint or byte budget disagrees")
    if "file_count" in report and (
        type(report["file_count"]) is not int or report["file_count"] != len(names)
    ):
        raise ValueError("recorded file_count disagrees")
    if "total_bytes" in report and (
        type(report["total_bytes"]) is not int or report["total_bytes"] != total
    ):
        raise ValueError("recorded total_bytes disagrees")
    signals = report.get("signals", {})
    if not isinstance(signals, dict) or any(
        not isinstance(v, list) or any(not isinstance(s, str) for s in v) for v in signals.values()
    ):
        raise ValueError("recorded signals must contain lists of paths")


def write_bundle(report: dict[str, Any], target: Path) -> None:
    _validate_bundle_report(report)
    target = no_links(target)
    if target.exists() or target.is_symlink():
        raise ValueError(f"bundle already exists: {target}")
    entries = {
        "continuity.json": render_json(report),
        "HANDOFF.md": render_markdown(report),
        "HANDOFF.html": render_html(report),
        "VERIFY.txt": f"manifest_sha256={report['manifest_sha256']}\n",
    }
    payload = {name: content.encode("utf-8") for name, content in entries.items()}
    if (
        any(len(raw) > MAX_MEMBER_BYTES for raw in payload.values())
        or sum(map(len, payload.values())) > MAX_BUNDLE_BYTES
    ):
        raise ValueError("Rendered bundle exceeds its bounded format")
    target.parent.mkdir(parents=True, exist_ok=True)
    no_links(target)
    with target.open("xb") as output, ZipFile(output, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in payload.items():
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content)


def verify_bundle(bundle: Path, root: Path) -> dict[str, Any]:
    bundle, root = no_links(bundle).resolve(), no_links(root).resolve()
    if not root.is_dir():
        raise ValueError("verification root must be an existing directory")
    contents = read_bundle(bundle)
    previous = json_bytes(contents["continuity.json"])
    _validate_bundle_report(previous)
    if contents["VERIFY.txt"] != f"manifest_sha256={previous['manifest_sha256']}\n".encode():
        raise ValueError("Bundle verification record disagrees with its manifest")
    if "scan_scope" in previous:
        excluded_names = _validated_scope(previous["scan_scope"])
        scope_source = "versioned"
    else:
        # Legacy reports recorded effective exclusions in privacy metadata.
        privacy = previous.get("privacy", {})
        if not isinstance(privacy, dict):
            raise ValueError("legacy privacy metadata must be an object")
        excluded_names = _validated_scope(
            _scope(privacy.get("excluded_names", sorted(DEFAULT_EXCLUDES)))
        )
        scope_source = "legacy-privacy" if "excluded_names" in privacy else "legacy-defaults"
    current = analyze(
        {
            "root": str(root),
            "exclude": excluded_names,
            "scan_limits": previous.get("scan_limits"),
            "sections": previous.get("sections", {}),
            "recovery_checklist": previous.get("recovery_checklist", []),
            "previous": previous,
        }
    )
    changes = current["changes"]
    missing_signals = [
        name
        for name, entries in previous.get("signals", {}).items()
        if entries and not current["signals"].get(name)
    ]
    return {
        "schema_version": 1,
        "project": PROJECT,
        "bundle": str(bundle),
        "root": str(root),
        "scan_scope": current["scan_scope"],
        "scan_scope_source": scope_source,
        "scan_limits": current["scan_limits"],
        "scan_complete": True,
        "bundle_manifest_sha256": previous.get("manifest_sha256"),
        "current_manifest_sha256": current["manifest_sha256"],
        "matches": not changes["added"] and not changes["removed"] and not changes["changed"],
        "changes": changes,
        "missing_capability_signals": missing_signals,
        "current_gaps": current["gaps"],
        "boundary": "Verification compares file evidence and declared continuity signals; it does not execute restore or deployment commands.",
    }
