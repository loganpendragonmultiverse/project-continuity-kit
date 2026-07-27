# Project Continuity Kit

[![CI](https://github.com/loganpendragonmultiverse/project-continuity-kit/actions/workflows/ci.yml/badge.svg)](https://github.com/loganpendragonmultiverse/project-continuity-kit/actions/workflows/ci.yml)

Build a portable, redacted handoff and recovery package from a local repository. Version 1.1 inventories files without copying their contents, fingerprints the repository, detects operational signals, records six continuity domains, audits missing knowledge, tracks recovery evidence, and compares the result with a previous manifest.

## Three-minute start

```bash
python -m pip install .
continuity-kit examples/sample.json
continuity-kit examples/sample.json --format json --output continuity.json --bundle continuity.zip
```

The deterministic ZIP contains `continuity.json`, `HANDOFF.md`, and `VERIFY.txt`. It never contains source files. Existing report and bundle targets are never overwritten.

## Continuity model

Inputs can document architecture, operations, dependencies, deployment, recovery, and handoff ownership. Recovery steps carry `verified`, `unverified`, or `blocked` status plus evidence references. Secret-shaped keys are always redacted, and explicit terms can be redacted throughout supplied notes.

The report detects dependency manifests, lockfiles, environment examples, CI workflows, container definitions, operational documentation, and recovery documentation. It reports gaps without claiming that observed files prove operational readiness.

## Privacy and interpretation boundary

Everything runs locally. `.git`, real environment files, virtual environments, dependencies, and build outputs are excluded by default. File paths, byte counts, and SHA-256 hashes are recorded; file contents are never included in the package. A green handoff result means the explicit v1.1 evidence contract is satisfied—it does not prove that a restore or deployment works.

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
