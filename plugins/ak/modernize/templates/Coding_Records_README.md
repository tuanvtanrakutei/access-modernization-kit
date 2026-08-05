# Coding Records

> **Template.** Copy to `{{DOCS_DIR}}/Coding_Records/README.md`.
>
> **For end-to-end work use `MASTER_WORKFLOW.md`, not the per-stage prompt below.** Coding is Stage 3a (backend) and Stage 3b (frontend); they run after Stage 2 and before Stage 4a.

Stage 3a and 3b artifact. One file per screen recording **what was actually built** — files touched, decisions made, deviations from the plan, and open questions.

> **Naming note.** A "coding record" is a written record of implementation work. It is **not** runtime logging; logger usage rules live in `{{CONVENTIONS_DOC}}`.

## Why This Artifact Exists

Without it, a reviewer must reconstruct intent by diffing every file, and a deferred item survives only in someone's memory. The record makes implementation auditable and makes deferrals visible to the gate that would otherwise flag them as omissions.

It is also the handoff from coding to test and review: Stage 4 learns what to exercise, and Stage 5 learns where to look.

## Agent Prompt For One Coding Record

```text
Please create or refresh the coding record for this screen:

- screen: {screen}
- screen_key: {screen_key}
- module: {module}
- track: backend | frontend | both

Output target: {{DOCS_DIR}}/Coding_Records/{screen}.md

Resolve project values from PROJECT_CONFIG.md first.

Prerequisites:
1. Read {{BACKEND_RULES_DOC}} (for the backend track) and {{FRONTEND_RULES_DOC}} (for the frontend
   track), plus {{CONVENTIONS_DOC}}. These rules are non-negotiable.
2. Confirm Business_flows/{screen}.md and Screen_plans/{screen}.md exist and are current. If either
   is missing, that is an upstream gap — resolve it before coding.
3. Note the run mode for this track. In Backfill mode, do NOT write new code; document the code that
   already exists.

Workflow:
1. Implement or update code under {{BACKEND_ROOT}} (3a) and/or {{FRONTEND_ROOT}} (3b).
2. Run {{LINT_CMD}} for the backend track, {{FE_LINT_CMD}} for the frontend track. Resolve findings
   on files you touched.
3. Write or refresh the coding record using the template in this README. Fill only the sections for
   the tracks you worked on; leave the other track's sections as they were.
4. Append a changelog row for this iteration.
5. Update the index table in this README.
6. Do NOT report the track as complete if lint failed, tests failed, or coverage is unknown. Set the
   status honestly so the reviewer can act.

Rules:
- Follow {{MIGRATIONS_POLICY}} for schema ownership. If a needed model exists nowhere, stop and
  follow {{MISSING_MODEL_ESCALATION}} rather than creating one here.
- Do not rename existing tables or columns.
- Do not change legacy behavior that the screen plan says is preserved.
- Reference files by path with line numbers. Do not paste long file contents into the record.
- Keep the record under roughly 250 lines. Design-level prose belongs in the screen plan.
```

## File Naming

One file per screen: `{{DOCS_DIR}}/Coding_Records/{screen}.md`, matching the `screen` value in `Screens_Registry.md`.

## Required Structure

