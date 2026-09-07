# Acquisition Modes: Where Sources Come From

There is one workflow, not two. Declare every source you have, ask which phases
that evidence reaches, add what is missing, then run. The mode is a description
of what you declared, not a decision you make.

## The mode is an observation

`project.acquisition_mode` records what the declared artifacts are:

| Mode | Meaning |
|---|---|
| `extract` | Sources come from Access binaries (`.mdb`, `.accdb`, `.adp`) |
| `export` | Sources come from already-exported source trees |
| `mixed` | Both |

`init` writes it. Acquisition recomputes it and uses the observed value: a stale
label is corrected and reported, never a reason to refuse work. Documents,
screenshots and samples ride along with any mode and do not change it.

What *does* stop a run is a declaration that cannot be honoured either way. The
router keys on `kind` before `acquisition`, so `kind: access_database` always
routes to the managed adapter; declaring `acquisition: imported` on one is
reported as `ACQUISITION_IGNORED` and refused, rather than silently ignored.

## The two source paths are complementary, not alternatives

They produce different evidence, and the phase gates need both kinds:

| Capability | extract | export |
|---|:--:|:--:|
| `access_schema_inventory` | yes | no |
| `field_inventory` | yes | no |
| `key_index_inventory` | yes | no |
| `access_object_inventory` | yes | no |
| `boundary_inventory` | yes | if declared |
| `ui_object_inventory` | names | names **and definition text** |
| `vba_query_inventory` | query SQL | query SQL **and module source** |
| `document_inventory` | no | yes |

Consequences, from `contracts/phase_readiness.py`:

- **Only extract reaches Phase 1.** It requires `field_inventory`,
  `key_index_inventory` and `boundary_inventory` together. No export declares them.
- **Only an import reaches Phase 5 fully.** It requires `document_inventory`.
- Phase 2 and Phase 3 gates open from either, but the gate opening is not the same
  as having the evidence those phases analyse - see below.

## A gate opening is not the same as evidence

The Phase 2 and Phase 3 gates ask only for an inventory. Extraction through the
DAO tier yields object *names*, so both gates open - while the definitions those
phases actually read are absent:

| Phase | Gate from extract alone | What is still missing |
|---|:--:|---|
| 1 | READY | nothing |
| 2 | READY | form and report controls, record sources, event handlers |
| 3 | READY | VBA module source (query SQL is present in full) |

Object definition text comes from exactly one of two places: the Access host tier
(`runtime.skip_object_export: false`), or an imported export package. Choose
either; declaring both is normal and `_flag_export_drift` reports it when an
export was produced from a different copy of the database than the one read.

## Administrator rights: only one tier can need them

Extraction has two tiers, and only the second involves Access itself:

| | Tier 1 - DAO | Tier 2 - Access host |
|---|---|---|
| COM object | `DAO.DBEngine.36`, in process | `Access.Application`, out of process |
| Elevation | never needed | fails `0x800702E4` if the executable carries RUNASADMIN |
| Startup code | not loaded | AutoExec and startup VBA run |
| Yields | schema, indexes, relations, query SQL, object names | object definition text, VBA references |
| Disabled by | - | `runtime.skip_object_export: true` |

`runtime.skip_object_export: true` therefore means: no host, no AutoExec, no modal
dialog, no administrator requirement, unattended. Preflight distinguishes
`needs.access` from `needs.access_host` and only mentions elevation when a host
will actually start.

`allow_run_as_invoker` cannot substitute for elevation. It sets `__COMPAT_LAYER`
on the PowerShell host, and the Access COM server is launched by the service,
which does not inherit it. The remedies that work are removing RUNASADMIN from
the executable's `AppCompatFlags\Layers` value, or running from an elevated
terminal.

## Export packages need a producer manifest

The imported adapter refuses a bare directory: without a declaration of what the
package should contain it cannot tell a complete export from a truncated one.

- no `import-source-manifest.yaml` - `IMPORT_MANIFEST_REQUIRED`
- a file the manifest does not declare - `UNDECLARED_PACKAGE_MEMBER`
- a file it cannot classify - the build command fails rather than labelling it

`scripts/build_import_manifest.py` writes that manifest, classifying by containing
directory to match the layout `tools/ExportAccessObjects.bas` and
`scripts/extract_access.ps1` produce: `forms/`, `reports/`, `macros/`, `vba/`,
`queries/`, `schema/`.

## The workflow

```
ak.py init --root <parent> --app-id <ID> --name-en "<name>" --source <staging>
# resolve role: unknown, and decide skip_object_export per database

ak.py acquire plan --manifest <path> --require-phases 1,2,3
# exits 2 while any requested phase is out of reach; nothing has been opened yet

ak.py acquire run --manifest <path> --output-root <dir> \
    --authorize access_snapshot_extract --require-phases 1,2,3
# fails if the acquired evidence leaves a required phase blocked
```

`acquire plan` reports phase readiness twice: `guaranteed`, from what the declared
artifacts must yield, and `if_content_present`, from what they yield if the sources
hold the objects they are expected to. A capability listed under
`content_dependent` names its condition, so a thin result is a stated risk rather
than a surprise.
