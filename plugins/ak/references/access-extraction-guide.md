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
   ExportAccessObjects "D:\Anrakutei\<APP>\input\exports\<DATABASE_ID>-<YYYY-MM-DD>"
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

## Reading the links, without deleting them

That last rule is the kit's position and it has not changed: **nothing needs to be
deleted for the analysis to be right.** A06's frontend carried 188 table objects for 35
tables, and since A39 the catalogue reconciles the two itself — it names the 153
auto-numbered duplicates, keeps the three ODBC links, keeps the one source table that
genuinely ends in digits, and reports both bounds where two paths name one table.
Cleaning the database changes none of those figures.

`tools/ListStaleLinks.bas` exists for the other case: an operator who has decided, for
their own maintenance reasons, to remove links their application no longer resolves.
That decision belongs to whoever owns the application. What the tool does is stop it
being made by hand, one object at a time, in a list of 188.

Run it inside the frontend from the Immediate window:

```
ListStaleLinks
```

It writes `stale-links-<timestamp>.txt` beside the database and **changes nothing**.
Each link is classified:

| Class | Meaning |
|---|---|
| `AUTO_NUMBERED_DUPLICATE` | safe to remove; every condition below held |
| `UNREACHABLE_DISTINCT` | a real table this database can no longer reach — reported, never deleted |
| `HELD_BACK` | matched the name rule and failed a safety condition |
| `LIVE` | resolves now |

A link is offered for deletion only when all four hold:

1. its name is `<source table name>` followed by digits — the rule Access itself
   follows when a name is taken;
2. a link named exactly `<source table name>` also exists;
3. **that base link resolves right now**;
4. no saved query names it.

Condition 3 is the one that matters. Deleting `商品マスタ3` while `商品マスタ` itself is
broken removes the last route to the table.

Two things the tool deliberately will not do. It will not treat an unequal source name
as a duplicate — SQL Server answers `dbo.商品マスタ` for a link named `商品マスタ`, and on
A06 that comparison would have removed three tables carrying 16, 43 and 68 fields. And
it will not judge by the suffix: `商品情報20121115` is a real table named for a date, and
it is reported as `UNREACHABLE_DISTINCT`, never as a duplicate.

Forms, reports and modules are **not** searched — a macro cannot read their definitions
without exporting them. Run `ExportAccessObjects` first and search the export package;
on A06 that covered 87 definitions and found none of the 153 candidates referenced.

To delete, set `DELETE_CONFIRMED = True` in the module, save, and run
`DeleteStaleLinks`. **Back the file up first** — Access has no undo for a deleted
object. On A06 the classification is 153 duplicates, 26 live, 1 unreachable-distinct,
0 held back.
