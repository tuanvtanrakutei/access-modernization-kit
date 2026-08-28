# Input Preconditions

This specification defines the minimum inputs and environment each app workspace
needs before the six-phase investigation runs. It is advisory: `preflight.py`
reports gaps as warnings and the investigation records missing inputs as
assumptions or open questions. It never silently invents evidence.

## Host prerequisites

Installing this package as a plugin installs no Python dependency: neither plugin
manifest declares one and there is no install hook. Two packages are required and
must be installed separately:

```
pip install -r requirements.txt
```

`init` is deliberately stdlib-only and runs without them. Everything from `acquire`
onward imports `yaml` and `jsonschema` at module level, so `preflight` reports both as
required and fails when either is absent, rather than passing and letting acquisition
die on `ModuleNotFoundError`. When PyYAML is missing, `preflight` falls back to
pattern-matching the manifest and marks the result `yaml_parsed: false` so the guesses
are not mistaken for a parse.

`requirements-documents.txt` is optional: local readers for spreadsheets, PDF, Word and
PowerPoint, needed only when Phase 5 has to read document evidence locally and the agent
runtime does not already provide readers.

## Input modes

Every artifact declared in the manifest is routed to one of four acquisition
adapters, by `kind`, `acquisition` and `format` (`contracts/acquisition_orchestrator.py`,
`route_adapter`). The operator chooses which inputs to provide; nothing falls back
automatically.

| Adapter | Provide | Access runtime | Authorization |
|---|---|---|---|
| `imported_sources` | Exported text: a single file, or a directory/`.zip` package | No | None |
| `managed_access` | `.mdb` / `.accdb` / `.adp` | **Yes** | `access_snapshot_extract` |
| `msaccess_vcs` | An MSAccess-VCS add-in export (`kind: producer_export`, `format: msaccess-vcs`) | No | None |
| `sql_server` | SQL Server catalog / DDL evidence (`kind: sql_server*`) | No | None |

**Adapters combine in one run.** A hybrid project is the normal shape for an
application whose VBA project cannot be loaded unattended: `managed_access` reads
schema, fields, indexes and relationships from the database through the DAO tier,
while `imported_sources` supplies the form, report, macro and module definition
text from an export. `preflight.py` reports this as `mode: mixed`, and reports
whether extraction is still outstanding separately as `needs_extraction`.

Manifest version: `acquire` requires a **V2.2** classified manifest. Artifacts are
declared under the top-level `artifacts:` list with a `project.classification`
block. The V2.1 `sources.access_databases[]` shape is still readable by `preflight`
and by the migration proposer, but acquisition rejects it - run
`scripts/ak.py manifest --manifest <PATH>` to propose a migration.

### Export inputs (recommended default)

Pre-exported, human-readable sources. No Access runtime is required.

| Input | Location | Requirement |
|---|---|---|
| VBA modules/forms (exported text) | `sources/vba/` | Required for screen and logic phases |
| SQL schema, queries, stored procedures | `sources/sql/` | Required for data and logic phases |
| Export package (forms/reports/macros/modules/queries together) | declared per artifact | See below |
| Screen captures | `sources/screenshots/` | Recommended; visual evidence for Phase 2 |
| Reports/output samples | `sources/reports/` | Recommended; evidence for Phase 4 |
| Sample data files | `sources/samples/` | Optional; file-interface evidence |
| App-specific documents | `sources/documents/` | Optional |
| Shared Japanese documents | `shared-docs/` | Recommended for Phase 5 document integration |

A **single file** declared directly as an artifact (for example
`format: vba`) needs nothing further. A **directory or `.zip` package** additionally
requires a producer manifest, `import-source-manifest.yaml`, beside its contents.
Without one the adapter fails the artifact with `IMPORT_MANIFEST_REQUIRED`, by
design: the manifest is what lets it verify that every file was declared, that none
appeared or vanished, what each file is, and what produced the export. Generate it
with:

```
python scripts/ak.py import-sources --source <PACKAGE_DIR> \
  --producer-id <WHAT_EXPORTED_IT> --producer-version <ITS_VERSION> \
  --logical-id-prefix <ARTIFACT_ID> [--source-database <THE_MDB>]
```

Pass `--source-database` whenever the database is available. It records that
database's digest, which is the only thing that can later detect an export gone
stale against the database acquired beside it (`EXPORT_SOURCE_DRIFT`). Files are
classified by their containing directory (`forms/`, `reports/`, `macros/`, `vba/`,
`modules/`, `queries/`, `schema/`, `documents/`, `screenshots/`, `samples/`); a file
that cannot be classified is refused rather than mislabelled, unless
`--allow-unclassified` is passed.

When VBA or SQL is absent, the affected phases still run but must mark the
missing coverage as an assumption or open question rather than guessing.

### Managed Access inputs (requires a compatible host)

A live Access database is provided and its schema, and optionally its object
definition text, are produced by the extractor.

| Input | Location | Requirement |
|---|---|---|
| Access database | `sources/access/*.mdb` `*.accdb` `*.adp` | Required |
| Manifest entry | `artifacts[]` with `kind: access_database` | Required (`id`, `role`, `format`, `source_ref`) |
| Authorization | `--authorize access_snapshot_extract` | Required; acquisition is `BLOCKED` without it |

