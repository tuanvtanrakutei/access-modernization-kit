# Screen Plans

> **Template.** Copy to `{{DOCS_DIR}}/Screen_plans/README.md`.
>
> **For end-to-end work use `MASTER_WORKFLOW.md`, not the per-stage prompt below.** The master workflow runs pre-flight, resolves run modes, consults the issue log, and applies update gates that this README does not. Use this prompt only when refreshing the screen plan alone.

Stage 2 artifact. This is the **technical contract** for one screen: what the legacy system did, what the new system will expose on the backend, and what the new system will render on the frontend.

Stage 3a codes against §3. Stage 3b codes against §4. Gate G2 checks that every business rule reached §5, and gate G3 checks that §3 and §4.2 reached actual code. A vague screen plan therefore does not merely slow coding — it makes the gates unable to verify anything.

## What Belongs Here

1. Legacy behavior proven by evidence, with anchors.
2. The backend API contract.
3. The frontend contract, including a control inventory.
4. Legacy-to-new mapping, row by row.
5. Accepted differences, confirmed fixes, and remaining gaps.

## What Does Not Belong Here

- Business-only narrative for non-technical reviewers — that is `Business_flows/{screen}.md`.
- Test execution steps and commands — that is `Test_Instruction/{screen}.md`.
- A record of what was actually built — that is `Coding_Records/{screen}.md`.

## Agent Prompt For One Screen Plan

```text
Please create or refresh the screen plan for this screen:

- screen: {screen}
- screen_key: {screen_key}
- module: {module}

Output target: {{DOCS_DIR}}/Screen_plans/{screen}.md

Resolve project values from PROJECT_CONFIG.md first.

Use available evidence:
- the exported legacy form, report, VBA, queries, and stored procedures for this screen,
  per LEGACY_EVIDENCE.md for {{LEGACY_VARIANT}}
- screenshots and legacy output samples
- {{TABLE_MAP_DOC}} for table and field names
- the current backend sources under {{BACKEND_ROOT}}
- the current frontend sources under {{FRONTEND_ROOT}}
- Business_flows/{screen}.md
- any open traceability rows from gate G1 for this screen

If the target file exists, do not treat it as the source of truth. Preserve confirmed notes and open
decisions, then reconcile against current evidence and current code.

Workflow:
1. Trace legacy behavior from evidence. Record anchors in the format defined in TRACEBACK_GATES.md.
2. Trace current backend and frontend behavior from the sources, if any exists.
3. Write the file using the structure in this README.
4. Fill BOTH contracts. A screen plan with no frontend contract fails gate G2.
5. Populate the control inventory in §4.2 — one row per legacy control. Gate G3's UI sub-check reads it.
6. Mark the backend contract status in §3.4 as draft or frozen. Only a frozen contract permits
   Stage 3a and 3b to run concurrently.
7. Record every accepted difference and every open decision. Do not silently normalize legacy oddities.
8. Update the index table in this README.

Rules:
- Start from evidence, not from assumption. Cite an anchor for every legacy claim.
- Distinguish confirmed legacy behavior from partial evidence, and say which.
- If a legacy defect is being fixed deliberately, state why it is a defect and why preserving it
  would be wrong.
- If exported text looks like garbage, re-read it using {{SOURCE_ENCODING}} before concluding
  anything about field names or formulas.
- Keep business narrative brief and link to Business_flows instead of restating it.
```

## File Naming

One file per screen: `{{DOCS_DIR}}/Screen_plans/{screen}.md`, using the `screen` value from `Screens_Registry.md` verbatim.

## Required Structure

