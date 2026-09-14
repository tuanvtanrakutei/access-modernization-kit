# Catalogue contract

<!--
  This is not a document anybody writes. `$ak catalogues` generates
  `{{APP_ID}}_DataCatalogue.md`, `{{APP_ID}}_ScreenCatalogue.md` and
  `{{APP_ID}}_LogicCatalogue.md` from the sealed bundle, and this file records what
  those three are FOR, what a phase document may and may not do with them, and the
  rules a change to `scripts/generate_catalogues.py` must not break.

  It exists because the phase templates all say "read the figure from the catalogue
  rather than counting again", and until now nothing said what the catalogue promises
  in return.
-->

## Why they exist

A14 measured it: `A05_Phase1` named 20 of 118 tables, 4 of 328 distinct column names and
5 of 77 queries. Every aggregate figure in it was correct and almost nothing that was
counted was named. A narrative cannot carry 1,055 columns, and one carrying a sixth of
them is worse than a citation, because it reads like the whole set.

So enumeration lives here, at 100%, generated; and the phase documents carry the claims.
The split is the point: **a catalogue says what is there, a phase document says what it
means, and neither does the other's job.**

## The three

| Catalogue | Enumerates | Read by |
|---|---|---|
| `{{APP_ID}}_DataCatalogue.md` | every table object, column, key, index, link target and declared relationship | Phase 1 |
| `{{APP_ID}}_ScreenCatalogue.md` | every form and report, with record source, bound fields, event procedures, embedded controls and what references it | Phase 2 |
| `{{APP_ID}}_LogicCatalogue.md` | every saved query and VBA module, the statement each query actually runs, and every file crossing the boundary | Phase 3, and Phase 1 §6 |

## Rules a catalogue holds itself to

**One reader per rule.** Where a catalogue and a checker both need a rule — what counts as
a duplicate link, what a connect string points at, which module is the kit's own tool —
both call the same function. Two readers of one rule drift, and A33 is the entry that
proves it.

**Count the subject the column names.** 188 table *objects* is not 35 *tables*: a table in
a backend is also an object in every frontend that links it. A39 published 209 for 35.
Where two readings of a count are both defensible, print both bounds and name who resolves
them — never pick one silently.

**A marker means "look here", so it must never mean "nothing to see".** `_partial_` on a
name whose English is already complete sent a reader looking for a missing word that did
not exist (A53). `_needs DOCUMENT_` is the honest half of a catalogue and is never omitted
to make a phase look finished.

**Absence of a reference is unreachability, not disuse.** Every "referenced by nothing"
list carries that sentence, because the objects on it may be opened from a navigation pane,
from a database property, or under a name the code builds at run time — A06 has four
reports opened as `"受注数調整リスト" & <option group>`, and no search can find a name that
is never written down.

**Carry the name the operator uses, beside the name the code uses.** A catalogue keyed only
on object names cannot be joined to any evidence a person produced. An interview, an
operating procedure and a training manual all name the *caption* — the title bar — and a
screen an operator calls by one name is filed under another. A06 published a screen called
`商品情報登録` because nothing carried captions: no object has that name; it is the caption
on `商品情報設定画面`. The column is cheap and it pays on its own — it showed that a hidden
screen carries the live daily import's caption character for character, and that
`前日準備リスト` prints as `受注差分リスト`. A caption is a label and establishes no meaning
(EC-01); what it establishes is the join.

**Generated output is reproducible.** Re-running against an unchanged bundle produces an
identical file: no timestamps, no run ids, sorted throughout. A diff between two catalogues
is then a diff between two applications.

## What a phase document may do with a catalogue

- **Quote a figure**, naming the catalogue as the source. Never re-count.
- **Characterise the set behind a figure** only by re-deriving it from the catalogue's full
  list. Characterising it from the members you happened to open is errata cause class
  `DESCRIBED_NOT_COUNTED`, and it has already cost this project two corrections.
- **Group** what the catalogue enumerates — superseded variants, sub-menus, reports with no
  launcher — because a grouping is what turns a number into something an operator can
  answer.

## What a phase document must not do

- **Restate the rows.** E-07 was published this way: 37 unreferenced objects against 26
  actual, a figure computed from a subset and written as the whole.
- **Re-derive a list the catalogue already computes.** Cite it.
- **Promote a name to a meaning.** An English alias is composed from a term dictionary. It
  is naming only; a business meaning needs a DOCUMENT or an INTERVIEW (rule EC-01).

## The English alias column

Every production name carries a composed English alias, and its status is one of:

| Status | Means |
|---|---|
| accepted | a person recorded it in `input/decisions/glossary.yaml` |
| A01 precedent | every term came from the A01 conversion table; binding on later projects |
| composed | built from the term dictionary and nobody has accepted it |
| `_partial_` | some of the name matched no term — the alias is incomplete |
| `_no term matched_` | none of it did |

A `_partial_` name is never printed inline in a phase document, only in an appendix: a
half-finished name in a sentence reads like a finished one.

**A vocabulary gap does not return nothing — it returns the nearest match.** A06 composed
`合計金額` as `total_friday`, because `金` is a weekday term and nothing longer stood above
it; `商品マスタサブメンテサブ` as `product_master_sample_sample`, because `サ` is a column
prefix. Both were labelled `_partial_`, which a reader takes for *unfinished* rather than
*wrong*. So the fix for a bad alias is to add the **longer** term, never to remove the
shorter one, and before adding a one-character term, count how many other names contain it.
