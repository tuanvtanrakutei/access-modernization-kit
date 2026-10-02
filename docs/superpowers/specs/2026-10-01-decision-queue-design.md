# Decision Queue Design

**Status:** Approved by the maintainer on 2026-10-01 (section 10). Slice 1 is built on `feat/decision-queue-register` and slice 2 on `feat/decision-queue-agenda` (backlog A75). Slices 3 and 4 are not.
**Canonical language:** English
**Reader:** the maintainer deciding whether to build it, then the agent implementing it. This is not a phase document.
**Related:** backlog A19 (collection step), A58 (a question the bundle already answered), A60 (carry the unknowns); `specifications/identifier-scheme.yaml`; `specifications/errata-contract.yaml`; `plugins/ak/templates/target-intent.README.md`; `plugins/ak/modernize/templates/Business_flows_README.md`.
**Out of scope:** deployment, environment, the wireframe output, rewriting Stage 6 acceptance. The first two are deferred by the maintainer to the modernization step.

## 1. Summary

The end goal is a modernization process that is about 95% automated, in which a developer decides only what a machine cannot. Today a person is asked in at least ten places, in four different shapes, with no ranking, no batching, and no record of what the pipeline did while it waited.

This design makes one ranked, batched queue out of material the phases already write: the open questions and unknowns, the assumptions the pipeline proceeds on meanwhile, and the mitigation each risk already carries, which is a recommended answer for a legacy defect.

It adds almost no new concepts. Measured on A06, every field the queue needs exists today as prose in four tables, and the identifier register carries none of them. The work is to move those fields into the register when an item is allocated, link the three tables that describe one decision, apply standing policy, and render the result.

It also removes the need for modernize Stage 1 (Business flow). Its two sections that are not a re-reading of extraction, "Legacy versus new system" and the reviewer checklist, are the DISPOSITION items and the batch of this queue.

## 2. What A06 shows

Measured on 2026-10-01 from A06's phase 1 to 4 documents and `A06_Identifiers.json`, with a throwaway script that wrote nothing into the workspace.

### 2.1 Where a person is asked today

| Place | Shape |
|---|---|
| Phase `Questions` tables | ID, Question, Blocks, Owner |
| Phase `Unknowns` tables | ID, Unknown, Why it matters, What would settle it, Who can settle it |
| Phase `Risks` tables, Mitigation column | a recommended action for the replacement, never asked |
| `{APP_ID}_QuestionList.md` | required control output, written by hand at the end |
| `input/decisions/meanings.yaml` | blanks enumerated by `$ak meanings` |
| `input/interviews/QA-register.csv` | the customer's own Q&A log |
| `input/target-intent/` | scope decisions and change requests |
| modernize `Business_flows/{screen}.md` §7 | accepted differences and open decisions |
| modernize `Screen_plans/{screen}.md` gap matrix | status `open-decision` |
| modernize `Known_Issues.md` | types `legacy-bug` ("preserve or fix") and `business` |
| modernize `Final_Acceptance/{screen}.md` | the user decision |

### 2.2 The fields exist; the register has none of them

| Table every phase writes | Columns | Register entry carries |
|---|---|---|
| Questions | ID, Question, Blocks, Owner | id, title |
| Unknowns | ID, Unknown, Why it matters, What would settle it, Who can settle it | id, title |
| Assumptions | ID, Assumption, If wrong | id, title |
| Risks | ID, Risk, Severity, Detail, Mitigation | id, title, severity |

All 157 register entries carry only `id`, `namespace`, `phase`, `title`, `evidence_ids`, and sometimes `severity`, `resolved_by`, `superseded_by`. There is no owner, no blocks, no default. Whether an item is open is inferred from neither closing field being set.

One short script parsed all 24 UK, 21 Q, 14 AS and 18 risk rows out of the markdown, and no identifier in a table was missing from the register. The join is possible. Phase 1 writes its risk ID inside the first cell (`RD-01 — Missing primary keys`) rather than in its own column.

