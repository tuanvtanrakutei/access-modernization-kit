---
name: review-screen
description: "Review one screen against every upstream artifact and record a verdict (Stage 5). Reviews whatever upstream artifacts exist and says what's missing, rather than refusing outright. Trigger when the user explicitly wants a review or a verdict for one screen. Examples: \"/ak:review-screen OrderEntry\", \"review screen X against its artifacts\", \"give a verdict for screen Y\"."
---

# Review One Screen

Run **Stage 5** for the screen named in the request, following `Code_Review/README.md`.
`TRACEBACK_GATES.md` governs how a gate finding is classified and whether it may be upgraded
or downgraded here.

## Read everything upstream first, in one batch

If no screen was named in the request, stop and ask which screen before reading anything —
do not guess a screen from recent conversation context.

`Business_flows/{screen}.md`, `Screen_plans/{screen}.md`, `Coding_Records/{screen}.md`,
`Test_Instruction/{screen}.md`, the code files the coding record cites, every traceability row
for the screen, and the open `Known_Issues.md` rows for the screen and module. These reads are
independent — issue them together.

If any of the first four is missing, say which and review only what exists. A review that
silently covers less than it appears to is the failure this stage exists to prevent.

## Verdict

Write `Code_Review/{screen}.md` with findings and one verdict. A blocker sends the screen back
to Stage 3a; a business-rule ambiguity sends it back to Stage 1 with the business owner, not
back to coding.

Set `status_be` / `status_fe` to `verified` **only** when this stage approves. `implemented`
means code exists; `verified` means this review passed. Conflating them is how a project comes
to believe it has verified work it has only written.

## Checks that catch what a reading pass misses

- **A decorator being present proves nothing if the function it calls returns immediately.**
  Open the function.
- **A test being present proves nothing if a fixture patches out the thing under test.** An
  autouse fixture that mocks the check makes every test pass regardless.
- **A "latest row" query needs a total order.** Ordering on a timestamp alone ties, and the
  tie-break is arbitrary — a real defect found this way returned the wrong import batch.
- **A test that restates the query it verifies cannot fail when production is wrong.** Both
  sides carry the same fault.
- **A resolved issue row citing a file that no longer exists** is stale documentation; run the
  `validate-docs` skill rather than judging by eye.

Report findings ranked most severe first, with the failing scenario for each — concrete inputs
or state leading to the wrong output. A finding without one is a guess.
