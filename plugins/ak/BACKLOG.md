# Investigation-Side Backlog

Improvement notes for the `ak` investigation pipeline - acquisition, extraction,
fact derivation, and the phase contracts. The modernize plugin keeps its own list in
`modernize/BACKLOG.md`.

Each entry records what was observed, on what evidence, and what is not yet known.
An entry is only closed by a change plus the run that proves it, not by reasoning
that it should now work.

---

## Open

### A24 - a sample that contradicts its declaration is reported to a terminal and nowhere else

**Observed 2026-09-08, on the run that closed A23.** `$ak samples` prints the
disagreement and exits 1. Nothing carries it any further, and three places that should
hold it do not:

- `LogicCatalogue`'s boundary table has a `Declared columns` column, filled from the
  specification, and no column for what the supplied file actually contains. So the
  published document states `DPSHOHIN ﾘﾝｸの定義: 28 column(s)` next to a file carrying
  29 and reads as though nothing contradicted it;
- the bundle's `evidence-sources/samples/inventory.json` records a sample's name, size
  and SHA-256. Integrity, again, and nothing a later reader can use: not the encoding,
  not the field count, not whether a header row is present. The one evidence class that
  can settle a FORMAT claim reaches a phase document as a hash;
- `$ak citations` and `$ak conformance` can only resolve a claim to an evidence id, and
  no id is minted for a reading that exists as terminal output.

**The register already has the shape**, which is what makes this worth doing rather
than arguing about. An `evidenceItem` carries `statement`, `source_path`,
`source_sha256`, `evidence_class` and `claim_kind`, so "`Dpshohin.csv` carries 29
fields where `DPSHOHIN ﾘﾝｸの定義` declares 28" is expressible today as SAMPLE_DATA
supporting a FORMAT claim, with the file's own digest beside it.

**What to build, and the trade-off to decide first.** Either the check writes a record
under `.ak/extracted/` that `generate_catalogues` reads - the `$ak completeness` shape,
one command measuring and another publishing - or the catalogue reads `input/samples/`
itself. The first risks a catalogue publishing a stale reading, which is worse than
publishing none, so a record has to carry the run that produced it and the digest of
the file it read, and the catalogue has to say **not measured** where the digest no
longer matches. The second cannot go stale and makes every catalogue run re-read every
sample, which on A05 is 5.7 MB and on an application supplying a year of feeds is not.

Two facts from the same run that currently live in no document. A05's six inbound
files arrive in **two encodings** - three CP932 and three UTF-8, none with a BOM - and
no specification declares one: `MSysIMEXSpecs.FileType` is 0 for all eight, and what
that field says about encoding is not established here. An importer written against
either half corrupts the other. And `StartRow` differs within the one application,
three feeds skipping a row and three not, so the migration's importer cannot carry one
answer either.

### A22 - a table excluded by its shape leaves no record of its shape

**Observed 2026-09-08, in A05's backend export.** Both acquisition routes drop a table
whose fields are exactly Text/Text/Long as an Access ImportErrors table. The rule is
deliberate and the reason is good: this frontend carried 210 of them against 21 real
tables, and identifying them by name fails because the name is localized and one
legitimate table matched the Japanese word for "error".

Shape has its own false positives, and the backend export lists two candidates among its
17 exclusions:

    集計分類マスタ
    雑貨Ⅱ集計分類マスタ

Both read as business masters - "aggregation category master" - not as import residue.
The other 15 are unambiguous: 12 `MSys*`, one `~TMPCLP144831`, and two whose names
actually do end in an error word (`Sheet1$_インポート エラー`,
`商品情報_エクスポート エラー`).

**The defect is not the rule; it is that the exclusion cannot be reviewed.** Both routes
record only the *name*. `export-manifest.txt` lists it, and `extract_access.ps1` does not
even do that - it increments a counter. So neither the operator nor a later reader can
tell `Error / Field / Row` from `分類コード / 分類名 / 表示順`, and the two tables above
are absent from the bundle entirely: `tables.json` has no row for either, so their shape
is recorded nowhere at all. An exclusion whose evidence is destroyed by the exclusion
cannot be checked, only trusted.

**Verified 2026-09-08: both are real, and the mechanism is a GROUP BY.** The entry
first said this needed somebody who knows the application. It did not - the corpus
answers it. `集計分類マスタ` is referenced 56 times across 11 files including five forms
and `メインメニュー`; `雑貨Ⅱ集計分類マスタ` 18 times, and there is a form named
`雑貨Ⅱ集計分類設定` whose whole purpose is maintaining it.