### 2.3 Four findings that shape the design

1. **A table cell is not a safe home for a field a program reads.** Across 39 open Q and UK cells there are 12 distinct spellings of the owner. The same department is `常温庫` (9), "Warehouse operations" (10), and `常温庫 / システム課` (3); the rest are three personal names, roles ("Master-data owner", "Product owner"), and a share path. Q120's row shows what a prose table costs: when it was marked answered, its cells were rewritten in place. The Blocks column now holds the original question, the Owner column holds an evidence id, and the real owner is gone. (An earlier draft of this document blamed a stray `|`; the row has the right number of cells, so that was a wrong reading.)
2. **The register and the document already disagree about status.** Phase 4 says Q120 is answered by E-11 and "should never have been asked". The register still lists it as open, because only the prose in that cell knows.
3. **UK and Q are mostly one item written twice.** Of 20 open UK, about 15 have a Q asking the same thing (read from titles, not computed). 19 open Q plus 20 open UK is about two dozen distinct asks. A text-overlap check finds only 4 of those 15 at a 0.30 threshold, so the link must be declared when the item is allocated, not discovered afterwards. The register's `superseded_by` exists for this and was used once in 47 items.
4. **The ask, the default and the recommended answer are all already written, unlinked.**
   - AS-31 ("the 2024-02-09 memo still describes current practice") is what the pipeline assumed while Q116 asks whether it does. AS-33 and Q115 pair the same way.
   - All 14 assumptions carry an "If wrong" column: the list of what must be revisited if the answer differs.
   - All 18 risks carry a Mitigation. Five wait on an open Q or UK by name: RA-02, RA-03, RA-07, RW-02, RW-06.

Closing already works for every evidence class. Of the eight Q and UK items A06 has closed: three by CODE or UI evidence (Q102, UK-D02, Q109), three by INTERVIEW (Q6, UK-S04, UK-L03), one by TARGET_INTENT (UK-D06, a disposition), and one superseded (Q108 by Q103). Q109 and Q120 were put to a person and then answered by the bundle, both found by hand after publication (A58).

## 3. Principles

1. **Ask only what the bundle cannot answer, what something downstream waits on, and what no standing policy settles.**
2. **Never wait.** An item with a default proceeds on it. The default is recorded as an assumption, and the eventual answer either confirms it or contradicts it. Only an item with no default blocks, and it blocks only the objects it names.
3. **Ask once, in a batch, one party at a time**, ordered so that an answer settling other items comes first.
4. **An answer is evidence, never queue text.** The queue holds a pointer: INTERVIEW for facts about the legacy system, TARGET_INTENT for decisions about the new one (EC-01, EC-07). An answer that exists only in someone's memory has no anchor and cannot pass G1.
5. **A rule asked once beats the same question asked per instance.**
6. **The machine reports what it did for the person**: what it withdrew, defaulted and asked.

## 4. Model

### 4.1 A queue item is a register entry plus a `needs` block

No new identifier family. `Q`, `UK-`, `RD-`/`RA-`/`RW-`/`RS-`, `AS-` and `F-` keep their addresses (ID-03). An entry is in the queue if and only if it has a `needs` block.

```json
{
  "id": "Q117", "namespace": "Q", "phase": 4,
  "title": "Which date is entered as 日付 on the evening build",
  "evidence_ids": ["A06-P4-CODE-001"],
  "needs": {
    "kind": "FACT",
    "party": "常温庫",
    "named": [],
    "blocks": ["WF-001", "BR-ORD-10", "RW-05"],
    "default": "AS-32",
    "gap": "UK-W01",
    "depends_on": []
  }
}
```

