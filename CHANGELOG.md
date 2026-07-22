# Changelog
## [2.6.2] - 2026-07-22

### Added

- A pinned, isolated Graphify runtime bootstrap that installs on first Phase/run use without modifying system Python, the plugin cache, or an app workspace.
- A deterministic binary-free Graphify corpus normalizer for UTF-8/UTF-16/CP932/Shift-JIS text, Access VBA, CSV/TSV, XLS/XLSX, DOCX, PPTX, text-layer PDF, and OCR-capable scanned PDF/image sources.
- Corpus provenance/fingerprint auditing, graph acceptance state, and phase-specific query receipts.

### Changed

- Graphify is now a mandatory freshness/query gate before every Phase 1-6. Installation, corpus validation, graph build/update, or phase-query failures block Phase output with an explicit status.
- Multi-agent orchestration now publishes every phase separately and places a Graphify gate before each phase while preserving parallel source/module evidence collection.
- New workspaces default to managed Graphify 0.9.18 with PDF/Office extras and a binary-free normalized corpus policy. Existing 2.1 manifests remain compatible and receive the same gate defaults at runtime.

### Security

- MDB/ACCDB/ADP files, Access locks, and disposable snapshots are explicitly excluded from Graphify ingestion; the corpus audit must report zero binary files ingested.

## [2.6.1] - 2026-07-22

### Fixed

- Source preflight and worker task envelopes now resolve VBA, SQL export, and document paths from the app manifest instead of assuming only `sources/vba`, `sources/sql`, and `sources/documents`. Local-only MDB applications with database-specific VBA export folders no longer receive a false missing-VBA warning, and an intentionally empty SQL Server export list is treated as not applicable.

### Changed

- Refresh skill UI metadata and the visible skill heading to the current 2.6 release line.

## 2.2.2 - 2026-07-17

- Add explicit safe adoption of an existing app workspace without modifying its current files.

## 2.2.1 - 2026-07-16

- Replace app-specific onboarding examples with reusable <APP_ID> placeholders.


## 2.2.0 - 2026-07-16

- Package the kit as the installable `ak` Codex plugin and publish the `access-modernization-kit` marketplace catalog.
- Move implementation resources beneath `plugins/ak` so a plugin installation is self-contained.
- Simplify the public README to the user journey: install, initialize one app, and ask an agent.

All notable changes to this project are documented in this file. The format follows Keep a Changelog principles and versions use semantic versioning.

## [Unreleased]

### Planned

- ADP extraction validation on a compatible legacy Access environment.
- A01 regression trial only after explicit authorization.

## [2.6.0] - 2026-07-22

### Added

- `templates/recommended-optional-evidence.md`: a standard, per-phase list of optional (non-blocking) supplementary evidence — sample input/output files, business documents, screenshots, and boundary/link targets. `$ak assess` now emits it so every app is prompted to strengthen coverage without ever inventing missing sources.

### Changed

- `tools/ExportAccessObjects.bas` now excludes system (`MSys*`), temporary (`~*`), and Access auto-generated ImportErrors tables (3-field Error/Field/Row signature) from `schema/tables.txt`, and reports the excluded count and names in `export-manifest.txt`. This keeps the exported data model clean at the source, so there is no need to delete objects from the live database.
- Presentation output is now **optional and off by default** (`outputs.derived.presentation_pptx: false` in new manifests); generate a PPTX only when the manifest enables it or the user explicitly requests one. E2E Trace and Boundary Map remain on by default.

## [2.5.2] - 2026-07-21

### Changed

- Renamed the project to **Access Modernization Kit**. The repository/package is `access-modernization-kit`, the plugin and CLI are `ak` (commands are `$ak ...`, the package lives under `plugins/ak/`, the CLI is `scripts/ak.py`), and the marketplace catalog is `access-modernization-kit`. Install with `codex plugin add ak@access-modernization-kit` (Codex) or `/plugin install ak@access-modernization-kit` (Claude Code). This is a rename only — the six-phase contract, schemas, and outputs are unchanged. References to the actual legacy "SMS" system under investigation are unchanged.

## [2.5.1] - 2026-07-21

### Fixed

- `tools/ExportAccessObjects.bas`: output is now uniformly UTF-8. `SaveAsText` writes the system codepage (Shift-JIS on Japanese Windows), so the exporter transcodes each form/report/macro/module file to UTF-8 to match the UTF-8 query and schema files. Also renamed the module to `modExportAccess` (a module sharing the Sub's name caused "Expected variable or procedure, not module"), and made every object export independently so one failing object is recorded under `skipped=` instead of aborting the run.

### Changed

- `references/access-extraction-guide.md`: expanded the manual-export guide with per-database split-database steps, VBA-editor import (not the Access database import), `Shift` startup bypass, missing-reference handling, UTF-8 output, and guidance to filter junk tables during analysis rather than deleting objects from the live database.

## [2.5.0] - 2026-07-21

### Added

- `tools/ExportAccessObjects.bas`: a VBA module that exports every form, report, macro, module, query, and table schema from inside Access via the Immediate window — no external COM automation and no administrator elevation. This is the recommended export-mode path when a compatible, activatable Access runtime is not available (no Access on the host, elevation-blocked activation, or a non-Windows environment). Filenames keep the original object names and de-duplicate only on real collisions.

### Changed

- `scripts/extract_access.py`: an authorized `--execute` run now fails fast with `BLOCKED` status **before copying a snapshot** when the runtime cannot be activated (for example a `RunAsAdmin` executable that requires elevation), and the warning explains the remedy (run elevated, `--allow-run-as-invoker`, `--powershell`, or `--skip-runtime-check`). Previously it copied the snapshot and only then reported the adapter failure.

## [2.4.1] - 2026-07-21

### Fixed

- `scripts/extract_access.ps1`: `Get-SafeName` now appends a deterministic hash of the original object name. Previously non-ASCII names (for example Japanese forms, queries, and reports) all sanitized to identical underscore filenames, so distinct objects overwrote one another on disk and the extraction silently lost sources (observed: 51 forms → 21 files, 98 queries → 60, 63 reports → 32). Extraction is now lossless; re-extract affected apps to recover the missing objects.

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

- Added the user-facing `ak.py` CLI for package validation, app-workspace initialization, and capability preflight.

### Changed

- Documented the recommended agent-skill entry point and a minimal CLI alternative before the detailed investigation workflow.

## [2.1.6] - 2026-07-16

### Changed

- Renamed the Codex/Claude skill identifier from `$access-modernization-kit` to the shorter `$ak`; the repository and package name remain unchanged.

## [2.1.7] - 2026-07-16

### Added

- Added a documented shorthand command guide for the agent skill: `help`, `init`, `assess`, `phase`, `run`, `status`, and `render`.

## [2.1.8] - 2026-07-16

### Added

- Added `ak.py install` and the matching `$ak install` agent commands for Codex and Claude skill discovery.

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
