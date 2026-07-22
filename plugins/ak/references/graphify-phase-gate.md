# Graphify Runtime, Corpus, and Phase Gate

Graphify is mandatory navigation context for Phase 1-6. It remains supporting
infrastructure: source-backed locations are evidence; inferred graph edges are
leads only.

## Installation boundary

Installing the `ak` plugin does not execute Python package installers. At the
first Phase/run request, `scripts/graphify_runtime.py ensure` creates a pinned
virtual environment under the user's local cache, installs Graphify plus the
tested document extras, and registers the Graphify skill for Codex or Claude.
It never installs into system Python, the plugin cache, or the app workspace.

The managed runtime is pinned by `specifications/graphify-runtime.json`. A
different global `graphify` executable may coexist, but the Phase gate uses the
managed executable and records its exact Python path and version.

## Required sequence before every phase

1. Build or validate `extracted/component-index.json` and the module plan.
2. Run `graphify_phase_gate.py prepare --app-root <APP_ROOT> --phase <N>
   --runtime <codex|claude|generic>`.
3. The prepare action installs the managed runtime when missing and rebuilds the
   deterministic text-only corpus under the manifest's Graphify output folder.
4. If the result is `GRAPH_BUILD_REQUIRED`, use the installed Graphify skill to
   build the full graph from the reported `corpus_root`.
5. If the result is `GRAPH_UPDATE_REQUIRED`, follow the Graphify skill's update
   workflow. Source/document changes may require semantic re-extraction; do not
   treat a static-only refresh as complete when Graphify reports `needs_update`.
6. Run `graphify_phase_gate.py finalize ...` after the graph build/update. This
   validates `graph.json`, pins it to the corpus fingerprint, runs the
   phase-specific Graphify query, and writes a receipt under
   `graphify-out/phase-context/`.
7. Run `graphify_phase_gate.py check ...`. Start the phase only when it returns
   `READY` for that phase and current corpus fingerprint.

Repeat the freshness check and phase-specific query for Phase 1, 2, 3, 4, 5,
and 6. `$ak run` does not bypass these six gates.

## Binary-free corpus policy

`scripts/normalize_graphify_corpus.py` discovers manifest-declared sources plus
the canonical component index/module plan. It writes UTF-8 derivatives with
source paths and hashes, then writes `CORPUS_AUDIT.json`.

Never ingest:

- MDB, ACCDB, ADP, LACCDB, LDB, or any disposable snapshot
- credentials, DSNs, run state, evidence outputs, or prior rendered outputs
- a binary document merely because Graphify recognizes its extension

The audit must report `binary_files_ingested: 0`. Access code and metadata enter
the graph only through exported/normalized text such as SaveAsText, QueryDef
SQL, schema JSON, and the deterministic component index.

## Format support and normalization

| Input | AK handling before Graphify |
|---|---|
| TXT, MD, JSON, YAML, HTML, SQL and common source files | Strict UTF-8/UTF-16/CP932/Shift-JIS decode, then UTF-8 text |
| Access VBA BAS, CLS, FRM, VB | Normalize to UTF-8 `.txt`; do not rely on a generic `.cls` parser |
| CSV, TSV | Convert to Markdown tables with provenance |
| XLSX | Convert worksheets with `openpyxl` from the managed runtime |
| XLS | Convert worksheets with `xlrd` from the managed runtime |
| DOCX | Convert paragraphs and tables with `python-docx` |
| PPTX | Convert slide text with `python-pptx` |
| PDF with text layer | Extract with `pypdf` |
| Scanned PDF or image | Render/OCR with Tesseract when available; Japanese sources require `jpn` data |
| Legacy DOC or PPT | Report `CONVERSION_REQUIRED`; do not claim successful ingestion |

Tesseract is an external executable and is not silently installed by the Python
runtime bootstrap. A missing OCR capability is recorded as `OCR_REQUIRED` in
the corpus audit. Other readable sources can still produce a graph, but Phase 5
must report the document coverage gap and must not invent the missing text.

## Build/update invocation

Follow the installed Graphify skill, including its file-count, token, semantic
extraction, and honesty gates. Direct the output to the app's configured
Graphify folder. The environment variable `GRAPHIFY_OUT` can point to that
absolute folder while the input path is the reported normalized corpus.

Do not run Graphify against the app root or `sources/access`. Do not accept an
old graph merely because `graph.json` exists: `GRAPH_STATE.json`, the graph
hash, corpus fingerprint, and the current phase query receipt must all match.
