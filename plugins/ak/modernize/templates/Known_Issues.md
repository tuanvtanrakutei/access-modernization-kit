# Known Issues, Decisions, And Cross-Screen Q&A

> **Template.** Copy to `{{DOCS_DIR}}/Known_Issues.md`.

The cross-screen log. Issues belonging to one screen live in that screen's own artifact; this file holds what spans several screens, the system as a whole, or must outlive a single change.

## What Goes Where

| Issue | Home |
|---|---|
| Legacy defect affecting one screen | `Coding_Records/{screen}.md` §Discovered during coding |
| Business rule unclear for one screen | `Business_flows/{screen}.md` §Legacy versus new system |
| Design ambiguity for one screen | `Screen_plans/{screen}.md` gap matrix |
| Review finding on one screen | `Code_Review/{screen}.md` findings |
| **Legacy defect pattern repeating across screens** | **here** |
| **Tooling or infrastructure issue affecting several modules** | **here** |
| **Decision that changes a system-wide rule** | **here** |
| **External blocker** — file share down, reference database unavailable | **here** |
| **Coverage gap raised by a gate** | **here**, as `traceability` |

If the same open item is being copied into two per-screen files, promote it here and link both files to the row.

## Issue Types

| Type | Meaning |
|---|---|
| `legacy-bug` | Defect in the legacy behavior. Decision needed: preserve or fix |
| `tech-stack` | Framework, database, library, tooling, build, or test-infrastructure issue |
| `business` | Business-rule ambiguity or a decision needed at system level |
| `data` | Reference data quality, encoding, missing seed, or a gap in the table mapping |
| `environment` | Reference database unreachable, file share down, CI broken, secrets missing |
| `process` | Workflow, documentation, or policy issue affecting how screens get built |
| `traceability` | Coverage gap surfaced by gate G1, G2, or G3. Carries a severity suffix — see below |

## Status Lifecycle

```text
open  →  in_progress  →  resolved
                      →  deferred
                      →  wont_fix
```

- `open` — identified, not yet investigated
- `in_progress` — owned, work underway
- `resolved` — closed with a recorded outcome
- `deferred` — out of current scope; will reopen on a stated trigger
- `wont_fix` — deliberate decision not to act, with the reason recorded

### Severity Suffix For `traceability` Rows

Rows of type `traceability` carry severity in the status cell: `open (HIGH)`, `open (MEDIUM)`, or `open (LOW)`. The gate that found it assigns the severity per `TRACEBACK_GATES.md`; the Stage 5 reviewer may change it with a recorded reason.

A HIGH row should be resolved before the pipeline run that produced it finishes, because HIGH blocks and prompts the user immediately. MEDIUM and LOW are confirmed at Stage 5.

## Active Log

Newest first. Never delete a row — the audit trail is the point of the file.

| # | Date | Type | Title | Affects | Status | Owner | Decision / Next step |
|---|---|---|---|---|---|---|---|
| 1 | YYYY-MM-DD | | | | open | — | |

`Date` is the date the event actually happened — when the gate fired, when the defect was found, when the decision was taken. It is **not** the date someone last edited the file. A row recording a May finding keeps its May date forever, even when updated in July.

When closing a row, set the status and add `Closed: YYYY-MM-DD` with the change or review that resolved it in `Decision / Next step`.

## Row Format

Fill every column. Write `—` for one that genuinely does not apply.

For a row needing more than one line of explanation, add a subsection below keyed to the row number:

```markdown
### Issue #N — Title
- **Reported by**:
- **Reproduce**:
- **Evidence**: file and line, screenshot path, or command output
- **Discussion**:
- **Decision**: (when resolved)
- **Closed**: YYYY-MM-DD
```

Use subsections sparingly — when the table row would otherwise become unreadable.

## When Rows Are Written

Tied to pipeline events, not to whim.

| Trigger | What happens here |
|---|---|
| Gate G1, G2, or G3 finds a coverage gap | New `traceability` row with a severity suffix |
| Coding stage end | New rows for blocking questions, and promotion of cross-screen findings |
| Review verdict | New rows for systemic follow-ups; closure of rows this change resolved |
| Pipeline abort from a cross-screen cause | New `environment`, `data`, or `tech-stack` row |
| User assigns an owner | Status `open` → `in_progress`, owner filled |
| User defers or declines | Status → `deferred` or `wont_fix`, with a reason |

Forbidden: adding a row that describes a single-screen issue; closing a row without naming what resolved it; two agents writing this file at once — the parent agent queues those writes.

## How Agents Use This File

At pre-flight the agent greps this file for the target screen and its module, lists every `open` or `in_progress` row, and reports them before Stage 1. Rows of type `traceability` get particular attention because they change what the current run's gates should look for.

This is what stops the same legacy defect being rediscovered and re-argued on every screen that touches it.

## Archive Policy

The log grows. When it passes roughly 150 rows or becomes slow to search:

1. Move rows that are `resolved` or `wont_fix` with a close date older than 90 days into `Known_Issues_Archive.md`.
2. **Keep the original row numbers.** Cross-references in old changes and coding records must still resolve.
3. Never archive `open`, `in_progress`, or `deferred` rows regardless of age. A deferred row is tracking work that has not happened, so it belongs in the active log until it does.
4. Archive in its own change, not bundled with screen work, and note the row range moved.

## Related Documents

| Document | Relationship |
|---|---|
| `MASTER_WORKFLOW.md` | Reads this log at pre-flight; defines the gates that write to it |
| `TRACEBACK_GATES.md` | Severity semantics for `traceability` rows |
| `Screens_Registry.md` | Source of the screen and module identifiers used in rows |
| `Coding_Records/{screen}.md`, `Code_Review/{screen}.md` | Promote cross-screen findings here |
