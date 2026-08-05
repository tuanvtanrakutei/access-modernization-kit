# Known Issues Archive

> **Template.** Copy to `{{DOCS_DIR}}/Known_Issues_Archive.md`. Starts empty; `Known_Issues.md`'s Archive Policy moves rows here.

Closed rows moved out of `Known_Issues.md` once they age past the archive threshold. This
file exists so the active log stays fast to search without losing history a coding record or
review might still cite.

## What Belongs Here

Only rows that were `resolved` or `wont_fix` in `Known_Issues.md`, with a close date older
than the threshold stated there. Nothing is written directly into this file — it only
receives rows moved from the active log, following `Known_Issues.md`'s own Archive Policy.

**Never move**: `open`, `in_progress`, or `deferred` rows, regardless of age. A `deferred` row
is tracking work that has not happened yet; archiving it would hide open work as if it were
finished.

## Row Numbers Are Permanent

A row keeps the number it had in the active log. Do not renumber, and do not reuse a number
once it has appeared here or in `Known_Issues.md` — coding records, review findings, and code
comments cite issues by number (`Known_Issues.md #12`), and a renumbered or reused row breaks
every citation silently. `validate-docs` checks that a number cited in code resolves to a row
in either file; it cannot check whether the row it finds is the one the citation meant.

## Table

| # | Date | Type | Title | Affects | Status | Owner | Decision / Next step |
|---|---|---|---|---|---|---|---|

Rows appended here keep the exact ten-column shape used in `Known_Issues.md`. A row with the
wrong column count renders silently wrong rather than raising an error — `validate-docs`
checks for this; do not skip it after a bulk move.

## Related Documents

| Document | Relationship |
|---|---|
| `Known_Issues.md` | The active log; states the Archive Policy that populates this file |
| `TRACEBACK_GATES.md` | Severity semantics for `traceability` rows, unchanged by archiving |
