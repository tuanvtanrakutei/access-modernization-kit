# Bug Reports

> **Template.** Copy to `{{DOCS_DIR}}/Bug_Reports/README.md`.
>
> Unlike the five numbered stages, this folder has no stage number and no closing gate. A bug is filed the moment it is found — during coding, testing, or review — not on a schedule.

Per-screen record of defects found while modernizing this screen: a legacy behavior the
current implementation does not reproduce, or a defect in the current implementation itself.
One file per screen, filed the moment the defect is found rather than batched until Stage 5.

This folder holds what `Known_Issues.md` explicitly does not: **single-screen** findings.
`Known_Issues.md` §"What Goes Where" is the boundary — if a pattern here repeats on a second
screen, promote it there instead of copying the entry.

## Why This Exists

A defect found mid-coding has nowhere obvious to go: it is not yet a review finding (Stage 5
has not run), and it is not cross-screen (so `Known_Issues.md` is the wrong home). Without a
place to file it, it either gets fixed silently with no record, or gets held in the agent's
context until Stage 5 and is sometimes lost in between. Neither is acceptable — the first
loses the evidence trail back to the legacy behavior; the second is a memory problem
disguised as a process.

## When To File

File the moment you notice, in any stage:

- **Stage 3a/3b** — the legacy evidence shows behavior the code you are about to write, or
  code already written earlier in Backfill mode, does not reproduce.
- **Stage 4a/4b** — a test reveals a defect that is not the thing the test was written to
  check.
- **Stage 5** — a finding that belongs in the coding record's history, not only in the review
  verdict, because it will matter to whoever next touches this screen.

Do not hold a finding until Stage 5 to file it as a review comment instead. Filing where it
was found keeps the discovery date and the discovering context attached to the defect.

## Agent Prompt For One Entry

```text
Please file a bug report for this screen:

- screen: {screen}
- module: {module}
- found during: Stage 3a | 3b | 4a | 4b | 5
- source: {legacy VBA file/routine, or the test/review finding that surfaced it}

Output target: {{DOCS_DIR}}/Bug_Reports/{screen}.md

Resolve project values from PROJECT_CONFIG.md first.

Workflow:
1. If the file does not exist yet for this screen, create it with the header below.
2. Assign the next sequential ID in this file — BUG-NNN for a defect, INFO-NNN for a
   clarification or decision that does not require a code change. IDs are per-screen and never
   reused, even if an entry is later closed as invalid.
3. Cite the legacy evidence with an anchor per `TRACEBACK_GATES.md` §Anchor Format, and the
   current code with `path:line`. A finding without both anchors cannot be verified later.
4. If this looks like it affects more than this screen, stop and ask whether to promote it to
   `Known_Issues.md` instead of filing it here.
5. State severity and suggested fix. Do not fix it here — this file is a record, not a patch;
   apply the fix in the stage you are in and reference the entry ID in that stage's changelog.
```

## File Naming

One file per screen: `{{DOCS_DIR}}/Bug_Reports/{screen}.md`. A screen with no findings has no
file — do not create an empty one.

## Required Structure

```markdown
# Bug Report — {screen}

> Created: YYYY-MM-DD · Source: Stage {N} · Module: `{module}`

## BUG-001 — One-line description of the defect

| Field | Detail |
|---|---|
| **Screen** | {screen} |
| **Severity** | High \| Medium \| Low |
| **Type** | Gap — backend/frontend missing legacy behavior \| Defect — current code wrong \| Regression |
| **Found during** | Stage 3a \| 3b \| 4a \| 4b \| 5 |
| **Status** | Open \| Fixed in {commit or coding-record iteration} \| Deferred \| Closed — will not fix |

### Legacy behavior

Cite the anchor. Quote the relevant VBA, query, or rule — enough that a reader does not need
to open the original file to understand the finding.

### Current behavior

Cite `path:line`. State what the code does today, in contrast to the legacy behavior above.

### Impact

Concrete consequence: what a user or caller can do because of the gap, not just that it exists.

### Suggested fix

What would close this, and where. If it was already fixed, name the commit or the coding-record
iteration instead of leaving this section as a to-do.

---

## INFO-001 — One-line description of the clarification

| Field | Detail |
|---|---|
| **Screen** | {screen} |
| **Type** | Closed — {business owner} decision YYYY-MM-DD: {one-line decision} |

### Background

What looked like a defect and turned out not to be one, and why — so the next reader does not
re-raise it.
```

## Status Lifecycle

| Status | Meaning | Who sets it |
|---|---|---|
| Open | Filed, not yet addressed | Whoever found it |
| Fixed in {ref} | Resolved; ref names the commit or coding-record iteration | Whoever fixed it |
| Deferred | Acknowledged, intentionally not fixed now | Tech lead, with a reason |
| Closed — will not fix | Decided against, with a named decision-maker and date | Business owner or tech lead |

Never delete an entry to close it. A closed entry with no reason reads, to the next person, as
an entry nobody looked at.

## Promotion To `Known_Issues.md`

Promote when a second screen shows the same pattern: a shared legacy quirk, a systemic tooling
gap, a decision that changes a rule beyond this screen. Leave the original entry here with a
note pointing at the promoted row — do not delete it, since the coding record and any commit
message may already cite its ID.

## Writing Rules

1. Cite both anchors — legacy evidence and current code. An entry with only one cannot be verified independently later.
2. One entry, one finding. Do not fold two unrelated defects into one ID because they were found together.
3. This file is a record, not a patch. Apply the fix in the stage's own artifact and its changelog; reference the entry ID there.
4. Severity is a statement about impact, not about how easy the fix is.
5. An `INFO` entry documents a decision, not a defect — do not use it to soften a real bug into something that reads as resolved.

## Related Documents

| Document | Relationship |
|---|---|
| `Known_Issues.md` | Promotion target when a finding here repeats across screens |
| `TRACEBACK_GATES.md` | Anchor format for citing legacy evidence |
| `Coding_Records/{screen}.md` | Where a fix is actually implemented and logged |
| `Code_Review/{screen}.md` | Open entries here are read at Stage 5; an unresolved High-severity one is a review finding |
