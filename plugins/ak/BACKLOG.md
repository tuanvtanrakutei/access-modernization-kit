# Investigation-Side Backlog

Improvement notes for the `ak` investigation pipeline - acquisition, extraction,
fact derivation, and the phase contracts. The modernize plugin keeps its own list in
`modernize/BACKLOG.md`.

Each entry records what was observed, on what evidence, and what is not yet known.
An entry is only closed by a change plus the run that proves it, not by reasoning
that it should now work.

---

## Open

### A15 - an imported export's completeness is never checked, only its integrity

**Observed 2026-09-04, on A05.** The imported-sources adapter verifies every file
against the SHA-256 the export manifest declares, and verifies the manifest against
the source database's own digest. All of it passed. The definition text was still
materially incomplete: `メインメニュー` arrived with 21 of its 45 procedures, 45 of its
114 control blocks and 1,642 of its 4,886 lines.

Integrity answers "is this the file the exporter wrote". Nothing answers "did the
exporter write the whole object". Ten errata followed from the gap - `E-14` to `E-18`,
`E-23` - and the largest was a third of the reachability figure.

**What a check could compare.** The managed route reads the object inventory from DAO,
so for a database acquired both ways the two routes' object lists can be reconciled -
counts matched here, which is why the incompleteness survived, so a count check alone
is not enough. Per-object signals that would have caught it: a form's `Begin Form`
block count against its control count, a module's `Attribute VB_Name` against the
procedures the same file declares, and - most simply - a definition text that ends
mid-object. `メインメニュー` ended on a complete `End Sub`, so even that would not have
fired here. The honest version of this entry is that **the check is not obvious**, and
that the fallback until one exists is to re-export and diff, which is what found it.

### A16 - a bundle's identity ignores the code that assembled it

**Observed 2026-09-04.** The bundle directory name and `bundle_id` derive from the
source digests alone. Fixing a defect in `bundle_assembly` and re-running therefore
produced the same name with different content, and `_publish_bundle` refused it as
`BUNDLE_PATH_CONFLICT` - a message that reads as tampering when the cause was the
kit's own code changing. Worked around by moving the previous bundle aside three
times in one session.

The identity should include the assembly's own version, so a re-assembly of the same
sources by different code is a different bundle and both can be kept. That also makes
"which code produced this bundle" answerable from the bundle, which it currently is
not.

### A13 - nothing checks the checkers against the contracts they enforce

**Observed 2026-09-03, publishing the first A05 Phase 3.** Three defects, all of the
same kind, all found by *using* the apparatus on a document it had never seen:

- `validate_phase_conformance` carried a hand-written copy of the identifier
  namespaces listing nine; `identifier-scheme.yaml` declares fifteen. `RA-`, `RW-`,
  `RS-` and `Q` were missing, so Phase 3's eight risks and four questions were
  invisible to the check whose entire job is resolving identifiers.
- Its dangling report printed six entries with no count. The real number was 26.
- `advance_run` still named `gate_graph_phase2` in its readiness map after the
  Graphify waves were deleted from `orchestration/waves.json`. A dict lookup that
  misses is silent, so Phase 2 could no longer be marked READY and nothing said so.

Each is now closed - the finder table is tested against the scheme, counts are printed
before the sample, and `test_advance_run.py` asserts every wave name in the
orchestration code is a wave the sequence declares. **The general case is open.** The
kit verifies documents against contracts; nothing verifies that a checker still
enforces the contract it claims to, or that orchestration code still names steps the
orchestration data declares. Every such drift so far has been silent, and every one
was found by a person running the thing end to end.

The first attempt at a fix made it worse and is worth recording: deriving the finder
patterns from the scheme's own patterns removed the drift and introduced a false
negative, because finding an identifier in prose and judging its shape are two jobs.
A finder as strict as the scheme makes a malformed identifier invisible rather than
faulted, and it failed the reference set, whose Phase 3 writes `BR-M01`. The split -
permissive finder, scheme as validator, in the apparatus group - is the resolution.

### A14 - a narrative was the only deliverable, so enumeration had nowhere to live

**Observed 2026-09-03, on a completeness review the user asked for.** Counted against
the bundle, the published narratives named 20 of 118 tables, 4 of 328 distinct column
names, 22 of 51 forms and 5 of 77 queries. Every aggregate count was correct; almost
nothing counted was named.

Not a writing failure. The contract declared six phase documents and nothing else, and
a narrative carrying 1,055 columns stops being one. The reference set solves it with a
separate catalogue - `A01_Table_Definitions.md`, 83 KB - which is why its Phase 1
narrative is the shortest of its six.

Closed by `$ak catalogues`: three generated catalogues declared in the output contract,
enumeration at 100%, and unfillable columns present and marked so a missing input costs
one cell per row. Generating the first one found `E-07` (37 unreferenced objects
published, 26 actual) and `E-08` within minutes.

**What stays open** is the same as A13: nothing checks that a narrative's aggregate
figure agrees with the catalogue's count of the same thing. `E-07` was a published
figure contradicting a derivable one, and only a person comparing them noticed. A check
that reconciles the two is writable and is not written.

### A13a - the same shape again, in the register instead of the checker

**Observed 2026-09-03, migrating the A05 workspace to the current layout.** The move
relocated every acquired file and rewrote the manifest and the ignore files. It did not
touch the evidence register, so **66 of 67 items cited a path that no longer existed**.

`$ak conformance --strict` passed. `$ak citations` passed. The whole suite passed. All
of them read the register against the documents and none against the filesystem, so a
register in which every path was wrong looked exactly like one in which every path was
right.

