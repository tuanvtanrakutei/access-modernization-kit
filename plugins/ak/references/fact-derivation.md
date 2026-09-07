# Fact derivation

Before the first phase, the run derives the relationships its sources state
literally. One command, once per bundle:

```
python scripts/ak.py derive --app-root <APP_ROOT>
```

It writes `extracted/derived-extraction.json` and the distilled UI facts under
`extracted/ui-facts/`, and prints node, edge and object counts.

## Why it exists

Two problems, both observed on a real application.

An LLM-backed graph pass produced 79 nodes and no edges from a corpus of exported
query SQL: one node per file and not a single relationship. Yet every query names
the tables it reads, in text, next to the authoritative table list the acquisition
bundle already holds. Matching one against the other is exact, free and
reproducible; asking a semantic pass to infer it costs tokens to guess at something
the source states outright.

And the corpus excluded every `SaveAsText` definition, on the sound argument that a
graph cannot use "this form contains a TextBox with Top=1410". True of the
coordinates - but the same file carries `RecordSource`, `ControlSource`, the ProgID
of each embedded control and the name of every event procedure, which are exactly
the relationships Phase 2 asks about. So definitions are distilled rather than
dropped: the facts enter the corpus, the property soup does not.

On the same application the derivation produced 756 edges over 325 nodes, and put
UI evidence into the corpus for the first time.

## What it derives

| Edge | From | Read from |
|---|---|---|
| query → table | query SQL matched against the bundle's own table list | `queries/`, `databases/tables.json` |
| screen → record source | `RecordSource` on a form or report | `forms/`, `reports/` |
| screen → field | `ControlSource` on a bound control | `forms/`, `reports/` |
| screen → screen | `DoCmd.OpenForm` / `DoCmd.OpenReport` | definition text, modules, macros |
| screen → embedded object | `SourceObject` | definition text |
| screen → ActiveX control | `Class = "<ProgID>"` | definition text |

Two rules keep the result honest, and both were written after getting them wrong:

- **Node ids carry a digest.** Names are normalised to `{stem}_{entity}` for the
  id, and a short hash of the original name is appended. Without it, every Japanese
  name - the norm in this kit's target systems - normalises to the same underscore
  run and distinct entities merge into one node.
- **`Class` is matched with a preceding-letter guard.** `SaveAsText` writes
  `OLEClass ="<localized display name>"` beside the real `Class ="<ProgID>"`, and a
  naive pattern matches both, reporting a caption as a control.

Object names come from the extraction receipt's `components[].name` mapped through
`source_paths`, never from the definition header - the header yields report
*sections* (`詳細`, `ページヘッダー`) and inflates the graph with duplicates.

## What it is, and is not

It is **navigation context and a citable count**. Because it is deterministic, a
phase may write "756 relationships" and a reviewer can regenerate the number
exactly. Nothing else in the kit produces a figure a phase is allowed to cite
without opening the source.

It is **not evidence for a claim**. An edge says two names appear in a stated
relationship; it does not say what that relationship means to the business. A
statement resting on an edge still cites the file and location the edge came from.
See `specifications/evidence-classes.yaml`, rule EC-03: a name is not a meaning.

It **runs once**. The bundle is sealed and does not change between phases, so
per-phase re-derivation would compute the same answer six times. This replaces the
six per-phase graph gates removed in 2.9.0.

## When it fails

A failed derivation blocks phase output, because a phase that cannot enumerate its
own relationships cannot honestly report reachability, coverage or boundaries.
Nothing else about it can block a phase: there is no runtime to install, no network
call, and no model.
