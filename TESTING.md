# Testing

Run `python -m pip install -e ".[dev]"`, then `ruff format --check .`, `ruff check .`, `mypy src`, `pytest`, and `python -m build`.

Tests cover structured continuity domains, redaction, exclusions, capability signals, file fingerprints, previous-manifest diffs, recovery checklist evidence, non-executing recovery prerequisites, environment-name declarations without values, deterministic bundles, bundle verification, repository drift, invalid inputs, and replacement-safe CLI output.

## 1.3.0 regression acceptance

Run the complete existing suite plus the new regression fixtures. Confirm the documented command produces the selected output, malformed input remains actionable, and source files remain unchanged. Validate continuity inputs and add an HTML handoff with evidence links, ownership coverage and changes since a prior report.

## 1.3.1 — 2026-10-16

New reports include scan_scope version 1: sorted unique excluded_names (the effective defaults plus custom path-component names) and environment_files set to exclude-dotenv-except-example. Bundle verification validates and reuses this scope, so excluded additions and edits do not count as drift while included changes do. Unknown policy versions, malformed objects, unsafe names and missing default exclusions are rejected. Legacy bundles use validated privacy.excluded_names when available; bundles without that metadata use documented defaults and report scan_scope_source as legacy-defaults. Scope provenance is explicit in verification output. ZIP output remains deterministic and contains file metadata rather than source contents. Recovery, restore and deployment commands are never executed.

Regression tests use synthetic inputs and disposable trees. Run the complete suite and inspect built wheel/source documentation before preparing a draft PR.

## 1.4.0 acceptance

Retain the full original suite and unchanged 90% branch-coverage gate. Regressions include stream growth/change, all five scan budgets, excluded prerequisite files, text-observation bounds/hash changes, unsafe roots/ancestors, typed manifests, strict JSON, malformed directory/streams, duplicate/unknown/special ZIP members, fingerprint/VERIFY mismatches, output races and immediate unchanged-source verification. All fixtures are synthetic and disposable.

Run the full suite from fresh installed wheel and sdist environments, outside the source checkout with PYTHONPATH unset. Verify imports come from site-packages, run the actual `continuity-kit` console command for generation/verification, and compare installed README/DEVELOPMENT/TESTING/CHANGELOG/LICENSE/example bytes with the exact tag. Keep the full coverage command before any focused native suite.

`tests/test_native_paths.py` uses real Windows junctions for selected root, root ancestor, included directory and selected bundle. On Windows all four junction cases and all portable symlink cases must execute without skips for each installed artifact; native preflight must refuse unavailable OS capabilities rather than claim acceptance. POSIX FIFO acceptance is legitimately unavailable on Windows. Record platform/interpreter, exact source/ref/payload hashes and source preservation. Native acceptance is pending until actual exact-tag evidence has been independently reviewed.


## 1.4.1 release verification

For 1.4.1 release acceptance, use Python 3.12 (or 3.11+) for the release packaging helper because it uses standard-library `tomllib`. The runtime and platform test matrix still support Python 3.10. Run the full original quality suite, `python -m build`, then `python tools/release_package.py`. Independently compare both checksum rows with the exact installed/tag distributions. A mismatched GITHUB_REF_NAME must refuse checksum generation before publication. Require successful protected main and exact-tag jobs; retain actual Windows installed/native acceptance.

## 1.4.2 release identity checks

Release packaging compares runtime AST, project/tag version, and built wheel METADATA/source PKG-INFO Name, Version and Requires-Python before checksumming exactly two distributions. Run the packaging helper with Python 3.11+; supported application runtimes and native acceptance requirements are unchanged.
