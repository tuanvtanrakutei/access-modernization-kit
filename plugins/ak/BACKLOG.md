# Investigation-Side Backlog

Improvement notes for the `ak` investigation pipeline - acquisition, extraction,
fact derivation, and the phase contracts. The modernize plugin keeps its own list in
`modernize/BACKLOG.md`.

Each entry records what was observed, on what evidence, and what is not yet known.
An entry is only closed by a change plus the run that proves it, not by reasoning
that it should now work.

---

## Open

### A19 - five of the six phases degrade without interview evidence, and all six run before any is collected

**Observed 2026-09-07, reviewing where part 0's output actually goes.**
`evidence-classes.yaml`'s `phase_evidence_needs` records, per phase, what the phase
loses when a class is absent. Read down the `degraded_without` lists and one pattern
is unmissable: phase 1, 2, 4, 5 and 6 all name `DOCUMENT` or `INTERVIEW`. Phase 3
alone does not - it names `SAMPLE_DATA` and `OUTPUT_SAMPLE`, both artifacts rather
than people.

Phase 4's cost line is the sharpest of them: without `DOCUMENT` or `INTERVIEW`,
"the workflows become code paths, not workflows."

**There is no step that collects the class.** The command flow is `init` -> `assess`
-> `acquire` -> `derive` -> `documents` -> `phase`/`run` -> `citations` -> `status`
-> `render`. `$ak documents` normalizes documents that were already supplied; nothing
in that sequence asks a person a question. `$ak meanings`, landed 2026-09-07, is the
first thing in this kit that does, and it runs *after* the phases it would have fed.
`orchestration/waves.json` then publishes all six strictly sequentially, so the order
is not incidental - it is enforced.

So the degradation is not a phase being written badly. It is a phase being required
to publish before the class its own contract names, every time, by construction.

**The same fact, seen from the other end.** `modernize/docs/LEGACY_EVIDENCE.md` 6.4
records that phase 4's and phase 6's *content* is read by no script and cited by no
Stage 1 instruction in the modernize pipeline - only their gate status matters. The
two phases most dependent on evidence the pipeline never collects are also the two
nobody downstream reads. Neither observation explains the other; both follow from the
ordering.

**What the six phases are actually for.** Two audiences were designed for - the
modernize pipeline, and a stakeholder handover set - and a third was not written down:
they are how a developer learns the system well enough to ask a useful question. That
audience is real, and it is the strongest argument for keeping narrative at all. But
A05 phase 1 section 2 marks the ceiling, and it was written *after* full extraction:
"Seven copies of one shape; purpose not established from schema alone." Reading more
does not cross EC-01. The phases make a developer able to ask; they do not make one
able to answer.

**What to change.**

Phase 1 and phase 2's characteristic claims are STRUCTURE and UI_DEFINITION, and
`$ak catalogues` already enumerates both at 100% where the narratives named 20 of 118
tables (A14). Their enumerating half is now a second copy of a generated file; what
is left is the meaning, which is exactly what they cannot supply unaided.

Phase 3 is the only phase whose required class fully supports its characteristic
claim - `CODE` `supports: [STRUCTURE, BEHAVIOUR]` - and the only one whose degradation
list does not name a person. It should stay, and be the single LLM pass of part 0.

Phases 4, 5 and 6 move after collection. Once they are downstream of an answer rather
than upstream of one, there is no longer a reason for three documents where one brief
would do.

Add the collection step. `$ak meanings` is already the right shape and the wrong
scope: the machine enumerates the blanks, ranks them by `write_profile` and reference
count, a person fills them, and nothing is ever proposed. Generalize it past tables
and columns to screens, workflows and boundaries, and the question set stays closed
and countable - which is the property that keeps the collection from becoming an
open-ended conversation, and the brief from growing past what someone actually
answered.

**What this does not settle.**

*The anchor.* `TRACEBACK_GATES.md` anchors evidence as `file::Routine():start-end`.
An answer has no line number. Unless `INTERVIEW` gets an anchor form of its own,
G1 will report a coverage gap on precisely the claims with the best sources.

*Who answered.* `contracts/meanings.py` requires a `source`, but nothing distinguishes
the person who knows from the person who typed. A developer answering a MEANING
question is INFERRED, not INTERVIEW, and the difference is invisible in the file.
Related to A18, which has to be settled first: the file cannot say which classes may
carry a meaning while its own two halves disagree.

