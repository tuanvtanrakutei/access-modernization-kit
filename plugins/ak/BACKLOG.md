# Investigation-Side Backlog

Improvement notes for the `ak` investigation pipeline - acquisition, extraction,
the Graphify phase gate. The modernize plugin keeps its own list in
`modernize/BACKLOG.md`.

Each entry records what was observed, on what evidence, and what is not yet known.
An entry is only closed by a change plus the run that proves it, not by reasoning
that it should now work.

---

## Open

### A1 - Graphify's AST pass yields no edges for a query-only corpus

**Observed 2026-08-26, A05.** A corpus of 79 exported `.sql` files plus 15
documents produced 79 nodes and **0 edges** from `graphify.extract`. One node per
file, no relationships. Clustering over that graph is meaningless, and the phase
gate accepts it because `graph_shape` only requires `node_count > 0`.

The relationships exist and are unambiguous: every query names the tables it
reads. Matching query text against the authoritative table inventory produced 238
edges, all `EXTRACTED` with a real line number - no inference. That was done by
hand for this run.

**Not yet known:** whether this is better solved in the kit (derive the edges
deterministically as part of corpus preparation, where the table inventory is
already available) or left to the Graphify skill's semantic pass. The
deterministic route is exact and free; the semantic pass costs tokens and can only
guess at what the SQL states literally.

### A2 - Japanese identifiers collapse under Graphify's node-ID rule

**Observed 2026-08-26, A05.** The skill's ID rule normalizes to `[a-z0-9_]`, which
erases every character of a Japanese name. `受注データ`, `商品マスタ` and
`店舗マスタ` all reduce to the same underscore run, so distinct entities become
one node. Worked around by appending a short sha1 of the original name - the same
technique `extract_access.ps1` already uses for its filenames, and `init_app.py`
for artifact ids.

This kit targets Japanese legacy systems, so the collapse is the normal case here,
not an edge case. Anyone following the skill's rule literally builds a graph whose
Japanese nodes are silently merged.

### A3 - UI evidence never reaches the graph

**Observed 2026-08-26, A05.** `CORPUS_AUDIT.json` reported 132 gaps against 98
ingested files:

- 81 `EXCLUDED_POLICY` - SaveAsText definition text, excluded deliberately
- 51 `OCR_REQUIRED` - every screenshot, because `tesseract` is absent

Both exclusions are individually defensible. Together they mean no form or report
evidence of any kind enters the graph: not the definitions, not the screenshots.
Phase 2 asks the graph about screens and the graph has never seen one.

**Not yet known:** whether the definition-text exclusion should be narrowed (the
property soup is noise, but control names and record sources are not), and whether
OCR should be part of the corpus contract rather than an optional capability.

### A4 - `Error in loading DLL` on the A05 frontend: cause unresolved

**Observed 2026-08-26.** After RUNASADMIN was removed from `MSACCESS.EXE`'s
`AppCompatFlags\Layers` value, COM activation succeeded (`ok: true, version:
11.0, bitness: 32`) and `品揃支援data.mdb` extracted completely through the Access
host with no dialog: 104 tables, 39 queries, 4 reports, 1 module.

The frontend `品揃支援（windows11専用）.mdb` behaved differently in the same
non-elevated configuration: the VBA project dropped into break mode, then raised
`Error in loading DLL`, which needed a human click. `AutomationSecurity = 3`
prevented the break but not the reference load, because references load when the
project opens, before any macro runs.

Two candidate causes, not yet distinguished:

1. a reference to a 32-bit library that is missing or unregistered on Windows 11
2. a library that loads only with elevation

**Decisive test:** run the frontend extraction from an elevated terminal. If it
completes, cause 2; if it still fails, `project_context.references` names the
library whose `broken` flag is set. Either answer is actionable, and both are
cheap now that `--timeout` bounds a hang and terminates only the host this run
started.

---

## Closed

Closed entries name the commit that closed them and the run that proved it.

- **Managed Access extraction never worked against a real database** - 31 defects
  found by running both adapters against a real split Access 2003 application.
  `692f25d`. Proven by acquiring `A05_DATA`: 18 of 116 tables before, 104 after.
- **`graph_shape` reported every graph as having no edges** - Graphify writes the
  node-link shape, whose edge list is named `links`; the gate read only `edges`.
  `94b4e5f`. Receipt went from `edges: 0` to `edges: 237` on the same graph.
- **A declared Access runtime was recorded and never enforced** - `runtime.access_path`
  wrote `matches: false` into the receipt and nothing read it, so a run proceeded
  against an install the operator had explicitly said it was not. Preflight also never
  reported which Access would open the database. Both closed by naming the registered
  executable and version in preflight, and refusing the run on a mismatch.
- **Acquisition mode was inferred twice, by two rules that could disagree** -
  `8616a8a` made it a declaration, `c0d4a47` demoted it to an observation and put
  the protection where it belongs: `--require-phases` fails when the evidence
  cannot carry the phases asked for.
