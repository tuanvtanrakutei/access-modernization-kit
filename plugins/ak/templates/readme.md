# {{APP_ID}} — how to read this document set

{{APP_NAME}}. Six phase documents plus their control artifacts, produced by run
`{{RUN_ID}}` on {{GENERATED_AT}}.

## 1. Start at Phase 6, and read its errata first

Phase 6 opens with an errata table. It supersedes claims made in Phases 1–5 and
names which sections carried them. **Read it before quoting anything from an
earlier phase**, or you will quote a statement this run has already corrected.

## 2. The documents

| Phase | File | What it establishes | Scope |
|---|---|---|---|
| 1 | `{{APP_ID}}_Phase1_DataUnderstanding_{{LANG}}.md` | Tables, columns, keys, relationships, and what the data means | {{APP_ID}} |
| 2 | `{{APP_ID}}_Phase2_ScreenAnalysis_{{LANG}}.md` | Screens, how each is reached, what it binds to, who uses it | {{APP_ID}} |
| 3 | `{{APP_ID}}_Phase3_LogicProcessing_{{LANG}}.md` | Processing pipelines, file formats, business rules | {{APP_ID}} |
| 4 | `{{APP_ID}}_Phase4_WorkflowReconstruction_{{LANG}}.md` | End-to-end workflows: user action → screen → processing → data → output | {{APP_ID}} |
| 5 | `{{APP_ID}}_Phase5_DocumentIntegration_{{LANG}}.md` | What the business says the system does, and where that differs from the code | {{SYSTEM_SCOPE}} |
| 6 | `{{APP_ID}}_Phase6_Synthesis_{{LANG}}.md` | One decision-grade account, with errata, risks, unknowns and a roadmap | {{SYSTEM_SCOPE}} |

Derived views: `{{APP_ID}}_BoundaryMap.html` (what crosses the boundary) and
`{{APP_ID}}_E2ETrace.html` (what one unit of work does to the data, step by step).

## 3. Reading order by role

- **Management / PM** — Phase 6 executive summary, risks, roadmap. Then Phase 5 for business context.
- **Migration developer** — Phase 6, then Phase 1 (data model), Phase 3 (logic), Phase 4 (workflows).
- **Business analyst** — Phase 5, then Phase 4, then Phase 2.
- **Tester** — Phase 2 (per-screen validation), then Phase 4 (end-to-end paths).

Phase 6's Appendix A indexes every section back to the phase that established it.

## 4. Identifiers

Findings carry stable identifiers, allocated by the phase that discovered them and
never renumbered. Every one cites the evidence behind it.

| Prefix | Meaning | Allocated in |
|---|---|---|
| `BR-{DOMAIN}-nn` | Business rule | Phases 3–5 |
| `WF-nnn` | End-to-end workflow | Phase 4 |
| `F-nnn` | Screen or report — always shown beside the object's real name | Phase 2 |
| `OB-nn` | Technical observation | Phase 1 |
| `RD/RA/RW/RS-nn` | Risk: data · application · workflow · security | Phases 1–6 |
| `DISC-nn` | Document contradicts code | Phase 5 |
| `UK-{D,S,L,W,P}nn` | Unknown carried forward | Phases 1–5 |
| `AS-nn` | Assumption carried forward | any |
| `E-nn` | Errata — supersedes an earlier claim | Phase 6 |
| `Q-n` | Open question to a stakeholder | any |
| `d0n` / `r0n` | Inbound / outbound interface file | Phase 5 |

## 5. Evidence

`{{APP_ID}}_Evidence.json` is the register every claim resolves to. An item records
what was observed, from which file and location, and at what confidence:

- `EXTRACTED` — stated directly by a source.
- `INFERRED` — a reasonable conclusion from several observations. Not a fact.
- `AMBIGUOUS` — conflicting or incomplete; needs review.

**A claim about business meaning, usage or intent requires a document, an interview,
or an operator's declaration.** No volume of schema or code substitutes, and where a
document is missing the phase says so by name rather than filling the gap.

Everything named here is in this directory. What produced it - the acquisition
bundle, the extraction output, the run's working state - is under `.ak/`, which
you never need to open: an evidence item cites a full path when you want to follow
one back.

`{{APP_ID}}_TraceabilityMatrix.csv` maps workflow steps to the evidence behind them.
`{{APP_ID}}_QuestionList.md` holds what is still open and who can settle it.
`{{APP_ID}}_QA_Report.md` is the independent check, including the defects it found in
this run's own output.

## 6. Naming

Table, object and file names are the **production names**, unchanged. Where they are
Japanese the documents are JP-primary: the Japanese name is authoritative and a
Romaji alias follows in parentheses for cross-reference. A translated name reads like
a definition and is not one — never substitute one for the real name in code,
configuration, or a migration plan.

## 7. What this run did not have

{{SOURCE_GAPS}}

Each gap is stated where it bites rather than only here, so a reader of any single
section can see what that section could not establish.

---
*Run `{{RUN_ID}}` · {{APP_ID}} · generated {{GENERATED_AT}}*
