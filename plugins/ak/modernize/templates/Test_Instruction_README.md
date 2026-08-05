# Test Instructions

> **Template.** Copy to `{{DOCS_DIR}}/Test_Instruction/README.md`.
>
> **For end-to-end work use `MASTER_WORKFLOW.md`, not the per-stage prompt below.** Testing is Stage 4a (backend) and Stage 4b (frontend). 4a runs after Stage 3b's gate; 4b runs after 4a because the end-to-end suite needs a working backend.

Stage 4a and 4b artifact. One file per screen holding the test specification, the commands that were run, their results, and the legacy-parity evidence a reviewer needs.

## Guiding Principle

Push every assertion as far toward automation as it will go. Only genuinely visual judgment stays manual. A test plan full of "operator verifies visually" is a plan that will not be re-run, and a test that is not re-run does not protect anything.

## Test Roles — Backend

| Role | Data strategy | Purpose |
|---|---|---|
| **Regression** | Seeded or factory data | Fast unit and API tests. Proves a specific business rule in isolation. Safe to run on every change |
| **Parity** | A case copied from reference data | Proves the new implementation returns what the legacy system returned for the same inputs. Required whenever the handoff needs real parameters and expected totals |

Regression tests may be credited as coverage when they prove a named business rule. Parity tests are the only acceptable evidence for "matches legacy".

## Test Tiers — Frontend

Classify every frontend assertion into one tier and automate everything above tier 3.

| Tier | What it covers | How |
|---|---|---|
| **1 — UI and interaction** | Controls exist and are reachable; interactions fire; loading, empty, and error states render; keyboard and focus behavior recorded as preserved actually works | `{{FE_E2E_TEST_CMD}}` against a running backend |
| **2 — Data and output** | Values shown match the API response; grid column order and totals match the plan; a generated file's contents match expectations, verified by **parsing** the file rather than eyeballing it | End-to-end test plus programmatic parsing of the downloaded artifact |
| **3 — Residual visual** | Print layout, page breaks, pixel-level report appearance — things that only a human comparing against a legacy sample can settle | Manual, with the exact steps and the legacy sample to compare against recorded here |

Tier 2 is where most teams give up and fall back to manual checking. Parsing an exported spreadsheet or delimited file is straightforward and turns a recurring manual chore into a permanent guarantee.

## Data Rules

1. Reference data access is **read-only**. Never mutate it.
2. Only the disposable test database is mutated.
3. The API client collection is a handoff artifact, not a pass/fail authority. Tests decide pass or fail.
4. Manual legacy comparison uses the **same parameter set** the automated parity test recorded, so the two are talking about the same case.
5. If reference data is unavailable, mark the parity check blocked with a reason and the exact rerun command. Do not report it as a pass, and do not report it as a functional failure.

Project-specific constraints live in `{{REFERENCE_DB_POLICY}}`.

## Agent Prompt For One Screen's Tests

```text
Please execute the test workflow for this screen:

- screen: {screen}
- screen_key: {screen_key}
- track: backend | frontend | both

Output target: {{DOCS_DIR}}/Test_Instruction/{screen}.md

Resolve project values from PROJECT_CONFIG.md first.

Prerequisites:
1. Business_flows/{screen}.md, Screen_plans/{screen}.md, and Coding_Records/{screen}.md must exist.
   If any is missing, that is an upstream gap — resolve it before testing.
2. For the frontend track: Stage 4a must be green and the backend must be running.

Workflow — backend (4a):
1. Build a coverage map: every business rule in the business flow, mapped to the test that proves it.
   A rule with no test is a gap, and it belongs in section 6 rather than being quietly skipped.
2. Check what regression coverage already exists before writing new tests.
3. Where real parameters are needed, probe reference data read-only, copy the minimal comparable case
   into the test database, and assert there.
4. Run {{TEST_CMD}}. Record the exact command and its result.
5. Normalize the per-screen folder under {{API_COLLECTION_DIR}} to the registry screen_key, then
   refresh the examples from cases the tests approved.

Workflow — frontend (4b):
1. Classify every assertion from the screen plan's control inventory and interaction table into
   tier 1, 2, or 3.
2. Automate tiers 1 and 2. Run {{FE_E2E_TEST_CMD}} and {{FE_UNIT_TEST_CMD}} if defined.
3. For output screens, download the generated artifact and assert on its parsed contents — column
   order, headers, totals, signs, row count.
4. Leave in tier 3 only what genuinely requires human visual comparison, and record the legacy
   sample to compare against plus the exact steps.
5. Record every failure as a finding with expected versus actual. Do not weaken an assertion to make
   a test pass; fix the locator, not the expectation.

Rules:
- You are testing, not fixing. If the code deviates from the plan, record it as a finding with root
  cause and impact, and stop there.
- Never mutate reference data.
- Never treat the API client collection as the pass/fail authority.
- If the environment blocks a test, record it as a blocker with the exact rerun command rather than
  reporting a failure.
```

