# Changelog

## 1.4.2 — 2026-10-21

- Verify built distribution Name, Version and Requires-Python against project, runtime and tag identity before writing exact two-payload checksums.
- Add portable metadata mismatch, duplicate and missing-field, runtime, tag and payload-set regressions without changing native requirements or supported runtimes.

## [1.4.1] - 2026-10-21

- Repeat full formatting, lint, strict types, regression, audit and build checks in the exact-tag release workflow.
- Check runtime/package/tag version agreement and ship SHA256SUMS covering exactly the wheel and source distribution.
- Pin release actions to reviewed official commits; retain the original platform matrix and coverage requirements.

## [1.4.0] - 2026-10-21

- Fail closed on incomplete, unsafe, changed or over-budget inventories and record reusable scan limits.
- Keep all prerequisite observations inside the same included, hash-bound inventory.
- Verify complete bounded ZIP members, strict report metadata, manifest fingerprints and verification records before drift comparison.
- Redact explicit private terms from owners and checklist notes; protect distinct CLI outputs with exclusive creation and avoid self-generated drift.
- Ship all four authority documents, license and runnable example instructions with installed distributions.

## [1.3.1] - 2026-10-16

New reports include scan_scope version 1: sorted unique excluded_names (the effective defaults plus custom path-component names) and environment_files set to exclude-dotenv-except-example. Bundle verification validates and reuses this scope, so excluded additions and edits do not count as drift while included changes do. Unknown policy versions, malformed objects, unsafe names and missing default exclusions are rejected. Legacy bundles use validated privacy.excluded_names when available; bundles without that metadata use documented defaults and report scan_scope_source as legacy-defaults. Scope provenance is explicit in verification output. ZIP output remains deterministic and contains file metadata rather than source contents. Recovery, restore and deployment commands are never executed.


## 1.3.0 - 2026-09-07

- Validate continuity inputs and add an HTML handoff with evidence links, ownership coverage and changes since a prior report.
- Added regression coverage for the audited behavior and invalid inputs.

## 1.2.0 - 2026-08-03

- Added non-executing recovery drills for required commands, files, artifact patterns, declared environment names, and documented commands.
- Added bundle-to-working-tree verification with current and recorded fingerprints, file drift, missing capability signals, and current continuity gaps.
- Recorded explicit privacy evidence that environment values are not read and arbitrary recovery commands are not executed.

## 1.1.0 - 2026-07-27

- Added six structured continuity domains covering architecture, operations, dependencies, deployment, recovery, and handoff.
- Added secret-key and operator-term redaction, repository capability signals, continuity gap analysis, recovery evidence, previous-manifest diffs, and aggregate fingerprints.
- Added deterministic ZIP continuity bundles containing the structured manifest, handoff report, and verification record without copying repository contents.

## 1.0.0 - 2026-07-26

- Released the first complete Project Continuity Kit command-line workflow.
- Added deterministic JSON and Markdown reporting, representative examples, and cross-platform tests.
