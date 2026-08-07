---
name: ak
description: Analyze Microsoft Access VBA applications and MDB/ACCDB/ADP projects connected to SQL Server through a mandatory six-phase, evidence-backed legacy-system investigation with Access extraction, deterministic module planning, and provider-neutral multi-agent orchestration. Use when an agent must package, initialize, analyze, review, or continue investigation of an SMS A-series satellite app and produce Phase documents, E2E traces, boundary maps, question lists, QA, or presentation inputs.
---

# Access Modernization Kit V2.8.0

Use one shared investigation method while keeping every app's sources, graph, decisions, sessions, and outputs isolated.

Treat `scripts/`, `references/`, `specifications/`, `schemas/`, `templates/`, and `orchestration/` below as paths under this plugin's package root, two levels above this `SKILL.md` file.

## Interpret the user command guide

Treat these short forms as explicit user requests. They are agent commands, not shell commands.

**Typical flow for one app, in order:** `init` → `assess` → `acquire` → `phase`/`run` →
`status` → `render`. Each later step depends on the one before it — `acquire` needs a
workspace from `init`; `phase`/`run` need an approved bundle from `acquire`; `render` needs
Phase 6 and QA gates already passed. `help` and `install ...` are one-time housekeeping, not
part of this per-app sequence — most users only ever need them once, if at all.

| User input | Required action |
|---|---|
| `$ak init <APP_ID> [--source <PATH>]` | Scaffold or adopt an app workspace. If `--source` is provided (folder or .zip), automatically copy/extract sources and auto-generate `manifest.yaml`. For non-empty workspaces without `--source`, require `--adopt-existing`. |
| `$ak assess <APP_ID>` | Resolve or propose the project classification, inspect authorized artifacts/staging, report bundle and phase readiness, gaps, required approvals, and recommended optional evidence without analyzing a phase. |
| `$ak acquire <APP_ID>` | Automatically plan and run acquisition to create a canonical bundle for analysis. For imported sources (exported VBA/SQL or zip packages), no Access runtime is required. For managed Access MDB files, requires host Access/ACE runtime and explicit `access_snapshot_extract` authorization. |
| `$ak phase <1-6> <APP_ID>` | For V2.2 require an approved bundle and non-blocked phase readiness before Graphify; for V2.1 warn that migration is pending, preserve the legacy gate, then run only the named phase. |
| `$ak run <APP_ID>` | Run technically permitted phases in order, stopping on `BLOCKED`; this never authorizes live Access, ADP, SQL Server, backup restore, or network access. |
| `$ak status <APP_ID>` | Report app/run/phase/QA status without changing evidence or outputs. |
| `$ak render <APP_ID> [LANGUAGE]` | Render declared outputs only after the required Phase 6, traceability, and QA gates pass. |
| `$ak help` | Show this guide again; does not modify an app workspace. |
| `$ak install codex` | One-time, and only if you did **not** already use `codex plugin add` to install this package — explains that `$ak` is already installed as a Codex plugin, and does not create a manual skill link. Skip this if you installed from the marketplace. |
| `$ak install claude <PROJECT_PATH>` | One-time, and only for pinning this package into one specific project **without** going through `/plugin install` — runs `scripts/ak.py install --runtime claude --project <PROJECT_PATH>`, reports the discovery path and restart requirement. Skip this if you installed from the marketplace. |

This table covers six-phase investigation only — `$ak help` does not describe or run the
separate modernization pipeline this package also ships (`bootstrap-project`,
`modernize-screen`, `validate-docs`, `triage-suite`, `plan-screen`, `code-screen`,
`test-screen`, `review-screen`, `screen-status` skills). Invoke those directly by name or
natural-language request; see the repository root README's modernization Command Guide for
the full list.

Accept the equivalent Vietnamese or plain-language request. If an app ID is omitted, ask for it before any app-specific action. Never interpret `run` as approval for live Access/ADP or SQL Server access; require that approval separately.

## Select the operating mode

1. Use **package mode** when asked to create, install, validate, or modify this kit. Do not analyze A01 or another app unless the user separately authorizes a trial.
2. Use **app initialization mode** when asked to scaffold a new app workspace. For a non-empty existing project, require explicit --app-root and --adopt-existing; never overwrite files, then stop unless analysis is also requested.
3. Use **investigation mode** only when asked to run one or more phases for a named app.
4. Use **rendering mode** only after Phase 6 and traceability validation are complete.
5. Use **orchestration mode** when the user requests multi-agent execution. Parallelize evidence collection and affected leaf modules, but publish the six phases sequentially through coordinator-owned gates.

## Load the mandatory contracts

Before investigation work, read these files completely:

- `specifications/senior-system-analyst-instruction.md`
- `specifications/evidence-policy.yaml`
- `specifications/output-contract.yaml`
- `specifications/package.json`
- `specifications/runtime-capabilities.yaml`
- `specifications/language-support.yaml`
- The target app's `manifest.yaml`