## File Naming

One file per screen: `{{DOCS_DIR}}/Test_Instruction/{screen}.md`.

## Required Structure

```markdown
# {screen} — Test Instruction

> Last refreshed: YYYY-MM-DD · Backend: pass | fail | blocked · Frontend: pass | fail | blocked

## 1. Summary

- **Backend tests**: pass | fail | not run — command and result
- **Frontend tests**: pass | fail | not run — command and result
- **Legacy parity**: verified | partial | blocked (reason)
- **Manual cases remaining**: count

One paragraph on what was verified and what remains unverified.

## 2. Source Documents

- Business flow, screen plan, coding record
- Legacy output samples used as comparison baselines, with anchors

## 3. Backend Tests

### 3.1 Coverage Map

Every business rule, mapped to the test that proves it. A rule with no test is recorded, not hidden.

| Rule (BF §N) | Test | Role | Status |
|---|---|---|---|

### 3.2 Regression Tests

Test names, what each asserts, and the data strategy.

### 3.3 Parity Tests

| # | Parameter set | Source of expected values | Result |
|---|---|---|---|

Record the exact parameters so the manual legacy comparison uses the same case.

### 3.4 Commands And Results

```bash
{{TEST_CMD}}
```

Paste the outcome summary, not the full log.

### 3.5 API Client Artifacts

Folder used under `{{API_COLLECTION_DIR}}`, whether it was renamed to match `screen_key`, and which
cases were exported.

## 4. Frontend Tests

### 4.1 Tier Classification

| # | Assertion | Source (SP §4.2 row / §4.3 row) | Tier | Automated? |
|---|---|---|---|---|

Every row in the screen plan's control inventory and interaction table appears here exactly once.

### 4.2 Tier 1 — UI And Interaction

Test names and what each asserts. Include the loading, empty, and error states, and any keyboard or
focus behavior the screen plan marked as preserved.

### 4.3 Tier 2 — Data And Output

| # | What is asserted | How the artifact is parsed | Legacy baseline | Result |
|---|---|---|---|---|

### 4.4 Tier 3 — Residual Manual

| # | Case | Exact steps | Legacy sample to compare | Result | Verified by |
|---|---|---|---|---|---|

Keep this list short. An item here that could be parsed programmatically belongs in tier 2.

### 4.5 Commands And Results

```bash
{{FE_E2E_TEST_CMD}}
```

## 5. Legacy Parity Comparison

The same parameter set run against the legacy application, and what differed.

| # | Parameter set | Legacy result | New result | Verdict |
|---|---|---|---|---|

Verdict is one of: match, accepted difference (with the screen plan reference), or defect.

## 6. Gaps, Blockers, And Environment Notes

| # | Item | Type | Impact | Rerun command |
|---|---|---|---|---|

Types include: rule with no test, environment blocker, reference data unavailable, flaky test.
Anything affecting more than one screen is promoted to `Known_Issues.md`; note the row number.

## 7. Handoff To Review

- Which findings the reviewer must judge, ranked by impact
- Which assertions are unverified and why
- Whether the backend must be running to reproduce the frontend suite
```

## Writing Rules

1. Record the exact command, not a paraphrase. The reviewer reruns it.
2. A rule with no test is written down, never omitted. An invisible gap is worse than a known one.
3. Never weaken an assertion to turn a test green. Fix the selector or the setup; if the expectation was wrong, that is a screen-plan correction.
4. Distinguish an environment blocker from a functional failure. Conflating them makes the test signal useless.
5. Keep tier 3 minimal and justify each entry.
6. Update the index table when adding a file.

## Current Test Instructions

| Screen | Test instruction | Backend result | Frontend result | Parity | Code review |
|---|---|---|---|---|---|
| | | | | | |

## Related Documents

| Document | Relationship |
|---|---|
| `MASTER_WORKFLOW.md` | Runs Stages 4a and 4b |
| `Screen_plans/{screen}.md` | §4.2 and §4.3 are the source of the frontend tier classification |
| `Coding_Records/{screen}.md` | Says what was built, including deferrals that explain missing coverage |
| `Code_Review/{screen}.md` | Downstream: reads this file as parity and correctness evidence |
| `LEGACY_EVIDENCE.md` | Where the legacy comparison baselines come from |
