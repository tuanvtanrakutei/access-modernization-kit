# `input/` — everything you supply

This folder is yours. The kit reads it and never writes it, and **a file is declared
by being here** — there is no manifest to keep in step.

Each folder below is one *class of evidence*, and the class decides what a claim in
the published documents is allowed to say. That is the rule the whole analysis turns
on: a schema can tell you a column is `Short Text(8)`; only a person or a document can
tell you what it is *for*. So an empty folder is not an oversight to apologise for —
it is a statement about what the analysis cannot establish, and the documents say so
in those terms.

After adding anything, from the workspace root:

```
$ak documents  --app-root .     # read the new files into the corpus
$ak catalogues --app-root .     # regenerate the catalogues
$ak references --app-root .     # refresh the source list, with digests
$ak bilingual  --app-root .     # refresh the English names in the narratives
```

---

## The folders

| Folder | Evidence class | What only this can establish |
|---|---|---|
| `documents/` | DOCUMENT | What a table, screen or process is **for**. Business roles. Why something exists. |
| `interviews/` | INTERVIEW | Meaning and usage nobody wrote down. Whether a screen is still pressed. |
| `screenshots/` | SCREENSHOT | Layout, grouping, tab structure, and **which controls an operator can actually see**. |
| `samples/` | SAMPLE_DATA | What an inbound file really contains — especially where the link declares `HDR=NO` and column meaning is positional. |
| `report-samples/` | OUTPUT_SAMPLE | What the application actually produced, as opposed to what the code appears to write. |
| `access/`, `vba/`, `sql/` | SCHEMA · CODE · UI_DEFINITION | The application itself. |
| `shared-docs/` | DOCUMENT | Documents this application shares with others in the same estate. |
| `decisions/` | OPERATOR_DECLARATION | Names and meanings **you** have settled. See below. |

### `documents/`

Anything in any state: an operational function list, a data dictionary, a screen list,
a training manual, a handover note, a system inventory, a procedure someone printed
years ago. A document with a date and an author beats a polished one with neither.

A *system* inventory establishes what an application is for. A *data* dictionary
establishes what its tables are for. They are different documents and the catalogues
need the second one to fill their business-meaning column.

### `screenshots/`

Runtime images show what an operator sees. **Design-view images show what is there** —
including controls that are hidden, overlapped, or in a section the form does not
display. Supply both if you can; they answer different questions.

Name them so the object is obvious: `<form name>-<tab or state>-runtime.png`,
`<form name>-design.png`.

Better than either: run `ExportAccessObjects` (see below) and drop the resulting
`ui/controls.json` here. It records `visible` and the attached label per control as
data rather than as a picture.

### `samples/`

One real example of each inbound file, as the sender produces it — not a file made up
to look right. Anonymise the values if you must, but keep the column count and the
widths: those are the thing being read.

### `decisions/` — the two files you edit

| File | What it settles |
|---|---|
| `glossary.yaml` | The English name for each production name. Change any that is wrong and set `status: accepted`; an accepted name always wins over a composed one. |
| `meanings.yaml` | Business meaning per table or column. **An entry must name its source** — `evidence_class` (DOCUMENT, INTERVIEW or OPERATOR_DECLARATION) and `source` — or it is ignored and the cell keeps reading `_needs DOCUMENT_`. |

That last rule is the same discipline the kit applies to itself: a meaning with no
source is the kind of claim that becomes a fact by repetition.

Neither file is one you start from a blank page. `$ak glossary` proposes a name for
every production name, and `$ak meanings` writes a **blank** entry for every table and
column that still needs a meaning, ordered so the ones the application actually uses
come first, each with what the kit knows beside it — who writes the table, how many
objects name it. Run `$ak meanings --top 50` to start somewhere; a later run adds the
rest and never touches what you have written.

The asymmetry is deliberate. A name can be proposed because it is composed from terms
that were themselves decided; a meaning cannot be composed from anything, so the tool
offers you the question and never the answer.

**An answer from a conversation counts.** Record it as `INTERVIEW` with who said it and
when — a name and a date is the whole requirement, and a remark at somebody's desk is
an interview if you write down whose remark it was. What does *not* count is what you
worked out from reading the code: that is CODE, and rule EC-01 says no volume of it
establishes what a table is for, however careful the reading. Ask, then record the
answer.

---

## Getting more out of Access

`plugins/ak/tools/ExportAccessObjects.bas` exports everything from inside Access, with
no COM automation and no elevation. Open the database, **Alt+F11**, *File > Import
File*, pick the `.bas`, then **Ctrl+G** and:

```vba
ExportAccessObjects "<a folder to write into>"
```

It writes the definition text for every form, report, macro and module, the SQL of
every query, the table schema, and **`ui/controls.json`** — every control with its
name, type, caption, **attached label**, tooltip, **visible**, position and OnClick.

Those last two matter more than they look. Access stores a button's visible text on a
*separate* label control and records no link between the two, so reading a button's
name as its caption is a guess; and in definition text a hidden control is
indistinguishable from one an operator uses every morning.

Each object is opened in design view, hidden, and closed with `acSaveNo` — design view
does not fire `Form_Open`, so no startup code runs, and nothing is ever saved.

### A report sample

With a PDF printer as the default — most machines have one — printing the report
normally produces a PDF:

```vba
DoCmd.OpenReport "<report name>", acViewNormal
```

Access 2003 has no `acFormatPDF` constant for `OutputTo`, but PDF output needs a
printer driver rather than a constant. For a text-shaped sample that shows values
instead of layout:

```vba
DoCmd.OutputTo acOutputReport, "<report name>", acFormatRTF, "<path>.rtf"
```

### Row counts

An empty table and a live one look identical in a schema:

```vba
Open "<path>.txt" For Output As #1: For Each t In CurrentDb.TableDefs: Print #1, t.Name & vbTab & t.RecordCount: Next: Close #1
```

---

## What this project specifically still needs

Not here. `output/<APP>_EvidenceRequest.md` names it, item by item, with what each one
unblocks and what stays unanswerable without it — and it is regenerated as the
analysis learns more. This page describes the folders; that page describes the gaps.
