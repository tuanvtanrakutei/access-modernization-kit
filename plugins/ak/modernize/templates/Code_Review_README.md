# Code Review

> **Template.** Copy to `{{DOCS_DIR}}/Code_Review/README.md`.
>
> **For end-to-end work use `MASTER_WORKFLOW.md`, not the per-stage prompt below.** Review is Stage 5, the final stage. It runs only after Stage 4b's gate resolves.

Stage 5 artifact. One file per screen recording the review verdict, findings, and the merge gate.

A review answers five questions:

1. Does the implementation match the screen plan, on **both** tracks?
2. Does the code follow the project's coding rules?
3. Are there security, performance, or correctness risks?
4. Is test coverage and legacy-parity evidence sufficient?
5. What must be fixed before merge, and what may be deferred?

## Prerequisites

Do not start a review until all five upstream artifacts exist and their own gates passed:

| Artifact | Required state |
|---|---|
| `Business_flows/{screen}.md` | Exists, structured, reviewer-readable |
| `Screen_plans/{screen}.md` | Exists; both contracts present; control inventory populated |
| `Coding_Records/{screen}.md` | Exists; the tracks under review report `implemented`; lint passed |
| `Test_Instruction/{screen}.md` | Exists; tests green, or an explicit blocker with a rerun command |
| `Screens_Registry.md` | Row exists with both track statuses |

If any is missing or stale, fix it upstream. A review written on top of a broken upstream launders the problem instead of catching it.

## Agent Prompt For One Review

```text
Please create or refresh the code review for this screen:

- screen: {screen}
- screen_key: {screen_key}
- module: {module}
- tracks under review: backend | frontend | both

Output target: {{DOCS_DIR}}/Code_Review/{screen}.md

Resolve project values from PROJECT_CONFIG.md first.

Read: the business flow, the screen plan, the coding record, the test instruction, the coding rule
documents ({{BACKEND_RULES_DOC}}, {{FRONTEND_RULES_DOC}}, {{CONVENTIONS_DOC}}), the code cited in the
coding record, and every open traceability row for this screen in Known_Issues.md.

Prerequisite check:
1. Confirm all five upstream artifacts exist and pass their structure checks.
2. Confirm the coding record reports the reviewed tracks as implemented with lint passing.
3. Confirm tests ran. If they never ran, stop — return to Stage 4 rather than reviewing blind.

Workflow:
1. Walk every checklist group below. Mark each item pass, fail, or not-applicable, with one line of
   evidence — a file and line, or a command result.
2. Rerun lint and tests yourself. Do not take the coding record's word for it. A verdict of approved
   is not available if you did not reproduce the results.
3. Categorize findings as blocker, should-fix, nit, or follow-up. Only a blocker prevents merge.
4. Confirm every open traceability row, then run the independent coverage re-check in group 9.
5. Write the review using the structure below and append a changelog row.
6. Update this README's index and, on approval, the registry track statuses.

Rules:
- Read the code. Cite a file and line for every finding; a finding without a location cannot be acted on.
- Distinguish "differs from the plan" (a deviation, possibly acceptable) from "wrong" (a defect).
- A business-rule ambiguity is not a code defect. Route it to the business flow as an open decision.
- Do not edit the implementation during review. Reviews produce findings, not patches. If a fix is
  trivial, record it as a finding for the implementer.
- From the second iteration onward, scope the review to the files listed in the latest coding-record
  changelog row; carry forward items that already passed and mark them as carried.
```

## File Naming

One file per screen: `{{DOCS_DIR}}/Code_Review/{screen}.md`.

## Required Structure

