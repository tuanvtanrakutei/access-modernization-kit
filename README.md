# SMS Legacy Investigation Kit

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.1.8-green.svg)](specifications/package.json)

## What is this?

SMS Legacy Investigation Kit is a reusable **operating kit for investigating legacy business applications** built with Microsoft Access/VBA and SQL Server.

Use it once for each independent satellite application—for example A01, A03, or another Access/VBA app. It gives Codex, Claude, and other agents one evidence-backed way to turn legacy sources into a clear business and technical understanding.

It is not the replacement SMS application. It does not migrate code automatically. It does not analyze or connect to a database until an authorized app workspace and sources are provided.

```mermaid
flowchart LR
    APP[One legacy app\nA01, A03, or another satellite app]
    SRC[VBA, MDB/ACCDB/ADP, SQL,\nPDF, XLSX, screenshots, reports]
    KIT[SMS Legacy\nInvestigation Kit]
    EVIDENCE[Evidence and\ntraceability]
    OUTPUTS[Phase 1-6, E2E Trace,\nBoundary Map, questions, QA, presentation]
    AGENTS[Codex, Claude,\nand specialist agents]
    GRAPH[Graphify\nrelationship map]

    APP --> SRC --> KIT --> EVIDENCE --> OUTPUTS
    AGENTS --> KIT
    GRAPH -. supports discovery .-> KIT
```

## What problem does it solve?

Without a shared method, each agent may investigate a legacy app differently, mix facts between apps, or produce a presentation without traceable proof. This kit makes the investigation repeatable:

- Keep each app's sources, evidence, decisions, runs, and outputs isolated.
- Follow the same mandatory six-phase analyst workflow.
- Trace business behavior from screen/form to VBA, SQL, table/file, and output.
- Let specialists work in parallel while one coordinator controls canonical results.
- Produce handover-ready Phase documents, E2E Trace, Boundary Map, QA, and presentation inputs.

## Start here: choose one entry point

### Recommended: ask an agent skill

This is the normal path for an investigation. Do **not** memorize the internal Python scripts or six-phase mechanics.

In Codex, open `/skills`, select **SMS Legacy Investigation Kit**, then state the result you need. You can also mention the skill explicitly with `$sms-kit`.

```text
Use $sms-kit to initialize an isolated workspace for A03.
The legacy source is Access/VBA with SQL Server. Do not analyze it yet.
```

For a real investigation, say what app and outcome you need:

```text
Use $sms-kit to investigate app A03 from the authorized sources.
Run the six phases, preserve evidence, and produce English Phase documents,
an E2E Trace, a Boundary Map, and presentation inputs.
```

Claude uses the same root `SKILL.md` through the project skill link. Ask the same plain-language request; do not create a separate Claude-only workflow.

### Alternative: use the small CLI

Use the CLI only to validate the shared package, create an app workspace, or run a safe preflight without an agent.

```powershell
# Check that the shared kit is healthy; no app is analyzed.
py -3.11 scripts/sms_kit.py validate

# Install the skill for Codex on this developer machine.
py -3.11 scripts/sms_kit.py install --runtime codex

# Install the same skill for Claude in one project.
py -3.11 scripts/sms_kit.py install --runtime claude --project D:\investigations\A03

# Create a separate workspace for one app.
py -3.11 scripts/sms_kit.py init `
  --root D:\investigations `
  --app-id A03 `
  --name-en "A03 Legacy Application"

# Inspect capabilities and the manifest; no live Access or SQL connection is made.
py -3.11 scripts/sms_kit.py preflight `
  --app-root D:\investigations\A03
```

Run `py -3.11 scripts/sms_kit.py --help` for the supported commands. The CLI is intentionally small; use the agent skill for extraction, phases, multi-agent orchestration, and rendering.

### Agent command guide

These are short messages to an agent after selecting the skill. They are not PowerShell commands.

| What you want | Type this |
|---|---|
| See the guide | `$sms-kit help` |
| Install for Codex | `$sms-kit install codex` |
| Install for Claude in a project | `$sms-kit install claude D:\investigations\A03` |
| Create an app workspace only | `$sms-kit init A03` |
| Check source coverage and missing inputs | `$sms-kit assess A03` |
| Run one phase | `$sms-kit phase 1 A03` |
| Run the full six-phase investigation | `$sms-kit run A03` |
| Check progress without changing anything | `$sms-kit status A03` |
| Create approved final outputs | `$sms-kit render A03 English` |

`run` means the six-phase analysis only. It does **not** authorize live Access/ADP extraction or live SQL Server access; approve those separately when needed.

## What it is not

