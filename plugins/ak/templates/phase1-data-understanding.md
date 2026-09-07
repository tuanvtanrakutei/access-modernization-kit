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

<!-- The inventory is `{{APP_ID}}_DataCatalogue.md`, generated from the bundle:
     every table, every column, every index, the declared relationships. Do not
     restate it here. Measured against A05's bundle, the first run's narrative named
     20 of 118 tables, 4 of 328 distinct column names and 5 of 77 queries - every
     aggregate figure correct, and almost nothing that was counted named (A14). A
     narrative cannot carry 1,055 columns, and a second copy carrying a sixth of
     them is worse than a citation, because it reads like the whole set.

     Quote every figure below from the catalogue instead of counting again. Two
     counts of one thing is how E-07 reached publication - 37 unreferenced objects
     published against 26 actual - and the reconciliation nobody has written yet.

     What the data *means* is not here and is not dropped: it is section 3, which
     already asks for the entities the business runs on and what a replacement must
     preserve. This section is the shape of the set and the rule behind a grouping;
     section 3 is the claim about what any of it is for. -->

### 2.1 Shape of the set

| | Count | Read from |
|---|---:|---|
| Tables | | `{{APP_ID}}_DataCatalogue.md` |
| Columns | | `{{APP_ID}}_DataCatalogue.md` |
| Without a primary key | | `{{APP_ID}}_DataCatalogue.md` |
| Business meaning recorded | | `input/decisions/meanings.yaml` |
| Business meaning not established | | the catalogue's marked cells |

<!-- The last two rows are the honest half of this section and must never be omitted
     to make the phase look complete. The second set is not listed here either: `$ak
     meanings` writes it, ranked by who writes the table and how many objects name
     it, so an operator can start somewhere rather than at a blank page of 1,176. -->

### 2.2 By role

<!-- Grouping by name prefix or connect string is an INTERPRETATION, not something
     the database declares. Say which rule produced the grouping and label the
     result as interpreted. A `role` a person actually sourced lives in
     `meanings.yaml` and the catalogue prints it; this section is for the rule that
     produced a grouping, not for a second copy of the rows. -->

| Role | Tables | Without a primary key | How they were identified | Interpreted or sourced |
|---|---:|---:|---|---|

### 2.3 Naming conventions the application uses

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
