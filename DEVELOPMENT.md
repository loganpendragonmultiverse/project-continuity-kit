# Development contract

Generate and verify a portable, redacted project continuity package from a local repository.

Preserve deterministic, source-safe behavior and the interpretation boundary documented in the README. Recovery drills observe declared prerequisites but never execute arbitrary commands or read environment values. Bundle verification compares evidence without restoring files. Every feature release must update tests, version metadata, `CHANGELOG.md`, README claims and limitations, repository metadata, release assets, and the Forge catalog together.
