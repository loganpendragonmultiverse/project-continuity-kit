# Development contract

Generate and verify a portable, redacted project continuity package from a local repository.

Preserve deterministic, source-safe behavior and the interpretation boundary documented in the README. Recovery drills observe declared prerequisites but never execute arbitrary commands or read environment values. Bundle verification compares evidence without restoring files. Every feature release must update tests, version metadata, `CHANGELOG.md`, README claims and limitations, repository metadata, release assets, and the Forge catalog together.

## 1.3.0 improvement session

Validate continuity inputs and add an HTML handoff with evidence links, ownership coverage and changes since a prior report.

Field-specific checks cover root paths, list fields, sections, checklist records, ownership and prior file manifests. Optional `owners` maps continuity section names to owner names. HTML links checklist evidence and change entries to observed file records when exact relative paths match. Human notes, owners and checklist statuses remain author assertions, even when labeled verified by the author; they are separate from this run's file/hash and non-executing observations. Supply `previous` with a prior report for added/removed/changed/unchanged summaries. Deterministic bundles now include HANDOFF.html. Commands, restoration and deployment are never executed.

Local formatting, lint, strict types and regression tests pass. Public release completion requires the protected CI/CodeQL matrix, tagged artifacts and matching Forge catalog/detail deployment.

## 1.3.1 — 2026-10-16

New reports include scan_scope version 1: sorted unique excluded_names (the effective defaults plus custom path-component names) and environment_files set to exclude-dotenv-except-example. Bundle verification validates and reuses this scope, so excluded additions and edits do not count as drift while included changes do. Unknown policy versions, malformed objects, unsafe names and missing default exclusions are rejected. Legacy bundles use validated privacy.excluded_names when available; bundles without that metadata use documented defaults and report scan_scope_source as legacy-defaults. Scope provenance is explicit in verification output. ZIP output remains deterministic and contains file metadata rather than source contents. Recovery, restore and deployment commands are never executed.

## 1.4.0 contract

Keep the schema-3 report and legacy scope fallback compatible. Recorded version-1 scan limits are complete, typed and capped; a failed or partial scan must never report a verified match. Inventory and all prerequisite reads share exclusions and observed hashes. Preserve bounded full-stream ZIP validation, duplicate-key rejection, file-list fingerprint and VERIFY binding. Refuse linked/reparse paths before canonical resolution. Existing outputs are never replaced. This is local evidence comparison, not a backup system or command executor.

Native filesystem behavior requires actual Windows junction/symlink execution and POSIX symlink/FIFO execution, not mocked lstat metadata. Candidate CI and local installed tests do not substitute for exact-tag installed artifact review and required native acceptance. Public release remains pending until those gates and protected checks pass.
