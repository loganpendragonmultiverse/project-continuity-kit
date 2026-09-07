"""Non-executing schema checks and local HTML evidence review."""

from __future__ import annotations

import html
import json
from pathlib import PurePosixPath
from typing import Any


def validate_spec(data: Any) -> None:
    if not isinstance(data, dict):
        raise TypeError("input must be a JSON object")
    if "root" not in data or data["root"] == "":
        raise ValueError("root is required")
    if not isinstance(data.get("root"), str):
        raise TypeError("root must be a directory path string")
    for name in (
        "exclude",
        "redact",
        "required_commands",
        "required_files",
        "required_artifacts",
        "required_environment",
        "documented_commands",
    ):
        value = data.get(name, [])
        if not isinstance(value, list):
            raise TypeError(f"{name} must be a list")
        if any(not isinstance(v, str) or not v for v in value):
            raise ValueError(f"{name} must contain non-empty strings")
    for name in ("required_files", "required_artifacts"):
        for value in data.get(name, []):
            path = PurePosixPath(value.replace("\\", "/"))
            if path.is_absolute() or ".." in path.parts or ":" in value:
                raise ValueError(f"{name}: paths must stay relative to root")
    sections = data.get("sections", data.get("notes", {}))
    if not isinstance(sections, dict):
        raise TypeError("sections must be an object")
    for key, value in sections.items():
        if not isinstance(value, (dict, str, list)):
            raise TypeError(f"sections.{key} must be text, a list, or an object")
    checklist = data.get("recovery_checklist", [])
    if not isinstance(checklist, list):
        raise TypeError("recovery_checklist must be a list")
    ids = set()
    for index, item in enumerate(checklist):
        prefix = f"recovery_checklist[{index}]"
        if isinstance(item, str):
            if not item.strip():
                raise ValueError(f"{prefix}.step must not be blank")
            continue
        if not isinstance(item, dict):
            raise TypeError(f"{prefix} must be text or an object")
        for field in ("id", "step", "status", "evidence"):
            if field in item and not isinstance(item[field], str):
                raise TypeError(f"{prefix}.{field} must be text")
        if not item.get("step", "").strip():
            raise ValueError(f"{prefix}.step is required")
        identifier = item.get("id", f"REC-{index + 1}")
        if not identifier or identifier in ids:
            raise ValueError(f"{prefix}.id must be non-empty and unique")
        ids.add(identifier)
    owners = data.get("owners", {})
    if not isinstance(owners, dict) or any(
        not isinstance(v, str) or not v.strip() for v in owners.values()
    ):
        raise TypeError("owners must map section names to non-empty owner names")
    previous = data.get("previous")
    if previous is not None:
        if not isinstance(previous, dict) or not isinstance(previous.get("files"), list):
            raise TypeError("previous must be a report with a files list")
        paths = set()
        for index, record in enumerate(previous["files"]):
            if (
                not isinstance(record, dict)
                or not isinstance(record.get("path"), str)
                or not isinstance(record.get("sha256"), str)
            ):
                raise TypeError(f"previous.files[{index}] requires text path and sha256")
            if record["path"] in paths:
                raise ValueError(f"previous.files[{index}].path is duplicated")
            paths.add(record["path"])


def render_html(report: dict[str, Any]) -> str:
    escape = html.escape
    files = report.get("files", [])
    anchors = {item["path"]: f"file-{index}" for index, item in enumerate(files)}

    def evidence(path: str) -> str:
        label = escape(path)
        return f'<a href="#{anchors[path]}">{label}</a>' if path in anchors else label

    parts = [
        '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Continuity handoff</title>',
        "<style>body{font:17px system-ui;max-width:1080px;margin:auto;padding:22px;background:#f5f1e8;color:#203442}section{background:white;padding:20px;border:1px solid #bcc;margin:18px 0;border-radius:12px}pre{white-space:pre-wrap;overflow-wrap:anywhere}li{margin:10px 0;overflow-wrap:anywhere}a{color:#165778}</style>",
        "<h1>Project continuity handoff</h1><p>File observations and human assertions are separate. Recovery and deployment commands were never executed.</p>",
    ]
    parts.append("<section><h2>Changes since the supplied bundle/report</h2>")
    for kind, values in report.get("changes", {}).items():
        parts.append(
            f"<h3>{escape(kind)} ({len(values)})</h3><ul>"
            + "".join(f"<li>{evidence(p)}</li>" for p in values)
            + "</ul>"
        )
    parts.append("</section><section><h2>Ownership coverage — author assertions</h2><ul>")
    for section, owner in report.get("ownership", {}).get("by_section", {}).items():
        parts.append(f"<li>{escape(section)}: {escape(owner or 'Unassigned')}</li>")
    parts.append(
        "</ul></section><section><h2>Unverified human assertions</h2><pre>"
        + escape(json.dumps(report.get("sections", {}), indent=2))
        + "</pre><ul>"
    )
    for item in report.get("recovery_checklist", []):
        parts.append(
            f"<li>{escape(item['step'])} — author status: {escape(item['status'])}; evidence: {evidence(item['evidence'])}</li>"
        )
    parts.append("</ul></section><section><h2>Observed files</h2><ul>")
    for item in files:
        parts.append(
            f'<li id="{anchors[item["path"]]}">{escape(item["path"])} — {item["bytes"]} bytes<br>SHA-256: {escape(item["sha256"])}</li>'
        )
    parts.append(
        "</ul></section><section><h2>Observation checks</h2><pre>"
        + escape(json.dumps(report.get("recovery_drill", report), indent=2))
        + "</pre></section></html>"
    )
    return "\n".join(parts)
