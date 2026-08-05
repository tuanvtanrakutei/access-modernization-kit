# Frontend Testing Method (Stage 4b)

> **Layer 1 document.** The transferable method for testing a modernized screen's frontend. Commands and paths resolve from `PROJECT_CONFIG.md`.
>
> Per-project specifics — component selectors, service ports, container names, credentials — belong in the project's own testing notes, **never in this document or in a shared plugin.**

Stage 4b of `MASTER_WORKFLOW.md`. Runs after Stage 4a because it needs a working backend.

## Contents

- [Role](#role)
- [Source Of Truth, In Priority Order](#source-of-truth-in-priority-order)
- [The Three Tiers](#the-three-tiers)
  - [The Rule That Matters Most](#the-rule-that-matters-most)
- [Backend Dependency Pre-Check](#backend-dependency-pre-check)
- [Mocking Principle](#mocking-principle)
- [What Every Screen Must Cover](#what-every-screen-must-cover)
- [Recording Results](#recording-results)
- [Relationship To The Pipeline](#relationship-to-the-pipeline)
- [Project-Specific Notes Live Elsewhere](#project-specific-notes-live-elsewhere)

## Role

**You are a tester, not a fixer.** The screen was implemented by someone else, possibly by an earlier pipeline pass.

- Do not fix production code, backend or frontend.
- Do not weaken an assertion to turn a test green. Fix the locator or the setup; if the expectation itself was wrong, that is a screen-plan correction, recorded as a finding.
- Where behavior deviates from the specification, write a finding with root cause, impact, and suggested fix — and stop there.

## Source Of Truth, In Priority Order

1. `Test_Instruction/{screen}.md` — the specification, if it exists
2. `Screen_plans/{screen}.md` — the frontend contract: control inventory, interactions, validation
3. Legacy evidence — the exported form, report, and VBA, read with `{{SOURCE_ENCODING}}`
4. Current code — last resort. When used, say so explicitly: *expected behavior derived from the current implementation; no specification comparison performed.* That sentence is the difference between a test that verifies a requirement and one that merely freezes today's behavior.

## The Three Tiers

Classify every assertion, then push it as far up the automation ladder as it will go.

| Tier | Covers | Method | Case id |
|---|---|---|---|
| **UI** | Anything the DOM can observe: rendering, field labels, validation messages, button states, toggles, dialogs, loading and empty states, focus and keyboard behavior, presence of a preview frame | End-to-end browser test via `{{FE_E2E_TEST_CMD}}` | `TC-{SCREEN}-UI-NN` |
| **AUTO** | The **content** behind a report or export: call the real running backend and assert the JSON, then download the real artifact and **parse** it. Column names and order, cell types, blank columns, row sort order, grouping, filter-driven exclusions, totals | End-to-end test plus programmatic parsing of the downloaded file | `TC-{SCREEN}-AUTO-NN` |
| **MAN** | Only what needs human eyes on rendered output: glyph rendering, subtitle and date format strings, header and footer text placement, physical print layout | Manual, with exact steps and the legacy sample to compare | `TC-{SCREEN}-MAN-NN` |

### The Rule That Matters Most

**Do not default report and export cases to manual.** The data feeding a PDF or spreadsheet is fully testable against the live backend. Reserve manual checks for pixels.

This is where most teams quietly lose their test suite. Marking a column-order check as "operator verifies visually" feels reasonable once; after twenty screens it is a hundred manual steps nobody will ever run again, and the column order regresses unnoticed. Parsing a spreadsheet takes a few lines and holds forever.

If a tier-3 case could be answered by parsing a file or asserting a JSON field, it is a tier-2 case that has been misfiled.

## Backend Dependency Pre-Check

Before writing any AUTO test, read the service for calls that reach external systems on every request — a network file share, an SMB mount, a third-party API, a refresh of a cached master table.

If one exists, AUTO tests cannot run against the live backend while that dependency is unavailable. Mark the affected cases pending, file a finding describing the dependency, and say plainly that frontend verification is blocked — rather than reporting a pass for the cases that happened to avoid the dependency.

## Mocking Principle

Mock only as much as is needed to keep the page from crashing, and no more. Over-mocking produces a test that passes against a fiction.

| Target | Treatment |
|---|---|
| Master-data lookups that only populate dropdowns | Mock empty so the form renders |
| The screen's main data endpoint | Empty for the no-data path; one minimal row for the has-data path |
| Export endpoint | Mock a tiny binary only when the assertion is that the call fired |
| Fonts and other assets the renderer needs | **Never mock.** Mocking them breaks the very rendering being tested |
| A popup or new window | Assert its URL, then close it immediately. Do not wait for its content to finish rendering |

For AUTO tier, do **not** mock the backend. The point of that tier is that the real service produced the real content.

## What Every Screen Must Cover

Derive the case list from the screen plan's control inventory and interaction table — every row appears exactly once in the tier classification. Beyond that, these are always in scope:

- **Render**: title, section headings, field labels, default values on open, required-field marking, action buttons present and correctly enabled or disabled.
- **Validation**: each required field empty produces the specified message, per action button.
- **Three states**: loading, empty result, and error — each visually distinct. An empty state rendered as a blank region is the single most common frontend defect this pipeline catches.
- **Legacy parity behaviors** the screen plan marked preserved: keyboard navigation, focus order, locked versus disabled fields, message wording.
- **Output path**: for a report or export screen, the request fires with the right parameters, and the returned artifact's content matches the legacy baseline.

## Recording Results

Results go into `Test_Instruction/{screen}.md` §Frontend — the same artifact the backend track uses. Keeping one file per screen means the Stage 5 reviewer reads one place and the registry's `status_fe` has a single evidence source.

If the team also wants a spreadsheet view for QA, generate it **from** that section rather than maintaining it separately. Two hand-maintained records of the same test run will disagree within a week, and nobody will know which one is right.

Every finding carries: case id, expected, actual, root cause where known, impact, and suggested fix. A finding without an expected-versus-actual pair is an opinion.

## Relationship To The Pipeline

- Runs as Stage 4b, after Stage 4a is green.
- Its results are one of the inputs the Stage 5 reviewer checks, alongside the backend test results.
- It does not set `status_fe` — only a Stage 5 approval does that.
- Findings that affect more than one screen are promoted to `Known_Issues.md`.

## Project-Specific Notes Live Elsewhere

This document deliberately contains no ports, container names, credentials, or component selectors. Those change per project and, in the case of credentials, must never travel inside a shared plugin.

Keep them in the project's own testing notes and reference them from `PROJECT_CONFIG.md`. A selector cheat-sheet for custom components is genuinely valuable — it is simply project-scoped knowledge, not method.
