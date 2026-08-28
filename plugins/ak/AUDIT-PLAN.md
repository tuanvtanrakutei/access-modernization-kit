# Audit Plan — Phase 0–6 contract conformance

Opened 2026-08-28. Scope: the seven units of the investigation pipeline (Phase 0
acquisition plus Phases 1–6), audited against the A01 document set as the gold
standard. Outcome of one pass: a findings report plus repaired contracts. No phase
is re-run in this pass.

---

## Status

| Unit | State | Landed in |
|---|---|---|
| **U0** cross-cutting contracts | **done** | `461d826`, `e662dff` |
| Graphify removal | **done** | `461d826` |
| U1 Phase 1 | not started | |
| U2 Phase 2 | not started | |
| U3 Phase 3 | not started | |
| U4 Phase 4 | not started | |
| U5 Phase 5 | not started | |
| U6 Phase 6 | not started | |
| Conformance checker + gold-standard regression | not started | |

U0 delivered: `evidence-classes.yaml`, `identifier-scheme.yaml`,
`errata-contract.yaml`, a rewritten `output-contract.yaml` (document header,
per-phase diagram minimum, the sections Phases 5 and 6 were missing, README as a
required output), real `boundary-map.html` / `e2e-trace.html` / `readme.md`
templates, `$ak derive` and `$ak documents`, INTERVIEW and evidence-class fields in
the evidence schema, and 39 tests. Suite 1264 passing.

Still open in U0 and folded into U1-U6: the phase gates in
`contracts/phase_readiness.py` and `contracts/evidence_requirements.py` are not yet
evidence-class aware - `evidence-classes.yaml` declares `phase_needs` and nothing
reads it yet. That is the first thing U1 does, since it is the same code path for
all six.

---

## 1. The finding that motivates the audit

The kit's contracts specify **structure** — which sections a document has, which
files a run must produce, which capabilities a gate requires. They never specify
**which class of evidence a claim needs**.

That distinction is the whole defect, and the A05 run proves it in one sentence of
its own output. `A05_Phase1_DataUnderstanding_EN.md` §2 reports role counts, the
widest tables, and the application's naming conventions, and then says of the seven
`商品情報N` duplicates:

> purpose not established from schema alone

That statement is correct, honest, and exactly the problem. Schema alone was all the
gate required, so schema alone was all the phase could say. `phase1` passed READY on
`field_inventory` + `key_index_inventory` + `boundary_inventory` + one schema
inventory — four structural capabilities, every one satisfiable from two `.mdb`
files with no human input.

Compare the same section in A01:

> `Dèµ·æ³¨ãã¼ã¿` (D-JuchuData) — 42 columns — PK `JuchuBango` — Central order
> management table. Stores order date, delivery date, store, product, quantity,
> unit price, amount, delivery route, and various status flags.

Nothing in that row comes from a schema. It comes from the training manual, the
operational-functions spreadsheet, the CRUD table, the business diagram PDF, real
data samples, and recorded Q&A with the customer. The A01 set is good **because the
inputs were good**, and the kit currently has no contract that says so.

**Structural evidence produces structural statements. Semantic statements require
semantic evidence.** The gates measure only the first and declare the phase READY.

A second, smaller failure runs beside it: automation reached for the shape it could
compute (counts, inventories, distributions) and the templates accepted it, because
the templates are section skeletons with no depth rule. Every phase template is
25–38 lines. There is no worked example, no minimum unit of analysis, no required
diagram, and no identifier scheme for anything the analysis discovers.

---

## 2. Gold standard

The A01 set is normative for this audit:

