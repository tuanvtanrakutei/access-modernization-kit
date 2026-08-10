# Changelog

## [2.8.0] - 2026-08-05

### Added

- Merged the `access-modernize` pipeline into this package as a second, independently invokable pipeline (`plugins/ak/modernize/`). Six stages carry a project from six-phase output through a working Django REST + React implementation, one screen at a time, with coverage gates tracing every legacy artifact to implemented code. Running one pipeline never auto-triggers the other. All nine modernization skills live at `plugins/ak/skills/` — the same folder as the six-phase skill, not nested under `modernize/` — so every skill works on **both Claude Code and Codex CLI**, one install, no extra steps: Codex's manifest already points at that exact path (`"skills": "./skills/"`, enforced by `validate_structure.py`), confirmed against a real 2.7.3 install cached on the author's own machine (`~/.codex/plugins/cache/access-modernization-kit/ak/2.7.3/`), which showed the exact fault this fixes.
- `bootstrap-project` skill: one-time project setup that copies templates, seeds `Screens_Registry.md` from a six-phase run's Phase 2 inventory after a single accept over the whole table, and wires a pointer block into the target project's `CLAUDE.md`/`AGENTS.md` (created if missing, otherwise updated in place inside a marked block) so a fresh session has standing awareness of the pipeline before any skill's own trigger phrase fires.
- `validate-docs`, `triage-suite`, and `modernize-screen` skills; five single-stage skills (`plan-screen`, `code-screen`, `test-screen`, `review-screen`, `screen-status`); an orchestration policy set (`write_paths` allowlist) for multi-screen batches; a non-writing scope-sensor hook.
- `templates/FRONTEND_API_PATTERNS_TEMPLATE.md` and `FRONTEND_UI_PATTERNS_TEMPLATE.md` — fill-in-the-blank starting points for a project's own concrete frontend patterns, generalized from a real implementation.
- `docs/PHASE_OUTPUT_GUIDE.md` — a human-oriented quick reference for reading a six-phase run's output before or while bootstrapping a modernization project on it.

### Changed