```markdown
# {screen} — Coding Record

> Last refreshed: YYYY-MM-DD · be_mode: greenfield | backfill | refresh · fe_mode: greenfield | backfill | refresh

## 1. Summary

- **Screen**: {screen}
- **Module**: {{BACKEND_ROOT}}/{module}
- **Backend status**: implemented | partial | blocked | not_started
- **Frontend status**: implemented | partial | blocked | not_started
- **Backend lint**: pass | fail | not run
- **Frontend lint**: pass | fail | not run
- **Backend tests**: pass | fail | not run (command and result)
- **Frontend tests**: pass | fail | not run (command and result)

Status rules, per track:
- `implemented` only when §7.1 has no open row for that track.
- `partial` when work was intentionally deferred (§7.2 populated) and §7.1 is clear.
- `blocked` when §7.1 has any open row for that track.

One paragraph: what was built in this iteration and what is intentionally out of scope.

## 1.1 Changelog

Append-only. Never delete a prior row.

| Iteration | Date | Track | Trigger | Files touched | Lint | Tests | Notes |
|---|---|---|---|---|---|---|---|
| v1 | YYYY-MM-DD | backend | initial | ... | pass | pass | ... |
| v2 | YYYY-MM-DD | frontend | initial | ... | pass | fail | ... |
| v3 | YYYY-MM-DD | backend | review blocker #2 | ... | pass | pass | resolves #2 |

## 2. Source Documents

- Business flow: `{{DOCS_DIR}}/Business_flows/{screen}.md`
- Screen plan: `{{DOCS_DIR}}/Screen_plans/{screen}.md`
- Backend rules: `{{BACKEND_RULES_DOC}}` · Frontend rules: `{{FRONTEND_RULES_DOC}}` · Style: `{{CONVENTIONS_DOC}}`
- Table mapping: `{{TABLE_MAP_DOC}}`
- Legacy evidence relied on: list anchors

## 3. Backend

Skip this section entirely if the backend track was not touched. Do not leave a half-filled section.

### 3.1 API Surface Delivered

| Method | Path | View class | Purpose | Screen plan ref |
|---|---|---|---|---|

Note the pagination class, filters, and ordering for each list endpoint.

### 3.2 Files Touched

Grouped by role, with repo-relative paths. Cite line ranges for the parts that carry business logic.

- Models used (imported, per `{{MIGRATIONS_POLICY}}`):
- Serializers:
- Views:
- Services:
- URLs:
- Tests:

### 3.3 Key Decisions

Numbered. One sentence on the choice, one on the reason. Examples: ORM versus raw SQL, pagination
strategy, where totals are computed, transaction boundary placement, export filename rule.

### 3.4 Deviations From The Screen Plan

| # | Planned | Implemented | Reason | Screen plan needs refresh? |
|---|---|---|---|---|

## 4. Frontend

Skip this section entirely if the frontend track was not touched.

### 4.1 Routes And Components Delivered

| Route | Component | Purpose | Screen plan ref |
|---|---|---|---|

### 4.2 Files Touched

- Pages:
- Components:
- API client modules:
- Types:
- Stores:
- Hooks:
- Translations:
- Tests:

### 4.3 Key Decisions

Include every legacy-UI-parity decision explicitly: keyboard behavior, focus order, locked versus
disabled, message wording, grid editability, preview versus direct download.

### 4.4 Deviations From The Screen Plan

| # | Planned | Implemented | Reason | Screen plan needs refresh? |
|---|---|---|---|---|

## 5. Legacy-To-New Mapping Applied

The rules that actually drove this implementation. The full mapping stays in the screen plan.

| Legacy anchor | Backend location | Frontend location | Note |
|---|---|---|---|

Cite the screen plan section or the legacy anchor, and code as `path:line`, so gate G3 can verify
that each planned item reached code.

## 6. Verification Commands

Exact commands and their outcomes. The reviewer reruns these.

```bash
{{LINT_CMD}}
{{TEST_CMD}}
{{FE_LINT_CMD}}
{{FE_E2E_TEST_CMD}}
```

## 7. Open Items And Q&A

Fill all three subsections. Write `None` rather than leaving one blank — an empty section and an
overlooked section look identical.

### 7.1 Pending Answers (block progress)

While any row exists here, the affected track's status is `blocked`.

| # | Track | Question | Type | Asked to | Asked on | Status |
|---|---|---|---|---|---|---|

### 7.2 Not Yet Implemented (intentional)

| # | Track | Item | Reason for deferral | Tracked in |
|---|---|---|---|---|

Gate G3 reads this table. An item listed here with a reason is a deferral; the same item missing
from here is an omission.

### 7.3 Discovered During Coding (no decision yet)

| # | Finding | Type | Routed to |
|---|---|---|---|

Anything affecting more than one screen is promoted to `Known_Issues.md`; note the row number here.

## 8. Handoff Notes For Test And Review

- For test: which scenarios matter most, which legacy parameter set to reuse, any environment blocker,
  and whether the backend must be running for the frontend suite.
- For review: which checklist areas need extra attention — raw SQL used, custom pagination, a new
  export format, a legacy-parity decision that deserves a second opinion.
```

## Writing Rules

1. Record what was built, not what should be built. Intent belongs in the screen plan.
2. Reference files by path and line; never paste long contents.
3. Keep the two tracks separate. A single merged narrative makes it impossible to tell which track is complete.
4. If lint or tests failed, say so. A record that hides a red result makes the reviewer's approval meaningless.
5. Every deferral needs a reason and a tracking location, otherwise a gate will correctly treat it as an omission.
6. Update the index table below when adding a file.

## Current Coding Records

| Screen | Coding record | Backend status | Frontend status | Test instruction | Code review |
|---|---|---|---|---|---|
| | | | | | |

## Related Documents

| Document | Relationship |
|---|---|
| `MASTER_WORKFLOW.md` | Runs Stages 3a and 3b; defines the closing gates |
| `TRACEBACK_GATES.md` | G3 reads §5 and §7.2 to distinguish deferral from omission |
| `Screen_plans/{screen}.md` | Upstream contract this record implements |
| `Test_Instruction/{screen}.md` | Downstream: exercises what this record describes |
| `Code_Review/{screen}.md` | Downstream: verifies it |
| `{{BACKEND_RULES_DOC}}`, `{{FRONTEND_RULES_DOC}}`, `{{CONVENTIONS_DOC}}` | The rules this record must comply with |
