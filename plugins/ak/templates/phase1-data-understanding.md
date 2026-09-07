# {{APP_ID}} — Phase 1: Data Understanding

<!--
  Characteristic claim of this phase: what the data is, AND what it means to the
  business. The second half is the one that gets lost. A schema yields an
  inventory; only a document, an interview or an operator's declaration yields a
  meaning (evidence-classes.yaml, rule EC-01).

  The rule this phase is judged by: every table is either given a meaning with a
  citation, or listed in §2.3 as meaning-not-established. There is no third state,
  and a table quietly left out of both is the defect this template exists to stop.

  Delete these comment blocks as you fill the document in.
-->

## Naming Convention

<!-- Generated from the bundle's own object names, not written by hand. -->

Table and object names are the **production names**. Where they are Japanese the
document is JP-primary: the Japanese name is authoritative and a Romaji alias
follows in parentheses for cross-reference. **Never translate a production name** —
a translation reads like a definition and is not one.

| Japanese (production) | Romaji alias | Role |
|---|---|---|

## Source Coverage

<!-- Per evidence class: what was available, and what its absence costs THIS phase.
     A gap that is named is a gap; a gap that is unnamed is a defect (rule EC-06). -->

| Evidence class | Supplied | Scope | What its absence costs |
|---|---|---|---|
| SCHEMA | | | |
| CODE | | | |
| DOCUMENT | | | |
| INTERVIEW | | | |

## Contents

1. [System and Database Overview](#1-system-and-database-overview)
2. [Table and Column Inventory](#2-table-and-column-inventory)
3. [Key Entities and Business Meaning](#3-key-entities-and-business-meaning)
4. [Relationships and Integrity Controls](#4-relationships-and-integrity-controls)
5. [Queries, Stored Procedures, and Functions](#5-queries-stored-procedures-and-functions)
6. [Shared Databases and External Data Dependencies](#6-shared-databases-and-external-data-dependencies)
7. [Observations and Data Risks](#7-observations-and-data-risks)
8. [Assumptions, Unknowns, and Questions](#8-assumptions-unknowns-and-questions)

---

## 1. System and Database Overview

<!-- What the system is for, in the business's terms; the stack; the scale. -->

| Component | Detail |
|---|---|
| Front-end | |
| Back-end | |
| Connection | |
| Encoding | |
| Totals | tables · columns · indexes · declared relationships |

## 2. Table and Column Inventory

### 2.1 By role

<!-- Grouping by name prefix or connect string is an INTERPRETATION, not something
     the database declares. Say which rule produced the grouping and label the
     result as interpreted. -->

| Role | Tables | Without a primary key | How they were identified |
|---|---:|---:|---|

### 2.2 Per table

<!-- One row per table. `Business meaning` is a MEANING claim: it needs a DOCUMENT
     or INTERVIEW citation, or it does not go here. Do not paraphrase the table's
     own name into the meaning column - rule EC-03. -->

| Table | Cols | Primary key | Business meaning | Evidence |
|---|---:|---|---|---|

### 2.3 Meaning not established

<!-- Every table absent from §2.2 appears here. This list is the honest half of the
     inventory and must never be omitted to make the phase look complete. Say which
     evidence class would settle each - that is what the operator goes and fetches. -->

| Table | Shape | What would settle it |
|---|---|---|

### 2.4 Naming conventions the application uses

<!-- Prefixes, suffixes, dated snapshots, numbered duplicates - the application's
     own vocabulary, which a migration has to decide what to do with. -->

## 3. Key Entities and Business Meaning

<!-- The handful of entities the business actually runs on. For each: identity,
     the attribute groups that carry business rules, and what a replacement must
     preserve. An entity here without a DOCUMENT or INTERVIEW citation is a
     structural claim wearing a business label. -->

### {{ENTITY_NAME}}

| Attribute group | Columns | Why it matters |
|---|---|---|

### Entity relationship diagram

<!-- Required. Core entities and their cardinalities; not every table. -->

```mermaid
erDiagram
```

## 4. Relationships and Integrity Controls

<!-- Keep declared and enforced-elsewhere strictly apart. A relationship the
     database declares is a fact; one enforced by VBA is a reading of code and is
     labelled INFERRED with its source. -->

### 4.1 Declared

| From | Column | To | Column | Cardinality | Meaning |
|---|---|---|---|---|---|

### 4.2 Enforced outside the schema

| From | Column | To | Where it is enforced | Evidence | Status |
|---|---|---|---|---|---|

### 4.3 Integrity that is absent

<!-- Missing keys, absent NOT NULL, orphan risk. State the consequence for
     migration, since this is where a target schema will surface dirty data. -->

## 5. Queries, Stored Procedures, and Functions

| Name | Kind | Purpose | Evidence |
|---|---|---|---|

<!-- Give the signature and the logic of any function the application depends on
     rather than only naming it. -->

## 6. Shared Databases and External Data Dependencies

<!-- Linked tables, other databases, replication, drive mappings. Each is a
     boundary Phase 5 will catalogue as d0n/r0n; name the ones visible from here. -->

| Dependency | Direction | Reached how | Resolvable in this environment | Evidence |
|---|---|---|---|---|

## 7. Observations and Data Risks

### Observations

<!-- OB-nn. A property worth carrying forward that is not yet a rule or a risk.
     Each cites evidence. -->

| ID | Observation | Evidence |
|---|---|---|

### Risks

<!-- RD-nn, severity HIGH/MEDIUM/LOW, and a mitigation or an explicit "none
     proposed". A risk without a severity cannot be prioritised. -->

| ID | Risk | Severity | Consequence at migration | Mitigation |
|---|---|---|---|---|

## 8. Assumptions, Unknowns, and Questions

### Assumptions

| ID | Assumption | If wrong |
|---|---|---|

### Unknowns

<!-- UK-Dnn. Each names the evidence class that would close it, so the operator is
     told what to fetch rather than that something is missing. -->

| ID | Unknown | Why it matters | What would settle it | Who can settle it |
|---|---|---|---|---|

### Questions

<!-- Q-n. Goes to a stakeholder. When answered, the answer becomes INTERVIEW
     evidence with its own id and the question is marked resolved against it. -->

| ID | Question | Blocks | Owner |
|---|---|---|---|

---

## Evidence Register

<!-- Every claim above resolves here. Status is EXTRACTED, INFERRED or AMBIGUOUS;
     an INFERRED claim carries its confidence and never loses the label. -->

| Claim | Status | Class | Source | Location | Confidence |
|---|---|---|---|---|---:|
