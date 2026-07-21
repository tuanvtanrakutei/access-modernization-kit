# Changelog
## 2.2.2 - 2026-07-17

- Add explicit safe adoption of an existing app workspace without modifying its current files.

## 2.2.1 - 2026-07-16

- Replace app-specific onboarding examples with reusable <APP_ID> placeholders.


## 2.2.0 - 2026-07-16

- Package the kit as the installable `sms-kit` Codex plugin and publish the `sms-legacy-kit` marketplace catalog.
- Move implementation resources beneath `plugins/sms-kit` so a plugin installation is self-contained.
- Simplify the public README to the user journey: install, initialize one app, and ask an agent.

All notable changes to this project are documented in this file. The format follows Keep a Changelog principles and versions use semantic versioning.

## [Unreleased]

### Planned

- ADP extraction validation on a compatible legacy Access environment.
- A01 regression trial only after explicit authorization.

## [2.4.0] - 2026-07-21

### Added

- `specifications/input-preconditions.md` defines the minimum inputs and environment for each input mode: export mode (pre-exported VBA/SQL in `sources/`, no Access runtime) and extract mode (an MDB/ACCDB/ADP requiring a `READY` runtime host).
- `scripts/preflight.py` now detects the input mode, scans the app `sources/` tree, reports an `input_preconditions` block (mode, present inputs, recommended-missing, and — for extract mode — the runtime host status), and surfaces missing inputs as warnings. Missing app sources never fail preflight; only the package contract does.

## [2.3.0] - 2026-07-21

### Added

- `scripts/access_runtime.py` discovers a compatible Access automation host without opening any database: it reads the 32-bit and 64-bit registry views for `Access.Application`, ACE OLEDB, and DAO, resolves the registered executable and file version even when the `LocalServer32` path is unquoted and contains spaces, detects `RunAsAdmin` AppCompat flags, selects a bitness-matched PowerShell host, and can run an optional COM activation smoke test. Runnable as a CLI (`--smoke-test`, `--powershell`, `--allow-run-as-invoker`, `--require-ready`).
- `scripts/extract_access.py` now records the runtime discovery in the extraction `runtime` block, drives the PowerShell adapter with the bitness-matched host, warns when the registered Access executable requires elevation, and blocks an authorized `--execute` run with `BLOCKED` status when no compatible runtime host is `READY`. New flags: `--powershell`, `--allow-run-as-invoker`, `--skip-runtime-check`.
- `scripts/preflight.py` reuses the shared runtime probe so capability reports include the selected host, runtime status, and elevation flag, with a registry-only fallback when the module is unavailable.
- `scripts/bump_version.py` updates every version-carrying manifest and doc in one command.

### Changed

- `package.json` is now the single source of truth for the version: `validate_structure.py` and the smoke test derive it and assert every manifest stays in lock-step, and the README uses a dynamic release badge instead of a hardcoded version.

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

## [2.1.6] - 2026-07-16

### Changed

- Renamed the Codex/Claude skill identifier from `$sms-legacy-investigation-kit` to the shorter `$sms-kit`; the repository and package name remain unchanged.

## [2.1.7] - 2026-07-16

### Added

- Added a documented shorthand command guide for the agent skill: `help`, `init`, `assess`, `phase`, `run`, `status`, and `render`.

## [2.1.8] - 2026-07-16

### Added

- Added `sms_kit.py install` and the matching `$sms-kit install` agent commands for Codex and Claude skill discovery.

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