*The blast radius, which is smaller than it looks.* Exactly three places read phase
output: `MASTER_WORKFLOW.md`'s pre-flight check on `phase_gates` for
phase2/phase4/phase6, `scan_phase2_inventory.py` reading phase 2 section 1 to seed the
registry, and `LEGACY_EVIDENCE.md` 6.1's enriched-tier table. Phase 4 and phase 6 can
be demoted to optional deliverables today without touching any of the three.

Found by asking where each phase document's content is read, rather than whether it
was published - the question the gates do not ask, and the same blind spot as A13.

### A18 - the class table and rule EC-01 disagree about OPERATOR_DECLARATION, in one file

**Observed 2026-09-07, writing the meanings worklist.** `evidence-classes.yaml` defines
`OPERATOR_DECLARATION` with `cannot_support: [BEHAVIOUR, FORMAT, MEANING, USAGE,
INTENT]` and a note that reads "a declaration about the inputs, not a source of
business knowledge". Forty lines below, in the same file, rule EC-01 says a MEANING,
USAGE or INTENT claim "requires DOCUMENT, INTERVIEW **or OPERATOR_DECLARATION**".

One of them has to go, and until one does the kit contradicts itself in a way that is
now enforced: `_ec01_violations`, added 2026-09-04, evaluates `cannot_support`, so it
would report as a violation exactly what the rule beside it permits. Nobody has hit
this only because no register has carried an `OPERATOR_DECLARATION` item with
`claim_kind: MEANING` yet.

It reaches further than the taxonomy. `contracts/meanings.py` lists
`OPERATOR_DECLARATION` in `VALID_CLASSES`, so a business meaning recorded that way in
`meanings.yaml` is accepted and rendered into the catalogue today; and
`build_references.py` describes `input/decisions/` as "OPERATOR_DECLARATION — accepted
names and recorded meanings". Two parts of the kit are built on the permissive reading
and one checker on the strict one.

**Which is probably right.** The class note is the more considered of the two - it
states a scope ("which artifact is the backend, which copy is current") and a reason.
EC-01's third option reads like it was added to a list. If the strict reading wins,
`VALID_CLASSES` should lose the class and the guidance should say what it now says:
that an answer from a conversation is an INTERVIEW, named and dated. If the permissive
reading wins, the class table needs a second `supports` line and the note needs
rewriting, because "not a source of business knowledge" cannot stand beside it.

Found the same way as every A13 instance: by using the apparatus rather than testing
it. The worklist's header had to tell an operator which class to write, and there was
no answer that both halves of one file agreed with.

### A17 - the two tables that define a text link's columns are excluded as system tables

**Observed 2026-09-04, on A05.** A05 links six delimited text files, every one of
them declaring `FMT=Delimited;HDR=NO;IMEX=2` and `DSN=<spec name>`. With `HDR=NO`
there is no header row, so the column meaning is positional, and the `DSN=` says
where the positions are defined: `MSysIMEXSpecs` and `MSysIMEXColumns`, inside the
MDB.

The extractor excludes both, by name, as system tables - alongside `MSysObjects`,
`MSysQueries` and the rest. For a text link with an IMEX spec those two are not
system noise; **they are the boundary contract**, and they are the only copy of it
that does not depend on the upstream file being reachable.

That mattered here because the other record failed too. All six linked tables
reported `read_error` - *"could not find the object 'order.txt'"* - with `columns: 0`,
because the `L:` share was not mounted when the database was acquired. Access cannot
enumerate a text link's columns without reading the file. So the layout of the entire
inbound boundary was unreachable from a bundle that otherwise passed every gate, and
Phase 3 §4 was published as inference on that basis.

It was closed by supplying samples, which is the right evidence for a FORMAT claim
under EC-02 and should stay that way. But the samples settled it only by luck: three
of the six arrived carrying a header row and matching a headerless file
column-for-column. Without that coincidence, six sample files with no header would
have shown the *values* and still not named the columns.

**What to change.** Exclude the `MSys*` tables as a default, not as a rule, and
capture `MSysIMEXSpecs` and `MSysIMEXColumns` whenever any link's connect string
contains `DSN=` - which is cheap to detect, since the connect strings are already
read. Two consequences follow: a text link's declared columns become available as
`SCHEMA` evidence independent of the file, and the more useful check becomes possible
- comparing what the spec declares against what a supplied sample contains, which is
where a sender that has quietly added a column shows up.

Both tables are ordinary Jet tables and readable through DAO; `MSysIMEXColumns` has
one row per column with its name, data type, position and width.

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

