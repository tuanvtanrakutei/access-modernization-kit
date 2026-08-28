# {{APP_ID}} — Phase 2: Screen & Form Analysis

<!--
  Characteristic claim: what each screen is, how it is reached, and who uses it.
  Definition text answers the first two. It cannot answer the third, and it cannot
  see layout, tab grouping or which controls an operator can actually see - those
  need a SCREENSHOT, and purpose needs a DOCUMENT or INTERVIEW.

  Two rules this phase is judged by:

  1. An object no code path opens is UNREACHABLE, not unused (rule EC-05). Say
     which routes were not examined - the navigation pane, custom menus, another
     copy of the frontend - every time the figure is quoted.
  2. `F-nnn` is an index, not an identifier. For Japanese-named objects it tells a
     reader nothing on its own, so the object's real name appears beside it
     everywhere, and every downstream key uses the name rather than the index.

  Delete these comment blocks as you fill the document in.
-->

## Naming Convention

Object names are the **production names**, unchanged. Where they are Japanese the
document is JP-primary, with a Romaji alias for cross-reference. Never translate.

| Japanese (production) | Romaji alias | Kind |
|---|---|---|

## Source Coverage

| Evidence class | Supplied | Scope | What its absence costs |
|---|---|---|---|
| UI_DEFINITION | | | |
| CODE | | | |
| SCREENSHOT | | | |
| DOCUMENT / INTERVIEW | | | |

## Contents

1. [Screen, Form, and Report Inventory](#1-screen-form-and-report-inventory)
2. [Navigation Map](#2-navigation-map)
3. [Per-Screen Analysis](#3-per-screen-analysis)
4. [Shared UI and Validation Patterns](#4-shared-ui-and-validation-patterns)
5. [Reachability and Missing Captures](#5-reachability-and-missing-captures)
6. [Assumptions, Unknowns, and Questions](#6-assumptions-unknowns-and-questions)

---

## 1. Screen, Form, and Report Inventory

### 1.1 Totals

| | Forms | Reports |
|---|---:|---:|
| Total | | |
| Declaring a record source | | |
| Carrying event procedures | | |
| Embedding a third-party control | | |

<!-- A count is not a description of what was counted. If you characterise the set
     behind a number - "all eight are X" - re-derive that from the full list, never
     from the members you happened to open. This is errata cause class
     DESCRIBED_NOT_COUNTED, and it has already cost this project two corrections. -->

### 1.2 Entry points

| ID | Object | Type | Business purpose | Entry path | Evidence |
|---|---|---|---|---|---|

<!-- `Business purpose` is a MEANING claim. Without a DOCUMENT or INTERVIEW it is
     written as "not established" - not guessed from the object's name. -->

## 2. Navigation Map

<!-- Required diagram. Follow the application's own open calls, not a plausible
     hierarchy. -->

```mermaid
flowchart TD
```

## 3. Per-Screen Analysis

### {{F_ID}} — {{OBJECT_NAME}}

- **Purpose:**
- **Who uses it:**
- **Record source:**
- **Reached from:**
- **Preconditions:**

| User action | VBA event | Validation / condition | What it does | Data or file target | Evidence |
|---|---|---|---|---|---|

<!-- One of these per screen that carries behaviour. For a screen whose behaviour is
     a single open call, the inventory row is enough - say so rather than padding. -->

## 4. Shared UI and Validation Patterns

<!-- A pattern repeated across screens is a requirement in disguise: a replacement
     has to decide whether to reproduce it. State how many objects carry it, so the
     decision is scoped. -->

| Pattern | Objects carrying it | What a replacement must decide | Evidence |
|---|---:|---|---|

## 5. Reachability and Missing Captures

### 5.1 Reachability

| Route | Objects |
|---|---:|
| Reachable from the entry point by an open call | |
| Referenced by another object but not from the entry point | |
| Embedded as a subform or subreport | |
| **Referenced by nothing** | |

**This is reachability, not disuse.** Routes not examined:

<!-- Name them. A screen can be opened from the navigation pane, from a toolbar or
     custom menu the definitions do not carry, or by code in a copy not analysed.
     The figure travels with this qualifier or it will be quoted without it. -->

### 5.2 Unreferenced objects, grouped

<!-- Superseded variants, sub-menus nothing opens, reports with no launcher. Naming
     the groups is what turns a number into something an operator can answer. -->

### 5.3 Missing captures

<!-- What no screenshot means for this document, concretely: layout, grouping, tab
     order, control visibility. If an operator screenshot shows something the
     definition text does not carry, record it as an open question, not a finding. -->

## 6. Assumptions, Unknowns, and Questions

### Assumptions

| ID | Assumption | If wrong |
|---|---|---|

### Unknowns

| ID | Unknown | Why it matters | What would settle it | Who can settle it |
|---|---|---|---|---|

### Questions

| ID | Question | Blocks | Owner |
|---|---|---|---|
