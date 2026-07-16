# Changelog

All notable changes to this project are documented in this file. The format follows Keep a Changelog principles and versions use semantic versioning.

## [Unreleased]

### Planned

- Live Access/ACE extraction validation on approved synthetic databases.
- ADP extraction validation on a compatible legacy Access environment.
- A01 regression trial only after explicit authorization.

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
