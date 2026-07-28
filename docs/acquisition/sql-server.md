# SQL Server Evidence Acquisition

## Prerequisites

- SQL scripts are UTF-8 and contain DDL or programmable-object definitions.
- Catalog JSON matches `sql-server-catalog.schema.json`.
- A DACPAC contains exactly one `model.xml` and is treated as a read-only ZIP package.
- BAK references are external-only. Live connection and restore automation are outside standard acquisition.

## Commands

```text
python plugins/ak/scripts/ak.py acquire plan --manifest <APP_ROOT>/manifest.yaml
python plugins/ak/scripts/ak.py acquire run --manifest <APP_ROOT>/manifest.yaml --output-root <BUNDLE_ROOT>
```

## Failures

- `UNSUPPORTED_DIRECT_ATTACH`: MDF or LDF input was declared.
- `UNSUPPORTED_SQL_ARTIFACT`: the format is outside SQL, catalog JSON, DACPAC, or BAK reference.
- `DACPAC_MODEL_REQUIRED`: the package does not contain exactly one `model.xml`.
- Schema validation errors: catalog JSON does not satisfy the canonical catalog contract.

## Bundle Contribution

SQL scripts route to `code.sql_server`. Validated catalog and DACPAC objects route to database tables or objects and provide `server_object_inventory`. A BAK reference alone remains `PARTIAL`, contributes no backup path, and does not satisfy ADP readiness.