And `アイス確認表` shows where the shape comes from:

    sql = "select ... from 商品マスタ where 酒ＦＬＧ = -1 group by Ｐ分類,Ｐ分類名 "
    SCDB.Execute sql
    DoCmd.OpenForm "集計分類..."

The table is a derived aggregation of two text columns plus a count. Three fields,
Text/Text/Long - identical to an ImportErrors table, and not by coincidence: **any
`GROUP BY` of two text columns with a count will be excluded**, in either route.

**What to change.** Two things, and the first holds whatever happens to the rule. Record
the three field names beside the excluded name, in both routes - one string per excluded
table, and enough for a person to see in one line whether the rule was right. Then give
the rule a second condition: a genuine ImportErrors table's three fields are named
`Error`, `Field` and `Row` in some locale, and the 210 in one A05 frontend share that
naming, while `Ｐ分類 / Ｐ分類名 / <count>` does not.

Found by reading an export manifest, which is the first time anybody had a reason to.
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

Add the collection step, and size it to the project. `$ak meanings` is already the
right shape: the machine enumerates the blanks, ranks them by `write_profile` and
reference count, a person fills them, and nothing is ever proposed. At A05's 1,176
subjects that shape has to be a process. On a smaller application it does not.

What survives a deep pass over the evidence that is actually supplied - VBA, form and
report definitions, schema, saved SQL, file samples, screenshots - is a short residue,
and a short residue is a numbered list of exceptions rather than a stage. Ask because
a named decision is blocked, not to fill a section. That ordering - evidence first,
questions only for what evidence cannot settle - is what keeps the question set closed
and the brief from growing past what someone actually answered.

**Landed so far.**

`5ba6d60` - phase 1 section 2 stopped asking for a second copy of the DataCatalogue;
the per-table table and the per-table "meaning not established" list are gone, the
counts carry where they were read from, and section 3 keeps the meaning. Drafting it
reintroduced the defect two sections away first, which is worth knowing about this
kind of edit.

`3d606ce` - phase 2 section 1.1 and section 5.2 the same way, against the
ScreenCatalogue. Section 1.2 did **not** move: entry points are an interpretation the
catalogue does not make, so the plan above was wrong to treat all of phase 2 as
duplication, and the seeder that reads 1.2 needs no re-pointing at all.

`a378aee` - that seeder could not read the shipped phase 2 template in the first
place, which is what looking for the re-pointing found. `50ec38b` - the ScreenCatalogue
wrote ten cells under a nine-column header, found the same way. Both had no test
asserting the shape of what they produced.

`6749f3a` - the three derived outputs no longer hang off phase 4.
`E2ETrace` names the TraceabilityMatrix and the Evidence register, `BoundaryMap` names
the LogicCatalogue's boundary section; the PPTX keeps phase 6, which a presentation
genuinely renders. This is the ordering rule this entry had to be corrected for
missing, discharged before the phases move rather than after.

`cbd1afb` - `DOCUMENT` and `INTERVIEW` have anchor forms, the two directories they
need are declared and wired into the group envelope, and the rule is stated where the
forms are: an answer only in somebody's memory has no anchor and cannot pass G1.

`7ac931a` - the collection step reaches screens. It had covered tables and columns;
`ScreenCatalogue`'s purpose column was a literal, so it asserted a gap rather than
reporting one and could not have changed if anybody answered it. Ranked the same way -
by what opens it, how many events it carries - and EC-05 written into the note of any
screen nothing opens.

`c501268` - phases 4, 5 and 6 are requestable rather than assumed, declared in
`outputs.phases` and defaulting to requested. A declined phase carries `NOT_REQUESTED`
for the whole run; the wave graph is untouched, because optionality belongs in run
state the way `presentation_pptx`'s does. This makes the demotion possible without
performing it: the default is deliberately unchanged, and choosing it is not a
maintenance decision. It also turned up [[A20]] - `NOT_APPLICABLE` is ranked and
produced by nothing - which is the status this work would have borrowed.

`55c4a02` - the collection step reaches boundary files, which was the last subject
kind this entry named that a bundle can enumerate. The boundary table had no column for
what a file is *for* at all: it carried the path, the direction and the declared format,
and nothing about who sends it, how often, or what happens when it does not arrive.

