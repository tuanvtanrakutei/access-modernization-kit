# Minimal synthetic app

This directory demonstrates a public-safe manifest and source layout. All names and behavior are invented. It contains no Access database, live connection, customer data, A01 material, or proprietary evidence.

Build the deterministic component index and module plan from the repository root:

```powershell
py -3.11 scripts/build_component_index.py --app-root examples/minimal-app
py -3.11 scripts/build_module_plan.py --component-index examples/minimal-app/extracted/component-index.json --output-dir examples/minimal-app/extracted/module-plan
```
