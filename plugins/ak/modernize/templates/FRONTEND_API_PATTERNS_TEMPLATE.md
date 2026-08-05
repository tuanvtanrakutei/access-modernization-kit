# API And Hooks Patterns

> **Template.** Concrete patterns for this project's API client and data-fetching layers.
> Read before defining a new API function, hook, or query key.
>
> Principles live in `{{DOCS_DIR}}/{{FRONTEND_RULES_DOC}}` sections 3 and 4 (API client
> layer, data fetching). This file records what *this* codebase actually does. Where the
> two differ on a project-specific detail, this file wins — `{{FRONTEND_RULES_DOC}}` states
> that division of authority itself, so it is not repeated here.

{{fill: when and how this was written — e.g. "extracted from the existing implementation on
{{date}}, describing what N screens already built already do, not a proposal" if
backfilling an existing codebase; "written before the first screen, to be revised once
patterns emerge" if starting greenfield}}

## 1. Layers

{{fill: name this project's layers between a component and the network call — e.g. API
function / hook / component — where each lives, what each owns, and what crossing a layer
boundary looks like as a defect (a component calling the HTTP client directly, a hook
building a URL, etc.)}}

## 2. Where An API Function Belongs

{{fill: the rule that decides which folder a new endpoint's code goes in — by URL prefix,
by domain, by ownership. Name whichever rule is most often gotten wrong; that is usually
the one worth writing down most precisely, with the concrete cost of getting it wrong (a
shared endpoint duplicated per screen, a contract change missed in one copy)}}

## 3. Shared API File Pattern

{{fill: naming convention for a file that wraps one endpoint. Include one real, complete
worked example from this codebase. List what to copy from it — request param casing,
response validation, where response/request types come from}}

## 4. Screen-Owned API Folder Pattern

{{fill: how a screen that owns its own endpoints organizes them — barrel file, constants,
aggregation into one object hooks import}}

## 5. Query Keys

{{fill: where query keys are centralised (or "n/a — inlined per hook" if that is this
project's actual convention) and the rule that every result-affecting parameter must be
part of the key, with the concrete symptom of skipping it (stale data after a filter
change, presenting as a backend bug)}}

## 6. Query Hook Pattern

{{fill: one worked example, naming convention, the options-typing convention if this
project has one (e.g. omitting `queryKey`/`queryFn` from the caller-supplied options type)}}

## 7. Export / Download Hooks

{{fill: the shared pattern for file-download endpoints — filename constants, response
type, shared hook if one exists — or "n/a, no export screens yet"}}

## 8. Errors

{{fill: how a server error reaches the user — the shared component or path, so every
screen fails visibly the same way rather than each screen inventing its own error
presentation}}

## Checklist Before Adding An API Or Hook

{{fill: a short, project-specific checklist derived from the sections above — a handful of
concrete, checkable items, not a restatement of general good practice}}
