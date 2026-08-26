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

### A5 - `build_import_manifest.py` refuses the exporter's own metadata file

**Observed 2026-08-26, A05.** `tools/ExportAccessObjects.bas` writes
`export-manifest.txt` at the root of every package it produces. Building the
producer manifest for that package fails:

```
unclassified: ["export-manifest.txt"]
remedy: Move them into a recognized directory (...) or pass --allow-unclassified.
```

Classification keys on the containing directory, and a file at the package root
has none, so the kit refuses the artifact its own exporter placed there. Passing
`--allow-unclassified` declares it as `metadata` and the import succeeds - which
is the right outcome, reached through a flag whose documented purpose is to
tolerate files the kit does not recognize.

The same round-trip class as the `.txt`-classified-as-`sample` defect that
`init --source` had: producer and consumer inside one package disagreeing about a
convention the package itself defines. A known producer's own manifest file should
be recognized by name, not require an override that also lowers the bar for
everything else in the tree.

### A7 - deliberate exclusions are counted as extraction failures

**Observed 2026-08-26, A05.** `coverage.json` reported `unclassified: failed=11`.
Reading the eleven: eight are linked tables whose external file is genuinely
unreadable, and three are exclusion tallies the extractor emits on purpose -
`Excluded 5 non-model tables`, `Excluded 3 Access-generated hidden queries`,
`Excluded 55 Access-generated hidden queries`.

Filtering an ImportErrors table or a `~sq_*` query is the extractor working
correctly, and the count is worth recording. Sending it down the same `failures`
channel as "this object could not be read" makes coverage overstate failure by
more than a third, and makes a clean run look damaged.

Two different facts share one channel. An exclusion tally belongs in its own field
- `exclusions`, counted separately - so `failed` keeps meaning "evidence that
should exist and does not".

---

## Closed

Closed entries name the commit that closed them and the run that proved it.

- **`Error in loading DLL` on the A05 frontend was not an elevation problem** -
  the dialog appeared again in a **non-elevated** run, was dismissed, and the
  extraction then completed both tiers: 51 forms, 63 reports, 43 queries, 7 modules,
  1 macro, all with definition text. All six VBA references resolved with `broken:
  false`. So the load failure is a dismissable one-time failure, not a permission
  wall, and running as administrator is not required to acquire this application.
  What the references do show is recorded as A6.
- **`Error in loading DLL` was a VBIDE reference hijacked by a third-party Office** -
  the frontend ships in two states on this machine. The 187MB `_Backup` carries six
  VBA references including `VBIDE` pointing at
  `C:\Program Files (x86)\Kingsoft\WPS Office\...\office6be6ext.olb`, and it
  raises the dialog. The 17MB compacted copy carries five - no `VBIDE` - and opens
  clean through automation in under 60s, non-elevated. Object inventories are
  byte-for-byte equal in shape: 22 tables, 43 queries, 51 forms, 63 reports, 7
  modules, 1 macro, no name differing. So Compact & Repair dropped the hijacked
  reference, and neither elevation, snapshot location, write permission, nor
  `AutomationSecurity` was involved. Prefer the compacted file: same evidence,
  reproducible unattended.
- **A hung Access host destroyed the DAO tier's own results** - the extractor wrote
  `schema/tables.json`, `component-index.json` and its receipt only after both tiers
  finished, so the caller's timeout killed the process before any of it existed. A
  real hang left 43 query files and nothing else: `dao_tier: null`, zero components.
  The two-tier promise that tier 2 "is allowed to fail without costing the DAO tier's
  results" held for an exception and never for a hang - the failure mode the timeout
  itself introduces. The write block is now a function called as soon as tier 1
  completes and again at the end. Verified by timing out tier 2 on purpose.
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