- Upgraded `examples/minimal-app` from the legacy V2.1 manifest shape to a classified V2.2 acquisition fixture. Its existing VBA and SQL files are now explicit artifacts, with a minimal SQL catalog containing only facts already present in `demo_orders.sql`. Added regression coverage for the checked-in fixture's preflight, acquisition plan/run, bundle validation, inventories, and honest readiness result (Phases 1/2/3/4/6 `BLOCKED`, Phase 5 `LIMITED`). This fixes the acquisition seam without pretending the fixture is a completed six-phase investigation.
- `README.md` and every document under `plugins/ak/modernize/docs/` restructured for navigation: a nested Contents/TOC on all ten, an "At A Glance" diagram leading `modernize/README.md` ahead of the detailed stage diagram, and an explicit split between human-facing and agent-facing documents.
- `plugins/ak/modernize/docs/LEGACY_EVIDENCE.md` documents the exact handoff contract between the six-phase pipeline and the modernization pipeline — real output filenames (not the template's own), cross-artifact screen-identity matching and its limits, and why the pre-flight gate check reads three phases rather than being simplified to one.
- The five single-stage skills (`plan-screen`, `code-screen`, `test-screen`, `review-screen`, `screen-status`) shipped for most of 2.8.0 as `plugins/ak/commands/*.md`, a separate manifest field, Claude-Code-oriented. Converted to the same `skills/{name}/SKILL.md` shape as the other nine, each with its own `agents/openai.yaml`, after real testing against a Codex 2.8.0 install found the `commands` field unreliable — only 2 of the 5 files ever surfaced, with no file- or manifest-side cause found (`plugins/ak/modernize/BACKLOG.md` entry G10). The conversion also resolves the ugly auto-generated `Ak: Source Command <Name>` labels Codex fell back to for commands, since there is no longer a `commands` field or mechanism at all — every one of the ten skills now uses the one mechanism already proven reliable. `commands/` removed; `"commands"` dropped from both `.claude-plugin/plugin.json` and `.codex-plugin/plugin.json`. Not yet re-verified against a real Codex cache (`plugins/ak/modernize/BACKLOG.md` entry G11).
- `skills/ak/SKILL.md`'s own `$ak help` output listed its ten verbs with no indication of run order, and put the rarely-needed `install codex`/`install claude` rows near the top. Added a "Typical flow" line (`init` → `assess` → `acquire` → `phase`/`run` → `status` → `render`), reordered the table to match, and moved the two install rows to the end with a "skip if already installed via marketplace" note.
- Renamed the six-phase skill from `ak` to `investigate` (`plugins/ak/skills/ak/` → `plugins/ak/skills/investigate/`), so its Claude Code slash form reads `/ak:investigate` instead of `/ak:ak` — the old form was two copies of the same word and, unlike `/ak:bootstrap-project` etc., told a user nothing about what it does. The `$ak init`/`$ak assess`/... chat-trigger vocabulary, the plugin's own name (`ak`), and the Codex cache path are unchanged — only this one skill's registered name and folder moved. Updated every reference: `validate_structure.py` (3 hardcoded checks), `adapters/adapter-map.json`, `CONTRIBUTING.md`, `modernize/SMOKE_TEST_PROMPT.md`, `scripts/bump_version.py`, `references/agent-compatibility.md`, both READMEs. Also fixed a real bug the rename's own grep audit missed: `scripts/ak.py`'s `install_destination()`/`install_skill()` built the old skill path via `Path` joins rather than a matching literal string, so `$ak install claude <PROJECT_PATH>` would have installed against the wrong path — caught by `pytest`, not by grep (`plugins/ak/modernize/BACKLOG.md` entry G12).

### Fixed

- **Managed Access extraction had never once worked against a real `.mdb`, and twenty-four defects were found and fixed by running it.** The `examples/minimal-app` fixture ships no Access database, so this whole path was exercised only by Python-written fixtures; a real run against a split Access 2003 application (frontend plus data `.mdb`, 11.0.5614 32-bit) surfaced the lot. Four were a producer and a consumer inside this package disagreeing on a key, invisible to any fixture written in Python: the bundle router read `type`/`object_type` while `extract_access.ps1` emits `kind`, so every component of a clean extraction landed in `databases.objects` and the `ui`/`code`/`interfaces` sections stayed empty; the extractor writes its receipt with a BOM while the adapter read it as plain `utf-8`, so `json.loads` rejected every real receipt; `Artifact` is a frozen dataclass with fixed fields, so the per-artifact `runtime` block the manifest schema permits was dropped at load time and every runtime declaration silently had no effect; and the bundle keys code records by `logical_id` while the extractor emits `id`, so assembly raised `KeyError` on every managed-access contribution.
- Three defects destroyed the evidence of their own failure, which is why none of the above had ever been diagnosed: the extraction loop ran over `MSys*` system tables whose definitions are unreadable, and with a stop-on-error preference and only an outer `try/catch` the run aborted at table 19 of 116, silently dropping 98 tables plus every query, report and module; `Get-FileHash` on the snapshot raced Access's handle release after `Quit()` and threw before the script could write its result file, taking all collected warnings with it; and the adapter decoded the child process's output as strict `utf-8`, so cp932 diagnostics from a Japanese-Windows PowerShell killed subprocess's reader threads and reduced every failure to a bare returncode. Each loop now isolates errors per item and skips `MSys*` tables, the snapshot digest is taken before Access opens the file (which is also the only digest that matches the source, since opening mutates it), and child output is decoded with `errors="replace"` and attached to the failure record.
- Extraction is now two tiers, because reading a single table used to require starting the Access host, which loads the VBA project and runs AutoExec: on a real application the startup code entered the VBA debugger's break mode behind a hidden host and hung indefinitely with no timeout at any layer, and a broken reference then raised a modal `Error in loading DLL` no unattended run can answer. A DAO tier (`DAO.DBEngine.36`, read-only) now reads schema, queries and - via DAO containers - the complete form, report, macro and module inventory without starting Access at all; the Access host tier only exports definition text and may fail to `PARTIAL` without costing the DAO tier's results. Added `--timeout` plus an `access-host.json` recording only the PIDs a run started, so a hung host is killable without touching an Access the operator opened; `AutomationSecurity = msoAutomationSecurityForceDisable` to make the open inert; and declared-runtime selection (`--access-progid`, `--dao-progid`, `--access-path` verified against the executable COM would really activate, `--skip-object-export`), reachable per artifact through the manifest via a fixed allow-list so a manifest cannot inject arbitrary arguments.
- Two capabilities the phase gates require could never be reported by anything in the package. Field and index detail reached `schema/tables.json` but never the bundle, because normalization reads only the extraction record - `databases.fields`/`indexes` were declared, read, and written to the bundle, yet nothing anywhere appended to them, so `field_inventory` and `key_index_inventory` were unreachable and Phase 1 could not pass its own baseline; the extraction schema now carries an optional `tables` key (older extractions still validate) and the adapter flattens it. `backend_authority_declared`, required by the backend and split-topology profile rules, was likewise referenced only by consumers, fixtures and tests; it is a statement about which store the project treats as authoritative, so it is now derived from the manifest declaring a required backend artifact with an explicit `backend_kind`, not from an adapter describing extracted evidence.
- `ak.py print_json` died with `UnicodeEncodeError` under a cp932 console, discarding a completed acquisition's entire report after all the work was done. `errors="replace"` stopped the crash but not the data loss: redirecting that report to a file still encoded it as cp932, so every glyph outside that codepage was written as `?` and the saved report was quietly lossy. Output is now reconfigured to `utf-8` with `errors="replace"`, so a redirected report is byte-faithful and only a genuinely unprintable glyph on the console costs a glyph.
- **This package disagreed with its own exporter about three policies, and the copy operators actually rely on was the wrong one.** `tools/ExportAccessObjects.bas` already encodes the correct rules; `extract_access.ps1` diverged on all three. Its `Get-SafeName` replaced every character outside `[A-Za-z0-9._-]` with an underscore, so `共通ルーチン` and `q受注データ` came out as `_____` and `q______` — every Japanese object name destroyed and distinct objects collapsed onto one filename, in a kit whose entire target population is Japanese legacy applications. A package test asserted that exact output, which is how it survived a full suite: the test was protecting the bug, and was rewritten to assert the real names are preserved. Names are now kept as-is and altered only when the filesystem forces it, with a short digest appended whenever they are, so an altered name can never silently collide. Import-error residue and hidden objects were also being inventoried as real schema — 209 of a reported 334 tables were `インポート エラー` leftovers — so tables are now classified as junk by field **shape** (a three-field `(text, text, long)` table), not by name, which the real data proved necessary: one legitimate table carries `エラー` in its name but has a single field. `~`-prefixed hidden queries are skipped. Every exclusion is summarized in the run's warnings, so a drop is never silent.
- **Installing this package installed nothing it needs to run, and the gap was hidden almost perfectly.** Neither plugin manifest declares a Python dependency, there is no install hook, and no user-facing document mentioned `pip` at all — README, the skill's own command guide, `references/` and `docs/` contained zero occurrences. `init` is stdlib-only so it worked on a bare Python; `assess` reported `PASS` while quietly downgrading its manifest read to a pattern scan; `acquire` then died with `ModuleNotFoundError`, since `manifest_v22` and `bundle_assembly` import `yaml` and `jsonschema` at module level. A new user's first three commands succeeded, lied, and crashed, in that order. Both packages are now `required` in preflight so the failure lands where it can be explained, with the install command in the recommendation, and `manifest_needs` records `yaml_parsed` so a pattern-matched manifest is never reported as a parsed one. `requirements-dev.txt` was the only dependency file and pointed users at `pytest`; split into `requirements.txt` (the runtime minimum), `requirements-documents.txt` (optional local readers for Phase 5 document evidence), and a dev file that composes both plus the test runner. Writing the test for the fallback exposed a further defect inside it: the no-PyYAML branch only ever matched V2.1 keys, so a V2.2 Access-only project reported `access: false` — the same defect already fixed in the parsed branch, left standing in the branch where it is far harder to notice.
- **A hybrid project was reported as extract-only, pushing operators toward a runtime they do not need.** `preflight`'s V2.2 reader counted an artifact as an exported source only when `format: vba`, so a directory or `.zip` package — the shape the imported adapter requires and `build_import_manifest.py` produces — was neither VBA nor SQL. An application whose 51 forms, 67 reports, 7 modules and 79 SQL definitions all arrived that way reported `vba: false, sql: false` and `mode: extract`. `mode` also conflated inputs with outstanding work: it was derived from whether extraction was still pending, so identical inputs read `mixed` before acquisition and `export` after it. It now describes only which inputs were provided, with `needs_extraction` reported separately, and a published `acquired/bundle-*` directory satisfies `extracted_access` — which the legacy `extracted/access/` path alone never did, because acquisition does not write there.
- **`specifications/input-preconditions.md` is the document a developer reads to learn what to provide, and it was wrong in four ways**, each enough to block a new project: it declared Access databases under the V2.1 `sources.access_databases[]` shape that `acquire` rejects; it advised `--allow-run-as-invoker` as the remedy for a RUNASADMIN-flagged Access, which cannot work; it described two mutually exclusive input paths when the orchestrator routes four adapters and combines them in one run; and its export table never mentioned that a directory or `.zip` package needs an `import-source-manifest.yaml`, so anyone following it hit `IMPORT_MANIFEST_REQUIRED` with no stated cause. Rewritten against the code, including the two-tier extraction model, the honored `runtime` keys, when to use `skip_object_export`/`skip_object_inventory`, and a host-prerequisites section covering the dependency install above.
- **A bundle could not tell exported evidence from freshly extracted evidence.** The import manifest's entire purpose is to record what produced a package and when, and `imported_sources` discarded it: every source was written to `provenance.json` as the literal string `declared_import` with the adapter's own version standing in for the producer's, so a package declaring `ExportAccessObjects.bas` version `2026-07` was indistinguishable from text read out of the database in this run. Producers are now recorded per source, because one run can legitimately import several packages produced by different tools at different times — a single adapter-level producer could never have expressed that. Added `--source-database` so a package can record the digest of the database it was exported from, and a drift check that reports `EXPORT_SOURCE_DRIFT` when an export declares an origin that is not among the databases acquired alongside it. A hybrid run taking schema from the live database and definition text from an earlier export is legitimate, and for an application whose VBA project cannot be loaded unattended it is the only way in; doing it silently is not, because the bundle would mix current schema with stale definitions and say nothing. Drift is recorded as a failure rather than raised, since the operator may knowingly use an older export, and absent a declared origin nothing is claimed in either direction — silence is not evidence of a match. Only the digest reaches the bundle, never the database's filename, which the bundle's own no-raw-binary guard correctly refused.
- **Imported acquisition — the mode that needs no Access install at all — could not be used by anyone.** `imported_sources` deliberately refuses a bare directory, because a producer manifest is what lets it verify that every file was declared and what each file is; but nothing in the package could write that manifest, so an operator holding a perfectly good export had no way in. Added `scripts/build_import_manifest.py` and `$ak import-sources`, which classifies by container directory to match this kit's own exporters, detects each file's encoding, and refuses rather than mislabelling a file it cannot classify. Two defects then blocked it anyway. Its conflict key applied the same lossy substitution described above, collapsing every Japanese name onto one value and reporting `ARTIFACT_CONFLICT` between completely unrelated objects; the key is now NFKC + casefold only, which is precisely what Access object identity means, and bundle filenames are hashed from the logical id, so there was never a filesystem collision to defend against. Conflicts were also pooled across every artifact in one run, so a split application's legitimately same-named query in both its frontend and its backend export failed the whole import — detection is now scoped per package, with a single declared file treated as its own package so the duplicate-id check still applies. Finally, when an imported export supplies the definition text, the DAO tier's inventory of those same objects double-counted them (102 forms, 158 queries for an application with 51 and 79); `--skip-object-inventory` was added and threaded through the extractor, the CLI and the manifest's per-artifact runtime block. Verified end to end against the real split application, unattended and with no Access host: acquisition exit 0 with zero failures, `bundle validate` **VALID**, readiness **phase1/2/3 READY**, carrying all 51 forms, 67 reports, 1 macro, 7 VBA modules and 79 Access SQL definitions with their full definition text — which the managed path had never once delivered.
- `init --source` hard-coded `topology: monolith`, `role: frontend` for every `.mdb` and `backend_kinds: embedded_access` - all three wrong for a split application, which is the normal shape for this family. The role was the costly one: with both databases labelled frontend nothing declares an authoritative backend, so Phase 1 could never leave BLOCKED no matter how complete the extraction. Two or more Access databases now yield `split_file` with `backend_kinds: [access_file]`, and their role is set to the schema's own `unknown` rather than guessed from a filename, with `init` printing which ids still need a human decision. Artifact ids were built by stripping every non-`[A-Z0-9_]` character, so a Japanese name lost all of it and distinct objects collapsed onto one base separated by an arrival-order counter (`ART`, `ART_1`) that changed whenever the file order did; they now carry a short digest of the original name, the same technique the extractor already used for filenames.
- `preflight`'s `manifest_needs()` parsed only V2.1 `sources.*` keys, so on a V2.2 manifest every capability read `false` - Access itself on an Access-only project, and `graphify`, which silently suppressed the missing-runtime warning for a gate documented as mandatory. It now reads `artifacts` as well, and `init`'s V2.2 writer emits the `graphify` block it had been omitting, with the pinned version read from `specifications/graphify-runtime.json` rather than a third hard-coded copy. `extract_access.ps1` exports objects as `.txt` via `SaveAsText` while `init --source` classified `.txt` as `kind: sample`, so the package did not recognize its own output; classification is now directory-aware, and `.sql` inside a `queries/` folder no longer flips `backend_kinds` to `sql_server`, since Access query SQL is not evidence of a server.
- `preflight` reported Access `READY` from a discovery pass that never attempts activation, so a PASS did not predict whether extraction could run. The report now states `activation_verified` outright, recommends the DAO-only tier or a real check when it is false, and `--verify-access-activation` performs one. Relatedly, `--allow-run-as-invoker` was advised as the remedy for an elevation-flagged Access and cannot work - `__COMPAT_LAYER` is set on the PowerShell host while the COM server is launched out of process - so its help text and the extractor's warning now name the remedy that does work (clear `RUNASADMIN` from the executable's `AppCompatFlags\Layers` value, or run elevated) and point at `--skip-object-export` as the way to read schema and inventory with no Access host at all.
- `investigate/SKILL.md`'s own frontmatter `description:` never mentioned `$ak` anywhere, unlike all nine other skills, which each end with an `Examples: "..."` tail naming their own trigger phrases. Since natural-language skill matching reads from `description:`, a cold `$ak help` typed without first selecting `/ak:investigate` from the picker had nothing in this skill's metadata connecting it to that phrase. Added the same kind of example tail the other nine already have.
- `plan-screen`, `code-screen`, `test-screen`, `review-screen`, and `screen-status` referred to "the screen named in the request" throughout but never said what to do if the request never named one. Audited all ten skills for this class of gap (user asked directly): `investigate`, `bootstrap-project`, and `modernize-screen` already guarded their parameters; these five did not. Added an explicit stop-and-ask step to each, worded consistently to avoid guessing a screen from conversation context.
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
