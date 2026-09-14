# {{APP_ID}} — Phase 2: Screen & Form Analysis

<!--
  Characteristic claim: what each screen is, how it is reached, and who uses it.
  Definition text answers the first two. It cannot answer the third, and it cannot
  see layout, tab grouping or which controls an operator can actually see - those
  need a SCREENSHOT, and purpose needs a DOCUMENT or INTERVIEW.

  Two rules this phase is judged by:

  1. An object no code path opens is UNREACHABLE, not unused (rule EC-05). Say
     which routes were not examined - the navigation pane, custom menus, another
     copy of the frontend - every time the figure is quoted.
  2. `F-nnn` is an index, not an identifier. For Japanese-named objects it tells a
     reader nothing on its own, so the object's real name appears beside it
     everywhere, and every downstream key uses the name rather than the index.

  Delete these comment blocks as you fill the document in.
-->

## Naming Convention

Object names are the **production names**, unchanged. Where they are Japanese the
document is JP-primary, with a Romaji alias for cross-reference. Never translate.

| Japanese (production) | Romaji alias | Kind |
|---|---|---|

<!-- Compose this from the catalogue, never by hand. A hand-written alias is not a
     small defect: a reader who searches the catalogue for the English this document
     gave them finds nothing, and cannot tell whether the row is missing or the name
     is. A06 published `daily_stock_report_print` against a catalogue composing
     `date_by_stock_report_print`, and the rule forbidding it was stated in this very
     section of the document that broke it.

     The diagrams are where the reader needs this most. A node cannot carry
     `その他データ (other_data)` eleven times, so a map of what a screen writes prints
     production names alone - and a reader who cannot read Japanese gets nothing from
     it. List the names the diagrams print bare, and say which section prints them. -->

## Captions

<!-- THE CAPTION IS NOT THE OBJECT NAME, and an operator names the caption.

     A06 published a screen called `商品情報登録` for two drafts. No object in the
     application carries that name: it is the title bar on `商品情報設定画面` and the
     label on the switchboard button that opens it. The interview that is the entire
     basis for the finding names two captions - 『商品情報登録』『商品情報一覧登録』 -
     and the document had folded both into one screen that does not exist, attaching
     the finding to the wrong object.

     So whenever evidence names a screen in an operator's words - an interview, an
     operating procedure, a screenshot, a training manual - resolve it through the
     catalogue's Caption column before writing the name down. A screen an operator
     calls by one name is filed under another.

     Recording captions is cheap and pays twice more:
       - `新規事業部受注取込画面` carries the caption `受注データ取込`, character for
         character the caption on the live daily import. The hidden screen does not
         merely write the same tables; it presents itself as the same screen.
       - `前日準備リスト` prints as `受注差分リスト`, so the report an operator asks for
         by name is not findable under it.

     A caption establishes no meaning - it is a label, like the object name, and rule
     EC-01 still applies. What it establishes is the join between what people say and
     what the code contains. -->

## Source Coverage

| Evidence class | Supplied | Scope | What its absence costs |
|---|---|---|---|
| UI_DEFINITION | | | |
| CODE | | | |
| SCREENSHOT | | | |
| DOCUMENT / INTERVIEW | | | |

<!-- WHO READS THIS, AND WHAT THAT COSTS YOU

     A reference file is read by an agent. A phase document is read by a developer who
     has to rebuild the system, and they read it once, under time pressure, looking for
     what they must not get wrong. Two habits follow:

     Open with what they must not get wrong. A short numbered list, each item pointing at
     the section that proves it. A06's Phase 2 was correct and unusable before it had one:
     the fact that re-running the morning import destroys the quantities staff typed the
     night before was in the document, four sections deep, in prose.

     Diagram a mechanism; tabulate a set; write prose only for what neither can hold.
     One required diagram per phase is a floor, not a budget. Reach for one whenever the
     thing being described has a shape: an order of steps, a cycle, a lifecycle with a
     failure branch, a fan-out from one object to many, or three artefacts that should
     agree and do not. A06's Phase 2 carries five and is shorter than the four-diagram
     draft it replaced, because each one removed a paragraph that was describing a picture.

     Mermaid renders, or it is not evidence a reader can see. Check it - `mmdc -i x.mmd -o
     x.svg` - before publishing. A sequence diagram reads better than a flowchart for
     anything with an actor and an order; a flowchart with a red-filled node is the
     cheapest way to say "this is where it goes wrong".

     Keep the document's own revision history out of it. How many drafts a figure went
     through is a fact about the analysis, not about the application, and a developer
     reading once does not need it: A06's Phase 2 carried a paragraph explaining that a
     count had been "wrong twice before it was right", naming all three numbers and both
     causes, and it was the hardest paragraph in the document to read.

     That history belongs in `BACKLOG.md` and in the commit. What the document keeps is
     the part a reader could otherwise get wrong - what a figure counts and what it
     excludes, stated plainly, so that a recount giving a different number is explained
     before it happens rather than after:

         A recount can legitimately give a different number, so two exclusions are worth
         stating. `DoCmd.OpenQuery` opens a query, not a screen: its 3 edges are excluded
         here, and counting them gives 39.

     The exception is a claim an earlier PUBLISHED phase made and this one corrects. That
     is errata, it has its own register and its own `E-nn` identifier, and it is owed to
     the reader because they may have acted on the earlier statement. A draft nobody
     outside the run ever saw owes nothing.
