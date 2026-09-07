# Development contract

Generate and verify a portable, redacted project continuity package from a local repository.

Preserve deterministic, source-safe behavior and the interpretation boundary documented in the README. Recovery drills observe declared prerequisites but never execute arbitrary commands or read environment values. Bundle verification compares evidence without restoring files. Every feature release must update tests, version metadata, `CHANGELOG.md`, README claims and limitations, repository metadata, release assets, and the Forge catalog together.

## 1.3.0 improvement session

Validate continuity inputs and add an HTML handoff with evidence links, ownership coverage and changes since a prior report.

Field-specific checks cover root paths, list fields, sections, checklist records, ownership and prior file manifests. Optional `owners` maps continuity section names to owner names. HTML links checklist evidence and change entries to observed file records when exact relative paths match. Human notes, owners and checklist statuses remain author assertions, even when labeled verified by the author; they are separate from this run's file/hash and non-executing observations. Supply `previous` with a prior report for added/removed/changed/unchanged summaries. Deterministic bundles now include HANDOFF.html. Commands, restoration and deployment are never executed.

Local formatting, lint, strict types and regression tests pass. Public release completion requires the protected CI/CodeQL matrix, tagged artifacts and matching Forge catalog/detail deployment.