**Changed 2026-09-07, not closed.** `$ak completeness` records each object's
definition-text shape - lines, `Begin`/`End` blocks, procedures - into
`.ak/extracted/object-shapes.json`, and compares it against the last record and
against the other acquisition route. It does not claim to be the missing check, and
`contracts/export_completeness.py` says so where somebody reading it will see: one
observation of a file cannot establish that the exporter wrote all of it, which is
exactly why A05 got through. What changed is that the diff which found this now
happens without anybody deciding to do it - the two routes' readings of `メインメニュー`
sat in one workspace the whole time - and that a first export, which can be compared
with nothing, leaves something for the second to disagree with. Disagreement is
reported in both directions: A05's correction arrived as a *rise*, so a rule watching
only for drops would have been silent at the moment the evidence appeared.

**Run on A05 the same day, and it reproduces this entry's numbers unaided.** 207
objects measured, 123 of them acquired by both routes, 71 cross-route disagreements.
Among them, verbatim:

    ROUTES  WINDOWS11_45D0FDDD:form:メインメニュー: procedure(s): 21 then, 45 now
    ROUTES  WINDOWS11_45D0FDDD:form:メインメニュー: line(s): 1642 then, 4886 now

21 of 45 and 1,642 of 4,886 are the figures at the top of this entry, arrived at by
hand. The staging copy is still the first, incomplete export - 91,119 bytes, 1,642
lines, ending on a clean `End Sub` - and the corrected one has been in the bundle
since 2026-09-04. Both sat in the workspace the whole time. That is the part worth
keeping: the evidence was never missing, only uncompared.

One prediction in this entry is wrong, in the useful direction. It says a definition
ending mid-object would not have fired, and that is right - the file ends on a complete
`End Sub`. But **block balance does fire**: content was lost from the middle, not the
end, so 27 staging objects report more `Begin` than `End`, `メインメニュー` among them at
77 against 68. The heuristic dismissed as useless catches this after all, because it
asks about the whole file rather than its last line.

Closing this still wants the case it was written for - a fresh re-export imported and
the difference named before a person looks - rather than the historical one it has just
re-derived.

Writing it also cost the check its own near-miss, which belongs here because it is the
same class of defect as the one being fixed: the procedure pattern ended `[A-Za-z0-9_]`
and so counted `Private Sub btn1_Click()` while skipping `Public Function 合計()`. A
completeness check that under-counts procedures in a Japanese application is worse than
none, and it took a test with a Japanese-named function to see it.

**2026-09-07: the truncation produced a wrong answer, not a thin one.** A05's six
inbound text files were traced for their consumers - which screen reads each one -
across the bundle's 87 code objects. The trace found one reference each, all inside
`本番テスト切替`, the production/test switch that cannot run, and none at all for two
of the files. Read at face value that says no screen imports any of them.

The real answer is that a single screen does: `メインメニュー`, through two buttons,
`取り込み_Click` requiring `Order.txt`, `Dpshohin.csv` and `Dptenpo.csv`, and
`取り込み幸松_Click` requiring `幸松受注.csv`, `２１受注.csv`, `２１商品.csv` and
`Dptenpo.csv`. Both handlers begin past line 4,000 of a form the staging copy cut at
1,642, so both were invisible. Re-running the same trace over `input/exports/` and the
staging tree together reached 336 definitions and found them immediately.

Two things this sharpens. First, the cost is not proportional to the fraction lost: a
consumer trace returns *absence*, and absence from an incomplete corpus is
indistinguishable from absence from a complete one - the reader has no signal that
anything is missing. Second, the bundle carries **no** form definition text at all
(`ui/forms/` holds only `inventory.json`), so any analysis reaching for form bodies is
already outside the bundle and into `input/exports/`, where nothing has checked
completeness. A completeness check that only ever runs at import would not have helped
the trace; the figure needs to travel with the corpus so a later reader sees it.

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

**Changed 2026-09-07, not closed.** `assembly_version` is in the identity, computed as
a digest of `bundle_assembly.py` rather than declared: a version somebody has to
remember to bump is wrong exactly when it matters, because the defect being fixed is
always the one that changed the output. A comment-only edit therefore also yields a new
id, which wastes a directory - the cheaper of the two mistakes by a wide margin.
`provenance.json` states it too, since a digest cannot be read back out of an id and
"was this built before or after the deduplication fix" is a real question about a
bundle nobody watched being built. `BUNDLE_PATH_CONFLICT` now means what it always
sounded like: both causes the kit knows about are in the identity, so what is left is
something outside the kit writing into a published bundle. Closing this wants the
re-assembly that used to fail.

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
