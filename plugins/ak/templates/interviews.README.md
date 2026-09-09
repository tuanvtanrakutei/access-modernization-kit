# `input/interviews/` — recorded answers from a named person

Written by `$ak init`. It describes the directory it sits in, and it is the same
everywhere, so editing it here only affects this workspace.

## Why this directory carries more weight than its size suggests

`specifications/evidence-classes.yaml` rule **EC-01**: a claim about **meaning**,
**usage**, or **intent** requires `DOCUMENT` or `INTERVIEW`. No volume of schema, code
or UI definition substitutes, however careful the reading, and neither does an
operator answering from their own knowledge — that *is* an interview, and it needs a
name and a date.

Five of the six phases name `DOCUMENT` or `INTERVIEW` in what they lose without it.
Phase 4's cost line is the sharpest: without it, *"the workflows become code paths, not
workflows."* Phase 6 without it produces a roadmap that is a proposal rather than an
agreed sequence.

Nothing the kit can run produces this class. It is the one evidence class that only
arrives because somebody asked a person a question and wrote the answer down.

## What an entry must carry

`schemas/evidence.schema.json` requires two fields on an `INTERVIEW` item and enforces
them with an `allOf`, so an answer that names nobody does not validate:

| Field | Meaning |
|---|---|
| `person` | Who said it. A name, not a team |
| `recorded_on` | `YYYY-MM-DD`. When they said it |
| `role` | Optional, and worth filling — it tells a reader how to weigh the answer |
| `question_id` | Optional. The `Q-` this closes, from the run's question list |

A gate cites an answer as `path::Q-NNN`, or `path::person, YYYY-MM-DD` when it closes
no numbered question. Both forms need the file to say who and when **inside** it — a
filename is not attribution.

## Accepted formats

| Put in | Read by | Note |
|---|---|---|
| `.md`, `.txt` | directly | The shortest path from a conversation to citable evidence |
| `.docx`, `.xlsx`, `.pdf` **with a text layer** | the document normalizer | A PDF exported from a document keeps its text |
| `.pdf` **scanned**, `.png`, `.jpg`, `.tif` | OCR | Needs Tesseract on the host, with `jpn` or `eng` language data |

`$ak documents` reports `OCR_REQUIRED` rather than guessing when Tesseract is absent,
and `CONVERSION_REQUIRED` for legacy `.doc` / `.ppt`. Either way the file is listed as
a gap, never silently skipped.

**A photograph of a whiteboard is fine evidence and a poor citation.** Where OCR is
unavailable or the handwriting defeats it, keep the image *and* add a short `.md`
beside it that transcribes the answer and names the source image. The image is what
was said; the transcription is what can be cited, and keeping both means a reader can
check one against the other.

## The shape to copy

Delete this heading and everything above it, or start a new file beside this one.
Neither this README nor any other file the kit writes counts as evidence of this
class — `contracts/evidence_classes.py` skips its own guide files, so a directory
holding only this one is correctly still empty.

```markdown
# Q&A — {topic}

Source: {conversation, meeting, email thread, desk visit}
Recorded by: {you}

## Q-19 — Does 担当者登録 become 商品区分登録, or are they different masters?

**{Person name}**, {role}, {YYYY-MM-DD}

{Their answer, in their words as far as you have them. Where you are paraphrasing,
say so — a paraphrase somebody can challenge is worth more than a quotation somebody
cannot check.}

## Q-20 — {next question}

**{Person name}**, {role}, {YYYY-MM-DD}

{answer}

## Asked and not yet answered

- Q-21 — {question}, sent {YYYY-MM-DD}, awaiting {who}
```

The last section matters as much as the answered ones. A question that was asked and
is still open is a different state from a question nobody thought to ask, and only one
of them needs chasing.
