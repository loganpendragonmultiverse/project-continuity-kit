# Testing

Run `python -m pip install -e ".[dev]"`, then `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, and `python -m build`.

Tests cover structured continuity domains, redaction, exclusions, capability signals, file fingerprints, previous-manifest diffs, recovery checklist evidence, non-executing recovery prerequisites, environment-name declarations without values, deterministic bundles, bundle verification, repository drift, invalid inputs, and replacement-safe CLI output.