Closed for this case: `$ak citations` now resolves each cited `source_path` under the
workspace, the migration repoints paths as part of the move, and its tests assert
against the filesystem rather than the rewritten string. Filed under A13 because it is
the same defect class - apparatus verified against itself - and because closing three
instances by hand is not the same as having a way to find the fourth.

It also exposed one that predated the migration: fifteen Phase 3 items cited
`.../fresh-01/modules/...` where the extractor writes to `vba/`. That directory never
existed in either layout, so those citations had never resolved from the moment they
were written.

### A13b - the register was schema-invalid, and the rule set was decorative

**Observed 2026-09-04, on A05.** Two more instances of A13, found the same way -
by using the apparatus rather than by testing it.

The evidence register carried **fifteen items whose `source_type` was an evidence
class** - `DOCUMENT`, `UI_DEFINITION`, `OPERATOR_DECLARATION` - none of them one of
the twelve media `evidence.schema.json` permits. `validate_structure.py` checks that
the schema file exists; nothing had ever validated a register against it.

Worse: **none of 113 items stated `evidence_class` or `claim_kind`**, which are the
two fields rules EC-01 to EC-06 are written against. The rules were prose an analyst
could follow or not, and no run had ever been checked against them. Populating both
fields and evaluating EC-01 for the first time found three violations, one of which -
a BEHAVIOUR conclusion drawn from a screenshot - was a published finding.

Closed for these cases: `$ak conformance` now validates the register against its
schema (`evidence_register_conforms`), evaluates EC-01
(`evidence_class_supports_claim`), and reports how many items state no class
(`evidence_classes_stated`). All three are apparatus checks, so the A01 reference is
not required to pass them. Filed under A13 for the same reason A13a is: three more
instances closed by hand is still not a way to find the fourth.

It also exposed a gap in the taxonomy itself. Three A05 findings - which backend
paths resolve, which drives are mapped, whether two files on disk are the same file -
had no class to sit in. Added `ENVIRONMENT`, with the two cautions that make it
different from the other nine: it goes stale when a share is remapped, and it
describes one deployment rather than the application.

### A12 - a scraped identifier register makes its own check vacuous

**Observed 2026-09-03, republishing A05 Phase 1 under the 2.9.0 contract.** The
republished Phase 1 allocated `Q3`, `Q4` and `Q5` to the drive mapping, the inbound
samples and the ＢＫ retention question. All three ids were already allocated by
`A05_QuestionList.md`, earlier in the same run, to *different* questions. Rule ID-03
says an identifier is allocated once and never reused; this reused three.

`$ak conformance --strict` passed throughout, and could not have done otherwise.
`A05_Identifiers.json` was generated by scraping the identifiers out of the published
documents, so the register contained exactly what the documents contained and
`identifiers_resolve` can never fail. A register derived from its own subject checks
nothing.

Two things follow, and only the first is in reach:

- **The register must be written at allocation time, by the phase that allocates**,
  not reconstructed afterwards. Then a second allocation of a live id is a collision
  the writer sees, and `identifiers_resolve` becomes a real check.
- **Semantic drift is not mechanically checkable.** Even an allocation-time register
  would not catch `Q3` being *reused for a different question* if the writer intended
  it; what it catches is the accident. A human reading the question list is what
  caught this one, and the honest position is to say so rather than add a check that
  appears to cover it.

Recorded as E-05 in the A05 errata register, and the three citations corrected to the
ids that already mean those things: `Q3` inbound samples, `Q6` drive mapping, `Q9`
ＢＫ retention.

### A11 - nothing verified that an embedded ActiveX control can actually load

**Observed 2026-08-26, A05 frontend.** Eight reports embed
`Class = "BARCODE.BarCodeCtrl.1"`, three of them reachable from the picking-list
launchers that produce the application's main output, and the extraction receipt said
nothing about whether that control was usable. `project_context.references` reports the VBA reference list, and a reference
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

A third error, this one in the phase output rather than the check: Phase 1 and the
first draft of Phase 2 both read the eight embeddings as "all eight are
ピッキングリスト variants, so one control gates the entire printing path". Recounting
by name found two `バーコード一覧` reports and a `レポート1` among them, only three of
the eight reachable at all, and four of the seven reachable picking-list variants
carrying no barcode control. The count was right and the description of what had been
counted was invented. Both documents corrected; `A05-P2-INVENTORY-025` records it.

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

- **Nothing checked that a document's evidence citations resolved** - a phase document
  can cite `A05-P2-FLOW-020` and mean nothing by it, and the document reads exactly the
  same whether the id names a measured statement or nothing at all. The A05 run
  produced 25 such citations across two phases: an entire phase's items were generated
  with a sequence continuing from the previous phase's item count, so the first was
  numbered 021 while the document, written first, cited 001; and a Phase 1 question
  cited the right task name at a sequence belonging to a different task. The first
  batch was caught by a hand-rolled check, which then reported "pass" on the second
  because its pattern matched `[A-Z]+` for the task name and so never tested
  `TABLE_INVENTORY` or `DATA_TYPES` at all - a validator that skips an id format
  silently is worse than no validator, because it is believed. Closed by
  `scripts/validate_evidence_citations.py` and `$ak citations --outputs <dir>`, which
  reads every `*.md` in an outputs directory plus the traceability matrix's
  `evidence_ids` column, fails on any unresolvable id, and reports uncited items
  without failing. Five tests, one per real defect. Fixing the Phase 1 citation also
  exposed a wrong claim behind it: Q1 said the `店舗マスタ` pair doubled like the
  product masters, and the pair had never been measured - it doubles in shape but both
  halves declare a primary key.
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
