# Changelog

## [2.8.0] - 2026-08-05

### Added

- Merged the `access-modernize` pipeline into this package as a second, independently invokable pipeline (`plugins/ak/modernize/`). Six stages carry a project from six-phase output through a working Django REST + React implementation, one screen at a time, with coverage gates tracing every legacy artifact to implemented code. Running one pipeline never auto-triggers the other. All nine modernization skills live at `plugins/ak/skills/` — the same folder as the six-phase skill, not nested under `modernize/` — so every skill works on **both Claude Code and Codex CLI**, one install, no extra steps: Codex's manifest already points at that exact path (`"skills": "./skills/"`, enforced by `validate_structure.py`), confirmed against a real 2.7.3 install cached on the author's own machine (`~/.codex/plugins/cache/access-modernization-kit/ak/2.7.3/`), which showed the exact fault this fixes.
- `bootstrap-project` skill: one-time project setup that copies templates, seeds `Screens_Registry.md` from a six-phase run's Phase 2 inventory after a single accept over the whole table, and wires a pointer block into the target project's `CLAUDE.md`/`AGENTS.md` (created if missing, otherwise updated in place inside a marked block) so a fresh session has standing awareness of the pipeline before any skill's own trigger phrase fires.
- `validate-docs`, `triage-suite`, and `modernize-screen` skills; five single-stage skills (`plan-screen`, `code-screen`, `test-screen`, `review-screen`, `screen-status`); an orchestration policy set (`write_paths` allowlist) for multi-screen batches; a non-writing scope-sensor hook.
- `templates/FRONTEND_API_PATTERNS_TEMPLATE.md` and `FRONTEND_UI_PATTERNS_TEMPLATE.md` — fill-in-the-blank starting points for a project's own concrete frontend patterns, generalized from a real implementation.
- `docs/PHASE_OUTPUT_GUIDE.md` — a human-oriented quick reference for reading a six-phase run's output before or while bootstrapping a modernization project on it.

### Changed

- `README.md` and every document under `plugins/ak/modernize/docs/` restructured for navigation: a nested Contents/TOC on all ten, an "At A Glance" diagram leading `modernize/README.md` ahead of the detailed stage diagram, and an explicit split between human-facing and agent-facing documents.
- `plugins/ak/modernize/docs/LEGACY_EVIDENCE.md` documents the exact handoff contract between the six-phase pipeline and the modernization pipeline — real output filenames (not the template's own), cross-artifact screen-identity matching and its limits, and why the pre-flight gate check reads three phases rather than being simplified to one.
- The five single-stage skills (`plan-screen`, `code-screen`, `test-screen`, `review-screen`, `screen-status`) shipped for most of 2.8.0 as `plugins/ak/commands/*.md`, a separate manifest field, Claude-Code-oriented. Converted to the same `skills/{name}/SKILL.md` shape as the other nine, each with its own `agents/openai.yaml`, after real testing against a Codex 2.8.0 install found the `commands` field unreliable — only 2 of the 5 files ever surfaced, with no file- or manifest-side cause found (`plugins/ak/modernize/BACKLOG.md` entry G10). The conversion also resolves the ugly auto-generated `Ak: Source Command <Name>` labels Codex fell back to for commands, since there is no longer a `commands` field or mechanism at all — every one of the ten skills now uses the one mechanism already proven reliable. `commands/` removed; `"commands"` dropped from both `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`. Not yet re-verified against a real Codex cache (`plugins/ak/modernize/BACKLOG.md` entry G11).

### Fixed

- Six `skills/*/SKILL.md` and `commands/*.md` files under `plugins/ak/modernize/` had unquoted YAML frontmatter (`description`, `argument-hint`) that a strict parser reads as a nested mapping or a flow sequence — quoted and re-verified against an actual YAML parser, not just visually.
- `plugins/ak/.claude-plugin/plugin.json` explicitly declared `"hooks": "./hooks/hooks.json"`, which Claude Code auto-loads by default at that same path — the explicit field caused a real `Duplicate hooks file detected` error on install. Removed the field; `hooks/hooks.json` still loads via the default convention.
- Both READMEs' modernization command tables showed bare `/plan-screen`-style command names and left `triage-suite`/`validate-docs` out entirely. Confirmed against a real Claude Code install that every skill and command in this package appears in the slash-command picker as `/ak:<name>` (all nine modernization entries, plus `/ak:ak` for the six-phase skill) — tables corrected to the real `/ak:` form, both missing skills added, and a "check the a01_docs set" example (a project-specific name, confusing as a generic example) reworded to "check the docs set".
- Root `README.md`'s six-phase Command Guide had drifted from `skills/ak/SKILL.md`'s own real command table: missing `$ak help`, `$ak install codex`, and `$ak install claude <PROJECT_PATH>` rows entirely, and still listing a `$ak preflight <APP_ID>` row that `SKILL.md` no longer defines (superseded by the broader `$ak assess <APP_ID>`). Realigned the README table, the Scenario B walkthrough, and the Safety Contract note to match `SKILL.md` exactly. Separately, `$ak help`'s own output (the table in `SKILL.md`) never mentioned that a second, independently invokable modernization pipeline exists in the same package — added one paragraph directly after the table so `$ak help` itself surfaces this, not just the README.

## [2.7.3] - 2026-08-04

### Added

- Streamlined `$ak init --source <PATH>` with auto-discovery for exported sources, directories, and ZIP archives.
- Streamlined 1-step `$ak acquire <APP_ID>` shortcut.

### Changed

- Streamlined user documentation in README.md and SKILL.md.

## [2.7.2] - 2026-07-28

### Added

- Canonical human/agent work packages, review receipts, and contract-impact records.
- Deterministic collaboration conflict checks, runtime task projection, and English team workflows.

### Changed

- Bundle locks may carry portable multi-developer artifact authority while legacy locks remain valid.

### Security

- Production bundles remain outside Git by default; scoped paths, evidence namespaces, publication authority, and reviewer independence are validated before integration.

## [2.7.1] - 2026-07-28

### Added

- Managed/imported Access, msaccess-vcs, and SQL Server acquisition adapters with `ak acquire plan|run`.
- Deterministic canonical bundle assembly and English acquisition decision guides.

### Fixed

- ZIP package acquisition now validates and reads declared members without extraction.
- Cross-adapter conflicts, stale bundle targets, stale managed-extraction receipts, and invalid pre-bundle acquisition are rejected.
- DACPAC object inventory and adapter-owned readiness capabilities prevent false Access/SQL completeness claims.

### Security

- Raw Access databases, SQL Server backups/data files, archive executables, path escapes, symlinks, undeclared package members, and unapproved bundles remain outside analysis inputs.
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