-->

## Contents

1. [Screen, Form, and Report Inventory](#1-screen-form-and-report-inventory)
2. [Navigation Map](#2-navigation-map)
3. [Per-Screen Analysis](#3-per-screen-analysis)
4. [Shared UI and Validation Patterns](#4-shared-ui-and-validation-patterns)
5. [Reachability and Missing Captures](#5-reachability-and-missing-captures)
6. [Observations and Screen Risks](#6-observations-and-screen-risks)
7. [Assumptions, Unknowns, and Questions](#7-assumptions-unknowns-and-questions)

---

## 1. Screen, Form, and Report Inventory

### 1.1 Totals

<!-- Every figure here is in `{{APP_ID}}_ScreenCatalogue.md`, which is generated from
     the bundle and lists every form and report with its record source, its bound
     fields, its event procedures and its embedded controls. Read them from there
     rather than counting again: two counts of one thing is how E-07 was published,
     37 unreferenced objects against 26 actual.

     A count is also not a description of what was counted. If you characterise the
     set behind a number - "all eight are X" - re-derive that from the catalogue's
     full list, never from the members you happened to open. This is errata cause
     class DESCRIBED_NOT_COUNTED, and it has already cost this project two
     corrections. -->

| | Forms | Reports | Read from |
|---|---:|---:|---|
| Total | | | `{{APP_ID}}_ScreenCatalogue.md` |
| Declaring a record source | | | `{{APP_ID}}_ScreenCatalogue.md` |
| Carrying event procedures | | | `{{APP_ID}}_ScreenCatalogue.md` |
| Embedding a third-party control | | | `{{APP_ID}}_ScreenCatalogue.md` |
| Controls hidden in the definition | | | `ui/controls.json` |
| Business purpose not established | | | the catalogue's marked cells |

<!-- The hidden-control row is not housekeeping. A06's switchboard carries 32 command
     buttons and seven of them are hidden with no code anywhere making them visible
     again - one of the seven would reach a screen that declares two live inbound
     feeds. A hidden control is REACHABILITY evidence and not usage evidence: a
     developer can unhide it and an operator may have another route, so the status of
     each one is an open question, never a conclusion that the function is retired. -->

### 1.2 Entry points

| ID | Object | Type | Business purpose | Entry path | Evidence |
|---|---|---|---|---|---|

<!-- `Business purpose` is a MEANING claim. Without a DOCUMENT or INTERVIEW it is
     written as "not established" - not guessed from the object's name. -->

## 2. Navigation Map

<!-- Required diagram. Follow the application's own open calls, not a plausible
     hierarchy. -->

```mermaid
flowchart TD
```

## 3. Per-Screen Analysis

### {{F_ID}} — {{OBJECT_NAME}}

- **Object:**
- **Caption:**
- **Purpose:**
- **Who uses it:**
- **Record source:**
- **Reached from:**
- **Preconditions:**

| User action | VBA event | Validation / condition | What it does | Data or file target | Evidence |
|---|---|---|---|---|---|

<!-- One of these per screen that carries behaviour. For a screen whose behaviour is
     a single open call, the inventory row is enough - say so rather than padding.

     `Who uses it` is the half of this phase's claim that definition text cannot
     answer. It comes from a DOCUMENT or an INTERVIEW or it reads "not established";
     an operating procedure that names a department beside a function - A06 has one
     naming 受注課 and 常温庫 against the morning and evening runs - is the cheapest
     evidence there is for it, and it is usually already in `input/documents`.

     Record it here when a screen CREATES OR DROPS a database object while running.
     A06 has three, and a migration that reads the object inventory as fixed is wrong
     about all of them: one builds and drops a staging table per day, one deletes and
     recreates a query before exporting it, and one drops a whole table and re-imports
     it from a spreadsheet. -->

## 4. Shared UI and Validation Patterns

<!-- A pattern repeated across screens is a requirement in disguise: a replacement
     has to decide whether to reproduce it. State how many objects carry it, so the
     decision is scoped. -->

| Pattern | Objects carrying it | What a replacement must decide | Evidence |
|---|---:|---|---|

## 5. Reachability and Missing Captures

### 5.1 Reachability

| Route | Objects |
|---|---:|
| Reachable from the entry point by an open call | |
| Referenced by another object but not from the entry point | |
| Embedded as a subform or subreport | |
| Opened by a name the code builds at run time | |
| Opened by a database property rather than by code | |
| **Referenced by nothing, and no route found** | |

<!-- The two middle rows are why the last one is not a deletion list. A06's four
     `受注数調整リスト1/2` and `残数記入リスト1/2` reports are opened as
     `"受注数調整リスト" & Me.fraレポート` - a name no search can find because it is
     never written down - and the switchboard itself is opened by the database's
     startup property. Five of that application's nine "referenced by nothing" objects
     were reachable, and finding them meant reading the open calls for concatenation
     rather than trusting the derived graph. Do that before grouping 5.2. -->

**This is reachability, not disuse.** Routes not examined:

<!-- Name them. A screen can be opened from the navigation pane, from a toolbar or
     custom menu the definitions do not carry, or by code in a copy not analysed.
     The figure travels with this qualifier or it will be quoted without it. -->

### 5.2 Unreferenced objects, grouped

<!-- The list is `{{APP_ID}}_ScreenCatalogue.md` section "Objects referenced by
     nothing", computed from the derived graph. Do not re-derive it here and do not
     restate its count: E-07 is exactly this figure published from a subset, 37
     against 26 actual, and it was caught by generating the catalogue rather than by
     reading the document.

     What belongs here is the grouping - superseded variants, sub-menus nothing opens,
     reports with no launcher - because naming the groups is what turns the
     catalogue's number into something an operator can answer. Say which routes were
     not examined every time the figure is quoted: absence of a reference is
     unreachability, not disuse (EC-05). -->

| Group | Objects | Why they are grouped this way | Routes not examined |
|---|---:|---|---|

### 5.3 Missing captures

<!-- What no screenshot means for this document, concretely: layout, grouping, tab
     order, control visibility. If an operator screenshot shows something the
     definition text does not carry, record it as an open question, not a finding. -->

## 6. Observations and Screen Risks

### Observations

<!-- OB-nn. A property worth carrying forward that is not yet a rule or a risk.
     Each cites evidence. -->

| ID | Observation | Evidence |
|---|---|---|

### Risks

<!-- RA-nn, severity HIGH/MEDIUM/LOW, and a mitigation or an explicit "none
     proposed". A risk without a severity cannot be prioritised, and Phase 6
     consolidates from the register rather than from this table - so the severity
     has to reach BOTH.

     RA, not RS. RS is Phase 5's and means security and compliance; a screen is
     application layer. A06's Phase 2 published five findings as RS-nn, one of them
     "grouping carried by 222 line and rectangle controls", and took Phase 5's
     numbers before Phase 5 ran.

     This section exists because A06's Phase 2 had none: thirteen identifiers were
     allocated into the register with nowhere in the document to appear, and four
     risks were never written down in any sentence a reader would see. -->

| ID | Risk | Severity | Consequence at migration | Mitigation | Evidence |
|---|---|---|---|---|---|

## 7. Assumptions, Unknowns, and Questions

### Scope

<!-- Required. A scope claim needs TARGET_INTENT and nothing else (rule EC-07):
     reading a screen establishes what it does, never whether it is being rebuilt.
     Either cite the project's TARGET_INTENT records, or say that none has been
     supplied and that no screen above is marked in or out of scope. An analyst's
     emphasis reads as a decision when this section is missing. -->

### Carried forward from earlier phases

<!-- REQUIRED in every phase after the first, and written BEFORE this phase's own
     unknowns and questions.

     List every `UK-` and `Q` an earlier phase allocated and still open, and give each
     a status:

       resolved   - this phase's evidence answers it. Cite the evidence id, and say
                    what the answer is. Mark it resolved in the register too.
       advanced   - not closed, but something changed. Say what.
       unchanged  - nothing this phase read bears on it. Still say so.
       duplicate  - it asks what another identifier already asks. Name that one and
                    stop carrying both.

     A06's Phase 2 skipped this section and allocated `Q108`, which asks what Phase 1's
     `Q103` already asked of the same owner about the same file. Two questions to one
     person about one thing is the cheapest kind of waste to avoid and the easiest to
     create.

     Before allocating any new `UK-` or `Q`, read this list. An unknown that is already
     open does not need a second identifier; an unknown this phase can close does not
     need carrying. -->

| ID | Raised in | Status | What this phase establishes |
|---|---|---|---|

### Assumptions

<!-- `AS-nn`. A belief the phase relies on that the evidence does not
     establish. `If wrong` says what in this document stops holding, which is
     what makes it worth writing down rather than a disclaimer. -->

| ID | Assumption | If wrong |
|---|---|---|

### Unknowns

<!-- `UK-Snn` - Screens, the letter this phase owns. Each names the evidence
     class that would close it, so the operator is told what to fetch rather than
     that something is missing. -->

| ID | Unknown | Why it matters | What would settle it | Who can settle it |
|---|---|---|---|---|

### Questions

| ID | Question | Blocks | Owner |
|---|---|---|---|

---

## Provenance note

<!-- Only when something about the acquisition qualifies what is above: screenshots
     that name no screen, an export produced by an older tool, a control inventory
     that failed on some objects. A06's case: 13 of its 14 screenshots carry no index
     naming the screen they show, so the one evidence class this phase degrades
     without is present and, for all but one screen, uncitable. -->

## Evidence Register

<!-- Every claim above resolves here. Status is EXTRACTED, INFERRED or AMBIGUOUS; an
     INFERRED claim carries its confidence and never loses the label. -->

| ID | Status | Class | Claim kind | Source | Confidence |
|---|---|---|---|---|---:|
