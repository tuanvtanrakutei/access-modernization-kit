# Changelog

All notable changes to this project are documented in this file. The format follows Keep a Changelog principles and versions use semantic versioning.

## [Unreleased]

### Planned

- Live Access/ACE extraction validation on approved synthetic databases.
- ADP extraction validation on a compatible legacy Access environment.
- A01 regression trial only after explicit authorization.

### Documentation

- Reframed the README around the kit's purpose, boundaries, per-app operating model, and input-to-output flow.

## [2.1.5] - 2026-07-16

### Added

- Added the user-facing `sms_kit.py` CLI for package validation, app-workspace initialization, and capability preflight.

### Changed

- Documented the recommended agent-skill entry point and a minimal CLI alternative before the detailed investigation workflow.

## [2.1.4] - 2026-07-16

### Changed

- Updated the development test dependency baseline to pytest 9.1.1 after successful Ubuntu and Windows CI validation.

## [2.1.3] - 2026-07-16

### Changed

- Updated GitHub Actions checkout to v7 and the PyYAML/jsonschema development dependency minimum versions after successful CI validation.

### Fixed

- Applied the jsonschema update directly after its Dependabot pull request conflicted with the prior PyYAML requirements update.

## [2.1.2] - 2026-07-16

### Fixed

- Accepted supported major versions of GitHub Actions checkout and setup-python actions so dependency-update pull requests validate their proposed workflow change.

## [2.1.1] - 2026-07-16

### Fixed

- Declared `requirements-dev.txt` as the dependency source for the GitHub Actions pip cache.
- Rejected duplicate keys in public YAML metadata through the synthetic test suite.
- Excluded virtual environments and generated dependency/cache directories from repository text-integrity scans.

### Changed

- Hardened the public release metadata and validation baseline without changing the 2.1 contract.

## [2.1.0] - 2026-07-15

### Added

- Snapshot-based MDB, ACCDB, and ADP extraction layer.
- Access project context, linked-table, QueryDef, form, report, macro, and VBA extraction contracts.
- Deterministic app component index and hierarchical leaf-first module planner.
- Incremental affected-module refresh and module-aware multi-agent task fan-out.
- Independent Git, Graphify, and investigation ignore policies.
- Programming language, query dialect, encoding, parser, and parse-status inventory.
- Read-only compilation database normalization with secret redaction and `NEVER_EXECUTE` policy.
- Public GitHub governance, CI, and synthetic tests.

### Changed

- Orchestration adds context-extraction and module-decomposition gates before Phase analysis.
- Package contract and schemas upgraded to 2.1.

## [2.0.0]

### Added

- Provider-neutral multi-agent roles, waves, task envelopes, handoffs, and coordinator-only merge.
- Immutable run state, evidence conflict preservation, checkpoints, and independent QA.
- Six-phase output, E2E, Boundary Map, and presentation contracts.
