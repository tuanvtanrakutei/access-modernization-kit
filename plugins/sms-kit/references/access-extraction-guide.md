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

`extract_access.py` runs this discovery automatically, records it in the extraction `runtime` block, and drives the adapter with the matched host. An authorized `--execute` run is refused with `BLOCKED` status **before any snapshot is copied** when the runtime cannot be activated (for example a `RunAsAdmin` executable that requires elevation). If the registered executable carries a `RunAsAdmin` flag, run the command from an elevated (Administrator) terminal, or pass `--allow-run-as-invoker` to activate it without an elevation prompt. Use `--skip-runtime-check` only to restore the pre-2.3 behavior of calling the default `powershell` host directly.

## Manual export from inside Access (recommended default)

When the runtime extractor cannot run — no Access on the host, activation blocked by elevation (`RunAsAdmin`), a split database whose startup code fails, or a non-Windows environment holding only a source dump — export from **inside** Access with `tools/ExportAccessObjects.bas`. This needs no external COM automation and no administrator elevation, because Access itself performs the export.

### Steps

1. **Open the database in Microsoft Access.** If the database has startup code (an `AutoExec` macro) that errors — common for a split front-end that relinks its back-end by a relative path — **hold `Shift` while opening** to bypass startup and avoid the error dialog.
2. **Open the Visual Basic editor with `Alt+F11`.** This is a *separate* window titled "Microsoft Visual Basic".
3. **Import the module in that editor:** menu **File → Import File…** (`Ctrl+M`) and choose `tools/ExportAccessObjects.bas`. Do **not** use the Access application's *File → Get External Data → Import* — that dialog only lists database files (`*.mdb`), not `*.bas`. (Alternative: **Insert → Module**, then paste the whole `.bas` file.)
4. **Run it from the Immediate window (`Ctrl+G`),** replacing the path with a per-database folder under the app `sources`:

   ```text
   ExportAccessObjects "D:\Anrakutei\<APP>\sources\<DATABASE_ID>"
   ```

5. For a **split database, export each `.mdb` separately** (Access opens one database at a time): run the exporter once per file into its own folder, e.g. `sources\<APP>_FRONTEND` and `sources\<APP>_DATA`.

### Output

Under the folder you pass:

- `forms/ reports/ macros/ vba/` — one `.txt` per object via `SaveAsText`
- `queries/` — one `.sql` per query (`QueryDef.SQL`)
- `schema/tables.txt` — every table with its LINKED/LOCAL flag and fields
- `export-manifest.txt` — object counts and the list of any **skipped** objects

Every object is exported independently: a failing object is recorded under `skipped=` and the run continues. Filenames keep the original (Japanese) object names, stripping only characters illegal in Windows filenames, and add a numeric suffix only on a real collision — nothing is lost to overwrite. **All output is written as UTF-8**; `SaveAsText` produces the system codepage (Shift-JIS on Japanese Windows) and the exporter transcodes it so every file is one consistent encoding.

### Common issues

- **"Expected variable or procedure, not module"** when calling the Sub: an older copy named the module the same as the Sub. Re-import the current `.bas` (module is `modExportAccess`, Sub is `ExportAccessObjects`), or rename the module via the Properties window (`F4` → `(Name)`).
- **"missing or broken reference" / compile error** (for example `MSBCODE.OCX`): click **OK** on the warning and run again; if a compile error persists, open **Tools → References…**, untick the entry marked `MISSING:`, then run. Record the missing dependency as an investigation finding — it does not block exporting object definitions.
- **Mojibake in a terminal** does not mean the file is wrong: the files are UTF-8. Verify by opening in an editor set to UTF-8, or by decoding programmatically, not by a console that cannot render CJK.

The result is export-mode input. Run `scripts/preflight.py` afterward to confirm the detected mode and coverage. Do **not** delete "junk" tables (for example Access's auto-generated `*_ImportErrors` / `*インポート エラー` tables) from the live database to clean the model — filter them during analysis instead; deleting objects in place risks removing real objects.
