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
     own vocabulary, which a migration has to decide what to do with.

     Include here any object the application addresses by a name it BUILDS AT RUN
     TIME. A06 has three: a staging table named `"受" & Format(date,"yyyymmdd")`, a
     query deleted and recreated each run, and four reports opened as
     `"受注数調整リスト" & <option group>`. None of those names is written down
     anywhere, so no reference search can find them and every one of them appears in
     the catalogue's "referenced by nothing" list while being in daily use. Where
     this pattern exists, say so here and quote the line - it is the sharpest case of
     rule EC-05 in the whole kit, and a reader who does not know about it will read
     an unreferenced-object list as a deletion list. -->

### 2.4 What changed in the database between acquisitions

<!-- Only when it did. An operator who cleans the application between runs leaves a
     gap no reader can close: A06's frontend held 188 table objects, then 32, then
     28, and a reader comparing two bundles would find 140 objects missing with no
     explanation in either document.

     Record, per change: the date, what was removed, and WHAT WAS MEASURED BEFORE IT
     WAS REMOVED. Then state that usage is not established - absence of a reference
     is unreachability, not disuse (EC-05), and 2.3 above is the reason that is not
     a formality. Name who decided. Do not write that the removed objects were dead
     unless somebody is on record saying so. -->

| Date | Removed | Measured before removal |
|---|---|---|

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

### Scope

<!-- Required, and usually one short paragraph saying that nothing here decides it.

     A scope claim needs TARGET_INTENT and nothing else (rule EC-07): no reading of
     the legacy application establishes what the replacement should contain. So this
     section either cites the project's TARGET_INTENT records, or says that none has
     been supplied and that no table, screen or feed above is marked in or out of
     scope. Saying nothing is what lets a reader take an analyst's emphasis for a
     decision. -->

### Questions

<!-- `Q<n>`, matching `identifier-scheme.yaml` - a bare Q and up to three digits, so
     `Q12`, not `Q-APP-12`. Goes to a stakeholder. When answered, the answer becomes
     INTERVIEW evidence with its own id and the question is marked resolved against
     it. -->

| ID | Question | Blocks | Owner |
|---|---|---|---|

---

## Provenance note

<!-- Only when something about the acquisition itself qualifies what is above: an
     export produced by a tool version older than the kit's, a database copy that is
     not the live one, a route that answered a question the other route could not.

     A06's case: both export packages were written by a pre-2.12 `ExportAccessObjects`,
     so neither manifest carries `exporter_version=` and the backend's still printed a
     gate removed two releases earlier. The effect on the analysis was nil and the note
     was written anyway, because "no effect" is a finding a reader is entitled to check
     rather than a reason for silence. -->

## Evidence Register

<!-- Every claim above resolves here. Status is EXTRACTED, INFERRED or AMBIGUOUS;
     an INFERRED claim carries its confidence and never loses the label. -->

| Claim | Status | Class | Source | Location | Confidence |
|---|---|---|---|---|---:|
