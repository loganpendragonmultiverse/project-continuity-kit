from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

PROJECT = "project-continuity-kit"
VERSION = 2
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


def _continuity(data: dict[str, Any]) -> dict[str, Any]:
    root = Path(_require(data, "root")).resolve()
    if not root.is_dir():
        raise ValueError("root must be an existing directory")
    extra_excludes = data.get("exclude", [])
    if not isinstance(extra_excludes, list):
        raise TypeError("exclude must be a list")
    excluded = DEFAULT_EXCLUDES | {str(item) for item in extra_excludes}
    files: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        relative = path.relative_to(root)
        if path.is_file() and not any(
            part in excluded or part.startswith(".env.") and part != ".env.example"
            for part in relative.parts
        ):
            content = path.read_bytes()
            files.append(
                {
                    "path": relative.as_posix(),
                    "bytes": len(content),
                    "sha256": hashlib.sha256(content).hexdigest(),
                }
            )
    terms_raw = data.get("redact", [])
    if not isinstance(terms_raw, list) or any(
        not isinstance(term, str) or not term for term in terms_raw
    ):
        raise ValueError("redact must contain non-empty strings")
    sections_raw = data.get("sections", data.get("notes", {}))
    if not isinstance(sections_raw, dict):
        raise TypeError("sections must be an object")
    sections = {name: _redact(sections_raw.get(name, {}), tuple(terms_raw)) for name in SECTIONS}
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
                "step": str(_require(record, "step")),
                "status": str(record.get("status", "unverified")),
                "evidence": str(record.get("evidence", "")),
            }
        )
    paths = [item["path"] for item in files]
    signals = _signals(paths)
    gaps = [f"missing {name} continuity notes" for name in SECTIONS if not sections[name]]
    if not signals["dependency_manifests"]:
        gaps.append("no dependency manifest observed")
    if not signals["ci_workflows"]:
        gaps.append("no CI workflow observed")
    if not checklist or any(item["status"] != "verified" for item in checklist):
        gaps.append("recovery checklist is not fully verified")
    digest_input = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {
        "root": root.name,
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "manifest_sha256": hashlib.sha256(digest_input).hexdigest(),
        "files": files,
        "signals": signals,
        "sections": sections,
        "recovery_checklist": checklist,
        "changes": _changes(files, data.get("previous")),
        "gaps": gaps,
        "ready_for_handoff": not gaps,
        "privacy": {
            "source_contents_included": False,
            "excluded_names": sorted(excluded),
            "redaction_terms_applied": len(terms_raw),
        },
    }


def analyze(data: dict[str, Any]) -> dict[str, Any]:
    return {"schema_version": VERSION, "project": PROJECT, **_continuity(data)}


def render_json(report: dict[str, Any]) -> str:
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


def write_bundle(report: dict[str, Any], target: Path) -> None:
    if target.exists():
        raise ValueError(f"bundle already exists: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    entries = {
        "continuity.json": render_json(report),
        "HANDOFF.md": render_markdown(report),
        "VERIFY.txt": f"manifest_sha256={report['manifest_sha256']}\n",
    }
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, content.encode("utf-8"))
