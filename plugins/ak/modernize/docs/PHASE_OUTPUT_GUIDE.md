# Reading The Six-Phase Output

> **Layer 1 document.** Project-independent. Orients a reader to `ak`'s Phase 1–6 output for
> one app before or while bootstrapping a modernize project on it. It does not replace
> `LEGACY_EVIDENCE.md` §6.1–6.4 — read this first for orientation, that one for the exact
> handoff contract, matching rules, and gate mechanics.

If you have never opened a six-phase run's output before, start here rather than opening six
long documents cold and guessing which one answers your question.

## Contents

- [1. Quick Start — "I want to understand ..."](#1-quick-start-i-want-to-understand)
- [2. File Naming — What You Actually See On Disk](#2-file-naming-what-you-actually-see-on-disk)
- [3. The Six Phases At A Glance](#3-the-six-phases-at-a-glance)
- [4. How This Feeds Modernize](#4-how-this-feeds-modernize)
- [5. Suggested Reading Order For A Newly Investigated App](#5-suggested-reading-order-for-a-newly-investigated-app)

## 1. Quick Start — "I want to understand ..."

| I want to understand ... | Go to |
|---|---|
| What screens, forms, and reports exist | Phase 2 §1 "Screen, Form, and Report Inventory" |
| What one specific screen does, control by control | Phase 2 §3 "Per-Screen Analysis" → `### {FORM_ID} — {FORM_NAME}` |
| What tables and columns the legacy DB has | Phase 1 §2 "Table and Column Inventory" |
| What a table means in business terms | Phase 1 §3 "Key Entities and Business Meaning" |
| Foreign keys and integrity rules | Phase 1 §4 "Relationships and Integrity Controls" |
| What a query or stored procedure does | Phase 1 §5, or Phase 3 §2 for how it's used |
| A business rule (validation, calculation, filter) | Phase 3 §4 "Business Rules" — cross-checked against documents in Phase 5 §2 |
| An end-to-end workflow that crosses multiple screens | Phase 4 §2 "End-to-End Workflows" |
| Whether a Japanese manual/spec still matches actual system behavior | Phase 5 §3 "Document-to-System Alignment" |
| A fast, single-document overview of the whole app | Phase 6 "Synthesis" — read this before 1–5, not after |
| Known risks or legacy quirks the analyst flagged | Phase 6 §6 "Risks / Legacy Issues" |
| Open questions the analyst could not resolve alone | `{APP_ID}_QuestionList.md` |
| Whether independent QA found problems | `{APP_ID}_QA_Report.md` |
| Which VBA event maps to which SQL/output, per workflow step | `{APP_ID}_TraceabilityMatrix.csv` |
| Exactly which source file and line backs a specific claim | `{APP_ID}_Evidence.json` → `evidenceItem.source_path` / `source_location` |
| Whether a phase is far enough along to build on | `run-state.json` → `phase_gates.phaseN`, must read `PUBLISHED` |

If your question is not above, it is probably answered inside Phase 6 — it is the one
document written to be read start to finish rather than looked up by section.

## 2. File Naming — What You Actually See On Disk

`ak`'s own templates are named e.g. `phase2-screen-analysis.md`; **real run output is not**.
Per `ak`'s `specifications/output-contract.yaml`, every phase document and control artifact is
prefixed with the app ID and carries a language token:

| You're looking for | Real filename pattern |
|---|---|
| Phase 1–6 documents | `{APP_ID}_Phase1_DataUnderstanding_{LANG}.md` … `{APP_ID}_Phase6_Synthesis_{LANG}.md` |
| Evidence register | `{APP_ID}_Evidence.json` |
| Dependency / workflow trace | `{APP_ID}_TraceabilityMatrix.csv` |
| Open questions | `{APP_ID}_QuestionList.md` |
| Independent QA result | `{APP_ID}_QA_Report.md` |
| Phase readiness | `run-state.json` (not app-prefixed — one per run, at `{{AK_RUN_DIR}}` root) |

Do not search by a bare `startswith("phase2")` or similar — the phase number is a substring
after the app ID, not the start of the filename. See `LEGACY_EVIDENCE.md` §6.2 for why this
matters mechanically, not just cosmetically.

## 3. The Six Phases At A Glance

| Phase | Title | Answers |
|---|---|---|
| 1 | Data Understanding | What tables exist, what they mean, how they relate |
| 2 | Screen & Form Analysis | What screens/forms/reports exist, what each one does |
| 3 | Logic & Processing | What the SQL and VBA processing actually computes |
| 4 | Workflow Reconstruction | How a user action turns into an end-to-end outcome across screens |
| 5 | Document Integration | Whether external manuals/specs still describe real behavior |
| 6 | Synthesis | Everything above, rolled into one reading pass |

Phases publish strictly in this order — Phase 4 cannot be `PUBLISHED` before Phase 3 is, and
so on through Phase 6. See `LEGACY_EVIDENCE.md` §6.4 for what that guarantees and does not.

## 4. How This Feeds Modernize

Modernize's Stage 1 pre-flight reads three things mechanically, not all six documents in
full: Phase 2 (screen inventory and per-screen detail), `TraceabilityMatrix.csv` (dependency
map), and `run-state.json` → `phase_gates` (readiness signal for phase2/phase4/phase6). The
`bootstrap-project` skill goes further and only ever touches Phase 2 — it seeds
`Screens_Registry.md` from Phase 2 §1 alone, because that is the only phase document with a
structured, per-object table; nothing else about a new project's registry needs Phase 4, 5,
or 6's content. Full mapping, precedence rules, and known limits: `LEGACY_EVIDENCE.md` §6.1–6.4.

Everything else in Phase 1, 3, 4, 5, and 6 remains valuable **reading**, for a human or an
agent doing Stage 1's actual business-flow writing — it is just not parsed by any script.

## 5. Suggested Reading Order For A Newly Investigated App

1. **Phase 6** — fast orientation to the whole app in one pass.
2. **Phase 2 §1** — the screen list; decide what you're bootstrapping first.
3. **Phase 1** — the data model behind the screens you care about.
4. **Phase 3 / Phase 4** for the specific screen or workflow you're about to work on — not
   the whole document, the section that covers it.
5. **Phase 5** only if a business rule's legacy-vs-documented behavior is in question.
6. **`QuestionList.md` / `QA_Report.md`** last — what's still open, and what QA already
   caught, so you don't re-discover either by hand.
