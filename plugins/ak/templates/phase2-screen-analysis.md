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

<!-- Every figure here is in `{{APP_ID}}_ScreenCatalogue.md`, which is generated from
     the bundle and lists every form and report with its record source, its bound
     fields, its event procedures and its embedded controls. Read them from there
     rather than counting again: two counts of one thing is how E-07 was published,
     37 unreferenced objects against 26 actual.

     A count is also not a description of what was counted. If you characterise the
     set behind a number - "all eight are X" - re-derive that from the catalogue's
     full list, never from the members you happened to open. This is errata cause
     class DESCRIBED_NOT_COUNTED, and it has already cost this project two
     corrections. -->

| | Forms | Reports | Read from |
|---|---:|---:|---|
| Total | | | `{{APP_ID}}_ScreenCatalogue.md` |
| Declaring a record source | | | `{{APP_ID}}_ScreenCatalogue.md` |
| Carrying event procedures | | | `{{APP_ID}}_ScreenCatalogue.md` |
| Embedding a third-party control | | | `{{APP_ID}}_ScreenCatalogue.md` |
| Business purpose not established | | | the catalogue's marked cells |

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

<!-- The list is `{{APP_ID}}_ScreenCatalogue.md` section "Objects referenced by
     nothing", computed from the derived graph. Do not re-derive it here and do not
     restate its count: E-07 is exactly this figure published from a subset, 37
     against 26 actual, and it was caught by generating the catalogue rather than by
     reading the document.

     What belongs here is the grouping - superseded variants, sub-menus nothing opens,
     reports with no launcher - because naming the groups is what turns the
     catalogue's number into something an operator can answer. Say which routes were
     not examined every time the figure is quoted: absence of a reference is
     unreachability, not disuse (EC-05). -->

| Group | Objects | Why they are grouped this way | Routes not examined |
|---|---:|---|---|

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
