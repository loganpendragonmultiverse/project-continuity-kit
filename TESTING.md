# Testing

Run `python -m pip install -e ".[dev]"`, then `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, and `python -m build`.

Tests cover structured continuity domains, redaction, exclusions, capability signals, file fingerprints, previous-manifest diffs, recovery checklist evidence, non-executing recovery prerequisites, environment-name declarations without values, deterministic bundles, bundle verification, repository drift, invalid inputs, and replacement-safe CLI output.

## 1.3.0 regression acceptance

Run the complete existing suite plus the new regression fixtures. Confirm the documented command produces the selected output, malformed input remains actionable, and source files remain unchanged. Validate continuity inputs and add an HTML handoff with evidence links, ownership coverage and changes since a prior report.

## 1.3.1 — 2026-10-16

New reports include scan_scope version 1: sorted unique excluded_names (the effective defaults plus custom path-component names) and environment_files set to exclude-dotenv-except-example. Bundle verification validates and reuses this scope, so excluded additions and edits do not count as drift while included changes do. Unknown policy versions, malformed objects, unsafe names and missing default exclusions are rejected. Legacy bundles use validated privacy.excluded_names when available; bundles without that metadata use documented defaults and report scan_scope_source as legacy-defaults. Scope provenance is explicit in verification output. ZIP output remains deterministic and contains file metadata rather than source contents. Recovery, restore and deployment commands are never executed.

Regression tests use synthetic inputs and disposable trees. Run the complete suite and inspect built wheel/source documentation before preparing a draft PR.