Read only the phase template needed for the current phase. Before any Phase/run request, read `references/graphify-phase-gate.md`. Read `references/presentation-guidance.md` only when generating a presentation. Read `references/agent-compatibility.md` only when installing or adapting the kit for another agent runtime.

For multi-agent work, also read `references/orchestration-guide.md`, `orchestration/roles.json`, `orchestration/waves.json`, and `orchestration/runtime-adapters.json`. When Access binaries, compilation databases, or module planning are present, also read `references/access-extraction-guide.md` and `references/module-and-build-context.md`.

## Preserve scope boundaries

- Treat legacy Access/VBA and SQL Server behavior as the investigation subject.
- Keep current replacement implementation outside analysis unless the manifest and user explicitly include comparison.
- Never copy A01 facts, counts, paths, table names, business rules, or decisions into another app.
- Reuse shared SMS infrastructure nodes such as NAS, shared databases, and system documents through references; do not duplicate them as app-local facts.
- Treat old Phase files as outputs to reconcile, never as the sole source of truth.

## Prepare source context safely

- Confirm input preconditions in `specifications/input-preconditions.md`. Export mode (pre-exported VBA/SQL in `sources/`) needs no Access runtime; extract mode (an MDB/ACCDB/ADP) requires a `READY` host. Missing inputs are warnings recorded as assumptions, never a silent gap.
- Run `scripts/preflight.py` before extraction. It reports capabilities, detects the input mode, flags missing sources, and never installs dependencies.
- For every MDB/ACCDB/ADP, run `scripts/extract_access.py --dry-run` first. Execute COM/DAO extraction only when authorized and a compatible Access runtime exists.
- Never open the original Access binary. Executable extraction creates and hash-verifies a disposable snapshot.
- Never store literal passwords in manifests or artifacts. Use external secret references and redact connection metadata.
- Normalize declared `compile_commands.json` files with `scripts/parse_compilation_database.py`. Never execute `command` or `arguments` values.
- Build the deterministic app index with `scripts/build_component_index.py`, then run `scripts/build_module_plan.py`. Every component must be assigned exactly once and module cycles are forbidden.
- Process modules leaf-first. For incremental work, compare component indexes and re-run affected leaves plus their ancestors; keep prior evidence immutable.
- Before Phase 1-6, run the managed Graphify prepare/check/finalize sequence in `references/graphify-phase-gate.md`. A missing runtime is installed into the kit-managed environment; a failed install, invalid corpus, stale graph, or missing phase-query receipt blocks that phase.

## Separate source, Git, and graph policies

- `.investigationignore` alone controls the immutable source inventory.
- `.gitignore` controls tracking and keeps generated state, credentials, and raw Access databases local by default.
- `.graphifyignore` excludes binaries, run state, outputs, and media while leaving extracted VBA/SQL and normalized metadata visible.
- Record ignored inventory entries and the matching rule. Do not silently omit files.

## Apply language and build-context rules

- Record human language, programming/query language, dialect, encoding, parser, parser version, and parse status per source.
- Treat Access VBA, Access SQL, T-SQL, and ODBC pass-through SQL as distinct dialects.
- Use CP932/Shift-JIS-aware decoding where indicated; never silently replace undecodable Japanese text.
- Compilation databases are optional read-only context for compiled languages. Clang/libclang is conditional enrichment, not a requirement and not an Access/VBA parser.
- Access-specific build context includes Access version/bitness, VBA references and broken references, conditional constants, startup form, AutoExec, linked tables, and redacted ADP connection metadata.

## Run the six phases in order

1. **Phase 1 — Data Understanding:** inventory tables, columns, keys, relationships, entities, stored logic, and business-level data structure.
2. **Phase 2 — Screen & Form Analysis:** inventory every relevant form/report, purpose, actions, events, validations, navigation, and triggered logic.
3. **Phase 3 — Logic & Processing:** trace VBA actions to SQL, stored logic, file operations, calculations, filters, updates, error handling, and transaction boundaries.
4. **Phase 4 — Workflow Reconstruction:** build user-to-output flows and cover create, update, approval, and reporting; mark unsupported use cases as evidence-backed `Not identified` or `Not applicable`.
5. **Phase 5 — Document Integration:** translate Japanese XLSX/PDF rules, compare them with observed code and data behavior, and record mismatches without silently choosing a winner.
6. **Phase 6 — Synthesis:** produce system overview, entities/data model, screens/functions, business rules, E2E workflows, risks/legacy issues, and assumptions/unknowns.

Do not skip a phase because sources appear incomplete. Produce a scoped gap report and open questions instead.

## Orchestrate multi-agent execution

