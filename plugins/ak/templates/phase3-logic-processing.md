# {{APP_ID}} — Phase 3: Logic & Processing

<!--
  Characteristic claim: what the processing does, step by step, and to which bytes.

  The rule this phase turns on: a claim about the format of a file the application
  READS needs SAMPLE_DATA, and about a file it WRITES needs OUTPUT_SAMPLE
  (rule EC-02). Code shows what a reader accepts, which is not what the producer
  writes. The strongest finding in the reference set - that a red/black flag column
  is ignored and the sign of the quantity routes the row - came from ~4,000 sample
  rows and no amount of code reading would have established it.

  Business rules get identifiers here: BR-{DOMAIN}-nn, per identifier-scheme.yaml.
  Each cites evidence. A rule with no citation is an impression.

  Delete these comment blocks as you fill the document in.
-->

## Naming Convention

Table, object and file names are the **production names**, unchanged. JP-primary
with a Romaji alias where they are Japanese. Never translate.

| Japanese (production) | Romaji alias | Role |
|---|---|---|

## Source Coverage

| Evidence class | Supplied | Scope | What its absence costs |
|---|---|---|---|
| CODE | | | |
| SAMPLE_DATA | | | |
| OUTPUT_SAMPLE | | | |
| DOCUMENT / INTERVIEW | | | |

## Contents

1. [Processing Inventory](#1-processing-inventory)
2. [Queries, Stored Procedures, and Functions](#2-queries-stored-procedures-and-functions)
3. [Core Processing Pipelines](#3-core-processing-pipelines)
4. [File Formats Crossing the Boundary](#4-file-formats-crossing-the-boundary)
5. [Business Rules](#5-business-rules)
6. [Action-to-Effect Traceability](#6-action-to-effect-traceability)
7. [Transactions, Partial Failure, and Recovery](#7-transactions-partial-failure-and-recovery)
8. [Risks](#8-risks)
9. [Assumptions, Unknowns, and Questions](#9-assumptions-unknowns-and-questions)

---

## 1. Processing Inventory

| Process | Trigger | Entry point | Reads | Writes | Evidence |
|---|---|---|---|---|---|

## 2. Queries, Stored Procedures, and Functions

| Name | Kind | Purpose | Called from | Evidence |
|---|---|---|---|---|

<!-- For anything the application depends on, give the signature and the logic, not
     the name alone. A replacement has to reproduce it. -->

## 3. Core Processing Pipelines

### {{PIPELINE_NAME}}

- **Trigger:**
- **Reads:**
- **Writes:**
- **Transaction boundary:**

<!-- Required diagram, one per pipeline. -->

```mermaid
flowchart TD
```

| Step | What it does | Condition | Effect | Evidence |
|---:|---|---|---|---|

<!-- Where a step hard-codes a value - a product code, a category number, a split -
     say so and quote it. Hard-coded business logic is what a migration must move
     into data, and it cannot move what the document did not surface. -->

## 4. File Formats Crossing the Boundary

<!-- One block per file. A format stated from code alone is INFERRED and says so;
     a format settled against a real sample is EXTRACTED and cites the sample. -->

### {{FILE_NAME}}

- **Direction:** inbound / outbound
- **Encoding:**
- **Evidence class behind this format:** SAMPLE_DATA / OUTPUT_SAMPLE / CODE only
- **Status:** EXTRACTED / INFERRED

| Position or column | Length | Content | Evidence |
|---|---:|---|---|

### Column mapping on write

<!-- Where a row is assembled from several sources - the file, a master, a counter,
     a constant - map every destination column to where its value came from. This
     is the table a replacement implements against. -->

| Destination column | Value from |
|---|---|

## 5. Business Rules

<!-- BR-{DOMAIN}-nn. Domains are declared in identifier-scheme.yaml; extend the
     list rather than filing a rule under a near miss. -->

| ID | Rule | Condition | Outcome | Status | Evidence |
|---|---|---|---|---|---|

## 6. Action-to-Effect Traceability

| Event | Form | SQL operation | Target |
|---|---|---|---|

## 7. Transactions, Partial Failure, and Recovery

<!-- Where a transaction starts and ends, what an error leaves behind, and whether
     anything can be re-run. Say plainly where a partial failure has no recovery
     path - that is a finding, not an omission. -->

## 8. Risks

| ID | Risk | Severity | Detail | Mitigation |
|---|---|---|---|---|

<!-- RA-nn for application-layer risks. Severity HIGH/MEDIUM/LOW, always. -->

## 9. Assumptions, Unknowns, and Questions

### Assumptions

| ID | Assumption | If wrong |
|---|---|---|

### Unknowns

| ID | Unknown | Why it matters | What would settle it | Who can settle it |
|---|---|---|---|---|

### Questions

| ID | Question | Blocks | Owner |
|---|---|---|---|
