# Minimal synthetic app

This public-safe fixture exercises the V2.2 acquisition contract with invented data only. It
contains no Access database, live connection, customer data, A01 material, or proprietary
evidence.

The fixture declares three artifacts:

- `input/vba/DemoOrderForm.bas` — one exported VBA form module.
- `input/sql/demo_orders.sql` — one SQL Server table definition.
- `input/sql/catalog.json` — the same table represented in the SQL Server catalog contract;
  it adds no object or behavior absent from the DDL.

From the repository root, copy this directory to a throwaway location before running it, then:

```powershell
python plugins/ak/scripts/ak.py preflight --app-root <copy> --runtime generic
python plugins/ak/scripts/ak.py acquire plan --manifest <copy>/manifest.yaml
python plugins/ak/scripts/ak.py acquire run --manifest <copy>/manifest.yaml --output-root <copy>/acquired
python plugins/ak/scripts/ak.py bundle validate --bundle-dir <bundle-dir-from-acquire>
```

Expected result: acquisition and bundle validation pass. This does **not** mean the app is
ready to publish all six investigation phases. The fixture intentionally lacks enough UI,
server-boundary/dependency, workflow-output, document, and accepted-prior-phase evidence:
Phases 1, 2, 3, 4, and 6 remain `BLOCKED`; Phase 5 remains `LIMITED`.

Do not add declarations solely to make those statuses green. A valid acquisition fixture is
not a completed investigation, and current deterministic scripts do not generate or validate
the six canonical Phase documents.