| Artifact | Role in the audit |
|---|---|
| `SMS_Phase1_DataUnderstanding_*.md` | per-entity depth, ER diagram, OB-nn observations, risk table with severity |
| `SMS_Phase3_LogicProcessing_*.md` | pipeline diagrams, CSV format tables, INSERT column mapping, VBA→SQL map |
| `SMS_Phase4_WorkflowReconstruction_*.md` | 18 × WF-nnn with sequence diagram + BR-Wnnn rules each |
| `SMS_Phase5_DocumentIntegration_*.md` | org, logistics, 54-system landscape, network architecture, d01–d07 / r01–r49 interface catalog, BR-Dnn, DISC-nn |
| `SMS_Phase6_Synthesis_*.md` | errata E-nn, consolidated BR register, four risk registers, UK-nn, AS-nn, roadmap, cross-reference index, glossary |
| `A01_BoundaryMap.html` | interactive zones, clickable nodes, detail panel, touchpoint inventory |
| `A01_E2ETrace.html` | timeline stepper, per-step data-state tables with +/~/− row diffs |
| `README.md` | reading order, language-version rule, errata-first warning |

"Normative" means: a phase output that cannot carry the same *kinds* of statement as
its A01 counterpart fails the audit, regardless of length. Length is not the measure
— A05 Phase 1 is 283 lines against A01's ~330 and is still the weaker document.

---

## 3. What the audit measures

Seven units (Phase 0 acquisition, Phases 1–6) × four axes:

| Axis | Question | Current state |
|---|---|---|
| **INPUT** | Which evidence *classes* must exist for this phase to make its characteristic claims? | Undefined. Only capabilities, all structural. |
| **OUTPUT** | Which sections, identifier vocabularies, diagrams and per-item depth must the document carry? | Section list only, 25–38 lines per template. |
| **GATE** | What blocks, what degrades to LIMITED, and what does the operator get told to go fetch? | Blocks on capability presence, never on evidence class. |
| **VERIFY** | What machine check proves the published document actually met the contract? | Only `validate_evidence_citations.py` (added this session). Nothing else. |

---

## 4. Cross-cutting defects found in the survey

| ID | Defect | Evidence | Consequence |
|---|---|---|---|
| **D1** | No stable identifier vocabulary for anything the analysis discovers | A01 uses `BR-{DOMAIN}-nn`, `WF-nnn`, `F-nnn`, `RD/RA/RW/RS-nn`, `UK-{D,S,P}-nn`, `AS-nn`, `DISC-nn`, `E-nn`, `d0n`/`r0n`. Kit templates have bare "Rule ID" / "Workflow ID" columns with no scheme; evidence IDs are the only defined identifier in the whole kit. | A rule discovered in Phase 3 cannot be tracked into Phase 6, cited by Phase 4, or checked for coverage by the modernize pipeline. Phase 6's job — consolidation — is impossible without it. |
| **D2** | No bilingual naming-convention contract | Every A01 document opens with the JP-primary rule plus a JP→Romaji quick-reference table. `language-support.yaml` declares encodings and dialects, not this. | A reader meets `店舗ピッキングライン表示情報` with no key, and a translator silently renames a production table. |
| **D3** | No errata / supersession mechanism | A01 Phase 6 opens with `E-01`…`E-13`, each naming the corrected claim, the affected sections and the source that corrected it. The kit has a QA report, which records findings but cannot mark an earlier published claim superseded. | Hit for real this session: the ActiveX claim was wrong in Phase 1 §2 *and* Phase 2 §2, and there was no contract for recording the correction — only prose edits. |
| **D4** | No diagram requirement | A01 is carried by mermaid: ER, flowchart, sequence, gantt. No template asks for one; no gate checks for one. | The relationships a reader needs most arrive as prose tables. |
| **D5** | Derived HTML templates are placeholder-grade | `boundary-map.html` is 21 lines, `e2e-trace.html` is 23. The A01 originals carry zone layout, clickable node → detail panel, touchpoint inventory, timeline stepper, per-step data-state diffs, and a language switch. | The two most-shown deliverables are the two least specified. |
| **D6** | No reading-order deliverable | A01 ships a README that says *start at Phase 6, read the errata first*. `output-contract.yaml` does not list it. | A six-document set is handed over with no entry point. |
| **D7** | Phase 6 template is missing five of A01's load-bearing sections | `output-contract.yaml` `phase6_required_sections` lists 7. A01 additionally carries: Naming Convention, Errata, Recommendations & Migration Roadmap, Appendix A cross-reference index, Appendix B glossary. | Phase 6 becomes a summary instead of the decision-grade hand-off it is supposed to be. |
| **D8** | Phase 5 template omits the entire system-landscape half | The template covers document inventory, extracted rules, and alignment. A01 Phase 5 additionally carries organisation and stakeholders, logistics and product flow, the 54-system landscape, network architecture, and the `d01`–`d07` / `r01`–`r49` input/output file catalog. | The interface catalog is the single most reused artifact downstream, and nothing asks for it. |

