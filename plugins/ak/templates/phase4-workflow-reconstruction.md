# {{APP_ID}} — Phase 4: Workflow Reconstruction

<!--
  Characteristic claim: what an operator does end to end, and when.

  Code gives the path. It cannot give the actor, the timing, or the frequency -
  those need a DOCUMENT or an INTERVIEW, and without them these are code paths
  rather than workflows. Say which you have.

  Every WF- carries a diagram, at least one BR-, and traceability rows covering
  every step. A workflow with none of those is a heading.

  Delete these comment blocks as you fill the document in.
-->

## Naming Convention

Object, table and file names are the **production names**, unchanged. JP-primary
with a Romaji alias where they are Japanese. Never translate.

| Japanese (production) | Romaji alias | Role |
|---|---|---|

## Source Coverage

| Evidence class | Supplied | Scope | What its absence costs |
|---|---|---|---|
| CODE | | | |
| UI_DEFINITION | | | |
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
     For this phase: a workflow IS a shape. Draw every one of them - actors on a
     sequence diagram, with the handoffs and the waiting between them visible. A
     workflow described only in prose is one nobody will check against reality.
-->

## Contents

1. [Workflow Inventory](#1-workflow-inventory)
2. [Workflow Map](#2-workflow-map)
3. [End-to-End Workflows](#3-end-to-end-workflows)
4. [Use-Case Coverage](#4-use-case-coverage)
5. [Cross-System Handoffs](#5-cross-system-handoffs)
6. [Operational Timing and Ordering Dependencies](#6-operational-timing-and-ordering-dependencies)
7. [Exceptions, Recovery, and Manual Controls](#7-exceptions-recovery-and-manual-controls)
8. [Observations and Risks](#8-observations-and-risks)
9. [Assumptions, Unknowns, and Questions](#9-assumptions-unknowns-and-questions)

---

## 1. Workflow Inventory

| ID | Name | Actor | Trigger | Final output | Evidence coverage |
|---|---|---|---|---|---|

<!-- `Actor` and `Trigger` are USAGE claims. Without a DOCUMENT or INTERVIEW they
     read "not established" - a plausible actor is worse than an admitted gap. -->

## 2. Workflow Map

<!-- Required diagram: the workflows and how they depend on one another, including
     any ordering dependency from §6. -->

```mermaid
flowchart TD
```

## 3. End-to-End Workflows

### {{WF_ID}} — {{WORKFLOW_NAME}}

- **Actor and business objective:**
- **Trigger:**
- **Preconditions:**
- **Success outcome:**
- **Failure or retry outcome:**

<!-- Required diagram, one per workflow. A sequence diagram where actors hand off
     to each other; a flow diagram where the shape is a decision tree. -->

```mermaid
sequenceDiagram
```

| Step | User action | Screen | Processing | Data or file | Output | Evidence |
|---:|---|---|---|---|---|---|

**Rules**

| ID | Rule | Evidence |
|---|---|---|

<!-- BR-W{nnn}-nn for a rule that holds only inside this workflow; promote it to a
     BR-{DOMAIN} form if it turns out to be general. -->

## 4. Use-Case Coverage

<!-- Where a use case is not covered, say whether it is absent from the application
     or absent from the evidence. They are different findings. -->

| Use case | Covered by | Status | Evidence or reason for N/A |
|---|---|---|---|
| Create | | | |
| Read / inquiry | | | |
| Update | | | |
| Delete or cancel | | | |
| Approval | | | |
| Reporting | | | |
| Import | | | |
| Export | | | |

## 5. Cross-System Handoffs

| Handoff | Direction | Mechanism | Counterparty | Failure mode | Evidence |
|---|---|---|---|---|---|

## 6. Operational Timing and Ordering Dependencies

<!-- The dependency worth hunting: one workflow that must run before another, where
     violating the order produces a WRONG RESULT rather than an error. In the
     reference set a monthly export silently wrote an empty file because the sync
     that sets its filter flag had not run. Name every one you find, and mark it in
     the map in §2. -->

| Must run | Before | Why | What happens if violated | Evidence |
|---|---|---|---|---|

### Daily and periodic rhythm

| When | Activity | Workflow | Evidence class behind the timing |
|---|---|---|---|

<!-- Timing is a USAGE claim. A clock time taken from a document or an interview is
     evidence; one inferred from a file name is not. -->

## 7. Exceptions, Recovery, and Manual Controls

<!-- What an operator does when a step fails, and what has no recovery path at all.
     A deletion with no backup, a counter that leaves gaps, a partial commit - these
     are the findings a migration plan is built on. -->

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

<!-- RW-nn for workflow and operational risks. Severity always. -->

## 9. Assumptions, Unknowns, and Questions

### Assumptions

<!-- `AS-nn`. A belief the phase relies on that the evidence does not
     establish. `If wrong` says what in this document stops holding, which is
     what makes it worth writing down rather than a disclaimer. -->

| ID | Assumption | If wrong |
|---|---|---|

### Unknowns

<!-- `UK-Wnn` - Workflow, the letter this phase owns. Each names the evidence
     class that would close it, so the operator is told what to fetch rather than
     that something is missing. -->

| ID | Unknown | Why it matters | What would settle it | Who can settle it |
|---|---|---|---|---|

### Questions

| ID | Question | Blocks | Owner |
|---|---|---|---|
