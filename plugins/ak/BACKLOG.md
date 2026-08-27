# Investigation-Side Backlog

Improvement notes for the `ak` investigation pipeline - acquisition, extraction,
the Graphify phase gate. The modernize plugin keeps its own list in
`modernize/BACKLOG.md`.

Each entry records what was observed, on what evidence, and what is not yet known.
An entry is only closed by a change plus the run that proves it, not by reasoning
that it should now work.

---

## Open

### A11 - nothing verified that an embedded ActiveX control can actually load

**Observed 2026-08-26, A05 frontend.** Eight reports embed
`Class = "BARCODE.BarCodeCtrl.1"` - every ピッキングリスト, the application's main
output - and the extraction receipt said nothing about whether that control was
usable. `project_context.references` reports the VBA reference list, and a reference
resolves through a different registry key than an embedded control does, so a clean
reference list is not evidence that a form will open.

`extract_access.ps1` now collects every `Class = "<ProgID>"` its own exported
definitions contain and resolves each one from the PowerShell host that drives
Access. That host's bitness matches the registered Access, so its registry reads go
through the same WOW64 redirection Access uses - which is the point: a control
registered into the other view is invisible from here in exactly the way it is
invisible to Access. The receipt records ProgID, CLSID, server path, whether the
server file exists, and whether the type library is registered; an unresolvable
class raises a warning naming the object that cannot load.

**What running it established, against the hypothesis that motivated it.** The
barcode control resolves completely from the 32-bit host - `registered: true`,
`type_lib_registered: true`, `server_exists: true` - and
`New-Object -ComObject BARCODE.BarCodeCtrl.1` in that host returns a live object. So
the control is not the cause of the `Error in loading DLL` dialog an operator sees
when opening a form, and the earlier reading of this entry was wrong. It was based
on querying `HKLM\SOFTWARE\WOW6432Node\Classes` from a 64-bit shell, which is the
wrong place twice over: ProgID keys under HKCR are shared between views rather than
redirected, and the redirected ones land under `HKLM\SOFTWARE\Classes\Wow6432Node`,
not under `HKLM\SOFTWARE\WOW6432Node\Classes`.

The check also caught a defect in its own first implementation: SaveAsText writes
`OLEClass ="<localized display name>"` beside the real `Class ="<ProgID>"`, and the
pattern matched both, so a caption - `Microsoft ﾊﾞｰｺｰﾄﾞ ｺﾝﾄﾛｰﾙ` - was reported as an
unloadable control. Fixed with a preceding-letter guard.

**Still unexplained:** what raises `Error in loading DLL` when an operator opens a
form. Disproved so far: elevation, snapshot location, write permission, Compact &
Repair, the VBIDE reference on the compacted copy, and now the barcode control. The
next datum that would settle it is which form was open when the dialog appeared -
its definition names everything it loads, and every candidate above can be checked
against that one object rather than against the application as a whole.

---

## Closed

Closed entries name the commit that closed them and the run that proved it.

- **A split application could not open its backend from a snapshot** - the frontend
  derives the backend path from its own location, so a snapshot directory holding one
  database can never satisfy it. Databases of one application are now snapshotted side
  by side, backends first, because the backend's copy has to exist beside the frontend
  by the time the frontend starts. Proven: the Access window that used to be an error
  dialog became the application's own main menu, and the run needs nobody to click.
- **Suppressing macros also suppressed the application's own repair step** - forcing
  AutomationSecurity off keeps an unattended run out of the VBA debugger, and on A05 it
  also disabled AutoExec2(), which relinks two tables whose stored Connect strings are
  stale. Now `runtime.automation_security` chooses: suppressed for a hands-off
  inventory, allowed when the run has to reflect the working application, with a
  warning recorded either way.
- **The importer refused the file its own exporter writes** - `export-manifest.txt`
  sits at the root of every package `tools/ExportAccessObjects.bas` produces, and
  building the producer manifest failed on it as unclassified unless the operator
  passed a flag that also lowered the bar for everything else in the tree. Recognized
  by name now, from the same layout declaration both sides read. Verified: a package
  imports with `status: WRITTEN` and no override.
- **Deliberate exclusions were counted as extraction failures** - filtering Access
  temporary tables, auto-generated ImportErrors tables and ~sq_* queries is the
  extractor working correctly, and reporting it through the same channel as "this
  object could not be read" made coverage overstate failure by more than a third. The
  extractor marks them, the adapter tags them, and coverage counts them under
  `skipped`. On a real acquisition: failed 9, skipped 3, where it used to say failed 11.
- **Graphify's AST pass produced no edges, Japanese ids collapsed, and no UI
  evidence reached the graph** - one derivation answers all three. A query names the
  tables it reads, in text, beside the authoritative table list the bundle already
  holds; matching one against the other is exact and free, where a semantic pass
  would spend tokens guessing at something the source states outright.
  `scripts/derive_graph_facts.py` emits nodes and edges from that matching, minting
  ids with the digest suffix `extract_access.ps1` and `init_app.py` already use - so
  受注データ, 商品マスタ and 店舗マスタ stay three nodes instead of merging into one
  underscore run. On A05: **325 nodes, all ids unique, 756 edges**, against 79 nodes
  and zero edges from the AST pass, and the hubs are the business entities - 商品名
  87, 商品マスタ 42, 受注データ 38.

  The same pass distils the definition text the corpus renounces. Excluding it
  wholesale was right about the geometry and wrong about the rest: the same file
  carries RecordSource, ControlSource, each embedded control's ProgID and every event
  procedure name, which is what Phase 2 asks the graph about. 113 screens now enter
  the corpus as relationships rather than coordinates, and the corpus went from 1 file
  to 114 on a workspace holding nothing but two databases.

  OCR stays optional, as decided. What changed is the accounting: a policy exclusion
  and an absent text layer are decisions already taken, not gaps in coverage, and
  counting them as gaps made a corpus that had ingested everything it meant to look
  two-thirds incomplete - 132 "gaps" that were 81 renounced definitions and 51
  screenshots. `gap_count` now counts only evidence that should be present and is
  not, with `excluded_by_policy_count` beside it. On the fresh workspace: gap_count 0,
  status READY.
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
  acquisition defect. It matters for Phase 4 specifically: a behavioural trace has to
  execute VBA, and executing it requires compiling it.

  Confirmed on a working copy by removing the reference through
  `Application.References.Remove` and then calling `acCmdCompileAllModules`: five
  references remain, none broken, and the project compiles. So removal is both safe
  and sufficient, and no elevation is involved.

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
