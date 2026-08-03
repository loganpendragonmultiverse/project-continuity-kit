# Project Continuity Kit

[![CI](https://github.com/loganpendragonmultiverse/project-continuity-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/project-continuity-kit/actions/workflows/ci.yml)

Build and verify a portable, redacted handoff and recovery package from a local repository. Version 1.2 inventories files without copying their contents, fingerprints the repository, detects operational signals, records six continuity domains, audits missing knowledge, observes declared recovery prerequisites without executing commands, and compares an existing bundle with the current working tree.

## Three-minute start

```bash
python -m pip install .
continuity-kit examples/sample.json
continuity-kit examples/sample.json --format json --output continuity.json --bundle continuity.zip
continuity-kit --verify-bundle continuity.zip --root path/to/repository --format json
```

The deterministic ZIP contains `continuity.json`, `HANDOFF.md`, and `VERIFY.txt`. It never contains source files. Existing reports and bundles are never overwritten.

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