---

## 5. Gate defects

| ID | Defect | Current rule (`contracts/phase_readiness.py`) |
|---|---|---|
| **G1** | Phase 3 passes on one capability | `any: {vba_query_inventory, compiled_object_inventory, server_object_inventory, data_only_proof}`. A01 Phase 3's strongest finding — `赤黒FLG == sign(quantity)` across ~4,000 sample rows — required real CSV samples, which no gate requires. |
| **G2** | Phase 5, the richest phase, is optional | `any: {document_inventory}`, status `LIMITED`. Treated as a nice-to-have; in A01 it is where the business exists. |
| **G3** | Phase 4 passes on one capability | `any: {trigger_effect_output_trace}` for a document that in A01 carries 18 workflows with a sequence diagram and a rule set each. |
| **G4** | No gate separates structural from semantic evidence | So `READY` never means "can produce the document", only "can compute an inventory". This is the root cause; G1–G3 are symptoms. |
| **G5** | Six blocking Graphify gates for a component that produced nothing | `waves.json` has `gate_graph_phase1`…`gate_graph_phase6`, each blocking. On A05, Graphify's AST pass produced 0 edges; `derive_graph_facts.py` — deterministic, no LLM, no runtime — produced 756. |

---

## 6. Graphify: removal (decided)

Graphify is removed as a gate and as a dependency; `derive_graph_facts.py` takes its
place as the mandatory pre-phase derivation step.

Rationale, from this project's own measurements: Graphify's AST pass produced 79
nodes and no edges from the A05 query corpus, and the phase gate reported
`edges: 0` for every graph it ever built (a defect closed in `94b4e5f` — the gate
read `edges`, the writer writes `links`). The deterministic derivation reads the
same sources and produces 756 edges by matching query text against the bundle's own
authoritative table list — exact, free, reproducible, and offline.

**Coupling to unwind — 37 files reference Graphify.** The removal touches:

- `orchestration/waves.json` — delete 6 `gate_graph_phase*` waves; the phase waves
  depend directly on their predecessor's publish gate.
- `orchestration/roles.json` — remove the `graph_builder` role.
- `scripts/` — remove `graphify_runtime.py`, `graphify_phase_gate.py`,
  `normalize_graphify_corpus.py`; remove the `graphify` verb from `ak.py`.
