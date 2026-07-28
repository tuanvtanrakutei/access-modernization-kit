# Acquisition Adapter Decision Guide

Use this guide after the V2.2 manifest classifies the project. The shared pipeline and bundle lifecycle remain defined in `docs/architecture/`.

| Declared artifact | Adapter | Required evidence |
|---|---|---|
| MDB, ACCDB, or ADP with managed acquisition | `managed_access` | Original path, compatible Access runtime, and explicit snapshot extraction authorization |
| User-exported VBA, SQL, forms, reports, documents, screenshots, reports, or samples | `imported_sources` | One declared file, or a directory/ZIP with `import-source-manifest.yaml` |
| msaccess-vcs export | `msaccess_vcs` | `vcs-options.json` with export format `4.1.2` or `5.0.0` |
| SQL Server scripts, catalog JSON, or DACPAC | `sql_server` | UTF-8 SQL, schema-valid catalog, or DACPAC containing one `model.xml` |
| SQL Server BAK | `sql_server` reference only | Redacted external reference and optional restore receipt; the BAK is never opened or bundled |
| MDF or LDF | None | Rejected as `UNSUPPORTED_DIRECT_ATTACH` |

Plan without reading application binaries:

```text
python plugins/ak/scripts/ak.py acquire plan --manifest <APP_ROOT>/manifest.yaml
```

Run imported acquisition:

```text
python plugins/ak/scripts/ak.py acquire run --manifest <APP_ROOT>/manifest.yaml --output-root <BUNDLE_ROOT>
```

The result is an unapproved canonical bundle. Approval remains a separate `bundle approve` action.
