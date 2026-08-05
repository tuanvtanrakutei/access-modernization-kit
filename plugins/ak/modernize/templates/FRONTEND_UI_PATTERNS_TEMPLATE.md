# UI Patterns: Forms And Tables

> **Template.** Concrete patterns for building a screen in this project. Read before
> building a new screen.
>
> Principles live in `{{DOCS_DIR}}/{{FRONTEND_RULES_DOC}}` sections 6, 7, 9, and 10 (forms,
> legacy UI parity, tables, mandatory states) — section 7 in particular explains *why*
> several rules below exist, if this project modernizes a legacy UI. This file records what
> *this* codebase actually does; on a project-specific detail it wins.

{{fill: when and how this was written — same note as `FRONTEND_API_PATTERNS.md`}}

## 1. File Layout

{{fill: per-screen directory shape — what goes in the screen's own folder versus shared
folders. Give one worked example each for a form screen and a table screen, naming a real
reference implementation of each if one exists yet}}

## 2. Messages Are Constants, Never Literals

{{fill: where validation/error/confirmation text lives per screen, and where shared
wording lives. If this project modernizes a legacy system, state plainly whether message
text is operator vocabulary carried over from the legacy screen (a requirement, not copy
to improve) or free to rewrite}}

## 3. Form Hook Pattern

{{fill: one worked example of this project's form-hook shape — validation schema,
resolver, what the hook returns, how server-supplied defaults are applied}}

## 4. Shared Field Components

{{fill: a table of this project's shared field components — name, adoption count if
known, what it's for. State plainly not to introduce a new component for something an
existing one already covers, and where to extend an existing one instead}}

## 5. Shared Behaviour Hooks

{{fill: a table of shared behaviour hooks — name, adoption count if known, what each does.
If this project preserves legacy keyboard or UX behavior (e.g. Enter-advances-focus,
date-range sync), name which hook reproduces which legacy behavior and why removing it
would regress the operator's experience, not just "looks less web-conventional"}}

## 6. Table Pattern

{{fill: this project's convention for row source, selection (index vs. a stable key —
name which, and why if index-based selection has ever broken after a delete), empty-state
seeding, derived-value recalculation, and any virtualization threshold}}

## 7. Modals

{{fill: which shared modal components exist and when each is used — error/info versus
destructive confirmation}}

## 8. Three States Are Mandatory

{{fill: n/a if this only restates the plugin principle — but name this project's own
concrete pattern for the empty state specifically if one exists, since an empty result
rendered as a blank area is the state most often missed}}

## Checklist Before Finishing A Screen

{{fill: a short, project-specific checklist derived from the sections above — end with a
line pointing at wherever this project records per-control coverage, e.g. a screen plan's
control inventory, so a reviewer has one place to check completeness}}
