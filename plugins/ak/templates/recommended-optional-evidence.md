# {{APP_ID}} — Recommended optional evidence

Status: **optional, non-blocking.** The six-phase investigation runs from the
sources already provided. Each item below strengthens a specific phase; anything
not supplied is recorded as an `Assumption` / `Open Question` in the Question
List — never invented. Emit this list during the assess/report step and mirror
open items into `{{APP_ID}}_QuestionList.md`.

## Already available (do not re-supply)

- Form / report / macro / module definitions and query SQL (from export or extraction)
- Table schema (`schema/tables.txt`; system/temp/ImportErrors tables already excluded)

## High priority

| Item | Place in | Strengthens | Status |
|---|---|---|---|
| Sample INPUT files the app imports (`.txt/.csv/.dat` fed to import/append routines) | `sources/samples/` | Phase 4 workflow + Boundary (inbound file interfaces) | {{STATUS}} |
| Sample OUTPUT files (Excel/CSV exports; printed PDF reports) | `sources/reports/` or `sources/samples/` | Phase 4 real output + Boundary (outbound); definitions give layout only | {{STATUS}} |
| Business documents (operational-function list, manual, business-flow / architecture PDF, XLSX) | `shared-docs/` or `sources/documents/` | Phase 5 Document Integration | {{STATUS}} |

## Medium priority

| Item | Place in | Strengthens | Status |
|---|---|---|---|
| Screenshots of key screens | `sources/screenshots/` | Phase 2 real UI evidence (complements export-derived wireframes) | {{STATUS}} |
| App-specific documents (screen list, business rules) | `sources/documents/` | Phase 5 + business context | {{STATUS}} |

## Boundary open questions

- For every LINKED table and every external path referenced in query SQL (e.g. `IN '<path>'`), record the link/interface target (another database, a SQL Server, or a NAS/mount path). Each is a boundary/integration point for the Boundary Map.

## Supply notes

- Keep original formats (`.csv/.txt/.dat` as-is; `.xls → .xlsx` only if needed). Data files may be Shift-JIS / CP932 — leave as-is; encoding is handled at analysis time.
- Provide small representative samples (a few rows / one period), never full customer data. No credentials, DSNs, or sensitive records.
- A one-line note per file ("input/output of which function") speeds Phase 4 mapping.
