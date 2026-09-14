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

<!-- WHO READS THIS, AND WHAT THAT COSTS YOU

     A reference file is read by an agent. A phase document is read by a developer who
     has to rebuild the system, and they read it once, under time pressure, looking for
     what they must not get wrong. Two habits follow:

     Open with what they must not get wrong. A short numbered list, each item pointing at
     the section that proves it. A06's Phase 2 was correct and unusable before it had one:
     the fact that re-running the morning import destroys the quantities staff typed the
     night before was in the document, four sections deep, in prose.

     Diagram a mechanism; tabulate a set; write prose only for what neither can hold.
     One required diagram per phase is a floor, not a budget. Reach for one whenever the
     thing being described has a shape: an order of steps, a cycle, a lifecycle with a
     failure branch, a fan-out from one object to many, or three artefacts that should
     agree and do not. A06's Phase 2 carries five and is shorter than the four-diagram
     draft it replaced, because each one removed a paragraph that was describing a picture.

     Mermaid renders, or it is not evidence a reader can see. Check it - `mmdc -i x.mmd -o
     x.svg` - before publishing. A sequence diagram reads better than a flowchart for
     anything with an actor and an order; a flowchart with a red-filled node is the
     cheapest way to say "this is where it goes wrong".

     Keep the document's own revision history out of it. How many drafts a figure went
     through is a fact about the analysis, not about the application, and a developer
     reading once does not need it: A06's Phase 2 carried a paragraph explaining that a
     count had been "wrong twice before it was right", naming all three numbers and both
     causes, and it was the hardest paragraph in the document to read.

     That history belongs in `BACKLOG.md` and in the commit. What the document keeps is
     the part a reader could otherwise get wrong - what a figure counts and what it
     excludes, stated plainly, so that a recount giving a different number is explained
     before it happens rather than after:

         A recount can legitimately give a different number, so two exclusions are worth
         stating. `DoCmd.OpenQuery` opens a query, not a screen: its 3 edges are excluded
         here, and counting them gives 39.

     The exception is a claim an earlier PUBLISHED phase made and this one corrects. That
     is errata, it has its own register and its own `E-nn` identifier, and it is owed to
     the reader because they may have acted on the earlier statement. A draft nobody
     outside the run ever saw owes nothing.
     For this phase: the thing with a shape is the pipeline. A sequence diagram per
     core pipeline, with the failure branch drawn rather than described, is worth
     more than any amount of step-by-step prose - and a table of a file's fields is
     worth more than a paragraph about them.
-->

## Contents

1. [Processing Inventory](#1-processing-inventory)
2. [Queries, Stored Procedures, and Functions](#2-queries-stored-procedures-and-functions)
3. [Core Processing Pipelines](#3-core-processing-pipelines)
4. [File Formats Crossing the Boundary](#4-file-formats-crossing-the-boundary)
5. [Business Rules](#5-business-rules)
6. [Action-to-Effect Traceability](#6-action-to-effect-traceability)
7. [Transactions, Partial Failure, and Recovery](#7-transactions-partial-failure-and-recovery)
8. [Observations and Risks](#8-observations-and-risks)
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

## 8. Observations and Risks

### Observations

<!-- `OB-nn`. A property worth carrying forward that is not yet a rule or a risk.
     Each cites evidence. An observation nobody can act on yet is still worth an
     identifier, because the phase that can act on it needs to cite something. -->

| ID | Observation | Evidence |
|---|---|---|

### Risks

| ID | Risk | Severity | Detail | Mitigation |
|---|---|---|---|---|

<!-- RA-nn for application-layer risks. Severity HIGH/MEDIUM/LOW, always. -->

## 9. Assumptions, Unknowns, and Questions

### Carried forward from earlier phases

<!-- REQUIRED in every phase after the first, and written BEFORE this phase's own
     unknowns and questions.

     List every `UK-` and `Q` an earlier phase allocated and still open, and give each
     a status:

       resolved   - this phase's evidence answers it. Cite the evidence id, and say
                    what the answer is. Mark it resolved in the register too.
       advanced   - not closed, but something changed. Say what.
       unchanged  - nothing this phase read bears on it. Still say so.
       duplicate  - it asks what another identifier already asks. Name that one and
                    stop carrying both.

     A06's Phase 2 skipped this section and allocated `Q108`, which asks what Phase 1's
     `Q103` already asked of the same owner about the same file. Two questions to one
     person about one thing is the cheapest kind of waste to avoid and the easiest to
     create.

     Before allocating any new `UK-` or `Q`, read this list. An unknown that is already
     open does not need a second identifier; an unknown this phase can close does not
     need carrying. -->

| ID | Raised in | Status | What this phase establishes |
|---|---|---|---|

### Assumptions

<!-- `AS-nn`. A belief the phase relies on that the evidence does not
     establish. `If wrong` says what in this document stops holding, which is
     what makes it worth writing down rather than a disclaimer. -->

| ID | Assumption | If wrong |
|---|---|---|

### Unknowns

<!-- `UK-Lnn` - Logic, the letter this phase owns. Each names the evidence
     class that would close it, so the operator is told what to fetch rather than
     that something is missing. -->

| ID | Unknown | Why it matters | What would settle it | Who can settle it |
|---|---|---|---|---|

### Questions

| ID | Question | Blocks | Owner |
|---|---|---|---|