- For new multi-developer kit or application work, require a schema-valid work package and an approved `scope_acceptance` receipt before projecting run tasks.
- Run collaboration conflict detection before execution. Do not widen accepted role, module, path, evidence, dependency, or publication scope in a projected task.
- Require contract-impact records for contract-sensitive changes and bind implementation or publication review to the exact changed artifact set.
- Follow `docs/collaboration/contributor-workflow.md` and `docs/collaboration/application-team-workflow.md`; do not duplicate the six-phase pipeline in team instructions.
- Create an immutable run with `scripts/create_run.py`, then provider-neutral task envelopes with `scripts/create_tasks.py`.
- When a module plan exists, task generation fans SQL, VBA/UI, interface, and logic work out by affected leaf module. Parent and cross-module analysis consumes those handoffs.
- Map abstract spawn, message, wait, inspect, and interrupt operations to the active runtime. Do not hard-code a provider into evidence or outputs.
- Let specialists work in parallel only inside assigned write scopes. Workers must not merge canonical phase files.
- Require every worker handoff to match `schemas/handoff.schema.json`; validate with `scripts/validate_handoffs.py`.
- Merge evidence deterministically with `scripts/merge_evidence.py`. Conflicting duplicate IDs are errors, not automatic winner selection.
- Apply checkpoints in `orchestration/waves.json`. Phase publication stays sequential even when extraction and modules run in parallel.
- Advance a completed wave with `scripts/advance_run.py`; use `--approve-checkpoint` only after the review occurs.
- Require independent QA before E2E, Boundary Map, and presentation rendering.
- Preserve unresolved conflicts under `orchestration/conflict-policy.json`.

## Maintain evidence while analyzing

- Create or update `evidence/evidence.json` using `schemas/evidence.schema.json`.
- Workers write role/module-scoped fragments inside the run; only the coordinator publishes merged evidence.
- Label every substantive statement `EXTRACTED`, `INFERRED`, or `AMBIGUOUS`.
- Attach source path and location whenever available.
- Separate verified facts, assumptions, unknowns, and stakeholder decisions.
- Preserve conflicts between code, database, documents, screenshots, and runtime files.
- Maintain this traceability chain:

```text
User action -> screen/form -> VBA event -> processing/query -> table/file -> output
```

## Use Graphify as supporting infrastructure

- Query an existing app graph before broad source search and before every phase.
- Keep one graph per app and link only verified shared nodes to the global SMS graph declared in the manifest.
- Never treat an inferred graph edge as code evidence.
- Use the Graphify skill for graph build/update and follow its corpus, scale, semantic extraction, and honesty gates.
- Bootstrap the pinned managed Graphify runtime when missing; do not mutate system Python or install dependencies in the app workspace.
- Run Graphify only on the audited UTF-8 corpus produced by `scripts/normalize_graphify_corpus.py`, never directly on MDB/ACCDB/ADP, snapshots, or binary documents.
- Before each Phase N, require `scripts/graphify_phase_gate.py check --phase N` to return `READY`. Refresh changed sources incrementally, accept the resulting graph hash, and run the N-specific query first.
- Graphify's lack of a guaranteed VBA AST does not weaken line-backed extraction evidence.
- Graphify does not replace the six-phase contract.
- CodeWiki is not a dependency. V2.1 independently implements component indexing, hierarchical decomposition, leaf-first ordering, session isolation, and affected-module refresh.

## Apply phase gates and generate outputs

Before completing each phase, verify required template sections, evidence status and locations, open questions, app isolation, and manifest language. Before HTML rendering, verify Phase 4 and traceability. Before PPTX, verify Phase 6, evidence, decisions, and presentation scope.

Use filenames in `specifications/output-contract.yaml`. Generate only declared language variants. **Presentation output is optional and off by default** (`outputs.derived.presentation_pptx: false`); generate a PPTX only when the manifest enables it or the user explicitly requests one. For presentations, use the available presentation skill/runtime and manifest template; do not mutate PPTX through ad hoc OOXML.

## Validate without running an app

Run structural validation after package changes:

```powershell
python scripts/validate_structure.py --package .
```

Synthetic sequence:

```powershell
python scripts/preflight.py --package . --runtime generic
python scripts/extract_access.py --database <ACCESS_FILE> --database-id <ID> --output-dir <TEST_APP_ROOT>/extracted/access --dry-run
python scripts/parse_compilation_database.py --input <compile_commands.json> --output <TEST_APP_ROOT>/extracted/build-context/compile_commands.normalized.json
python scripts/build_component_index.py --app-root <TEST_APP_ROOT>
python scripts/build_module_plan.py --component-index <component-index.json> --output-dir <TEST_APP_ROOT>/extracted/module-plan
python scripts/create_run.py --app-root <TEST_APP_ROOT> --runtime generic
python scripts/create_tasks.py --package . --run <RUN_DIRECTORY>
python scripts/validate_handoffs.py --run <RUN_DIRECTORY>
python scripts/merge_evidence.py --run <RUN_DIRECTORY> --dry-run
python scripts/advance_run.py --package . --run <RUN_DIRECTORY> --wave <WAVE_ID>
```

This sequence validates package behavior without analyzing A01 or another real app.
