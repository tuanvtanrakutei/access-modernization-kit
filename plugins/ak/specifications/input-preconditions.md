# Input Preconditions

This specification defines the minimum inputs and environment each app workspace
needs before the six-phase investigation runs. It is advisory: `preflight.py`
reports gaps as warnings and the investigation records missing inputs as
assumptions or open questions. It never silently invents evidence.

## Input modes

An app is analyzed through one of two input paths. They are not automatic
fallbacks; the operator chooses which inputs to provide.

### Export mode (recommended default)

Pre-exported, human-readable sources are placed directly in the workspace. No
Access runtime is required.

| Input | Location | Requirement |
|---|---|---|
| VBA modules/forms (exported text) | `sources/vba/` | Required for screen and logic phases |
| SQL schema, queries, stored procedures | `sources/sql/` | Required for data and logic phases |
| Screen captures | `sources/screenshots/` | Recommended; visual evidence for Phase 2 |
| Reports/output samples | `sources/reports/` | Recommended; evidence for Phase 4 |
| Sample data files | `sources/samples/` | Optional; file-interface evidence |
| App-specific documents | `sources/documents/` | Optional |
| Shared Japanese documents | `shared-docs/` | Recommended for Phase 5 document integration |

When VBA or SQL is absent, the affected phases still run but must mark the
missing coverage as an assumption or open question rather than guessing.

### Extract mode (deferred; requires a compatible host)

A live Access database is provided and the VBA/SQL is produced by the extractor.

| Input | Location | Requirement |
|---|---|---|
| Access database | `sources/access/*.mdb` `*.accdb` `*.adp` | Required |
| Manifest entry | `sources.access_databases[]` | Required (id, path, format, extraction_mode) |

Extract mode is only viable when a compatible runtime host is `READY`. Before
running `extract_access.py --execute`, verify the host:

```
python scripts/access_runtime.py --smoke-test [--allow-run-as-invoker]
```

Environment expectations:

- Windows with Microsoft Access or the ACE/DAO runtime registered.
- The Python/PowerShell host bitness must match the registered Access bitness.
  A 64-bit host driving a 32-bit Access install is the most common activation
  failure; `access_runtime.py` selects a bitness-matched PowerShell host.
- `.adp` projects require a compatible legacy Access runtime (for example Access
  2003); a modern runtime is not assumed compatible.
- If the registered Access executable carries a `RunAsAdmin` AppCompat flag, use
  `--allow-run-as-invoker` so COM activation does not prompt for elevation.
- The original database is never opened; extraction runs on a hash-verified
  snapshot and refuses to overwrite an immutable session.

If no host is `READY`, do not block: export the VBA and SQL manually on a
compatible machine and proceed in export mode.

## Mandatory pre-phase Graphify context

After export/extraction and deterministic module planning, every Phase 1-6
requires a fresh Graphify context. This is an execution gate rather than a
source-evidence requirement:

- bootstrap the pinned managed runtime when it is missing;
- normalize the authorized sources into a UTF-8, binary-free corpus;
- build or incrementally refresh the graph when the corpus fingerprint changes;
- validate graph/corpus provenance and zero Access binaries ingested; and
- run and record the query designed for the requested phase.

Missing business sources remain evidence gaps, but a failed Graphify install,
invalid corpus, stale/invalid graph, pending semantic update, or missing phase
query receipt blocks Phase output until corrected.

## Precondition outcomes

`preflight.py` reports an `input_preconditions` block describing the detected
mode, which inputs are present, which recommended inputs are missing, and — for
extract mode — the runtime host status. Missing app sources produce warnings and
recommendations, never a hard failure. The package-contract checks remain the
only conditions that fail preflight.
