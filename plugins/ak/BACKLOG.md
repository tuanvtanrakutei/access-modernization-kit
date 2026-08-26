# Investigation-Side Backlog

Improvement notes for the `ak` investigation pipeline - acquisition, extraction,
the Graphify phase gate. The modernize plugin keeps its own list in
`modernize/BACKLOG.md`.

Each entry records what was observed, on what evidence, and what is not yet known.
An entry is only closed by a change plus the run that proves it, not by reasoning
that it should now work.

---

## Open

### A9 - snapshot isolation breaks an app that resolves its backend as a sibling

**Observed 2026-08-26, A05 frontend.** Opening the frontend snapshot raises
`Run-time error '3024': Could not find file '...\staging\WINDOWS11_45D0FDDD\品揃支援DATA.MDB'`.
The cause is in the application, and it is a common Access pattern.
`メインメニュー.Form_Open` derives the backend path from its own location:

```vba
FWパス名 = SCRTDB.name                    ' the frontend's own full path
For FWI = Len(FWパス名) To 3 Step -1      ' scan back for the last "\"
    If Mid(FWパス名, FWI, 1) = "\" Then
        Sパス名 = Left(FWパス名, FWI)
        Exit For
    End If
Next FWI
Sパス名 = Sパス名 & FWデータ名             ' & "品揃支援DATA.MDB"
Set SCDB = OpenDatabase(Sパス名)
```

Four more forms do it directly:
`OpenDatabase(Application.CurrentProject.path & "\品揃支援data.mdb")` -
`アイス確認表2`, `酒アイテム別確認表`, `雑貨Ⅱアイテム別確認表`, `青果アイテム別確認表`.

In production both databases sit in one folder, so the sibling resolves. The
extractor snapshots one file into a directory of its own, so it never can. Every
symptom chased before this - elevation, write permission, Compact & Repair,
AutomationSecurity - was downstream of it.

**Fix direction:** the manifest already declares both databases. Snapshot the
artifacts of one application into a shared directory, preserving the sibling
layout, rather than one directory per artifact. A frontend that cannot open its
backend cannot export a form that binds to it, so this bounds what the Access host
tier can ever produce for a split application.

### A10 - forcing macros off disables the app's own repair step

**Observed 2026-08-26, A05.** `AutomationSecurity = 3` was added so a startup that
drops into the VBA debugger cannot hang an unattended run. On this application it
also disables the code that makes the application work:

```vba
Public Function AutoExec2()
    DoCmd.DeleteObject acTable, "商品情報"
    DoCmd.TransferDatabase acImport, "Microsoft Access", _
        "L:\sms\新品揃支援\XP\品揃支援data.mdb", acTable, "商品情報", "商品情報"
    DoCmd.TransferSpreadsheet acExport, acSpreadsheetTypeExcel9, _
        "商品情報", "L:\user\物流部\商品情報.xls", True, "出力結果"
End Function
```

The path it imports from carries `sms`, while the stored linked-table `Connect` for
the same database does not - so startup code is what reconciles a stale link, and
suppressing it leaves the stale one in force. That is also why the extraction
reported those tables unreadable.

The setting is right for an unattended inventory and wrong for a faithful run, and
it is currently unconditional. It belongs behind `runtime.automation_security` so a
run can choose: suppressed for hands-off extraction, enabled when the trace has to
reflect what the application actually does.

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

- **Two different failures wore the same name, and neither needed elevation** -
  the A05 frontend produced `Run-time error '3024': Could not find file
  ...\WINDOWS11_45D0FDDD\品揃支援DATA.MDB` and, separately, `Compile error: Error in
  loading DLL`. They have different causes and different fixes.

  3024 is the sibling-resolution problem recorded as A9: the frontend derives its
  backend path from its own location, so a snapshot directory holding one database
  cannot satisfy it. Fixed by snapshotting every database of one application into a
  shared directory, backends first. Proven: the window that used to be a dialog is
  now `【新受注システム連携】品揃支援システム - [メインメニュー]`, the application's
  own main menu, and the run needs nobody to click anything.

  `Error in loading DLL` is a **compile** error, raised when VBA compiles the project
  and cannot load `VBIDE`, which on this machine resolves to
  `C:\Program Files (x86)\Kingsoft\WPS Office\12.1.0.28032\office6\vbe6ext.olb` - a
  third-party Office registered itself as the provider. Nothing in the application
  uses VBIDE: zero hits for `VBIDE`, `VBProject`, `CodeModule`, `VBComponent` or
  `Application.VBE` across all 166 exported files, so the reference is vestigial and
  removing it is safe. Compact & Repair also drops it - the 17MB copy carries five
  references and no VBIDE.

  Extraction never meets this error because `SaveAsText` serializes without
  compiling, which is why every automated run completed while an interactive session
  hit it. That makes it harmless to the bundle and material to anything that has to
  **run or modify** the legacy application on this host - a Phase 1 risk, not an
  acquisition defect.

  Elevation was not involved in either. `品揃支援data.mdb` acquires cleanly through
  both tiers non-elevated, and so does the frontend once its backend sits beside it.
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