Linked tables are deliberately not in that section. A linked table is a table and
already carries a `tables:` entry - the fixture's `元受注データ` note reads "linked, so it
lives in another file" - so a second question would be the duplication this whole entry
exists to remove. Its row in the boundary table reads the answer from `tables:` instead.
Checked against the fixture before deciding, not reasoned about.

Phase 3 is untouched and stays that way: it is the one phase whose required class
supports its characteristic claim.

**What the collection step still does not reach.** Boundary files are enumerable from
`interfaces/linked-tables.json` and `interfaces/file-interfaces.json` and are the next
section. Workflows are not enumerable at all: a workflow is a phase 4 construct,
reconstructed rather than extracted, so there is nothing for a worklist to write a
blank against. This entry asked for all three as if they were the same kind of subject
and two of them are; the third needs a different mechanism, and naming which is the
useful half of finding out.

**What this does not settle.**

*The anchor - settled by `cbd1afb`, and this entry had it half wrong.* The concern
was right: `TRACEBACK_GATES.md` had a form for twelve evidence types and none for
`DOCUMENT` or `INTERVIEW`, which EC-01 makes the only two that can carry a claim about
meaning - so G1 did check coverage by an anchor that the best-sourced claims had no way
to produce. The stated reason was wrong. An answer does not lack a line number for want
of a format; `schemas/evidence.schema.json` has carried `source_type: INTERVIEW`,
`evidence_class: INTERVIEW` and an `attribution` object all along, with an `allOf`
making `person` and `recorded_on` mandatory. The register was ahead of the gate spec.
What was missing was the row, the mention of `attribution` in the field table, and any
directory for either class to live in - `PROJECT_CONFIG.md` declared CODE, UI and
OUTPUT and nowhere to put a recorded answer.

*Who answered.* `contracts/meanings.py` requires a `source`, but nothing distinguishes
the person who knows from the person who typed. A developer answering a MEANING
question is INFERRED, not INTERVIEW, and the difference is invisible in the file.
A18 settled the neighbouring question - which classes may carry a meaning at all -
and narrowed this one rather than answering it: with `OPERATOR_DECLARATION` gone,
every meaning now claims to be a DOCUMENT or an INTERVIEW, and an INTERVIEW asserts
that a named person said it on a named date. Nothing checks that the named person is
the one who knew.

*The blast radius, corrected the same day.* This entry first said three places read
phase output, and that phases 4 and 6 could be demoted today without touching any of
them. That was wrong, and wrong in the direction that breaks things.
`output-contract.yaml`'s `derived_outputs` is a fourth: `E2ETrace.html` requires
`Phase4`, `BoundaryMap.html` requires `Phase1` and `Phase4`, and the PPTX requires
both of those plus `Phase6`. The cross-screen view is not missing from this kit - it
exists, and it hangs off the two phases this entry proposes to move. Demoting them
without re-pointing those prerequisites orphans all three artifacts silently.

The four, then: `MASTER_WORKFLOW.md`'s pre-flight check on `phase_gates` for
phase2/phase4/phase6; `scan_phase2_inventory.py` reading phase 2 section 1 to seed
the registry; `LEGACY_EVIDENCE.md` 6.1's enriched-tier table; and the three
`derived_outputs` prerequisites. Still bounded and still nameable, but the
prerequisites have to move with the phases rather than be left pointing at them.

*Whether those artifacts were ever readable.* Recorded from the operator, on the
previous project: a boundary map and an E2E trace were produced, and the system still
could not be understood from them, because the scope was too large to hold. That is
evidence for this entry rather than against it - the defect was volume, not a missing
artifact - but it also means re-pointing a prerequisite is not by itself an
improvement. Nothing here measures whether a cross-screen artifact gets read at a
scale where it could be.

Found by asking where each phase document's content is read, rather than whether it
was published - the question the gates do not ask, and the same blind spot as A13.

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

**Changed `2026-09-08 by `acca7d5``: the figure now travels with the corpus.** The 2026-09-07 note
below says a completeness check that only ever runs at import would not have helped the
consumer trace, and that is what was still true: `object-shapes.json` was written by
`$ak completeness` and read by nothing but its own tests. So a reader tracing a screen's
consumers got the same silence as before, with the measurement sitting in the workspace
unopened - the same shape as the two readings of `メインメニュー` that sat there all along.

`ScreenCatalogue` now opens with one sentence about it and carries a `Definition text`
column per object. Three answers: a size when both routes agree, the imbalance or the
disagreement when they do not, and `_not extracted_` when nothing was measured. A
workspace where `$ak completeness` was never run says so in the headline rather than
reading like a clean one, which is the distinction the trace needed and did not have.

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

