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

## Contents

1. [Workflow Inventory](#1-workflow-inventory)
2. [Workflow Map](#2-workflow-map)
3. [End-to-End Workflows](#3-end-to-end-workflows)
4. [Use-Case Coverage](#4-use-case-coverage)
5. [Cross-System Handoffs](#5-cross-system-handoffs)
6. [Operational Timing and Ordering Dependencies](#6-operational-timing-and-ordering-dependencies)
7. [Exceptions, Recovery, and Manual Controls](#7-exceptions-recovery-and-manual-controls)
8. [Risks](#8-risks)
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

## 8. Risks

| ID | Risk | Severity | Detail | Mitigation |
|---|---|---|---|---|

<!-- RW-nn for workflow and operational risks. Severity always. -->

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
