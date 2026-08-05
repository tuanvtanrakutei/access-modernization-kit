# Final Acceptance

> **Template.** Copy to `{{DOCS_DIR}}/Final_Acceptance/README.md`.
>
> **For end-to-end work use `MASTER_WORKFLOW.md`, not the per-stage prompt below.** Final Acceptance is **Stage 6**. It runs only after Stage 5 returns `approved` or `approved with follow-ups`.

Stage 6 artifact. One file per screen recording the acceptance decision.

## What Stage 6 Is, And Is Not

**It is** a decision gate. The agent reads the full artifact set as a working product manager and technical lead, weighs business fit against implementation risk, and produces a concrete recommendation. The human user remains the final approver.

**It is not** another technical review pass. Stage 5 already checked rule compliance, contract match, and test evidence. Repeating that here wastes the reviewer's attention and produces two verdicts that will eventually disagree.

**It is not merge.** Acceptance means the screen is ready to merge. Who merges, when, and under what branch policy stays outside this pipeline.

## Why A Separate Stage

Stage 5 answers "is this correct?" Stage 6 answers "do we take it?" Those are different questions with different owners, and collapsing them produces a reviewer who either rubber-stamps business risk or blocks a technically sound change over a business preference.

The separation also gives the business owner one artifact to read per screen instead of a code review they were never the audience for.

## When To Run

Only after all upstream artifacts exist and Stage 5 has approved:

| Artifact | Required state |
|---|---|
| `Business_flows/{screen}.md` | Exists |
| `Screen_plans/{screen}.md` | Exists, both contracts present |
| `Coding_Records/{screen}.md` | Exists for the tracks under acceptance |
| `Test_Instruction/{screen}.md` | Exists, results recorded |
| `Code_Review/{screen}.md` | Exists, verdict `approved` or `approved with follow-ups` |

If any is missing, stale, or blocked, return to that stage first.

## Agent Prompt For Stage 6

```text
Run Stage 6 (Final Acceptance) for this screen:

- screen: {screen}

Resolve project values from PROJECT_CONFIG.md, and screen_key plus module from Screens_Registry.md.

Read: MASTER_WORKFLOW.md, this README, Code_Review/README.md, and the screen's five upstream
artifacts.

Prerequisite check — confirm each upstream artifact exists and that the Stage 5 verdict is
`approved` or `approved with follow-ups`. Stop if not.

Then act in two roles, separately:

As product manager, review: business flow and user flow fidelity, legacy parity, accepted
differences, and any open business decision. Ask whether an operator doing this job daily would
accept the screen.

As technical lead, review: artifact consistency across the set, implementation and test risk,
outstanding follow-ups from Stage 5, and how hard this would be to fix or roll back if a defect
surfaces after release.

Output target: {{DOCS_DIR}}/Final_Acceptance/{screen}.md

Allowed verdicts:
- PM verdict: pass | business mismatch | business decision required
- Tech lead verdict: pass | fix required | test rerun required | rollback proposed
- Recommendation: approve | approve with follow-ups | fix required | test rerun required |
  business decision required | rollback proposed
- User decision: pending | accepted | rejected | changed

Rules:
- Do not state the screen is ready to merge unless User decision is `accepted`.
- If the recommendation is anything other than approve, stop and name the exact route back.
- For `rollback proposed`, list the exact files, commits, and tests involved, and ask the user
  before touching anything.
- Do not re-litigate Stage 5 findings. Cite the review's verdict and move on to the acceptance
  question.
- Leave `User decision: pending` until the user actually answers. Never fill it in on their behalf.
```

## File Naming

One file per screen: `{{DOCS_DIR}}/Final_Acceptance/{screen}.md`, matching the `screen` value in `Screens_Registry.md`.

## Required Structure

```markdown
# {screen} — Final Acceptance

## 1. Summary

- **Screen** / **Module**
- **Reviewed on**: YYYY-MM-DD · **PM/TL agent**: {agent}
- **Stage 5 review**: `Code_Review/{screen}.md` — verdict quoted, not re-argued
- **Recommendation**: approve | approve with follow-ups | fix required | test rerun required | business decision required | rollback proposed
- **User decision**: pending | accepted | rejected | changed

One paragraph stating the recommendation and the single most important reason for it.

## 2. Upstream Artifact Check

| Artifact | Status | Note |
|---|---|---|

## 3. Product Manager Review

| Check | Verdict | Evidence | Required action |
|---|---|---|---|
| Business rules and user flow | pass / business mismatch / decision required | | |
| Legacy parity and accepted differences | | | |
| Open business decisions | | | |

## 4. Technical Lead Review

| Check | Verdict | Evidence | Required action |
|---|---|---|---|
| Artifact consistency across the set | pass / fix required | | |
| Implementation and test risk | pass / fix required / test rerun required | | |
| Outstanding Stage 5 follow-ups | | | |
| Fix and rollback risk after release | pass / rollback proposed | | |

## 5. Recommendation

- **PM verdict**:
- **Tech lead verdict**:
- **Recommendation**:
- **Rollback scope, if proposed**: exact files, commits, tests, and the risk of doing it
- **User decision**: pending until the user answers
- **User decision note**:

## 6. Routing

| Outcome | Next step |
|---|---|
| `approve` or `approve with follow-ups`, user accepted | Ready to merge |
| `fix required` | Return to Stage 3, then rerun 4, 5, 6 |
| `test rerun required` | Return to Stage 4, then rerun 5, 6 |
| `business decision required` | Stop; ask the user |
| `rollback proposed` | List the exact target; ask before acting |
```

## Registry Interaction

Stage 6 does **not** write track status in `Screens_Registry.md`. `verified` is granted by the Stage 5 verdict gate, because it records technical verification.

Acceptance is a business decision that does not change how a later pipeline run should behave — an accepted screen and a merely-reviewed one are both in Refresh mode. Keeping acceptance out of the registry leaves that file focused on its one job: resolving run mode. Acceptance state lives here, indexed in the table below.

## Current Final Acceptance Documents

| Screen | File | Stage 5 verdict | Recommendation | User decision | Date |
|---|---|---|---|---|---|
| | | | | | |

## Writing Rules

1. Quote the Stage 5 verdict; do not redo the review.
2. Keep the two roles separate. A merged narrative hides whether a concern is a business objection or a technical one, and those route differently.
3. Never fill in `User decision` yourself. A pending decision recorded honestly is useful; an assumed acceptance is a fabrication that later reads as approval.
4. For `rollback proposed`, be specific enough that the user can judge the risk without opening the code.
5. Record the date the decision was actually taken, not the date the file was last edited.

## Related Documents

| Document | Relationship |
|---|---|
| `MASTER_WORKFLOW.md` | Runs this stage; defines the routes out of it |
| `Code_Review/{screen}.md` | Upstream: the technical verdict this stage relies on |
| `Screens_Registry.md` | Not written here; `verified` comes from Stage 5 |
| `Known_Issues.md` | Where a follow-up accepted at this stage is recorded |