- **Nothing compared an import specification with the sample it describes** (A23)
  - A17 named the useful check and did not build it; A21 made it possible by proving both
  acquisition routes read `MSysIMEXSpecs` and `MSysIMEXColumns`. Both halves then existed
  for the first time - the specifications, and six real files an operator placed on the
  share - and `input/samples/` was inventoried and hashed with no reader ever opening a
  sample's bytes. `contracts/feed_samples.py` and `$ak samples` put them side by side.

  The join lives in one place now: `generate_catalogues.imex_columns` delegates to it,
  because two joins of the same two tables disagreeing about a layout is precisely the
  defect that catalogue cell exists to report.

  **Proven on A05 2026-09-08**, against the backend export of that date assembled through
  the imported route and the six files on the share:

      元受注データ      order.txt      cp932  spec 26  file 26  no header row               StartRow=0
      元受注データ幸松  幸松受注.CSV   utf-8  spec 26  file 26  the declared names, in order  StartRow=1
      元受注データ酒    ２１受注.CSV   utf-8  spec 26  file 26  the declared names, in order  StartRow=1
      元商品マスタ      dpshohin.csv   cp932  spec 28  file 29  no header row               StartRow=0
      元商品マスタ酒    ２１商品.CSV   utf-8  spec 29  file 29  the declared names, in order  StartRow=1
      元店舗マスタ      dptenpo.csv    cp932  spec  9  file  9  no header row               StartRow=0

      FIELDS    元商品マスタ (dpshohin.csv): the specification declares 28 column(s),
                the file carries 29

  Three of the six carry a header row whose names are the declared names **in order** -
  26, 29 and 26 of them - which is independent confirmation that sorting the
  specification by `Start` reproduces the file's real column order. `MSysIMEXColumns`
  returns those rows in no useful order; A05's first row is column 20 of 26.

  What the run added to what the entry predicted:

  - the three feeds that carry a header are the three arriving as UTF-8, and the three
  without one are CP932. No specification declares an encoding - `FileType` is 0 for all
  eight - so an importer has to detect it. Reported once at the application level rather
  than per feed, because it is one decision for whoever writes the replacement;
  - run against A05's own live workspace, whose newest bundle predates A17, the same
  command reports six `NO SPEC` lines rather than six agreements. That is the correct
  reading of that bundle and the reason the proving run used a bundle carrying the
  specifications.

  **What it must not claim, and this is tested.** Where a first record cannot be told
  apart from data - an all-text specification, no declared name matching - the reading
  is `UNKNOWN` and *nothing* is reported: "no header" and "a header this cannot
  recognise" are the same observation, and a `StartRow` finding built on the difference
  would be an invention about the sender. A header is recognised two ways, its cells
  equalling the declared names or a column declared numeric holding text, and the second
  is what would still catch a sender who renamed every column - the case a field-count
  check cannot reach, which is why the header comparison is part of the check rather
  than a refinement of it.

  It does not answer whether the import works. A05's product feed disagrees three ways -
  29 in the file, 28 in the specification, 30 columns in the destination table - and the
  third number is unreachable from here: `メインメニュー.取り込み_Click` builds the
  statement as `"INSERT INTO " & マスタ名 & " SELECT * FROM 元" & マスタ名`, so the
  destination never appears as a literal for any reader to resolve. The published
  disagreement also stops at the terminal, which is [[A24]].
