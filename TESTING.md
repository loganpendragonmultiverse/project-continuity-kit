# Testing

Run `python -m pip install -e ".[dev]"`, then `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, and `python -m build`.

Tests cover structured continuity domains, redaction, exclusions, capability signals, file fingerprints, previous-manifest diffs, recovery checklist evidence, non-executing recovery prerequisites, environment-name declarations without values, deterministic bundles, bundle verification, repository drift, invalid inputs, and replacement-safe CLI output.

## 1.3.0 regression acceptance

Run the complete existing suite plus the new regression fixtures. Confirm the documented command produces the selected output, malformed input remains actionable, and source files remain unchanged. Validate continuity inputs and add an HTML handoff with evidence links, ownership coverage and changes since a prior report.
