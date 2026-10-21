# Project Continuity Kit

[![CI](https://github.com/loganpendragonmultiverse/project-continuity-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/project-continuity-kit/actions/workflows/ci.yml)

Build and verify a portable, redacted handoff and recovery package from a local repository. Version 1.4 inventories files without copying their contents, fingerprints the repository, detects operational signals, records six continuity domains, audits missing knowledge, observes declared recovery prerequisites without executing commands, and compares an existing bundle with the current working tree.

## Three-minute start

```bash
python -m pip install .
continuity-kit examples/sample.json
continuity-kit examples/sample.json --format json --output build/continuity.json --bundle build/continuity.zip
continuity-kit --verify-bundle build/continuity.zip --root path/to/repository --format json
```

The deterministic ZIP contains `continuity.json`, `HANDOFF.md`, `HANDOFF.html`, and `VERIFY.txt`. It never contains source files. Existing reports and bundles are never overwritten.

## Continuity and recovery model

Inputs can document architecture, operations, dependencies, deployment, recovery, and handoff ownership. Recovery steps carry `verified`, `unverified`, or `blocked` status plus evidence references. Secret-shaped keys are always redacted, and explicit terms can be redacted throughout supplied notes.

The report detects dependency manifests, lockfiles, environment examples, CI workflows, container definitions, operational documentation, and recovery documentation. A recovery drill can check required commands, files, artifact patterns, declared environment-variable names, and documented commands. It never executes arbitrary recovery, build, restore, or deployment commands.

Bundle verification rescans a repository and reports added, removed, changed, and unchanged files, missing capability signals, current gaps, and both manifest fingerprints. This identifies drift; it does not restore files or prove that a deployment succeeds.

## Privacy and interpretation boundary

Everything runs locally. `.git`, real environment files, virtual environments, dependencies, and build outputs are excluded by default. File paths, byte counts, and SHA-256 hashes are recorded; file contents are never included in the package. Environment values are never read.

A green handoff or recovery-drill result means the declared evidence contract is satisfied. It does not prove that a restore, build, or deployment works. Command availability and documentation presence are observations, not execution evidence.

Python 3.10 or newer is supported on Windows, macOS, and Linux with no runtime dependencies, telemetry, account, or hosted service.

## Development

```bash
python -m pip install -e ".[dev]"
ruff format --check .
ruff check .
mypy src
pytest
python -m build
```

Part of the [Logan Pendragon Forge open-source collection](https://www.loganpendragonforge.com/open-source/). Licensed under the [MIT License](LICENSE).

## Version 1.3.0: reviewed improvements

Validate continuity inputs and add an HTML handoff with evidence links, ownership coverage and changes since a prior report.

```bash
continuity-kit examples/sample.json --format html --output build/handoff.html
```

Field-specific checks cover root paths, list fields, sections, checklist records, ownership and prior file manifests. Optional `owners` maps continuity section names to owner names. HTML links checklist evidence and change entries to observed file records when exact relative paths match. Human notes, owners and checklist statuses remain author assertions, even when labeled verified by the author; they are separate from this run's file/hash and non-executing observations. Supply `previous` with a prior report for added/removed/changed/unchanged summaries. Deterministic bundles now include HANDOFF.html. Commands, restoration and deployment are never executed.

## 1.3.1 — 2026-10-16

New reports include scan_scope version 1: sorted unique excluded_names (the effective defaults plus custom path-component names) and environment_files set to exclude-dotenv-except-example. Bundle verification validates and reuses this scope, so excluded additions and edits do not count as drift while included changes do. Unknown policy versions, malformed objects, unsafe names and missing default exclusions are rejected. Legacy bundles use validated privacy.excluded_names when available; bundles without that metadata use documented defaults and report scan_scope_source as legacy-defaults. Scope provenance is explicit in verification output. ZIP output remains deterministic and contains file metadata rather than source contents. Recovery, restore and deployment commands are never executed.

## 1.4.0 — complete observations and bounded verification

Inventory is complete or fails with an actionable error. Included symlinks, Windows junctions/reparse points (including selected-root ancestors), special files, unreadable entries, changing files and exhausted budgets refuse the scan; no partial result can establish a match. Excluded components are pruned before opening their contents. Default limits are 20,000 files, 50,000 directory entries, depth 32, 64 MiB per file and 256 MiB of file bytes. `scan_limits` records the complete version-1 policy and can lower, never raise, each positive integer limit. Verification reuses recorded limits as well as scan scope. Files are streamed in bounded blocks; at most one extra byte detects an understated extent and that byte is never accepted as evidence.

Required-file, artifact-pattern, documentation and environment-name observations use only the included inventory. Documentation/example text is read only when requested, capped at 1 MiB per file, and must still match its scanned hash. Excluded files cannot satisfy a prerequisite. Artifact globs match relative path components (`*` stays in one component; `**` can span components).

Bundles are limited to 32 MiB, four known metadata members (or the three legacy members), and 8 MiB per expanded member. Verification validates the bounded directory, full stored/Deflate streams, size/CRC, strict finite JSON with maximum nesting 64, unique relative file paths, typed counts/hashes, manifest fingerprint and `VERIFY.txt` binding before comparing the source. ZIP64 bundle directories are outside this bounded metadata format. These checks detect malformed or inconsistent evidence; hashes do not authenticate an untrusted publisher. Legacy bundles retain the documented scope fallback and default budget policy.

CLI outputs must be outside the scanned root or beneath an excluded component such as `build/`; this prevents a newly generated report becoming immediate source drift. Report and bundle destinations are checked together, must be distinct new paths, and use exclusive creation. A later I/O error can leave one newly created output; inspect it and choose fresh names when retrying. Existing files, dangling links and linked ancestors are refused. Source trees should remain quiescent; this tool does not provide a transactional filesystem snapshot or defend against hostile concurrent path replacement.

Explicit redaction terms cover owners, checklist step/evidence notes and section values. Technical paths, IDs, hashes, signal names and prerequisite subjects remain evidence, not anonymous data. Review every package before sharing; secret-shaped section keys are redacted, but arbitrary secrets cannot be inferred. No source content or environment value is exported and no recovery command is executed.


## 1.4.1 release verification

The 1.4.1 release includes `SHA256SUMS` for the exact wheel and source distribution. The release job repeats the full quality gate and refuses a tag/package/runtime version mismatch.