- **The VBA exporter read the same connect strings and not the specifications** (A21)
  - `extract_access.ps1` gained the two tables that declare a text link's columns in
  A17, and `tools/ExportAccessObjects.bas` did not, so it produced the links without the
  layout they point at. `evidence-layout.yaml` names that failure in its opening note.

  Written `213f4c2`, and **proven on A05 2026-09-08 by the operator running it**, which
  is the only way a file no test here can execute ever gets checked. Two runs, and both
  answers were needed:

      frontend  品揃支援（windows11専用）.mdb  imex_specification_rows=no link declares DSN=
      backend   品揃支援data.mdb              imex_specification_rows=184

  The frontend answer is correct, not a failure: its two linked tables both point at the
  backend `.mdb` and neither declares a DSN. The backend holds all six text links, and
  `schema/imex-specs.json` came back 30,861 bytes - `MSysIMEXSpecs` 8 rows,
  `MSysIMEXColumns` 176, both `status: read`.

  What that recovers is exactly what A17 said was lost. Every one of the six links sits
  in the bundle with `columns: 0` and `read_error: True`, because the `L:` share was
  unmounted when the database was acquired and Access cannot enumerate a text link's
  columns without reading the file. All six now resolve:

      元受注データ      Order ﾘﾝｸの定義2      26 column(s)
      元受注データ幸松  幸松受注 ﾘﾝｸの定義    26 column(s)
      元受注データ酒    ２１受注 ﾘﾝｸの定義    26 column(s)
      元商品マスタ      DPSHOHIN ﾘﾝｸの定義   28 column(s)
      元商品マスタ酒    ２１商品 ﾘﾝｸの定義    29 column(s)
      元店舗マスタ      DPTENPO ﾘﾝｸの定義     9 column(s)

  Two specifications name no current link - `Order ﾘﾝｸの定義` beside the `2`-suffixed one
  the link actually uses, and `新規受注 ﾘﾝｸの定義`. A recreated link and an abandoned
  one, which a migration wants to know about and neither route reported before.

  The run also found `d4b5558`: the exporter exported itself, because it has to be
  imported into the database to run. Seven modules against the previous six, the extra
  one being the kit's own file - measured afterwards as if it were the application's.

  Not closed by reasoning: the gate's behaviour on real strings could be checked here
  (`DSN=Order ﾘﾝｸの定義2` carries a space and half-width katakana, and both routes fire
  on all six), but that the VBA compiles, that DAO reads these two tables, and that 184
  rows come back could only be answered in Access.
- **The two tables that define a text link's columns were excluded as system tables**
  (A17) - A05 links six delimited text files, each declaring
  `FMT=Delimited;HDR=NO;IMEX=2` and `DSN=<spec name>`. `HDR=NO` means no header row, so a
  column's meaning is positional and the specification named by `DSN=` is the only
  declaration of what those positions mean. It lives in `MSysIMEXSpecs` and
  `MSysIMEXColumns`, inside the database, and the extractor skipped both by name
  alongside the `MSys*` tables DAO genuinely cannot read.

  It cost the layout of the whole inbound boundary. All six linked tables reported
  `read_error` - "could not find the object 'order.txt'" - with `columns: 0`, because the
  share was unmounted at acquisition and Access cannot enumerate a text link's columns
  without reading the file. The only copy of that layout which did not depend on the file
  being reachable was the one being skipped, and Phase 3 was published as inference on
  that basis.

  ``b33bebf`` reads both tables, but only when some link declares a DSN: reading them
  always would put Access's own bookkeeping in every bundle, and the condition is the
  link's own declaration. Every field of every row is emitted rather than a chosen few,
  because these column names are Access's and naming a subset is how a version difference
  would silently drop the evidence; the `SpecID` join is done in
  `generate_catalogues.py`, where it can be tested. `LogicCatalogue`'s boundary table
  gains a `Declared columns` column, and a link naming a specification the database does
  not hold reads **not in the database** rather than blank - the layout is then declared
  nowhere and a sample is the only remaining route (EC-02).

  Thirteen tests, and the ones that matter run the extractor's own function against a
  mocked DAO database - there is no Access here, and the function's whole job is talking
  to DAO, so the Database is mocked and the function is not. What stays open is the
  exporter: [[A21]], because the same read has to go into
  `tools/ExportAccessObjects.bas` and no test in this repository can execute VBA.
- **`NOT_APPLICABLE` was ranked, schema-declared, and produced by nothing** (A20) -
  `phase_readiness.py` ranked it at 0 beside `READY`, `_set_status` special-cased it so
  it won even against a worse status, and `classification-rule.schema.json` declared the
  `not_applicable_when` field that fed it. No profile ever shipped such a rule, and
  `test_not_applicable_requires_positive_proof` asserted the status never appears - which
  passed, vacuously, because nothing could produce it under any input.

  This entry preferred writing the rules to deleting the mechanism. **Writing them turned
  out not to be possible**, which is the part worth recording. `data_only_proof` declares
  one *database* data-only and the capability set is flat, carrying no database scope - so
  in a split application a `phase2` rule keyed on it cannot tell a data-only backend,
  whose frontend holds every screen, from an application with no screens at all. It would
  mark screen analysis inapplicable for an application full of screens. No
  `frontend_format` means "no frontend" either: mdb, accdb, adp, mde, accde and exported
  all have one, so a classified application always has screens. A monolith declared
  data-only is not an application but a database, which this kit is never pointed at. The
  remaining candidates are degradations rather than exclusions - `compiled_only` makes
  phase 3 LIMITED, a text-only backend makes phase 1 BLOCKED for want of a field
  inventory - and the ranking already carries "less can be said".

  So the second option, the honest one: the status, its special case, the schema field and
  both enum entries are gone, and `phase_readiness.py` now opens with the note explaining
  what was tried and what it would take to bring it back - capabilities scoped per
  database, so a proof can say which one it is about. ``5613363``. Two tests hold it: one
  asserts the status is absent *and* that the note explaining why is still there, because
  an unexplained absence is what gets re-added; the other checks the profiles rather than
  trusting the schema to have been applied to them.

  It had already nearly cost something. A19's requestable phases needed a status for "the
  operator declined this deliverable" and this one looked free. Borrowing it would have
  made a choice indistinguishable from a finding, and since nothing else produced the
  status, the choice would have become the only thing it ever meant. `NOT_REQUESTED`
  exists in run state instead, and the distinction is now structural rather than a rule
  somebody has to remember.