```markdown
# {screen} — Code Review

## 1. Summary

- **Screen** / **Module**
- **Tracks reviewed**: backend | frontend | both
- **Reviewed on**: YYYY-MM-DD  · **Reviewer**: agent | {name}
- **Verdict**: approved | approved with follow-ups | changes requested | blocked
- **Backend tests reproduced**: pass | fail | not run
- **Frontend tests reproduced**: pass | fail | not run

One paragraph: the outcome and the headline blockers.

## 1.1 Changelog

Append-only.

| Iteration | Date | Tracks | Verdict | Blockers filed | Blockers resolved |
|---|---|---|---|---|---|

## 2. Upstream Artifact Check

| Artifact | Status | Note |
|---|---|---|

If any row fails, the verdict is `blocked` and the rest of the review is skipped.

## 3. Checklist

Mark each item pass / fail / n-a with one line of evidence.

### 3.1 Backend rule compliance (vs {{BACKEND_RULES_DOC}} and {{CONVENTIONS_DOC}})
- [ ] Routes mounted under `{{API_PREFIX}}`
- [ ] View layer follows the project's default pattern; exceptions justified
- [ ] Schema ownership respects `{{MIGRATIONS_POLICY}}`; no unauthorized model or migration
- [ ] Naming conventions applied — `{{CODE_FIELD_SUFFIX}}`, `{{BOOL_FIELD_SUFFIX}}`, `{{TIME_FIELD_SUFFIX}}`
- [ ] Standard response wrapper `{{RESPONSE_CLASS}}` used; no raw framework response
- [ ] Status codes match the project's mapping
- [ ] Line length and import order per `{{CONVENTIONS_DOC}}`

### 3.2 Backend API contract (vs screen plan §3)
- [ ] Every planned endpoint is implemented and reachable
- [ ] Request schema matches — required versus optional, types
- [ ] Response schema matches — field names, nesting, totals placement
- [ ] Pagination matches the planned strategy; no forbidden fields on cursor endpoints
- [ ] Totals computed over the full filtered set, before pagination
- [ ] Side effects in §3.3 are implemented

### 3.3 Frontend rule compliance (vs {{FRONTEND_RULES_DOC}})
- [ ] No HTTP call outside `{{FE_API_DIR}}`
- [ ] Types mirror the backend contract; no silent field renaming; no `any` at the boundary
- [ ] Query keys include every parameter that affects the result
- [ ] Mutations invalidate the affected keys
- [ ] Server data is not duplicated into a global store
- [ ] Loading, empty, and error states all implemented and visually distinct
- [ ] All user-visible strings go through `{{I18N_LIB}}`
- [ ] Inputs have associated labels; interactive elements are keyboard-operable

### 3.4 Frontend legacy-UI parity (vs screen plan §4)
- [ ] Every control in the inventory (§4.2) exists as a component
- [ ] Every interaction in §4.3 has a handler with the recorded observable result
- [ ] Keyboard and focus behavior marked preserved is implemented
- [ ] Locked and disabled are distinguished, not collapsed into one
- [ ] Default values on a new record match the recorded legacy defaults
- [ ] Message text matches the legacy wording
- [ ] Grid editability matches legacy view type; a modal replacing an editable grid is flagged
- [ ] Column order, totals placement, and number and date formatting follow the legacy layout
- [ ] Every divergence is recorded in the screen plan as an accepted difference — not merely present in code

### 3.5 Business rule parity (vs business flow)
- [ ] Every rule is implemented, or recorded as an accepted difference in the screen plan
- [ ] Soft-delete and status filters applied wherever the legacy queries applied them
- [ ] Validations cover required inputs and locks on both client and server
- [ ] Calculations and rounding match the legacy formulas

### 3.6 Legacy parity evidence (vs test instruction)
- [ ] A parity test exists and passes, or a blocker is recorded with a rerun command
- [ ] Reference data was read-only; mutations were confined to the test database
- [ ] The manual legacy comparison used the same parameter set the parity test recorded
- [ ] Residual manual cases are minimal and justified

### 3.7 Output and export (when applicable)
- [ ] Output format follows the legacy contract; only Excel is converted per project policy
- [ ] Column order, headers, and sheet or section naming match the legacy sample
- [ ] Filename rule matches legacy and is applied in one place — server-side
- [ ] The frontend triggers the download rather than generating the artifact
- [ ] Export endpoints are not paginated

### 3.8 Security, performance, correctness
- [ ] No injection vector; any raw query is parameterized
- [ ] No N+1 on list endpoints; relations eager-loaded where the serializer traverses them
- [ ] Write paths that touch multiple rows or models are transactional
- [ ] Money and quantity use decimal end to end, never floating point
- [ ] Datetime handling matches `{{USE_TZ}}` and `{{TIMEZONE}}`
- [ ] No write to a read-only schema listed in `{{SCHEMAS_READONLY}}`
- [ ] Permission checks present per method where the project requires them
- [ ] Established what the **production** configuration enforces, not what the settings file currently shows — per `{{BACKEND_RULES_DOC}}` §12.1. With an authenticated baseline a gap is cross-role privilege escalation; without one it is unauthenticated access. Do not report the second when the first applies
- [ ] Development bypasses live in configuration, not in code — per §12.2. Specifically: the permission-check function has no unconditional early `return`, and no access-control class is commented out. Each such bypass is a manual revert someone must remember at release, and one inside a method body is invisible to anyone reviewing settings or environment files
- [ ] Read endpoints classified per §12.3: the screen's transaction read is protected; existence oracles such as duplicate checks are protected; reference lookups follow the project's recorded policy rather than being left open by default
- [ ] Any coverage figure quoted was produced by block-based decorator attribution, not a fixed lookback — and any security finding was confirmed by opening the file. A decorator that is present proves nothing if the function it calls returns immediately
- [ ] Errors handled at boundaries; nothing swallowed silently
- [ ] Tests cover non-trivial branches — calculations, totals, rejection paths

### 3.9 Traceability findings

Two parts. Confirm what the gates filed, then verify independently that they missed nothing.

#### 3.9.1 Confirm existing rows
- [ ] Every `open (HIGH)` row is resolved. A HIGH still open at review is itself a blocker
- [ ] Every `open (MEDIUM)` row is resolved, deferred with an owner and reopen trigger, or marked will-not-fix with a reason
- [ ] Every `open (LOW)` row is resolved, deferred, or marked will-not-fix
- [ ] Any severity change carries a one-sentence reason; upgrade effects per `TRACEBACK_GATES.md`

#### 3.9.2 Independent coverage re-check
Gates can miss findings. Verify rather than trust.
- [ ] Evidence versus business flow: list the evidence directories for this screen and confirm each applicable object appears in the business flow's evidence section. File a new row for anything missing
- [ ] Business flow versus screen plan: every rule has a mapping row
- [ ] Screen plan versus backend code: every planned endpoint has a route
- [ ] Screen plan versus frontend code: every control-inventory row has a component
Anything newly filed here is treated like a Stage 5 finding, and a HIGH one loops the pipeline.

### 3.10 Documentation honesty
- [ ] Coding record statuses reflect reality; nothing reports implemented while tests are red
- [ ] Screen plan gap matrix updated for every new fix or accepted difference
- [ ] Business flow updated only where a business-relevant change occurred, not for style
- [ ] Registry track statuses will be correct after this verdict is applied

## 4. Findings

| # | Severity | Track | Location | Finding | Suggested action |
|---|---|---|---|---|---|

Severity meanings: **blocker** prevents merge; **should-fix** in this change unless the team defers;
**nit** never blocks; **follow-up** is out of scope and filed separately.

## 5. Verification Reproduced

Commands the reviewer ran independently, and their outcomes. If a result differs from the coding
record, that difference is itself a finding.

```bash
{{LINT_CMD}}
{{TEST_CMD}}
{{FE_LINT_CMD}}
{{FE_E2E_TEST_CMD}}
```

## 6. Open Decisions For The Business Owner Or Tech Lead

Items the review cannot settle alone: business-rule ambiguities, architecture deviations, legacy
behaviors proposed for deliberate change.

## 7. Merge Gate

- [ ] No blocker findings
- [ ] Every upstream artifact in section 2 passes
- [ ] Backend and frontend tests reproduced by the reviewer
- [ ] Lint reproduced clean on both tracks
- [ ] Every traceability row closed or explicitly deferred with an owner
- [ ] Open decisions resolved, or deferred with an owner and a date

When every box is checked, set the verdict in section 1 and apply the registry status update for the
reviewed tracks.
```

