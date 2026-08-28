# {{APP_ID}} — Phase 6: Synthesis

<!--
  Characteristic claim: one decision-grade account, with its corrections.

  Phase 6 CONSOLIDATES. Every BR-, RD-, RA-, RW-, RS-, UK- and AS- here must
  already exist in a prior phase, or be an E- entry explaining why it is new
  (rule ID-04). A finding that first appears in Phase 6 with no errata behind it
  is a finding that was invented rather than synthesised.

  The errata table comes first because it governs how everything before it should
  be read. It is not an appendix and not an admission - it is the mechanism that
  lets a reader trust the rest.

  Delete these comment blocks as you fill the document in.
-->

## Errata

<!-- Rendered from {{APP_ID}}_Errata.json. Every entry names what was said, what is
     true, which sections carried it, and what settled it. See
     specifications/errata-contract.yaml. -->

| # | Original | Corrected | Affected sections | Cause | Source |
|---|---|---|---|---|---|

<!-- If this run corrected nothing, say "No claim published by Phases 1-5 has been
     superseded" rather than deleting the section - an absent errata table and an
     empty one read very differently. -->

## Naming Convention

Table, object, system and file names are the **production names**, unchanged.
JP-primary with a Romaji alias where they are Japanese. Never translate.

| Japanese (production) | Romaji alias | Role |
|---|---|---|

## Executive Summary

<!-- For a reader who will read nothing else: what the system is, what it anchors,
     where its design centre of gravity actually is, the highest risk, and the
     largest unknown. Then the three things the replacement team must act on first.
     Say what the evidence did NOT cover, here, not only in an appendix. -->

## Contents

1. [System Overview](#1-system-overview)
2. [Key Entities & Data Model](#2-key-entities--data-model)
3. [Screens & Functions](#3-screens--functions)
4. [Business Rules](#4-business-rules)
5. [End-to-End Workflows](#5-end-to-end-workflows)
6. [Risks / Legacy Issues](#6-risks--legacy-issues)
7. [Assumptions / Unknowns](#7-assumptions--unknowns)
8. [Recommendations & Migration Roadmap](#8-recommendations--migration-roadmap)
- [Appendix A — Cross-Reference Index](#appendix-a--cross-reference-index)
- [Appendix B — Glossary](#appendix-b--glossary)

---

## 1. System Overview

<!-- Scope, scale, stack, the operating rhythm, and what is explicitly out of
     scope. Where the rhythm is enforced only by staff knowledge, say so - that is
     a migration requirement disguised as a habit. -->

## 2. Key Entities & Data Model

<!-- Required diagram: the entities and the transaction types, consolidated. -->

```mermaid
flowchart LR
```

<!-- Then the reduction a migration actually needs: of N tables, how many are
     transaction, master, code, work scratch, and parallel-channel duplicates, and
     what to do with each. Reading the schema directly leads to over-counting. -->

| Prefix / group | Role | Count | Migration treatment |
|---|---|---|---|

## 3. Screens & Functions

| Category | Count | Representative objects |
|---|---:|---|

<!-- Include the objects recorded as unused, dangerous, or of unknown purpose, with
     the action each needs. They are scoping decisions, and Phase 6 is where they
     are put in front of someone who can make them. -->

## 4. Business Rules

<!-- The consolidated register, grouped by domain. Every row already exists in a
     prior phase and cites it. This is the section a vendor implements against, so
     a rule with no citation is worse than an absent rule. -->

### {{DOMAIN}}

| ID | Rule | Source phase | Evidence |
|---|---|---|---|

## 5. End-to-End Workflows

<!-- Required diagram: the consolidated workflow map, and a second showing
     cross-workflow data flow. Mark any ordering dependency from Phase 4 §6. -->

```mermaid
flowchart TD
```

| ID | Workflow | Trigger | Outcome | Key rules |
|---|---|---|---|---|

## 6. Risks / Legacy Issues

<!-- Four registers, each with severity and a mitigation for the replacement. -->

### Data and integrity (RD)

| ID | Risk | Severity | Detail | Mitigation |
|---|---|---|---|---|

### Application layer (RA)

| ID | Risk | Severity | Detail | Mitigation |
|---|---|---|---|---|

### Workflow and operations (RW)

| ID | Risk | Severity | Detail | Mitigation |
|---|---|---|---|---|

### Security and compliance (RS)

| ID | Risk | Severity | Detail | Mitigation |
|---|---|---|---|---|

### Critical path

<!-- The short list that blocks migration if unresolved. Say why each blocks, not
     only that it is severe. -->

| # | Issue | Why it blocks |
|---|---|---|

## 7. Assumptions / Unknowns

### Unknowns, by originating phase

| ID | Item | Why it matters | What would settle it | Owner |
|---|---|---|---|---|

### Assumptions

| ID | Assumption | Validation |
|---|---|---|

### Evidence coverage

<!-- Per area: what was extracted, what was inferred, what stayed ambiguous, and
     which evidence class was missing. This is the honest summary of what this run
     could and could not establish, and it belongs in the synthesis rather than
     only in the QA report. -->

| Area | Extracted | Inferred | Ambiguous | Evidence class missing |
|---|---:|---:|---:|---|

## 8. Recommendations & Migration Roadmap

<!-- The forward-looking half, and the reason a synthesis exists at all. Without it
     Phase 6 is a summary of five documents a reader could have read themselves. -->

### Strategic recommendations

<!-- Each states the finding it rests on. A recommendation with no finding behind
     it is an opinion. -->

### Phased roadmap

```mermaid
gantt
```

### Module prioritisation

| Priority | Module | Why first |
|---|---|---|

### What to discard

<!-- As important as what to keep, and easier to get agreement on early. -->

| Item | Why |
|---|---|

### What must be preserved exactly

<!-- Behaviour visible to a downstream system or an external party, which must
     match byte for byte during any parallel run. -->

| Item | Why |
|---|---|

---

## Appendix A — Cross-Reference Index

<!-- Every section here back to the phase and section that established it. This is
     what lets a reader who disagrees with a conclusion find the evidence for it. -->

| Phase 6 section | Established in |
|---|---|

## Appendix B — Glossary

| Term | Reading | Meaning |
|---|---|---|
