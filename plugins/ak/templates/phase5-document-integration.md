# {{APP_ID}} — Phase 5: Document Integration

<!--
  Characteristic claim: what the business says the system does, and where that
  differs from the code.

  This phase was treated as optional and it is the opposite. Everything the earlier
  phases could not say - what a table is for, who uses a screen, how often, why a
  rule exists, what happens outside the software - lives here or nowhere. DOCUMENT
  evidence is required; without it the phase is BLOCKED rather than degraded,
  because there is nothing for it to do.

  Its widest section is the one that used to be missing entirely: the landscape
  around the application. An application analysed without its neighbours produces a
  migration plan that discovers them at cut-over.

  Rule EC-04 governs every disagreement: a document claim contradicted by code
  produces TWO observations and one DISC- entry. Neither side wins silently.

  Delete these comment blocks as you fill the document in.
-->

## Naming Convention

Organisation, system, table and file names are the **production names**, unchanged.
JP-primary with a Romaji alias where they are Japanese. Never translate.

| Japanese (production) | Romaji alias | Kind |
|---|---|---|

## Source Coverage

| Evidence class | Supplied | Scope | What its absence costs |
|---|---|---|---|
| DOCUMENT | | | |
| INTERVIEW | | | |

## Contents

1. [Document Inventory and Translation Coverage](#1-document-inventory-and-translation-coverage)
2. [Business Context](#2-business-context)
3. [Organization and Stakeholders](#3-organization-and-stakeholders)
4. [Operational Flow](#4-operational-flow)
5. [System Landscape](#5-system-landscape)
6. [Network Architecture](#6-network-architecture)
7. [Inter-System Data Interfaces](#7-inter-system-data-interfaces)
8. [Operational Function Catalog](#8-operational-function-catalog)
9. [Extracted Business Rules](#9-extracted-business-rules)
10. [Document-to-System Alignment](#10-document-to-system-alignment)
11. [Unresolved Mismatches and Stakeholder Questions](#11-unresolved-mismatches-and-stakeholder-questions)

---

## 1. Document Inventory and Translation Coverage

| Document | Language | Pages / sheets used | Business scope | Evidence |
|---|---|---|---|---|

<!-- A document that could not be read - no text layer, unsupported format - is
     listed with that status, not omitted. It is a gap an operator can close. -->

### Terminology

<!-- Where a Japanese term carries business meaning a gloss would lose, keep the
     term and explain it. This is where a replacement team learns the vocabulary. -->

| Term | Reading | What it means in this business |
|---|---|---|

## 2. Business Context

<!-- What this organisation does, at what scale, for whom. The numbers that make
     the system's constraints legible: sites served, daily volume, cut-off times. -->

| Dimension | Value | Evidence |
|---|---|---|

## 3. Organization and Stakeholders

<!-- Required diagram: the departments, and which uses which system. A migration
     plan needs to know whose work changes. -->

```mermaid
graph TD
```

| Department | What it does | Systems it uses | Evidence |
|---|---|---|---|

## 4. Operational Flow

<!-- What happens outside the software: goods, paper, people, sites. The system
     exists to serve this, and a replacement that models only the data model will
     reproduce the schema and miss the business. Omit the section only if the
     documents genuinely describe none of it - and say so if you do. -->

## 5. System Landscape

<!-- Every neighbouring system, not only the ones this application talks to. State
     the canonical source and its date: a landscape read off one diagram is only as
     current as that diagram. -->

| ID | System | Role | Relationship to {{APP_ID}} | Evidence |
|---|---|---|---|---|

<!-- Where two families of system have similar names and opposite directions - one
     receiving from customers, one issuing to suppliers - state the distinction
     explicitly. Conflating them is a mistake that survives into design. -->

## 6. Network Architecture

<!-- Required diagram: hosts, databases, shares, and what reaches what. Record the
     database engine actually in use, from evidence, not from the surrounding
     convention - the reference set carried a wrong engine for a whole phase. -->

```mermaid
graph TB
```

| Host | Address | Runs | Used by | Evidence |
|---|---|---|---|---|

## 7. Inter-System Data Interfaces

<!-- Required diagram plus two catalogues. These are the most reused artifacts this
     phase produces: the boundary map is built from them, and so is the migration's
     interface inventory. -->

```mermaid
flowchart LR
```

### 7.1 Inbound files

| ID | Name | Format | Source system | Path | Cadence | Evidence |
|---|---|---|---|---|---|---|

### 7.2 Outbound files

| ID | Name | Format | Destination | Path | Cadence | Evidence |
|---|---|---|---|---|---|---|

<!-- d0n and r0n identifiers, allocated here and cited by Phase 4 and the boundary
     map. An interface whose source or destination is recorded as "unknown" in the
     documents keeps that word - it is a real finding about the estate. -->

## 8. Operational Function Catalog

<!-- The functions as the business lists them, with cycle and timing. This is where
     a function the documents call unused, dangerous, or of unknown purpose gets
     recorded - each is a question for §11, and each is a scoping decision. -->

| No. | Function | Cycle | Timing | Status per the documents | Evidence |
|---|---|---|---|---|---|

## 9. Extracted Business Rules

<!-- BR-DOC-nn: a rule the documents state. It may or may not match the code; §10
     is where that is settled. Do not merge a document rule into a code-derived
     BR- from Phase 3 - keep both until they are reconciled. -->

| ID | Rule | Source document | Evidence |
|---|---|---|---|

## 10. Document-to-System Alignment

### 10.1 Confirmed

| Document claim | Code verification | Status |
|---|---|---|

### 10.2 Discrepancies

<!-- DISC-nn. Each names the document's claim AND the observed behaviour, both
     cited, with a severity. Neither side is silently preferred (rule EC-04). -->

| ID | Document says | Code does | Severity | Consequence | Evidence |
|---|---|---|---|---|---|

### 10.3 In the documents, absent from the code

| Item | Where documented | Code status | What it means |
|---|---|---|---|

### 10.4 In the code, absent from the documents

<!-- Usually the more interesting direction: undocumented behaviour a replacement
     would omit without knowing it existed. -->

| Item | Where in the code | Why it matters |
|---|---|---|

## 11. Unresolved Mismatches and Stakeholder Questions

### Unknowns

| ID | Unknown | Why it matters | What would settle it | Who can settle it |
|---|---|---|---|---|

### Questions

| ID | Question | Blocks | Owner |
|---|---|---|---|

### Risks

| ID | Risk | Severity | Detail | Mitigation |
|---|---|---|---|---|

<!-- RS-nn for security and compliance risks surfaced by the documents. -->