Extraction runs in two tiers, and the first does not need Access at all:

- **DAO tier** (`DAO.DBEngine.36`, read-only): tables, fields, indexes,
  relationships, query SQL, and the complete form/report/macro/module inventory,
  without starting Access and therefore without running AutoExec or loading the
  VBA project.
- **Access host tier** (`Access.Application`): exports object definition text via
  `SaveAsText`. It may fail to `PARTIAL` without costing the DAO tier's results.

Declare per-artifact runtime choices in the manifest's `runtime` block:
`access_path`, `access_progid`, `dao_progid`, `timeout`, `password_env`,
`skip_object_export`, `skip_object_inventory`, `visible_host`. Only these keys are
honored, so a manifest cannot inject arbitrary extractor arguments.

Set `skip_object_export: true` when the host tier cannot run unattended, and
`skip_object_inventory: true` when an imported export supplies the same objects -
without the second, the DAO tier registers them by name as well and every object is
counted twice.

Before a real run, verify the host:

```
python scripts/access_runtime.py --smoke-test
python scripts/ak.py preflight --app-root <APP_ROOT> --verify-access-activation
```

Discovery alone does not prove COM activation works, so `preflight` states
`activation_verified` outright; `--verify-access-activation` performs a real
activate-and-release.

Environment expectations:

- Windows with Microsoft Access or the ACE/DAO runtime registered.
- The Python/PowerShell host bitness must match the registered Access bitness.
  A 64-bit host driving a 32-bit Access install is the most common activation
  failure; `access_runtime.py` selects a bitness-matched PowerShell host.
- `.adp` projects require a compatible legacy Access runtime (for example Access
  2003); a modern runtime is not assumed compatible.
- If the registered Access executable carries a `RUNASADMIN` AppCompat flag, COM
  activation fails with `0x800702E4`. Remove `RUNASADMIN` from that executable's
  `AppCompatFlags\Layers` value, or run from an elevated terminal.
  `--allow-run-as-invoker` **cannot** fix this and must not be relied on: it sets
  `__COMPAT_LAYER` on the PowerShell process, while the Access COM server is
  launched out of process and does not inherit it. Verified against a
  RUNASADMIN-flagged Access 2003 - `run_as_invoker: true`, activation still
  `0x800702E4`. To proceed with no Access host at all, pass `skip_object_export`
  and take the definition text from an export instead.
- The original database is never opened; extraction runs on a hash-verified
  snapshot and refuses to overwrite an immutable session.
- Startup VBA can stall a hidden host indefinitely. `--timeout` (default 1800s)
  bounds the wait, and only the process IDs a run itself started are terminated,
  recorded in `access-host.json`.

If no host is `READY`, do not block: export the VBA and SQL on a compatible machine
and provide them through `imported_sources` instead.

## Mandatory fact derivation, once

After export/extraction and deterministic module planning, and before the first
phase, the run derives the relationships its sources state literally
(`scripts/derive_graph_facts.py`): query text matched against the bundle's own
table list, each screen's record source and bound fields, screen-to-screen open
calls, and the ProgID of every embedded control. It also distils form and report
definitions into those facts, so a definition enters the corpus as
`RecordSource`, `ControlSource`, event names and embedded classes rather than as
coordinates.

It runs **once**, not once per phase: the bundle is sealed and does not change
between phases. It is deterministic - no managed runtime, no network, no model -
so re-running it reproduces the output exactly, which is what lets a phase cite a
derived count.

This replaces the six per-phase Graphify gates removed in 2.9.0. They were removed
on measurement, not preference: on a real application Graphify's AST pass produced
79 nodes and no edges from the query corpus, while the same sources derived
deterministically produced 756. A failed derivation blocks phase output; nothing
else about the derivation can block it.

## What each phase needs, by evidence class

Capability presence was never the right gate. Structural evidence produces
structural statements, so a phase satisfied by schema alone reports counts where
the business needs meaning - and reports `READY` while doing it.
`specifications/evidence-classes.yaml` defines the classes, which claims each can
carry, and per phase what is `required` versus what the phase is `degraded_without`.
`assess` reports the degradations by name, so the operator is told what to fetch
rather than that something unspecified is missing.

## Precondition outcomes

`preflight.py` reports an `input_preconditions` block describing the detected
mode, which inputs are present, which recommended inputs are missing, and — when
extraction is still outstanding — the runtime host status. Missing app sources
produce warnings and recommendations, never a hard failure. The package-contract
checks remain the only conditions that fail preflight.

`mode` describes only which inputs were provided — `export`, `extract`, `mixed`,
`none`, or `unknown` when there is no workspace beside the manifest. It is not a
statement about work already done: whether extraction still has to run is reported
separately as `needs_extraction`, so the same set of inputs is never described two
different ways depending on whether acquisition has happened yet.

`present.source_packages` covers directory and `.zip` export packages, which are
declared per artifact rather than found at a conventional path. `extracted_access`
is true once either the legacy `extracted/access/` path or a published
`acquired/bundle-*/` directory exists.
