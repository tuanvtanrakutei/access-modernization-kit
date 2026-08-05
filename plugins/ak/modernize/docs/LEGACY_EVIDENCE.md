# Legacy Evidence Taxonomy (Access Family)

> **Layer 2 document.** Applies to any Microsoft Access modernization project. Project-specific paths and encodings come from `PROJECT_CONFIG.md`.

This document answers one question: **where does business logic hide in a legacy Access application, and how do we prove we found all of it?**

Coverage gate **G1** (see `TRACEBACK_GATES.md`) enforces that every applicable evidence object for a screen has been examined. This document defines what "applicable" means for each legacy variant.

## Contents

- [1. Variant Matrix](#1-variant-matrix)
  - [1.1 Engine Consistency Check](#11-engine-consistency-check)
  - [Identifying A Split Design](#identifying-a-split-design)
- [2. Evidence Objects And What They Hide](#2-evidence-objects-and-what-they-hide)
- [3. Extraction Checklist Per Variant](#3-extraction-checklist-per-variant)
  - [All variants — front-end objects](#all-variants-front-end-objects)
  - [`adp` additionally](#adp-additionally)
  - [`mdb` / `accdb` additionally](#mdb-accdb-additionally)
  - [`accdb` / `split-accdb` additionally](#accdb-split-accdb-additionally)
  - [`split-mdb` / `split-accdb` additionally](#split-mdb-split-accdb-additionally)
- [4. Encoding](#4-encoding)
- [5. Access Constructs Needing Explicit Mapping](#5-access-constructs-needing-explicit-mapping)
- [6. Stage 0 Handoff Contract](#6-stage-0-handoff-contract)
  - [6.1 The Enriched Tier — When Stage 0 Is A Six-Phase Analysis](#61-the-enriched-tier-when-stage-0-is-a-six-phase-analysis)
  - [6.2 File Discovery — Match The Real Contract, Not The Template's Own Filename](#62-file-discovery-match-the-real-contract-not-the-templates-own-filename)
  - [6.3 Cross-Artifact Screen Identity — What Is Guaranteed And What Is Not](#63-cross-artifact-screen-identity-what-is-guaranteed-and-what-is-not)
  - [6.4 Why Pre-Flight Checks Exactly `phase2`/`phase4`/`phase6`, Not Fewer Or More](#64-why-pre-flight-checks-exactly-phase2phase4phase6-not-fewer-or-more)
- [7. Evidence Sufficiency Rule](#7-evidence-sufficiency-rule)
- [Related Documents](#related-documents)

## 1. Variant Matrix

This project's variant is `{{LEGACY_VARIANT}}`. Resolve it and treat **only that row** as
governing for this project — the other rows exist so a misconfiguration is checkable, not
because more than one variant applies at once.

| Variant | Front end | Data | Query layer | Table-level logic |
|---|---|---|---|---|
| `adp` | Forms, reports, macros, VBA in `.adp` | SQL Server | **Views + stored procedures + functions** in SQL Server | SQL Server constraints, triggers |
| `mdb` | Forms, reports, macros, VBA in `.mdb` | Jet tables in the **same** `.mdb` | **QueryDefs** (saved queries) | Field validation rules, relationships with RI |
| `accdb` | Forms, reports, macros, VBA in `.accdb` | ACE tables in the **same** `.accdb` | QueryDefs | Field validation rules, relationships, **data macros**, calculated fields |
| `split-mdb` | Forms, reports, macros, VBA, QueryDefs + **linked tables** | Jet tables in a separate `.mdb` | QueryDefs in the front-end file | Validation and relationships live in the **data** file |
| `split-accdb` | Same as `split-mdb` | ACE tables in a separate `.accdb` | QueryDefs in the front-end file | Validation, relationships, **data macros** in the data file |

### 1.1 Engine Consistency Check

`{{LEGACY_DB_ENGINE}}` must agree with what `{{LEGACY_VARIANT}}`'s **Data** column implies:

| `{{LEGACY_VARIANT}}` | Implies `{{LEGACY_DB_ENGINE}}` |
|---|---|
| `adp` | `sqlserver` |
| `mdb`, `split-mdb` | `jet` |
| `accdb`, `split-accdb` | `ace` |

If the two disagree, that is a `PROJECT_CONFIG.md` authoring error, not an unusual project —
stop and ask rather than guessing which one is right. A wrong engine value silently sends
evidence extraction toward the wrong query layer (§2: QueryDefs versus views/procedures) for
every screen, not just one.

### Identifying A Split Design

If you have two files and are unsure which is which: the **front-end** file contains forms and
reports; the **data** file contains tables and relationships but no forms. Linked tables appear
in the front end with an arrow icon and carry a connection string pointing at the data file.

Record both paths as `{{LEGACY_FE_FILE}}` and `{{LEGACY_DATA_FILE}}`. Two consistency checks
follow directly from `{{LEGACY_VARIANT}}`, and both are worth stopping on rather than silently
tolerating:

- If `{{LEGACY_VARIANT}}` is `split-mdb` or `split-accdb`, `{{LEGACY_DATA_FILE}}` must be filled
  and must **not** equal `{{LEGACY_FE_FILE}}` — a split design with one file recorded twice
  means the data file was never actually located.
- If `{{LEGACY_VARIANT}}` is anything else, `{{LEGACY_DATA_FILE}}` should be `n/a` — a value
  here for a non-split variant is itself worth a question, since `mdb`/`accdb` keep their data
  in the same file as the front end and `adp`'s data lives in SQL Server, addressed by
  `{{LEGACY_DB_SCRIPT}}` instead.

Examining only the front-end file in a split design is the single most common cause of missed
validation rules.

## 2. Evidence Objects And What They Hide

Every row below is a place business rules live. G1 checks that the ones relevant to the screen were opened.

| Evidence object | Applies to | Business logic it carries | Commonly missed because |
|---|---|---|---|
| **Form definition** | all | Layout, control list, `RecordSource`, tab order, control-level default values, input masks, conditional formatting | Reviewers read the code-behind and skip the property definitions |
| **Form event handlers (VBA)** | all | Search/filter construction, validation, save/delete flow, cross-field rules, locking, navigation | Handlers on rarely-used controls (`_AfterUpdate`, `_BeforeUpdate`, `_Exit`) |
| **Subforms** | all | Detail-line behavior, parent-child link fields, per-line calculations | Treated as part of the parent form and never opened separately |
| **Report definition** | all | Grouping and sort levels, page setup, `RecordSource`, header/footer calculated controls | Totals and running sums are expressions inside footer controls, not in code |
| **Report event handlers (VBA)** | all | Conditional formatting, page-break logic, suppression of empty groups | Assumed to be presentation-only |
| **Standard VBA modules** | all | Shared calculations, rounding rules, tax logic, formatting helpers | Named generically (`Module1`, `mUtils`) so they look unimportant |
| **Class modules** | all | Stateful helpers, custom collections | Rare, so not looked for |
| **Old-style macros** | all | Navigation, simple validation, `OpenForm`/`RunSQL` actions | Teams assume all logic is in VBA |
| **QueryDefs (saved queries)** | `mdb`, `accdb`, `split-*` | Filtering, joins, aggregation, crosstab pivots, update/delete semantics | Not code files, so not in a code review |
| **Views** | `adp` | Same role as QueryDefs | Live in the database, not the `.adp` |
| **Stored procedures / functions** | `adp` | Server-side business logic, transaction boundaries, batch operations | Reviewed as "just SQL" |
| **Table definitions** | all | Field types, `Required`, `AllowZeroLength`, `DefaultValue`, `ValidationRule`, `ValidationText`, indexes, uniqueness | Validation rules are properties, invisible unless explicitly dumped |
| **Relationships** | all | Referential integrity, cascade update/delete — maps to foreign-key delete behavior | Diagram is not exported by default |
| **Data macros** | `accdb`, `split-accdb` | Table-level triggers: Before Change, Before Delete, After Insert/Update/Delete | Invisible in the navigation pane; require explicit inspection |
| **Calculated fields** | `accdb`, `split-accdb` | Derived column expressions stored at table level | Look like ordinary fields |
| **Multi-value fields** | `accdb`, `split-accdb` | One logical field backed by a hidden junction table | Appear as a single column and break naive one-to-one mapping |
| **Attachment fields** | `accdb`, `split-accdb` | Multiple files per record | No direct relational equivalent |
| **Report output samples** | all | Column order, header text, totals, sign conventions, grouping, rounding | Treated as nice-to-have rather than a contract |
| **Screenshots** | all | Control labels, enabled/disabled states, default focus, message text | Considered redundant once code is available |

## 3. Extraction Checklist Per Variant

Perform extraction once per project, before Stage 1 of the first screen. Output goes into the evidence directories declared in `PROJECT_CONFIG.md`.

### All variants — front-end objects

1. Export every form, report, macro, and module to text. In Access VBA:
   `Application.SaveAsText acForm, "FormName", "path\Form_FormName.txt"` (and `acReport`, `acMacro`, `acModule`).
2. Capture a screenshot of every screen in its default state, plus one per major dialog or tab.
3. Dump table definitions including field properties (`Required`, `DefaultValue`, `ValidationRule`, `ValidationText`) and all indexes.
4. Dump the relationship list with referential-integrity and cascade settings.

### `adp` additionally

5. Script the SQL Server schema: tables, views, stored procedures, functions, triggers, constraints. Store at `{{LEGACY_DB_SCRIPT}}`.
6. For each form and report, record the `RecordSource` — it names the view, stored procedure, or inline T-SQL that feeds it.

### `mdb` / `accdb` additionally

5. Export every QueryDef's SQL text, including the query type (select, update, delete, crosstab, union, pass-through).
6. Record which queries are used as a form or report `RecordSource` versus called from VBA.

### `accdb` / `split-accdb` additionally

7. Inspect and export **data macros** for every table. These are table triggers and they are not visible in the navigation pane.
8. List calculated fields, multi-value fields, and attachment fields per table — each needs an explicit mapping decision.

### `split-mdb` / `split-accdb` additionally

9. Extract table definitions, relationships, and (for ACE) data macros from the **data** file, not the front end.
10. Record the linked-table connection strings so it is provable which tables were remote.

## 4. Encoding

Exported VBA and macro text uses the Windows codepage of the authoring machine, not UTF-8.

- `{{SOURCE_ENCODING}}` declares it (for example `cp932` for Japanese, `cp1252` for Western European).
- Reading an exported file as UTF-8 produces mojibake. When labels or comments look like garbage, **re-read with `{{SOURCE_ENCODING}}` before drawing any conclusion** — never treat mojibake as evidence of a naming convention.
- Convert to UTF-8 once during extraction if you prefer, but record that you did so; otherwise every reader must know the original codepage.

## 5. Access Constructs Needing Explicit Mapping

These appear constantly in Access code and have no direct equivalent in the target stack. Every occurrence is a mapping decision that belongs in the Screen plan, not an implicit choice made while coding.

| Access construct | Meaning | Mapping consideration |
|---|---|---|
| `Nz(expr, fallback)` | Null-coalesce | Explicit null handling; decide whether the fallback is a business rule or a display default |
| `DLookup`, `DSum`, `DCount`, `DMax` | Domain aggregate over a table with a filter | Becomes a query; watch for N+1 when it sits inside a loop |
| `DoCmd.RunSQL` | Fires an update/delete statement | Wrap in an explicit transaction boundary |
| `DoCmd.OutputTo` | Exports a report to file | Decides output format; see `PROJECT_CONFIG.md` §7 for which formats are preserved versus converted |
| `Me.Filter` / `Me.FilterOn` | Runtime record filtering | Becomes query parameters; preserve the operator semantics, including `Like` wildcards |
| `On Error Resume Next` | Swallows errors | Often hides a real rule ("ignore missing master row"). Decide deliberately; do not copy the suppression |
| Autonumber primary key | Surrogate key | Maps to an auto-increment id; business codes stay separate unique fields |
| Boolean stored as `-1` / `0` | Jet boolean | Normalize to a real boolean; confirm no code depends on `-1` |
| `Date()` / `Now()` | Server-local date/time | Depends on `USE_TZ` and `TIMEZONE` in `PROJECT_CONFIG.md` |
| Currency data type | Fixed-point, 4 decimal places | Use decimal, never float; confirm scale against the legacy field |
| Multi-value field | Hidden junction table | Model an explicit relation; do not flatten into one column |
| Cascade delete on a relationship | Deletes children | Contrast with a protective delete policy; treat any change as an accepted difference requiring sign-off |
| `Deleted` / soft-delete flag column | Row hidden rather than removed | Every query must filter it; missing the filter silently changes results |

## 6. Stage 0 Handoff Contract

Stage 0 (legacy analysis) is performed **outside this pipeline** — by tooling, by a separate plugin, or by hand. The pipeline does not care which, provided the output satisfies this contract.

**Required — the pipeline stops without these:**

1. Evidence files exist under the directories declared in `PROJECT_CONFIG.md` §2.
2. Files are **text-searchable with stable line numbers**, or paginated for binary outputs. Gate anchors reference `file::Routine():start-end` or `file page N`; evidence that cannot be anchored cannot be verified.
3. File names allow a screen to be matched to its evidence — either the legacy object name is in the filename, or a manifest maps screen to files.
4. Encoding is either normalized to UTF-8 or declared via `{{SOURCE_ENCODING}}`.

**Optional — improves pre-flight quality when present:**

5. A draft screen inventory (screen name, legacy object names, candidate module, dependencies) that seeds `Screens_Registry.md`.
6. A dependency map showing which shared modules, queries, or procedures each screen touches — lets G1 scope "applicable evidence" precisely instead of by filename guessing.
7. Extraction coverage report listing objects found versus exported, so a gap in extraction is distinguishable from a gap in review.

**Not expected from Stage 0:** business interpretation, target design, or code. Those are Stages 1, 2, and 3.

Because the contract is defined in terms of files and anchors rather than tooling, replacing manual extraction with automated analysis later requires **no change to the pipeline**.

### 6.1 The Enriched Tier — When Stage 0 Is A Six-Phase Analysis

Items 5–7 above are stated generically because Stage 0's producer is unspecified. When the
producer is a six-phase legacy analysis (this plugin is designed to run after one), those three
optional items exist concretely, and become the **primary** Stage 1 input rather than a bonus:

| Optional item above | Concrete artifact | Format |
|---|---|---|
| 5. Draft screen inventory | Phase2 §1 "Screen, Form, and Report Inventory"; per-screen detail in Phase2 §3 (`### {FORM_ID} — {FORM_NAME}`) | phase document |
| 6. Dependency map | `TraceabilityMatrix.csv` (`traceability-row`: `screen`, `vba_event`, `processing`, `data_target`, `output`, `evidence_ids`) | schema-defined CSV |
| 7. Extraction coverage report | `coverage.json` (`extracted` / `skipped` / `failed` / `unsupported` per object type), `failures/extraction-failures.json` | schema-defined JSON |

Two more artifacts have no generic-contract equivalent above, because nothing in a manual or
tool-agnostic handoff produces them:

- **`Evidence.json`** (`evidenceItem`, schema-defined) — a hash-anchored evidence register.
  `TRACEBACK_GATES.md` §Anchor Format cites its `id` in preference to a hand-built anchor
  whenever it is present.
- **`run-state.json` → `phase_gates`** — per-phase `PENDING | READY | PUBLISHED | REJECTED`.
  Pre-flight reads this before Stage 1 rather than judging evidence sufficiency by eye.

**Precedence when both exist:** the enriched artifacts are the source Stage 1 reads; raw
export directories (`{{EVIDENCE_CODE_DIR}}` etc.) remain the source for what the phases reference
but do not embed — report output samples for Stage 4 format comparison, screenshots for Stage
3b / G3 parity. Neither replaces §7's evidence sufficiency rule; a screen with `phase_gates:
phase2 = PUBLISHED` but no matching raw output sample still has nothing to compare a Stage 4
export against.

State in the pre-flight report which tier was used for this screen. A run that silently fell
back from the enriched tier to the generic minimum looks identical to one that had the
stronger signal, and that silent equivalence is the failure this note exists to prevent.

### 6.2 File Discovery — Match The Real Contract, Not The Template's Own Filename

`ak`'s `specifications/output-contract.yaml` names phase documents
`{APP_ID}_Phase2_ScreenAnalysis_{LANG}.md` (and the equivalent for phases 1, 3–6) — the phase
number is a substring after the app ID prefix, not the start of the filename. Anything that
discovers a phase document under `{{AK_RUN_DIR}}` must match on substring (`"phase2" in
name.lower()`), never `startswith`. A `startswith` check only matches this plugin's own
template filenames (`phase2-screen-analysis.md`), which do not occur in real output —
`scripts/scan_phase2_inventory.py` had exactly this bug until it was caught by renaming a
self-test fixture to the real convention before its first real-project run, not after.

### 6.3 Cross-Artifact Screen Identity — What Is Guaranteed And What Is Not

`Screens_Registry.md`'s `screen` column is documented as the join key across every per-screen
artifact this pipeline writes. What is **not** guaranteed is that the same string appears
identically in every artifact `ak` produces:

- `traceability-row.schema.json` declares `"screen": {"type": "string"}` with no pattern, no
  enum, and no cross-reference back to Phase 2's inventory. Nothing in `ak`'s own analyst
  instructions (`specifications/senior-system-analyst-instruction.md`) states that Phase 4's
  workflow reconstruction must reuse Phase 2's exact `Object` spelling for a screen it
  references — only that the same underlying concept ("user action → screen → processing →
  database → output") flows through both phases.
- `Evidence.json`'s `evidenceItem` is anchored by `id` and `source_path`, not by a `screen`
  field at all — it has no join-key role here.

**What this pipeline does about it, and does not:** `bootstrap-project` copies Phase 2's
`Object` value verbatim into `Screens_Registry.md`'s `screen` column — from that point on,
**this copy is the project's canonical spelling**, protected by Screens_Registry.md's own
"never rename `screen`" rule. When a later artifact (a `TraceabilityMatrix.csv` row, a
`Coding_Records` reference) names what is clearly the same legacy screen with a different
string, reconciling that is a **judgment call for the agent executing G1/G2 at gate time**,
the same way it already reads a hand-built anchor — not a job for a scripted fuzzy-match. A
script guessing two strings mean the same screen is exactly the kind of unverifiable guess
"machine detects, human decides" exists to rule out; if the agent cannot confidently match a
row to a registered screen, that omission is itself a G1/G2 finding to raise, not silently
resolve.

### 6.4 Why Pre-Flight Checks Exactly `phase2`/`phase4`/`phase6`, Not Fewer Or More

`ak`'s own `orchestration/waves.json` publishes phases strictly sequentially — each phase's
publish gate depends on the previous phase's publish gate, with no parallel path between them
(`gate_graph_phaseN` always depends on `gateN-1_publish_phaseN-1`). One consequence: `phase6:
PUBLISHED` cannot occur unless phases 1–5 already are. So checking `phase2`/`phase4`/`phase6`
is, under `ak` 2.7.3's own orchestration, equivalent to checking that the whole six-phase run
is done — `phase6` alone would currently be logically sufficient.

Pre-flight checks the three explicitly anyway, and should keep doing so: relying on `phase6`
alone hard-codes today's dependency chain from `waves.json` into this pipeline. If a future
`ak` version parallelizes phases (2.8 is in progress; nothing says it will not), a check
against `phase6` alone would silently stop being sufficient, while `phase2`/`phase4`/`phase6`
stay correct because they name the actual phases whose *content* this pipeline reads (Phase 2)
or whose *gate* it needs as a readiness signal for Stage 1 (Phase 4, Phase 6) — not because of
how many gates happen to be implied by which other gates this month.

Separately: `phase4-workflow-reconstruction.md` and `phase6-synthesis.md`'s **content** is
currently read by no script and cited by no Stage 1 instruction in this pipeline — only their
*gate status* matters mechanically. An agent doing Stage 1 work may still find it useful
reading material (Phase 6 in particular synthesizes Business Rules, Workflows and Risks in
one place), but that is a judgment call today, not a documented requirement. If that gap is
worth closing, the concrete step would be adding "read `{{AK_RUN_DIR}}`'s Phase 6 document for
scoping context" to the Pre-Flight Check list — not building anything new.

## 7. Evidence Sufficiency Rule

Before Stage 1 for any screen, at least one of the following must exist for that screen:

- an exported form or report definition, or
- a screenshot, or
- a legacy output sample.

If none exists, the pipeline stops and asks. Implementing a screen with no evidence is not modernization — it is redesign, which is out of scope.

## Related Documents

- `MASTER_WORKFLOW.md` — pipeline that consumes this evidence
- `TRACEBACK_GATES.md` — G1 checks evidence coverage against this taxonomy
- `PROJECT_CONFIG.md` — declares variant, paths, and encoding for the current project
