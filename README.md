# SMS Legacy Investigation Kit

[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Version](https://img.shields.io/badge/version-2.1.2-green.svg)](specifications/package.json)

An evidence-backed investigation kit for legacy Microsoft Access applications (`.mdb`, `.accdb`, and `.adp`) connected to SQL Server. It combines a mandatory six-phase senior-system-analyst workflow with safe Access extraction, deterministic module planning, provider-neutral multi-agent orchestration, Graphify integration, independent QA, and presentation-ready outputs.

Version 2.1.2 is packaged and synthetic-smoke-tested. Live Access/ADP extraction, live SQL Server access, and the A01 regression corpus are intentionally not part of the public test baseline.

## What it produces

- Phase 1 — Data Understanding
- Phase 2 — Screen & Form Analysis
- Phase 3 — Logic & Processing
- Phase 4 — Workflow Reconstruction
- Phase 5 — Document Integration
- Phase 6 — Synthesis
- Evidence and traceability records
- E2E Trace HTML
- Boundary Map HTML
- English, Japanese, or Vietnamese presentation inputs and PPTX outputs

## Core design

```text
Immutable sources
  -> Access/build-context extraction
  -> deterministic component index
  -> hierarchical module tree
  -> leaf-first, affected-module task fan-out
  -> sequential Phase 1-6 publication gates
  -> independent QA
  -> E2E / Boundary / Presentation rendering
```

Only the coordinator can merge evidence and publish canonical outputs. Source specialists may work concurrently inside isolated run and module scopes.

## Safety boundaries

- Never open the original Access database; executable extraction uses a hash-verified snapshot.
- Never execute `command` or `arguments` values from `compile_commands.json`.
- Never commit production databases, credentials, DSNs, connection secrets, customer documents, or investigation runs.
- Treat current replacement implementation as excluded unless the app manifest and user explicitly include comparison.
- Treat Graphify as supporting infrastructure, not as a replacement for evidence or the six-phase contract.

## Requirements

Required:

- Python 3.10 or newer; Python 3.11 is used by CI.
- A filesystem and an agent runtime capable of coordinator/worker execution.

Conditional:

- Microsoft Access/ACE and Windows PowerShell for MDB/ACCDB extraction.
- A compatible legacy Access environment for ADP extraction.
- `pyodbc` and a Microsoft SQL Server ODBC driver only when live SQL access is authorized.
- Graphify, spreadsheet, document, presentation, OCR, and browser capabilities only when requested outputs require them.

CodeWiki is not installed, imported, or vendored. V2.1 independently implements selected architectural patterns: component indexing, hierarchical decomposition, leaf-first ordering, session isolation, and affected-module refresh.

## Quick start

Clone or download the repository, enter its root directory, and validate the package:

```powershell
cd sms-legacy-investigation-kit
py -3.11 -m pip install -r requirements-dev.txt
py -3.11 scripts/validate_structure.py --package .
py -3.11 -m pytest -q
```

Initialize an isolated app workspace:

```powershell
py -3.11 scripts/init_app.py `
  --root D:\investigations `
  --app-id A03 `
  --name-en "A03 Legacy Application" `
  --runtime generic
```

Edit the generated `manifest.yaml`, place authorized sources in the declared folders, and run preflight:

```powershell
py -3.11 scripts/preflight.py `
  --package . `
  --runtime generic `
  --manifest D:\investigations\A03\manifest.yaml
```

## Preprocessing pipeline

Access preflight without copying or opening the database:

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
py -3.11 scripts/build_module_plan.py --component-index <APP_ROOT>/extracted/component-index.json --output-dir <APP_ROOT>/extracted/module-plan
```

Create an immutable run and module-aware tasks:

```powershell
py -3.11 scripts/create_run.py --app-root <APP_ROOT> --runtime generic
py -3.11 scripts/create_tasks.py --package . --run <RUN_DIRECTORY>
```

Read [SKILL.md](SKILL.md) for the canonical agent procedure, [the Access extraction guide](references/access-extraction-guide.md) for runtime safeguards, and [the orchestration guide](references/orchestration-guide.md) for multi-agent execution.

## Source and ignore policies

- `.gitignore` controls repository tracking.
- `.graphifyignore` controls Graphify input.
- `.investigationignore` in each app workspace controls the immutable source inventory.

These policies are deliberately independent. An ignored inventory entry is recorded with its matching rule instead of being silently omitted.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes. Do not report vulnerabilities or accidental sensitive-data exposure in a public issue; follow [SECURITY.md](SECURITY.md).

## License and acknowledgements

Licensed under the [Apache License 2.0](LICENSE). Copyright 2026 Vo Ta Tuan.

See [NOTICE](NOTICE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for attribution and architectural acknowledgements.
