# Managed Access Acquisition

## Prerequisites

- A V2.2 manifest declares each MDB, ACCDB, or ADP as `access_database` with `acquisition: managed`.
- The source path is local and read-only from the operator's perspective.
- A compatible Access/DAO runtime is available.
- The operator explicitly grants `access_snapshot_extract`.

## Commands

```text
python plugins/ak/scripts/ak.py acquire plan --manifest <APP_ROOT>/manifest.yaml
python plugins/ak/scripts/ak.py acquire run --manifest <APP_ROOT>/manifest.yaml --output-root <BUNDLE_ROOT> --authorize access_snapshot_extract
```

## Safety Boundary

`probe` and `plan` do not open Access. `run` delegates to `extract_access.py --execute`, which creates and hash-verifies a disposable snapshot before COM automation. The adapter never opens or modifies the original database directly. Raw Access binaries and snapshot paths never enter the canonical bundle.

## Failures

- `AUTHORIZATION_REQUIRED`: snapshot extraction was not explicitly authorized.
- `EXTRACTION_RESULT_MISSING`: the delegated extractor did not produce `access-extraction.json`.
- `PARTIAL`: protected objects, unavailable linked sources, or other extractor warnings remain visible.

## Bundle Contribution

Extracted VBA, Access SQL, forms, reports, macros, linked-table metadata, database metadata, failures, and source hashes are normalized into `bundle-contribution.schema.json`.