- **A test read PowerShell's output in the host's locale, so it passed only where
  the locale happened to fit** - `test_extract_ps1_safe_names_keep_the_original_object_name`
  captured with `subprocess.run(text=True)`, which decodes using the host's preferred
  encoding. The names under test are Japanese. On a cp932 workstation they decoded;
  on the CI Windows runner, cp1252 raised `UnicodeDecodeError` inside subprocess's
  reader thread, so `result.stdout` arrived as `None` and the failure surfaced as
  `AttributeError: 'NoneType' object has no attribute 'splitlines'` - a message that
  says nothing about encodings. The answer now crosses the pipe as base64 and is
  decoded explicitly as UTF-8, and stderr is decoded with `errors="replace"` so a
  failure path cannot raise the same way. What a console renders was never what this
  test was about.
- **The exporter asked the host which characters are illegal, so two hosts
  disagreed** - `Get-SafeName` in `extract_access.ps1` built its forbidden set from
  `[System.IO.Path]::GetInvalidFileNameChars()`, which returns the *running*
  platform's set. On Windows that is nine punctuation characters plus the control
  range; on Linux it is NUL and the path separator. One object named `c:d` exported as
  `c_d-256d2ec0` under Windows PowerShell and as `c:d` under pwsh.
  `specifications/evidence-layout.yaml` requires this script and
  `tools/ExportAccessObjects.bas` to write the same container names, and the .bas has
  always named its list outright - so the two agreed only when the host happened to be
  Windows, which was every host anybody ran it on. It surfaced as CI red on `main`
  since 2026-08-10, ubuntu only, for four weeks. `f2ae159` names the Windows set
  instead of asking, which is what the function's own comment already claimed it did.
  Proven by `test_both_exporters_forbid_the_same_characters`, which compares the set
  the .ps1 declares against the list the .bas replaces and fails against the version
  it replaced - that one declared nothing to compare, which is why four weeks passed.
  A13's shape once more: two copies of one policy, and nothing checking them against
  each other.
- **The class table and rule EC-01 disagreed about `OPERATOR_DECLARATION`, in one
  file** (A18) - the class declared `cannot_support: [BEHAVIOUR, FORMAT, MEANING,
  USAGE, INTENT]` under a note reading "a declaration about the inputs, not a source of
  business knowledge", and forty lines below, in the same file, EC-01 offered that class
  as a third route for exactly those claims. `contracts/meanings.py` and
  `build_references.py` were built on the permissive reading and `_ec01_violations` on
  the strict one; nobody had hit it only because no register had yet carried an
  `OPERATOR_DECLARATION` item with `claim_kind: MEANING`. Settled the strict way,
  because the class note states a scope and a reason while EC-01's third option reads
  like it was appended to a list. EC-01 now requires `DOCUMENT` or `INTERVIEW`;
  `VALID_CLASSES` lost the class; and the worklist header, `input/README.md` and
  `build_references.py` now say the same thing - an operator who knows the answer is a
  source, and the class for a source who is a person is `INTERVIEW`, named and dated.
  The refusal costs an operator nothing, which is why it is safe: the identical sentence
  is accepted the moment it carries a name and a date, and that is what the test
  demonstrates. `9019814`. Proven by
  `test_a_meaning_declared_by_the_operator_is_refused` and by
  `test_a_rule_may_not_offer_a_class_its_own_table_forbids`, which compares EC-01's
  prose against the table it sits beside and fails against the wording just removed -
  the A13 check applied inside a single file, which is what was missing.
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