- `specifications/` — remove `graphify-runtime.json`; strip the Graphify clauses
  from `output-contract.yaml`, `language-support.yaml`, `runtime-capabilities.yaml`,
  `evidence-layout.yaml`, `input-preconditions.md` ("Mandatory pre-phase Graphify
  context" section) and `package.json`.
- `schemas/manifest.schema.json` + `legacy-manifest-migration.schema.json` — remove
  the Graphify keys; `migration.py` stops proposing them.
- `references/graphify-phase-gate.md` — replaced by a derivation reference.
- `scripts/preflight.py`, `create_run.py`, `create_tasks.py`, `init_app.py`,
  `validate_structure.py` — drop the checks and scaffolding.
- Tests: `test_package_smoke.py`, `test_preflight.py`, `test_init_app.py`,
  `test_migration.py`, `test_phase_evidence.py` carry Graphify assertions to rewrite.
- `app.graphifyignore` template retires with it.

The `.graphifyignore` → corpus-normalisation idea does not retire: the distillation
that put UI facts into the corpus for the first time lives in `derive_graph_facts.py`
and stays.

**What is genuinely lost:** semantic/community queries over the corpus. Nothing in
Phases 1–6 as specified needs them, and nothing in the A01 gold standard was produced
with them.

---

## 7. Work units

Each unit produces the same four artifacts: an evidence-class table (INPUT), a
repaired template + identifier scheme (OUTPUT), a repaired gate (GATE), and a
conformance check (VERIFY).

### U0 — Phase 0 (acquisition) + cross-cutting contracts

The largest unit, because D1–D6 are settled here once for all phases.

- **Evidence-class taxonomy** — a new `specifications/evidence-classes.yaml`
  defining the classes the pipeline recognises and, for each, what it can and cannot
  support: `SCHEMA`, `CODE`, `UI_DEFINITION`, `SCREENSHOT`, `SAMPLE_DATA`,
  `OUTPUT_SAMPLE`, `DOCUMENT`, `INTERVIEW`, `OPERATOR_DECLARATION`. The rule the
  audit exists to write: *a claim about business meaning, frequency, ownership or
  intent requires `DOCUMENT`, `INTERVIEW` or `OPERATOR_DECLARATION`; no volume of
  `SCHEMA` substitutes.*
- **Identifier scheme** (D1) — `specifications/identifier-scheme.yaml` registering
  the `BR-`, `WF-`, `F-`, `RD/RA/RW/RS-`, `UK-`, `AS-`, `DISC-`, `E-`, `d`/`r`
  vocabularies, their namespaces, allocation rules, and the requirement that every
  one carries an evidence citation.
- **Naming convention block** (D2) — a required document header, generated from the
  bundle's own object names, not hand-written.
- **Errata contract** (D3) — an `{APP_ID}_Errata.json` register plus the Phase 6
  section that renders it; each entry names the superseded claim, its evidence ID,
  the affected sections and the correcting source.
- **Diagram requirement** (D4) — per-phase minimum diagram set.
- **Derived-output specs** (D5) — real `boundary-map.html` / `e2e-trace.html`
  contracts, derived from the A01 originals: zones, clickable node → detail panel,
  touchpoint inventory table; timeline stepper, per-step data-state table with
  `new`/`upd`/`del`/`unchanged` row marking.
- **README deliverable** (D6) — added to `output-contract.yaml`.
- **Interview/Q&A evidence shape** — A01 cites `Q&A ID-19 (Tanaka+Sekiya
  2026-05-06)` as a first-class source. The kit has no shape for it; add one to the
  evidence schema so an answer from the customer is citable like a file.

### U1 — Phase 1 (Data Understanding)

- INPUT: `SCHEMA` gets the inventory; per-table business meaning requires
  `DOCUMENT` or `INTERVIEW`. Gate reports which tables have meaning and which do
  not, rather than passing silently.
- OUTPUT: per-entity rows (columns / PK / business meaning), entity attribute
  groups, mermaid ER diagram, `OB-nn` observations, risk table with severity.
- VERIFY: every table in the inventory either carries a meaning with a citation, or
  appears in the "meaning not established" list. No third state.

### U2 — Phase 2 (Screen Analysis)

- INPUT: `UI_DEFINITION` gives inventory, binding and events; screen *purpose* and
  *who uses it* require `SCREENSHOT` + `DOCUMENT`/`INTERVIEW`.
- OUTPUT: `F-nnn` screen IDs, navigation map, per-screen action→event→validation→
  target table, shared UI patterns, unreachable-object list with the routes not
  examined stated (the A05 run got this one right; keep it).
- VERIFY: screen count reconciles with the bundle; every `F-nnn` resolves.

### U3 — Phase 3 (Logic & Processing)

- INPUT: `CODE` gives the pipeline; file-format claims require `SAMPLE_DATA`;
  output-format claims require `OUTPUT_SAMPLE`. Fixes **G1**.
- OUTPUT: per-pipeline mermaid flow, step tables, INSERT column mapping, VBA→SQL
  map, `BR-{DOMAIN}-nn` rules, risk register.
- VERIFY: every `BR-` cites evidence; every file format claimed has a sample cited.

### U4 — Phase 4 (Workflow Reconstruction)

- INPUT: needs Phases 2 and 3 published, plus `INTERVIEW`/`DOCUMENT` for timing and
  actor. Fixes **G3**.
- OUTPUT: `WF-nnn` per workflow with a sequence diagram and `BR-Wnnn` rules;
  cross-workflow data-flow diagram; operational timing.
- VERIFY: every `WF-` has ≥1 diagram and ≥1 rule; traceability rows exist per step.

### U5 — Phase 5 (Document Integration)

- INPUT: `DOCUMENT` is mandatory, not `LIMITED`-optional. Fixes **G2**.
- OUTPUT: adds the missing half (D8) — organisation, logistics, system landscape,
  network architecture, `d`/`r` interface catalog — plus `BR-Dnn` and `DISC-nn`
  document-vs-code discrepancies with severity.
- VERIFY: every `DISC-` names both the document claim and the code observation.

### U6 — Phase 6 (Synthesis)

- INPUT: all prior phases published + errata register.
- OUTPUT: adds the five missing sections (D7) — naming convention, errata,
  recommendations & roadmap, cross-reference index, glossary — plus the consolidated
  `BR-` register, four risk registers, `UK-nn`, `AS-nn`.
- VERIFY: every `BR-`/`UK-`/`AS-`/`RD-` in Phase 6 resolves to a prior phase; every
  errata entry names a real superseded claim.

---

## 8. Deliverables

1. `plugins/ak/AUDIT-FINDINGS.md` — the conformance matrix, seven units × four axes,
   each row citing the file and line that fails.
2. New specifications: `evidence-classes.yaml`, `identifier-scheme.yaml`,
   `errata-contract.yaml`.
3. Repaired: six phase templates, `boundary-map.html`, `e2e-trace.html`,
   `output-contract.yaml`, `question-list.md`, `qa-report.md`, plus a new
   `readme.md` template.
4. Repaired gates in `contracts/phase_readiness.py` +
   `contracts/evidence_requirements.py`, evidence-class aware.
5. Graphify removed across the 37 files; `derive_graph_facts.py` promoted to the
   mandatory pre-phase step.
6. New verifier `scripts/validate_phase_conformance.py` joining
   `validate_evidence_citations.py`, reachable as `$ak conformance`.
7. Tests for every new contract, in the existing style: one test per real defect.

---

## 9. Verification

- `python -m pytest plugins/ak/tests/ -q` — currently 1229 passing; must stay green.
- `python plugins/ak/scripts/ak.py validate` — package structure.
- `python plugins/ak/scripts/ak.py citations --outputs <dir>` — no dangling ids.
- `python plugins/ak/scripts/ak.py conformance --outputs <dir>` — new; each phase
  document carries its required sections, identifier vocabularies and diagrams.
- Regression against the gold standard: run the conformance checker over the A01
  document set. **It must pass.** A contract the reference set fails is a contract
  written wrong — this is the audit's own error check.
- Regression against A05: the same checker over the existing A05 Phase 1–2 outputs
  must *fail*, and its failures must name the gaps this plan identified. If it
  passes, the contract is still too weak.

---

## 10. Sequence

U0 first and alone — the identifier scheme, evidence classes and errata contract are
depended on by every later unit. Then U1–U6, each independently verifiable. Graphify
removal runs alongside U0 since it touches the same specifications.

Not in this pass: re-running any A05 phase. The A05 outputs stay as the "before"
sample the conformance checker is calibrated against.
