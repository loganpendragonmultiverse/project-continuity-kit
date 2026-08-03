# Changelog

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