| Field | Meaning | Where it lives today |
|---|---|---|
| `kind` | FACT, DISPOSITION, SCOPE, POLICY (4.2) | not recorded |
| `party` | one entry of `input/decisions/parties.yaml` (4.5) | the Owner / Who column, free text |
| `named` | people inside the party who can answer, from the Q&A register's Respondent column | free text, or absent |
| `blocks` | machine IDs (`F-`, `WF-`, `BR-`, `RW-`...) of what cannot be finalised without it | Blocks column, prose pointing at sections |
| `default` | the `AS-` id the pipeline proceeds on, or for a DISPOSITION the risk's own Mitigation | AS table, unlinked |
| `gap` | the `UK-` this item asks about | the twin row |
| `depends_on` | items that must be answered first | prose inside Mitigation |
| `class` (risks only) | technical, data, retired or behaviour, the key into policy (section 5) | not recorded |
| `qa` | the customer's Q&A register ids this item was posted as, once a person has posted it (`$ak decisions --link`). Added in slice 2: without it the queue cannot tell what is already with the customer | not recorded |

Status is **derived, never stored**: `open` until `resolved_by` or `superseded_by` is set, as the register contract already says. No new status is added. An item the bundle turns out to answer is closed by `resolved_by` naming the CODE, UI or SCHEMA evidence, which is what happened to Q109.

### 4.2 Four kinds

| Kind | Asks | Settled by | Default | Party |
|---|---|---|---|---|
| FACT | what the legacy system does, means, or who uses it | INTERVIEW or DOCUMENT | the assumption proceeded on, otherwise "not established, carried unchanged" | a customer party |
| DISPOSITION | what the new system does about a legacy behaviour: preserve, fix, drop, defer | TARGET_INTENT | the risk's Mitigation as written | the decider |
| SCOPE | whether a screen, report, table or boundary file is in the replacement | TARGET_INTENT | in scope | the decider |
| POLICY | a rule that settles a class of the above | TARGET_INTENT, recorded in `decisions/policy.yaml` | none | the decider |

`$ak meanings` stays the home of bulk FACT blanks (1,176 subjects on A05). The queue carries it as one batch item per party, with the count open and the next batch size, never as 1,176 items.

### 4.3 Defaults and blocking

- A FACT item proceeds on its assumption. Every section that depends on it already says so in the assumption's "If wrong" column.
- A DISPOSITION item proceeds on its Mitigation. If the Mitigation names an open item it waits on, the item queues behind that one and the interim default is "carry unchanged and flag it". RW-02 reads "do not migrate that column as history until Q119 says who reads it", and that is exactly this.
- An item blocks if and only if it has no default. It stops only the objects in `blocks`. The modernize parent already collects findings across groups and prompts once; the queue gives it the list.

### 4.4 Answer and contradiction

1. The answer is recorded as evidence (`interviews/` or `target-intent/`) and `resolved_by` is set.
2. If the item had a default assumption, the answer confirms it, or contradicts it. A contradiction is an errata entry under the existing contract. Its `affected` list is the assumption's "If wrong" column, and that list is the refresh set.
3. A DISPOSITION answer becomes a row in the screen plan gap matrix: `planned` for preserve, `accepted-difference` for fix or drop, each citing the item id.

### 4.5 Parties

`input/decisions/parties.yaml`, written by the kit from the Phase 5 organisation section and the Q&A register's respondents, edited by the maintainer, in the same family as `glossary.yaml` and `meanings.yaml`. Each party has a canonical name, aliases ("Warehouse operations" resolves to `常温庫`), and its people. A `party` that is not in the file fails the check. The two roles that decide rather than answer are `decider` for DISPOSITION, SCOPE and POLICY, and the customer parties for FACT.

## 5. Policy before instance

`input/decisions/policy.yaml`: the kit proposes, the maintainer edits. A policy settles a class once, and every item it settles still appears in the queue output as `settled by P-n`, so nothing disappears.

```yaml
policy:
  - id: P-1
    class: technical      # a defect with no business behaviour behind it
    disposition: fix      # A06 candidates: RD-01 missing keys, RA-08 no transaction, RA-11 silent failure
  - id: P-2
    class: retired
    disposition: drop     # A06 candidate: RA-10 floppy path
  - id: P-3
    class: data
    disposition: do_not_migrate_as_data   # A06 candidate: RD-03 placeholder 99
  - id: P-4
    class: behaviour
    disposition: ask      # RW-01, RW-04, RW-05: the Mitigation is the default
```