- Not a replacement-system implementation or code-migration framework.
- Not an A01-only repository; A01 is only a future regression corpus when explicitly authorized.
- Not an autonomous database crawler. Live Access, ADP, and SQL Server access require approval.
- Not a Graphify wrapper. Graphify supports discovery but never replaces source evidence or the six phases.
- Not a collection of separate Codex and Claude instructions. One root `SKILL.md` is canonical for every runtime.

## Input to output

For one app workspace, provide only authorized sources:

- Exported Access VBA/forms/reports; optionally `.mdb`, `.accdb`, or `.adp` files.
- SQL Server tables, views, queries, or stored procedures.
- Japanese operational manuals, report lists, business-flow PDFs, and screenshots.
- Optional `compile_commands.json` for non-Access compiled-language context.

The kit produces:

1. Phase 1 — Data Understanding
2. Phase 2 — Screen & Form Analysis
3. Phase 3 — Logic & Processing
4. Phase 4 — Workflow Reconstruction
5. Phase 5 — Document Integration
6. Phase 6 — Synthesis
7. Evidence records, traceability, E2E Trace HTML, Boundary Map HTML, question list, QA report, and presentation-ready inputs/PPTX outputs.

## How one app uses the kit

1. Initialize an isolated workspace for the app, such as `A03`.
2. Declare scope and authorized sources in its `manifest.yaml`.
3. Run preflight; extract Access/build context only when authorized.
4. Build a component index and leaf-first module plan when sources need decomposition.
5. Run Phases 1–6 in order and preserve source-backed evidence.
6. Validate traceability and QA, then render the E2E Trace, Boundary Map, and presentation.

The package itself stays shared. Generated sources, graphs, evidence, run state, and outputs belong to the individual app workspace—not this repository.

## Multi-agent operating model

Specialists can collect evidence in parallel by source type or affected leaf module. They cannot publish canonical Phase files. The coordinator merges validated handoffs, preserves conflicts, and releases phases sequentially.

This makes the kit compatible with Codex, Claude, and generic agents without allowing agent-specific behavior to change the investigation contract.

## Current status and safety boundary

Version 2.1.8 is packaged and synthetic-smoke-tested. Live Access/ADP extraction, live SQL Server access, and the A01 regression corpus are intentionally outside the public test baseline.

- Never open the original Access database; executable extraction uses a hash-verified snapshot.
- Never execute `command` or `arguments` values from `compile_commands.json`.
- Never commit production databases, credentials, DSNs, connection secrets, customer documents, or investigation runs.
- Exclude the current replacement implementation unless the manifest and user explicitly include comparison.

## Optional preprocessing

Run Access preflight without copying or opening the database:

```powershell
py -3.11 scripts/extract_access.py `
  --database <ACCESS_FILE> `
  --database-id <DATABASE_ID> `
  --output-dir <APP_ROOT>/extracted/access `
  --dry-run
```

Then normalize optional build context and build the module plan:

```powershell
py -3.11 scripts/parse_compilation_database.py --input <compile_commands.json> --output <APP_ROOT>/extracted/build-context/compile_commands.normalized.json
py -3.11 scripts/build_component_index.py --app-root <APP_ROOT>
py -3.11 scripts/build_module_plan.py --component-index <component-index.json> --output-dir <APP_ROOT>/extracted/module-plan
```

Read [SKILL.md](SKILL.md) for the canonical agent procedure, [the Access extraction guide](references/access-extraction-guide.md) for runtime safeguards, and [the orchestration guide](references/orchestration-guide.md) for multi-agent execution.

## Source and ignore policies

- `.gitignore` controls repository tracking.
- `.graphifyignore` controls Graphify input.
- `.investigationignore` in each app workspace controls the immutable source inventory.

These policies are deliberately independent. An ignored inventory entry is recorded with its matching rule instead of being silently omitted.

## Requirements

Required: Python 3.10+ and an agent runtime capable of coordinator/worker execution. CI uses Python 3.11.

Conditional: Microsoft Access/ACE and Windows PowerShell for MDB/ACCDB extraction; a compatible legacy Access environment for ADP; `pyodbc` plus a Microsoft SQL Server ODBC driver only for authorized live SQL access; and Graphify, spreadsheet, document, presentation, OCR, or browser capabilities only when their outputs are requested.

CodeWiki is not installed, imported, or vendored. V2.1 independently implements selected architectural patterns: component indexing, hierarchical decomposition, leaf-first ordering, session isolation, and affected-module refresh.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes. Do not report vulnerabilities or accidental sensitive-data exposure in a public issue; follow [SECURITY.md](SECURITY.md).

## License and acknowledgements

Licensed under the [Apache License 2.0](LICENSE). Copyright 2026 Vo Ta Tuan.

See [NOTICE](NOTICE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for attribution and architectural acknowledgements.
