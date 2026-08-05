# Frontend Coding Rules (Stage 3b)

> **Read before any frontend coding.** Invoked at Stage 3b of `MASTER_WORKFLOW.md`. Library names and paths resolve from `PROJECT_CONFIG.md` §4.
>
> Backend rules are in `{{BACKEND_RULES_DOC}}`. Language-level style is in `{{CONVENTIONS_DOC}}`.

Target shape: a React single-page application consuming the REST API this project's backend exposes. This document covers what the frontend code must look like; it does not cover business interpretation, which is Stage 1 and 2.

## Contents

- [1. Project Layout](#1-project-layout)
- [2. Routing](#2-routing)
- [3. API Client Layer](#3-api-client-layer)
- [4. Data Fetching](#4-data-fetching)
- [5. Global State](#5-global-state)
- [6. Forms And Validation](#6-forms-and-validation)
- [7. Legacy UI Parity](#7-legacy-ui-parity)
- [8. Output And Export Screens](#8-output-and-export-screens)
- [9. Tables And Grids](#9-tables-and-grids)
- [10. Three Mandatory States](#10-three-mandatory-states)
- [11. Internationalization](#11-internationalization)
- [12. Styling](#12-styling)
- [13. Accessibility Minimum](#13-accessibility-minimum)
- [14. Quality Gates](#14-quality-gates)
- [15. Project-Specific Patterns](#15-project-specific-patterns)
  - [15.1 Read The Reference Screen Before Building A New One](#151-read-the-reference-screen-before-building-a-new-one)
  - [15.2 Use `{{PACKAGE_MANAGER}}`, Not Whichever One Is Installed](#152-use-package_manager-not-whichever-one-is-installed)
- [16. What This File Is Not](#16-what-this-file-is-not)

## 1. Project Layout

| Concern | Location |
|---|---|
| Route-level screen components | `{{FE_PAGE_DIR}}/{feature}/` |
| Reusable UI components | `{{FRONTEND_ROOT}}/components/` |
| Typed API client modules | `{{FE_API_DIR}}/` |
| Shared TypeScript types | `{{FE_TYPES_DIR}}/` |
| Global state stores | `{{FRONTEND_ROOT}}/stores/` |
| Custom hooks | `{{FRONTEND_ROOT}}/hooks/` |
| Translation resources | `{{FRONTEND_ROOT}}/translation/` |
| Pure utilities | `{{FRONTEND_ROOT}}/libs/` |

One screen owns one directory under `{{FE_PAGE_DIR}}`. Shared pieces move up only when a second screen actually needs them — not in anticipation.

## 2. Routing

- All screens mount under `{{FE_ROUTE_BASE}}`.
- The route path for a screen comes from the screen plan's frontend contract, not invented at coding time.
- A screen reachable only from a parent screen is still a real route; deep-linking to it must work, because operators bookmark screens.

## 3. API Client Layer

**Components never call HTTP directly.** Every request goes through a typed module in `{{FE_API_DIR}}`.

- One module per backend resource, exporting one function per endpoint.
- Request and response types live in `{{FE_TYPES_DIR}}` and **mirror the backend contract** in the screen plan. If the backend returns `snake_case`, the type declares `snake_case` — do not silently rename fields in the client, because a renamed field breaks the traceability chain from legacy column to rendered cell.
- Every function's return type is explicit. No `any` at the boundary; parse or narrow instead.
- Error shape follows the backend's standard error payload. Do not invent a second error format on the client.

## 4. Data Fetching

Use `{{FE_QUERY_LIB}}` for all server data.

- **Query keys** are stable arrays that include every parameter affecting the result: `['orderInquiry', { storeCode, dateFrom, dateTo, cursor }]`. A key missing a filter causes stale data to be served after the user changes that filter — a defect that looks like a backend bug.
- **Never hand-roll caching** with a store or a `useEffect`. Cache invalidation belongs to the query library.
- **Mutations invalidate explicitly.** After a create, update, or delete, invalidate the affected query keys. If the legacy screen refreshed its grid after saving, the modern screen must too — that refresh is observable behavior, not an implementation detail.
- **Cursor pagination** (see `{{BACKEND_RULES_DOC}}`) has no total count and no page numbers. The UI therefore offers next and previous, or infinite scroll — never a numbered pager. If the legacy screen showed a record count, that requirement belongs in the screen plan as a gap to resolve, not as a client-side count of the current page.

## 5. Global State

Use `{{FE_STATE_LIB}}` for global state, and only for state that is genuinely global.

| State | Where it belongs |
|---|---|
| Server data | Query cache — never duplicated into a store |
| Form field values while editing | Form library state |
| Component-local UI state (open/closed, hovered) | `useState` in that component |
| Cross-screen session context (current user, permissions, selected period) | Global store |
| Filter values the user expects to survive navigation | Global store, only if the legacy screen preserved them |

Copying server data into a store is the most common source of screens that display stale values after a save.

## 6. Forms And Validation

Use `{{FE_FORM_LIB}}`.

- The validation schema mirrors the backend's validation rules and the legacy field rules recorded in the screen plan.
- **Client validation never replaces server validation.** It exists to give fast feedback. The server remains authoritative, and the client must render server-side field errors returned by the API.
- Required-field marking, input masks, and maximum lengths come from the legacy field properties captured during evidence extraction — not from a developer's assumption about what looks reasonable.
- Numeric fields that represent money or quantity use a decimal-safe representation end to end. Do not let a value pass through a JavaScript number where precision matters; keep it as a string in the payload if the backend expects a string.

## 7. Legacy UI Parity

This is the section that decides whether operators accept the new screen. Access forms carry behavior that is invisible in a screenshot and easy to drop. Each item below is either **preserved** or **an accepted difference recorded in the screen plan** — never silently changed.

| Legacy Access behavior | Why it matters | Modern handling |
|---|---|---|
| **Enter moves to the next control** | Access default. Operators type entire records without touching the mouse. Web default submits the form instead | Decide explicitly. If preserved, implement key handling per the screen plan; if changed, record it as an accepted difference — this one generates complaints |
| **Explicit tab order** | Data-entry speed depends on it; the visual order and the tab order often differ | Reproduce the recorded tab order; do not rely on DOM order alone |
| **Default focus on open** | The first field is often not the first control | Set focus per the screen plan |
| **Locked versus Disabled** | Access distinguishes them: locked is readable and copyable, disabled is greyed out and skipped in tab order | Do not collapse both into `disabled`; a locked field stays focusable and selectable |
| **Default values on a new record** | Business rules hide here (today's date, current user's store, a status code) | Implement from the recorded field defaults, not from what seems sensible |
| **Combo box limit-to-list** | Rejects values outside the list; the message text is part of the behavior | Match the constraint and the message |
| **Record navigation and record counter** | Bound forms show position within a result set | Reproduce only if the screen plan says operators used it; otherwise record the difference |
| **Continuous or datasheet view** | A repeating row grid where each row is fully editable | Implies an editable grid, not a read-only table with an edit modal — choosing a modal is a behavior change |
| **Dirty-record warning on navigate away** | Prevents silent loss of typed data | Implement an unsaved-changes guard |
| **Message box text** | Operators recognize and act on exact wording; support scripts quote it | Preserve the text through `{{I18N_LIB}}`; a reworded message is a behavior change |
| **Print preview** | Access opened a preview window before printing | Decide between an in-browser preview and a direct download, and record the choice |
| **Keyboard shortcuts and function keys** | Legacy screens often bind F-keys to actions | Reproduce what the screen plan lists; note any browser conflict as a gap |

If any of these is unclear from the evidence, it is an open question for Stage 2, not a decision to make while coding.

## 8. Output And Export Screens

For screens whose purpose is a report, export, or print:

- The **backend generates the file**; the frontend triggers the request and delivers the download. Do not build spreadsheets or PDFs in the browser — the legacy layout contract lives with the backend, and duplicating it on the client guarantees drift.
- Take the filename from the response's content-disposition header. Do not construct it client-side; the naming rule came from the legacy export and belongs in one place.
- Show progress for long-running generation, and a clear failure state. A silent no-op after clicking "export" reads as a broken screen.
- Preview rendering, if offered, is a convenience — the downloadable artifact remains the source of truth for layout comparison in Stage 4b.

## 9. Tables And Grids

- Column order, headers, and alignment follow the legacy output or form layout recorded in the screen plan.
- Totals and subtotals appear where the legacy screen placed them. Moving a total row from bottom to top is a behavior change.
- Sorting: only where the legacy screen allowed it. Adding sortable columns everywhere sounds like an improvement and quietly diverges from a report whose row order is part of its meaning.
- Number, date, and currency formatting comes from the legacy display format, not the browser locale default.

## 10. Three Mandatory States

Every screen that loads data implements all three, explicitly:

1. **Loading** — a skeleton or spinner; never a blank region that looks like an empty result.
2. **Empty** — distinct from loading and from error. "No matching records" is a legitimate answer and must be visually different from "something went wrong".
3. **Error** — renders the server's message where one is supplied, with a retry affordance. Never swallow an error into an empty state; that turns a backend fault into a silent wrong answer.

The most common defect at G3 UI is a missing empty state on a search screen.

## 11. Internationalization

- All user-visible strings go through `{{I18N_LIB}}`. No literal text in components.
- Legacy label text is the default translation source — the operator's vocabulary is the requirement, not a cleaned-up rewrite.
- Keys are namespaced per screen so a shared string change cannot alter unrelated screens unnoticed.

## 12. Styling

- Use `{{FE_STYLE_LIB}}` as the project uses it. Do not introduce a second styling mechanism for one screen.
- Reproduce the legacy layout structure closely enough that an operator recognizes the screen. Visual modernization is allowed; relocating controls is a behavior change.
- Density matters: legacy data-entry forms pack many fields into one view, and generous modern spacing that forces scrolling makes the screen slower to use.

## 13. Accessibility Minimum

- Every input has a programmatically associated label.
- Interactive elements are reachable and operable by keyboard.
- Focus is visible.
- Error messages are associated with their field, not only rendered nearby.

## 14. Quality Gates

Before closing Stage 3b:

- `{{FE_LINT_CMD}}` passes on touched files.
- Type checking passes; no new `any` at an API boundary.
- Every control listed in the screen plan's control inventory has a component, and every planned interaction has a handler — this is what G3's UI sub-check verifies.

## 15. Project-Specific Patterns

This document states **principles**. It deliberately does not name components, hooks, or directory layouts, because those differ per project and go stale the moment a component is renamed.

Concrete patterns live in the project and are declared as `{{FE_PATTERN_DOCS}}` in `PROJECT_CONFIG.md` §4. Expect them to cover:

- which shared component to use for each field type, and its exact props contract
- where a screen-private form or table hook lives, versus what belongs in shared hooks
- how validation and message strings are organized and named
- table column sizing conventions, virtualization thresholds, row memoization
- the project's own hook names for behaviors this document only describes in principle — for example, whichever hook implements Enter-advances-focus (§7) and date-range synchronization

**Division of authority.** On a project-specific detail — a component name, a file location, a props signature — the project pattern document wins. On pipeline behavior and legacy-parity obligations, this document wins. If the two genuinely conflict on the same question, that is a documentation defect: record it in `Known_Issues.md` rather than picking one silently.

If `{{FE_PATTERN_DOCS}}` is `n/a` for a project, this document is the only frontend standard in force, and a reviewer should expect component choices to vary between screens until patterns are written down.

Authoring `{{FE_PATTERN_DOCS}}` from nothing is harder than editing an existing one.
`templates/FRONTEND_API_PATTERNS_TEMPLATE.md` and `templates/FRONTEND_UI_PATTERNS_TEMPLATE.md`
are fill-in-the-blank starting points — not auto-copied at bootstrap, since a greenfield
project has no screens yet to extract patterns from. Copy them by hand once enough screens
exist that a real pattern, not a guess, can be written down.

### 15.1 Read The Reference Screen Before Building A New One

`{{FE_REFERENCE_SCREEN}}` names a screen already built and reviewed on this project. Open it before starting Stage 3b and follow its shape.

A written pattern document says what to do; a reference screen shows what it looks like when done, including the parts nobody wrote down. Prose cannot convey how the pieces are wired, and a new screen built only from principles reliably diverges in small ways that each look reasonable and together make the codebase inconsistent.

Take from it: file layout, where the screen-private hook sits and what it returns, how the form or table is split between container and presentation, how loading, empty and error states are rendered, and how messages are organized. Deviate only where this screen genuinely differs, and say so in `Coding_Records/{screen}.md` — an undocumented deviation reads as an accident to the reviewer.

If `{{FE_REFERENCE_SCREEN}}` is `n/a`, no screen has been reviewed yet. Say so in the coding record; the screen you are building becomes the reference and is worth extra care for that reason.

### 15.2 Use `{{PACKAGE_MANAGER}}`, Not Whichever One Is Installed

Run every frontend command through `{{PACKAGE_MANAGER}}`. Two managers in one repository produce two lock files, and the second one silently resolves a different dependency tree — a class of bug that reproduces on one machine and nowhere else.

This applies to running scripts too, not just installing. If a command in this document or in `PROJECT_CONFIG.md` is written for a different manager than the project declares, the declaration wins and the command is the defect.

## 16. What This File Is Not

- Not the backend contract — that is the screen plan §3 and `{{BACKEND_RULES_DOC}}`.
- Not the workflow — that is `MASTER_WORKFLOW.md`.
- Not the test specification — that is `Test_Instruction/README.md` §Frontend, executed at Stage 4b.
- Not the frontend test method — that is `FRONTEND_TESTING.md`.
- Not language-level style (naming, types, formatting) — that is `{{CONVENTIONS_DOC}}`.
- Not the project's concrete component patterns — see §15.

Where this file conflicts with `{{CONVENTIONS_DOC}}` on a frontend-specific matter, this file wins. Where it conflicts with the screen plan on observable behavior, the screen plan wins — and if the screen plan looks wrong, that is a Stage 2 correction, not a coding-time improvisation.