The classes above are examples read from A06 risk titles, for the maintainer to set. How many of A06's 25 risks each policy settles is a recount to do in slice 3, not a claim made here.

## 6. The command

`$ak decisions --app-root <PATH>` writes only its own outputs.

1. **Validate.** Every Q and UK carries the fields its kind requires (`decision_fields_present`, built in slice 1; risks and assumptions join in slice 3). The document tables must agree with the register on party, blocks, default and closure (`decision_tables_agree`, also slice 1), so the register is not scraped from its own subject (A12).
2. **Pre-check** every FACT item before it is accepted. Flags only, never a verdict. Slice 4: it needs the catalogues' `Offers` column, and nothing in the queue depends on it.
   - does a catalogue enumerate the object and the property the question names (A58's `Offers` column);
   - is there a `meanings.yaml` entry or an interview answer;
   - is it a declared twin of another open item.
3. **Derive status** (slice 2) from `resolved_by`, `superseded_by` and the Q&A register, which is read fresh on every run instead of from the record `$ak interviews` stored, because that record is a snapshot (A06's held five rows when the CSV beside it held six). An item linked to a Q&A page is `with_customer` while the page is open, `answered_unrecorded` when it holds a dated answer the register does not know, and `answer_missing` when the register says answered and the page holds none (A47). **Apply policy** is slice 3.
4. **Render** (slice 2).
   - `{APP_ID}_DecisionQueue.json`, read by agents, written beside the other registers.
   - `{APP_ID}_QuestionList.md`, generated instead of written by hand at the end of a run, and refused over a hand-written one without `--replace-handwritten`. One agenda per party, the decider's last. Within an agenda, items that wait behind another come after it; among the free ones, blocking before proceeding, then what unblocks others, then the severity of the risks they name, then how many things they name. Each item shows the ask, what it blocks (titles, and an `F-` always by its whole name), the default in use, what would settle it, and the evidence already read. Neither output carries a date, so the same register gives the same bytes.
   - `--party NAME` prints one agenda to paste. This is the customer-facing sheet of decision 4: rendered, and posted by a person.
   - The developer batch in the terminal (`ok` accepts every default, `N=<option>` overrides one, each answer written as a TARGET_INTENT record) is slice 3. Its subject is DISPOSITION items, and slice 3 is where they come from.
5. **Report the counts** (slice 2): open, blocking, proceeding on a default, with the customer, answered and not recorded, and closed by who closed them. `settled_by_policy` joins in slice 3.

## 7. What it replaces

| Consumer | Today | With the queue |
|---|---|---|
| modernize pre-flight | stops and asks for config, blocker rows, unmapped tables | also lists BLOCKING items naming the screen and the defaults it will use; announced in the pre-flight line |
| Stage 1 Business flow | per-screen narrative, closed by G1 | removed. §7 is the screen's DISPOSITION items, §8 is generated from them. G1 is computed from `TraceabilityMatrix.csv` and `Evidence.json` |
| Stage 2 gap matrix | hand-written `open-decision` rows | rows cite item ids; status follows the item |
| G2 | every rule in the business flow has a mapping row | every `BR-` touching the screen has a mapping row, from the identifier register |
| `Known_Issues.md` `legacy-bug`, `business` | free rows | pointers to item ids, no second copy |
| Stage 6 | the user decision per screen | also shows the defaults the screen shipped on |
| `target-intent/` | read by Phase 6 | read by the queue, if Phase 6 is removed as proposed in the phase reduction |
| `question-list.md` template | hand-written at the end | generated |

Nineteen files under `plugins/ak` reference `Business_flows`, including three skills (`plan-screen`, `bootstrap-project`, `review-screen`) and `validate_docs.py`, and G1 and G2 in `TRACEBACK_GATES.md` are defined against it. Removing Stage 1 is slice 4, and it is not started by this design.

## 8. Measuring "95%"

A target on total questions would be wrong: most of A06's questions are facts only the customer can supply, and no automation makes them disappear. The target is the **developer's touches**.

Reported per run: `raised`, `withdrawn_by_evidence`, `settled_by_policy`, `defaulted`, `asked`, `answered`, `answered_against_default`, `blocking_open`. A developer touch is an item a developer had to answer, plus each answer a developer had to paste in. Acceptance is counted separately because it is a decision by definition.

A06 baseline today, before any of this: 39 open Q and UK entries, about 24 distinct asks, 22 of the 39 addressed to `常温庫` alone or with `システム課`, and no machine-readable way to say any of it.

## 9. Build order

| Slice | Delivers | Held by tests that fail on the old behaviour |
|---|---|---|
| 1. Register (built) | `needs` block in the register contract and schema; `parties.yaml`; the phase templates gain Party, Default and Asked as columns; the `decision_fields_present` and `decision_tables_agree` apparatus checks; `$ak backfill-needs` and a reviewed backfill of A06 | a document row marked answered while the register has it open (Q120); a party cell holding an evidence id (Q120's overwritten Owner); `Warehouse operations` and `常温庫` resolve to one party; a risk ID inside the first cell (Phase 1); a declared UK/Q twin; a row whose width differs from its header, which makes positional parsing unsafe |
| 2. Render (built) | `$ak decisions`, status derivation from the Q&A register, generated `QuestionList.md` and `DecisionQueue.json`, `--party`, `--link`, the `qa` field | agenda order puts a dependency before its dependants; severity outranks a longer block list; an item with a default never waits; the same register gives the same bytes; a hand-written list is not overwritten |
| 3. Policy | `policy.yaml`, `class` on risks, DISPOSITION items from risks, defaults, contradiction to errata | a policy-settled item still appears; a contradicted default produces the refresh list from "If wrong" |
| 4. Consumers | the A58 pre-check; modernize pre-flight reads the queue; Stage 1 removed; gap matrix cites ids | a question whose answer a catalogue holds is flagged before it is asked |

Acceptance for the whole: run it on A06 and state the numbers in section 8. Each slice is its own branch and merge.

## 10. Decisions

All four were put to the maintainer with a recommendation on 2026-10-01 and accepted as recommended.

1. **Policy for behaviour defects:** ask, with the Mitigation as the default. Technical defects with no business behaviour behind them are settled by policy (slice 3). The alternatives were preserve-parity (safe, reproduces data loss such as RW-01) and fix-first.
2. **UK and Q:** keep both, linked by `gap`. The unknown is the gap in the document and the question is the action. The alternative was one table per phase.
3. **One `decider` role** for DISPOSITION, SCOPE and POLICY, instead of the PM and tech-lead split in modernize `DOCS_README.md` §6.
4. **Customer-facing sheet:** render it, and a person posts it. Posting to the customer's Q&A tool automatically is outward-facing and is a separate decision.

Open, found while building slice 1: A06 treats the customer's "Product owner" as the `decider` (UK-D05 says a decision by the new system's owner, and names the Product owner). If those are two different people on a project, `parties.yaml` splits them and the DISPOSITION items need a rule for which one settles what.

## 11. Risks

- **More fields per item at authoring time.** The phase writer fills them as it allocates (A12 forbids reconstructing the register afterwards). The check and the schema defaults carry the cost.
- **A wrong default proceeds silently until answered.** "If wrong" is the only guard. A HIGH DISPOSITION that no policy settles should have no default, and therefore block.
- **Policy can hide decisions.** Mitigated by every settled item appearing as `settled by P-n`.
- **Answers still arrive by hand.** A Notion export carries no comments (A47). The queue can say what is unanswered; it cannot see tomorrow's comment.
- **The sheet is as good as `blocks`.** If a phase writes `blocks` loosely, the batch order and the blocking rule are loose too. The apparatus check requires every `blocks` id to resolve.
