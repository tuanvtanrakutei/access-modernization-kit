# Access Extraction Layer

## Scope

The extraction layer accepts `.mdb`, `.accdb`, and `.adp` as first-class sources. It inventories local and linked tables, fields, indexes, relationships, QueryDefs/pass-through SQL, forms, reports, macros, VBA modules, startup properties, Access version/bitness, VBA references, broken references, conditional constants, and AutoExec presence when the runtime exposes them.

## Safety contract

- Never open the original database. `extract_access.py --execute` creates a byte-for-byte snapshot and verifies its SHA-256 before automation.
- Every extraction is isolated under `<DATABASE_ID>/<SESSION_ID>` and refuses to overwrite a non-empty session. The app-level component index selects the latest lexicographic session for each database unless a direct legacy index is present.
- Never store a literal database password in the manifest. Use `password_ref` and resolve it outside package artifacts. The extractor accepts only an environment-variable name through `--password-env`; the secret value is not placed on the command line.
- Redact passwords, user IDs, tokens, and keys from connection metadata and exported text.
- Treat linked-table and ADP server objects as boundaries. Use separately authorized SQL Server extraction for authoritative server schema/data.
- Access COM/DAO extraction is Windows-only and conditional. `.adp` may require a legacy Access runtime; a modern runtime is not assumed compatible.

## Commands

Preflight only, with no copy and no database open:

```powershell
python scripts/extract_access.py --database <PATH> --database-id <ID> --output-dir <APP>/extracted/access --dry-run
```

Authorized extraction from a disposable snapshot:

```powershell
python scripts/extract_access.py --database <PATH> --database-id <ID> --output-dir <APP>/extracted/access --execute [--session-id SESSION] [--password-env ACCESS_PASSWORD]
```

The PowerShell adapter is packaged but cannot be considered runtime-tested until executed on a compatible Access host. Preserve `BLOCKED` or `PARTIAL` status and warnings as evidence gaps.

## Runtime discovery

Before extraction, `scripts/access_runtime.py` inspects the host without opening any database. It reads the 32-bit and 64-bit registry views for `Access.Application`, ACE OLEDB, and DAO, resolves the registered Access executable and version, detects `RunAsAdmin` AppCompat flags, and selects a PowerShell host whose bitness matches the registered runtime — the most common cause of COM activation failures is a 64-bit host driving a 32-bit Access install.

```powershell
python scripts/access_runtime.py [--smoke-test] [--powershell <PATH>] [--allow-run-as-invoker] [--require-ready]
```

`extract_access.py` runs this discovery automatically, records it in the extraction `runtime` block, and drives the adapter with the matched host. An authorized `--execute` run is refused with `BLOCKED` status when no host is `READY`. If the registered executable carries a `RunAsAdmin` flag, pass `--allow-run-as-invoker` to activate it without an elevation prompt. Use `--skip-runtime-check` only to restore the pre-2.3 behavior of calling the default `powershell` host directly.