## Writing Rules

1. Cite a file and line for every finding. "This looks wrong" is not reviewable.
2. Separate deviation from defect. A deviation may be accepted; a defect must be fixed or explicitly waived by someone with the authority to waive it.
3. Reviews produce findings, not patches.
4. A verdict of `approved` requires that the reviewer reran the tests. Otherwise the approval certifies nothing.
5. Do not paper over a stale upstream artifact — fix it upstream.
6. In Backfill mode most should-fix items are pre-existing debt; downgrading them to follow-up and routing them to `Known_Issues.md` is legitimate, and hiding them is not.

## Current Reviews

| Screen | Code review | Tracks | Verdict | Date |
|---|---|---|---|---|
| | | | | |

## Related Documents

| Document | Relationship |
|---|---|
| `MASTER_WORKFLOW.md` | Runs this stage; defines the loop back to coding on a blocker |
| `TRACEBACK_GATES.md` | Severity semantics and upgrade effects used in group 3.9 |
| `Screen_plans/{screen}.md` | The contract groups 3.2 and 3.4 measure against |
| `Coding_Records/{screen}.md` | What was built, and which files to scope a re-review to |
| `Test_Instruction/{screen}.md` | Parity and correctness evidence |
| `{{BACKEND_RULES_DOC}}`, `{{FRONTEND_RULES_DOC}}`, `{{CONVENTIONS_DOC}}` | The rules groups 3.1 and 3.3 check compliance with |