```markdown
# {screen} ({module} module)

> Last refreshed: YYYY-MM-DD · doc_mode: greenfield | backfill | refresh · By: agent | {name} · Code ref at refresh: {short_sha}

## Summary

Screen scope, module ownership, and what this plan is for. Two or three sentences.

## 1. Evidence And Scope

### 1.1 Evidence
Every legacy object examined, with anchors. Include the exported form and report, VBA modules,
queries or stored procedures, table definitions, screenshots, and output samples.
For a split design, state explicitly which file each item came from.

### 1.2 In Scope
### 1.3 Out Of Scope

## 2. Legacy Baseline

Legacy purpose, controls, actions, data flow, calculations, locking, and side effects — each claim
carrying an anchor. Note which behaviors are proven by code versus inferred from a screenshot.

## 3. Backend Contract

### 3.1 Endpoints

| Method | Path (after {{API_PREFIX}}) | Purpose | Required? |
|---|---|---|---|

### 3.2 Request And Response

Per endpoint: parameters with required/optional and types; response shape including pagination
and any metadata block; error cases with status codes.

### 3.3 Side Effects

Writes, temp-table rebuilds, generated files, and anything observable beyond the response body.

### 3.4 Contract Status

`draft` or `frozen`. Frozen means the shape below will not change without a Stage 2 revision, which
is the precondition for running Stage 3a and 3b concurrently.

## 4. Frontend Contract

### 4.1 Route And Entry

Route under {{FE_ROUTE_BASE}}; how the user reaches the screen; parameters carried in the URL;
permissions required to open it.

### 4.2 Control Inventory

One row per legacy control. **Gate G3's UI sub-check reads this table**, so a control missing here
is a control nobody will notice is unimplemented.

| # | Legacy control | Legacy anchor | Type | Target component | Behavior notes |
|---|---|---|---|---|---|
| 1 | cboStore | Form_X.txt::property:RowSource | combo, limit-to-list | StoreSelect | rejects unlisted values; message text preserved |

### 4.3 Interactions

One row per user action, including what triggers it and what the user observes afterwards.

| # | Trigger | Action | Observable result | Legacy anchor |
|---|---|---|---|---|

### 4.4 Client Validation

Field rules mirrored from legacy field properties and from the backend contract. State explicitly
that the server remains authoritative.

### 4.5 State And Data Fetching

Query keys and their parameters; what lives in global state and why; what is intentionally local;
cache invalidation after each mutation.

### 4.6 Output Rendering

For report, print, and export screens: which endpoint produces the file, how the download is
delivered, whether a preview exists, and which legacy sample the output is compared against.

## 5. Legacy-To-New Mapping

One row per business rule or legacy concept. **Gate G2 reads this table.**

| # | Rule (BF §N) | Legacy anchor | Backend location | Frontend location | Status |
|---|---|---|---|---|---|

Status is one of: implemented, planned, accepted-difference, open-decision.

## 6. Gap Matrix

| Topic | Legacy behavior | New behavior | Status |
|---|---|---|---|

Status is one of: matched, accepted-difference, fixed-deliberately, open.

## 7. Acceptance And Validation Scenarios

What must be true for this screen to be considered aligned with the legacy system. Written so that
Stage 4a and 4b can turn each item into a test.

## 8. Implementation Phases

Separate what is already implemented from fix-now items and deferred work. State the reason for
each deferral, so gate G3 can distinguish a deliberate deferral from an omission.
```

## Writing Rules

1. **Anchor every legacy claim.** An unanchored claim cannot be verified by a gate or by a reviewer, so it is an assumption wearing the clothes of a fact.
2. Prefer live code over stale assumption when describing current behavior.
3. Mark accepted differences explicitly, and never bury one inside prose.
4. A deliberate legacy-defect fix needs a stated reason.
5. Re-read suspicious exported text with `{{SOURCE_ENCODING}}` before drawing conclusions.
6. One authoritative file per screen. Do not split legacy and new into separate documents — they must be read together.
7. The control inventory is not optional. It is the only place the frontend's completeness is measurable.

## Current Screen Plans

| Screen | Screen plan | Business flow | Coding record | Test instruction | Code review |
|---|---|---|---|---|---|
| | | | | | |

## Related Documents

| Document | Relationship |
|---|---|
| `MASTER_WORKFLOW.md` | Runs this stage; defines gates around it |
| `TRACEBACK_GATES.md` | G2 reads §5; G3 reads §3.1 and §4.2; anchor format defined there |
| `LEGACY_EVIDENCE.md` | What evidence exists to cite in §1.1 |
| `Business_flows/{screen}.md` | Upstream: the business rules this plan maps |
| `Coding_Records/{screen}.md` | Downstream: what was actually built against this contract |
| `{{BACKEND_RULES_DOC}}` / `{{FRONTEND_RULES_DOC}}` | How the contracts get implemented |
