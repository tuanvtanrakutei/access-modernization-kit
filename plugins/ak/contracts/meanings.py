"""Business meaning, recorded when someone with the standing to say it says it.

The catalogue's `Business meaning` column reads `_needs DOCUMENT_` on all 121 tables
and all 1,055 columns, and a fair question is when it fills in. Not by running more
phases: a phase reads what was supplied, and no volume of schema or code establishes
what a table is *for* - that is rule EC-01, and it is the finding this whole audit
started from.

It fills when DOCUMENT or INTERVIEW evidence arrives. Until this
file existed there was nowhere to put it, so an answer given in a meeting had no home
and the column would have stayed empty however many documents turned up. That was the
gap.

`input/decisions/meanings.yaml` is person-owned, like the glossary beside it, and it
is read - never written - by `$ak catalogues`.

**A meaning without a source is refused, not stored.** That is the whole discipline of
this kit in one rule: an entry must name where the meaning came from, because
"somebody said so at some point" is exactly the kind of claim that becomes a fact by
repetition. An entry missing `source` is reported as incomplete and the cell keeps
reading `_needs DOCUMENT_`.

An entry nobody has touched yet is a different thing, and is counted rather than
reported. `$ak meanings` writes a blank entry for every subject that needs one, so
"no meaning; no source; no class" describes 1,176 A05 subjects on the first run - and
a refusal printed 1,176 times is not a refusal anybody reads. The line is drawn at
the first keystroke: an entry carrying *any* of the three fields is being worked on,
and is held to all three.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

# What may be cited as a source, matching evidence-classes.yaml. A name is not a
# source, and neither is an inference from code.
#
# `OPERATOR_DECLARATION` was accepted here until 2026-09-07 (backlog A18). The class
# is a statement about the *inputs* - which file is the backend, which copy is current
# - and its own entry in the class table has always said it cannot support a MEANING
# claim; only EC-01's wording disagreed. An operator who knows the answer is still a
# source, and a source who is a person is an INTERVIEW: their name and the date.
VALID_CLASSES = ("DOCUMENT", "INTERVIEW")


@dataclass
class Meaning:
    """One recorded meaning and where it came from."""

    subject: str
    text: str
    source: str
    evidence_class: str
    role: str = ""

    @property
    def is_complete(self) -> bool:
        return bool(self.text and self.source
                    and self.evidence_class in VALID_CLASSES)

    def cite(self) -> str:
        """The cell a reader sees: the meaning, then who said it."""
        return f"{self.text} — _{self.evidence_class}: {self.source}_"


@dataclass
class Meanings:
    tables: dict[str, Meaning]
    columns: dict[str, Meaning]
    # Forms and reports, keyed `"{kind} {name}"`. A form and a report may share a name
    # - A05 has two objects called the same thing - so the kind is part of the key, the
    # same reason `generate_catalogues.py` keys objects by kind.
    screens: dict[str, Meaning]
    # Files crossing the application's boundary, keyed by file name. Linked tables are
    # deliberately absent: a linked table is a table, it already carries a `tables:`
    # entry whose note reads "linked, so it lives in another file", and asking again
    # here would be one subject asked twice - which is the duplication this whole line
    # of work exists to remove.
    boundaries: dict[str, Meaning]
    incomplete: list[str]
    # Subjects with a blank entry waiting to be filled. Counted, never listed: this is
    # the worklist `$ak meanings` wrote, not a set of defects.
    unfilled: list[str] = field(default_factory=list)

    def table(self, name: str) -> Meaning | None:
        entry = self.tables.get(name)
        return entry if entry and entry.is_complete else None

    def boundary(self, name: str) -> Meaning | None:
        """What a file crossing the boundary is for, and who sends or reads it."""
        entry = self.boundaries.get(name)
        return entry if entry and entry.is_complete else None

    def screen(self, kind: str, name: str) -> Meaning | None:
        """What a form or report is for. `kind` is `form` or `report`."""
        entry = self.screens.get(f"{kind} {name}")
        return entry if entry and entry.is_complete else None

    def column(self, table: str, column: str) -> Meaning | None:
        """A column meaning may be given for one table, or for the name everywhere.

        `受注データ.出荷数量` is that column in that table. `出荷数量` alone is the
        column wherever it appears - which is the useful form here, because 53 A05
        column names appear in several tables and mostly mean the same thing in each.
        """
        for key in (f"{table}.{column}", column):
            entry = self.columns.get(key)
            if entry and entry.is_complete:
                return entry
        return None


def load(path: Path) -> Meanings:
    """Read the decisions file. A missing file means nothing is recorded yet."""
    if not path.is_file():
        return Meanings({}, {}, {}, {}, [])
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    tables: dict[str, Meaning] = {}
    columns: dict[str, Meaning] = {}
    screens: dict[str, Meaning] = {}
    boundaries: dict[str, Meaning] = {}
    incomplete: list[str] = []
    unfilled: list[str] = []
    for section, target in (("tables", tables), ("columns", columns),
                            ("screens", screens), ("boundaries", boundaries)):
        for subject, entry in (data.get(section) or {}).items():
            if not isinstance(entry, dict):
                incomplete.append(f"{section}/{subject}: not a mapping")
                continue
            meaning = Meaning(
                subject=str(subject),
                text=str(entry.get("meaning", "") or "").strip(),
                source=str(entry.get("source", "") or "").strip(),
                evidence_class=str(entry.get("evidence_class", "") or "").strip().upper(),
                role=str(entry.get("role", "") or "").strip(),
            )
            if not meaning.is_complete:
                if not (meaning.text or meaning.source or meaning.evidence_class):
                    # A blank entry from the worklist. Nobody has claimed anything, so
                    # there is nothing to refuse.
                    unfilled.append(f"{section}/{subject}")
                    continue
                why = []
                if not meaning.text:
                    why.append("no meaning")
                if not meaning.source:
                    why.append("no source")
                if meaning.evidence_class not in VALID_CLASSES:
                    why.append(
                        f"evidence_class must be one of {', '.join(VALID_CLASSES)}")
                incomplete.append(f"{section}/{subject}: " + "; ".join(why))
                continue
            target[str(subject)] = meaning
    return Meanings(tables, columns, screens, boundaries, incomplete, unfilled)
