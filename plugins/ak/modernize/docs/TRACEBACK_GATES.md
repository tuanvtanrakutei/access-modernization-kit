# Traceback Gates

> **Layer 1 document.** Detailed specification of the three coverage gates referenced from `MASTER_WORKFLOW.md`. Project values appear as `{{PLACEHOLDER}}` and resolve from `PROJECT_CONFIG.md`.

Sequential stages drift silently. Stage 1 may never open a sub-form's code. Stage 2 may omit a business rule. Stage 3 may skip a planned endpoint or a screen control. Discovering any of these at review costs three to five stages of rework.

Traceback Gates catch **coverage** gaps between stages, while the context is still fresh.

## Contents

- [The Three Gates](#the-three-gates)
- [Severity Ladder](#severity-ladder)
  - [Classification Examples](#classification-examples)
- [Anchor Format](#anchor-format)
  - [When `Evidence.json` is present — cite the `evidenceItem`](#when-evidencejson-is-present-cite-the-evidenceitem)
  - [When it is not — use these hand-built forms](#when-it-is-not-use-these-hand-built-forms)
- [HIGH Confirmation Flow](#high-confirmation-flow)
  - [The `examine` Sub-Flow](#the-examine-sub-flow)
- [Mode-Aware Behavior](#mode-aware-behavior)
- [Upgrade And Downgrade At Review](#upgrade-and-downgrade-at-review)
- [Cross-Gate Visibility](#cross-gate-visibility)
- [What Gates Do Not Do](#what-gates-do-not-do)
- [Output Format](#output-format)
- [Related Documents](#related-documents)

## The Three Gates

| Gate | Position | What the agent checks |
|---|---|---|
| **G1 — Evidence Coverage** | End of Stage 1 | Every evidence object applicable to this screen — per the variant row in `LEGACY_EVIDENCE.md` §1 and the object table in §2 — is referenced in the business flow's evidence section with an anchor where one applies |
| **G2 — Rule Coverage** | End of Stage 2 | Every business rule in the business flow has a mapping row in the screen plan. Every open decision is acknowledged in the gap matrix. Both the backend contract and the frontend contract exist |
| **G3 — Implementation Coverage** | End of Stage 3b | **API sub-check:** every endpoint in the screen plan's backend contract has code. **UI sub-check:** every row in the screen plan's control inventory has a target component, and every planned interaction has a handler |

G3 has two sub-checks because the pipeline now covers both tracks. Report them separately — a screen can be fully covered on API and badly covered on UI, and a single combined number hides that.

## Severity Ladder

| Severity | Behavior |
|---|---|
| **HIGH** | Block immediately. Print a proposal and wait for `examine` / `defer` / `cancel` |
| **MEDIUM** | Continue. File a `Known_Issues.md` row with `status: open (MEDIUM)`. The Stage 5 reviewer confirms it |
| **LOW** | Continue. File a row with `status: open (LOW)`. The reviewer resolves, defers, or marks will-not-fix |

**An `evidenceItem` with `status: AMBIGUOUS` (see Anchor Format) sets a floor of MEDIUM** on
whatever finding cites it, regardless of the table below. The phase analysis already flagged
the conflict; re-deciding it as LOW discards that signal rather than acting on it.

If the enriched tier's `coverage.json` is present for this project, a non-zero `skipped`,
`failed`, or `unsupported` count for an object type this screen depends on is a **G1 finding
with no judgement required** — classify by what the missing object would have been (a form,
a report, a table) using the table below.

### Classification Examples

Anchors for judgment. **When in doubt, classify one level higher** — a reviewer downgrading is cheaper than a reviewer never seeing the issue.

| Gate | HIGH | MEDIUM | LOW |
|---|---|---|---|
| **G1** | The screen's main form or report export was never opened. The primary legacy output sample was never compared. In a split design, the data file was never examined. For `accdb`, data macros on a written table were never inspected | A sub-form, helper module, or secondary output file was not opened. A sub-dialog screenshot was not compared. A QueryDef used by the form was not read | An optional variant of an output sample was not compared when the main one was. A shared utility module is referenced by other screens but not clearly tied to this one |
| **G2** | A rule describing a calculation, total, lock, or destructive side effect has no mapping row. The frontend contract is missing entirely. The control inventory is absent | A rule describing a non-destructive side effect (refresh, redirect, focus) is unmapped. An accepted difference is not acknowledged in the gap matrix | An open business decision is unmapped because it is still open rather than forgotten. An out-of-slice nice-to-have is unmapped |
| **G3 API** | A planned endpoint has no route registered. A planned write endpoint (create, update, delete) is entirely absent | An optional endpoint was deferred with no deferral note in the screen plan. A serializer field for a non-critical column is missing | An endpoint appears in narrative prose but not in the contract table, so it is unclear whether it was ever in scope |
| **G3 UI** | A control that accepts input or triggers an action has no component. A planned validation is absent on both client and server. The screen's primary action (search, register, print, export) has no handler | A read-only display control is missing. A planned empty or error state is not implemented. Keyboard behavior recorded as preserved is not implemented | A cosmetic control (decorative label, spacer) is missing. A tooltip or help text is absent |

The agent classifies per finding. The Stage 5 reviewer may adjust with a recorded reason.

## Anchor Format

Anchors make findings verifiable by grep rather than by memory. Which form to use depends on
whether the enriched Stage 0 tier (`Evidence.json` from the six-phase analysis) is present for
this project — see `LEGACY_EVIDENCE.md` §6.

### When `Evidence.json` is present — cite the `evidenceItem`

Cite the item's `id` from the evidence register, not a hand-built path anchor. Its fields are a
**hash-verified** anchor, stronger than anything constructed by hand:

| Field | Gives |
|---|---|
| `source_path`, `source_location` | where in the source the statement comes from |
| `source_sha256` | proof the cited source has not changed since the item was recorded |
| `status` | `EXTRACTED` (read directly), `INFERRED` (reasoned from adjacent evidence), or `AMBIGUOUS` (sources conflict or evidence is thin) |
| `source_language` | `EN` / `JA` / `VI`, so a reviewer knows what encoding or translation step applies |
| `attribution` | who said it and when. `ak`'s `schemas/evidence.schema.json` requires it for an `INTERVIEW` item and enforces that with an `allOf`, so an answer in the register always names a person and a date; `question_id` names the `Q-` it closes. This is what a reviewer follows instead of a line number |

**`status: AMBIGUOUS` promotes a finding automatically** — fold it into the Severity Ladder
below as at least MEDIUM regardless of what the finding would otherwise classify as. The phase
analysis already flagged uncertainty; downgrading it back to LOW would be discarding a signal
the analysis worked to produce. `INFERRED` does not auto-promote, but say so in the finding: a
reviewer weighs an inferred statement differently than an extracted one.

A citation reads as `evidenceItem <id>` in a finding, and the reviewer follows `source_path` /
`source_location` to read the original if they need more than the statement.

### When it is not — use these hand-built forms

This is also what to use for the **raw supplement** — report output samples and screenshots —
which the phase documents reference but do not embed, even on a project with `Evidence.json`.

| Evidence type | Format | Example |
|---|---|---|
| Exported VBA (form, report, module, class) | `path::Routine():start-end` | `{{EVIDENCE_CODE_DIR}}/Form_OrderInquiry.txt::cmdSearch_Click():45-67` |
| Exported VBA, whole file | `path::*` | `{{EVIDENCE_CODE_DIR}}/mUtils.txt::*` |
| Form or report property (not code) | `path::property:PropertyName` | `Form_OrderInquiry.txt::property:RecordSource` |
| QueryDef | `path::query:QueryName` | `queries.txt::query:qryOrderByStore` |
| Stored procedure, view, function | `path::object:ObjectName` | `{{LEGACY_DB_SCRIPT}}::object:usp_GetOrderTotals` |
| Table definition or data macro | `path::table:TableName` | `schema_dump.txt::table:tblOrderHeader` |
| Legacy output sample, paginated | `path page N` | `{{EVIDENCE_OUTPUT_DIR}}/order_report.pdf page 1` |
| Screenshot, region matters | `path :: region description` | `{{EVIDENCE_UI_DIR}}/order_inquiry.png :: top toolbar` |
| Screenshot, whole image | `path` | `{{EVIDENCE_UI_DIR}}/order_inquiry.png` |
| Recorded interview answer, closing a numbered question | `path::Q-NNN` | `{{EVIDENCE_INTERVIEW_DIR}}/2026-09-07-operations.md::Q-19` |
| Recorded interview answer, no question id | `path::person, YYYY-MM-DD` | `{{EVIDENCE_INTERVIEW_DIR}}/notes.md::Horiuchi, 2026-09-07` |
| Business document, paginated | `path page N` | `{{EVIDENCE_DOCUMENT_DIR}}/operation_manual.pdf page 12` |
| Business document, a named section | `path::section:Name` | `{{EVIDENCE_DOCUMENT_DIR}}/data_dictionary.xlsx::section:商品マスタ` |
| Business flow section | `BF §N.M` | `BF §6.1` |
| Screen plan section or row | `SP §N` / `SP §N row M` | `SP §4.2 row 7` |
| Backend or frontend code | `path:line` | `{{BACKEND_ROOT}}/purchase/views/inquiry.py:23` |

`::` separates a file from a sub-anchor. A bare `:` separates a file from a line number, following the convention editors understand.

**An interview has to be written down to be citable, and that is the point rather than a
limitation.** `ak`'s rule EC-01 makes `DOCUMENT` and `INTERVIEW` the only classes that can
carry a claim about meaning, usage or intent - no volume of schema, code or definition text
substitutes - so these are the anchors the most consequential claims in a business flow rest
on. An answer that exists only in somebody's memory has no anchor, cannot be checked at G1,
and reads identically to a guess. Record it in `{{EVIDENCE_INTERVIEW_DIR}}` with the person
and the date, then cite the file.

## HIGH Confirmation Flow

On a HIGH finding the agent prints plain text and waits:

```text
Gate G{N} finding HIGH for screen {screen}:

  Sub-check: {evidence | rule | api | ui}
  Item:      {file, rule, endpoint, or control name}
  Anchor:    {per the anchor format above}
  Risk:      {one sentence on what may be missed}

Decision required before continuing:
  examine  → I do the work now, update the upstream artifact, then continue.
  defer    → I record it as MEDIUM with a reason and continue. The reviewer must confirm.
  cancel   → Abort. No registry or issue-log write for this gate.
```

Batch multiple HIGH findings at the same gate into one prompt; the user may answer per item, for example `1=examine, 2=defer`.

In a multi-screen batch, subagents never prompt directly — they report to the parent, which consolidates and prompts once. See `MASTER_WORKFLOW.md` §Multi-Screen Batch.

### The `examine` Sub-Flow

`examine` does **not** restart the stage. It performs a targeted repair:

1. Open the specific item named in the finding.
2. Update the upstream artifact — business flow evidence section, screen plan mapping or control inventory, or the code — using the anchor format.
3. Re-run only the failing sub-check for that item. New findings surfaced by the repair are filed separately and prompted on the next iteration.
4. When the item is clear, mark any provisional issue row `resolved` with a close date and continue.

Record in the stage report: `examine completed for finding #N — {one line on what was added}`.

If three rounds of `examine` do not resolve the finding, escalate; only `defer` and `cancel` remain.

## Mode-Aware Behavior

`MASTER_WORKFLOW.md` resolves three modes. Gates behave differently under each.

| Mode | Gate behavior |
|---|---|
| **Greenfield** | Full check, normal threshold. Most HIGH findings appear here because no prior pass examined the evidence |
| **Backfill** | Full check, HIGH threshold calibrated higher. The relevant G3 sub-check is usually a no-op because the code already exists — G3 reporting zero findings for that track is expected, not suspicious. G1 and G2 produce the value in this mode by catching documentation gaps against shipped code |
| **Refresh** | Fast-pass on the diff since the artifact's freshness header date: evidence files modified after it, rules added since, endpoints and components added since. If the freshness header is missing, fall back to a full check |

G3 respects each track's own mode. With `be_mode: Backfill, fe_mode: Greenfield`, the API sub-check fast-passes while the UI sub-check runs a full check.

## Upgrade And Downgrade At Review

The Stage 5 reviewer may change a `traceability` row's severity.

| Change | Effect |
|---|---|
| HIGH → MEDIUM or LOW | Update the status suffix. No rerun. Record the reason |
| MEDIUM → LOW | Same, note-only |
| LOW → MEDIUM | Same, note-only |
| MEDIUM or LOW → HIGH | Treated as a Stage 5 blocker under the loop rule. The pipeline returns to the appropriate coding stage. Registry track status is not reset to `blocked` for this; it holds whatever the coding stage reported until the loop completes |

Upgrades are rare and require an explicit recorded reason.

## Cross-Gate Visibility

Every gate writes to `Known_Issues.md` with `type: traceability`. Later gates read those rows during their own pre-check, which the pre-flight issue-log grep already covers.

- G2 reads G1 findings. If G1 deferred a sub-form as MEDIUM, G2 still attempts to map rules that file might hold — and upgrades to HIGH if a calculation rule turns up inside.
- G3 reads G1 and G2 findings to build a cumulative picture across both tracks.
- The reviewer reads all of them; Stage 5 is the canonical confirmation point.

A file missed at G1 therefore resurfaces at G2 as an unmapped-rule risk and at review as an implementation-risk question. It cannot quietly disappear.

## What Gates Do Not Do

- Gates check **coverage**, never correctness. "Does the endpoint exist?" — not "is its output right?" Correctness belongs to Stage 4 tests and the Stage 5 parity review.
- Only HIGH blocks. MEDIUM and LOW never stop the pipeline.
- Gates do not replace review. They move detection of one subset — coverage — earlier. The reviewer still performs the full correctness pass, plus an independent coverage re-check so a gate omission is caught.

## Output Format

Each gate appends a short report to the stage summary:

```text
Stage 3b complete.
  - Artifact: Coding_Records/{screen}.md §Frontend
  - Gate G3 (Implementation Coverage)
    API: 0 HIGH, 1 MEDIUM, 0 LOW
      MEDIUM #1: export endpoint deferred, no deferral note in screen plan → issue row added
    UI:  1 HIGH, 2 MEDIUM, 0 LOW
      HIGH  #1: "print preview" button has no handler → awaiting decision
      MEDIUM #2: empty-result state not implemented → issue row added
      MEDIUM #3: keyboard Enter-to-next-field recorded as preserved, not implemented → issue row added
  - Next: awaiting decision on HIGH #1 before Stage 4a
```

## Related Documents

- `MASTER_WORKFLOW.md` — the pipeline these gates sit inside
- `LEGACY_EVIDENCE.md` — defines what evidence is applicable, which is what G1 measures against
- `Known_Issues.md` — where findings are filed
- `Screen_plans/README.md` — the backend contract and control inventory that G2 and G3 read
- `Code_Review/README.md` — where the reviewer confirms findings and re-checks coverage independently
