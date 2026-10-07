"""Give an open question a default: an assumption the pipeline proceeds on meanwhile (A80).

A question with no default blocks what it names, and the modernize pre-flight stops on a
screen such a question names directly. That stop is right - there is nothing to proceed
on - and some of those questions sit with the customer for weeks. The register already
models the way out: a `needs.default` naming an `AS-` entry whose `if_wrong` says what
stops holding if the assumption is wrong. What it lacked was a way to write one that did
not mean editing the register by hand.

`assume` allocates the next `AS-`, records who assumed it and when, and sets it as the
question's default. The question stays open: the assumption is not an answer, and when
the answer arrives ID-13 holds the assumption to it - confirmed (`resolved_by`) or
corrected through an errata entry whose `affected` names its `if_wrong`.

The assumption is allocated in the phase that allocated the question, because the phase
document that has to change is that one: its Questions row's Default cell, and its
Assumptions table. The conformance gate reports the document until both agree.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

import decision_queue as dq

AS_ID = re.compile(r"^AS-([0-9]{2,})$")
DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
ASSUMABLE = ("FACT", "SCOPE")


class AssumeProblem(Exception):
    """Why nothing was written."""


@dataclass
class Assumption:
    entry: dict[str, Any]
    item: dict[str, Any]
    warnings: list[str] = field(default_factory=list)


def next_id(entries: list[dict[str, Any]]) -> str:
    numbers = [int(m.group(1)) for e in entries for m in [AS_ID.match(str(e.get("id") or ""))] if m]
    number = max(numbers, default=0) + 1
    if number > 99:
        raise AssumeProblem("AS-99 is taken: the scheme's AS- pattern has two digits")
    return f"AS-{number:02d}"


def assume(entries: list[dict[str, Any]], item_id: str, statement: str, if_wrong: str,
           by: str, on: str, parties: dq.Parties | None = None) -> Assumption:
    """Allocate the assumption and set it as the item's default, in place. Raises on any problem."""
    by_id = {str(e.get("id")): e for e in entries if e.get("id")}
    item = by_id.get(item_id)
    if item is None:
        raise AssumeProblem(f"{item_id}: not in the register")
    needs = item.get("needs")
    if not isinstance(needs, dict):
        raise AssumeProblem(f"{item_id}: has no `needs`, so nothing reads a default from it "
                            "(`$ak backfill-needs`)")
    if not dq.is_open(item):
        raise AssumeProblem(f"{item_id}: is closed; an answered question needs no assumption")
    if needs.get("kind") not in ASSUMABLE:
        raise AssumeProblem(f"{item_id}: is a {needs.get('kind')}; only a "
                            f"{' or '.join(ASSUMABLE)} question proceeds on an assumption "
                            "(a risk's disposition is decided with --decide)")
    if needs.get("default"):
        raise AssumeProblem(f"{item_id}: already proceeds on {needs['default']}; change that "
                            "assumption rather than stacking a second one")
    statement, if_wrong, by = statement.strip(), if_wrong.strip(), by.strip()
    if not statement:
        raise AssumeProblem("the assumption is empty: say what the pipeline proceeds on")
    if not if_wrong:
        raise AssumeProblem("--if-wrong is empty: say what stops holding if the assumption is "
                            "wrong (ID-12), or the answer cannot say what to correct")
    if not by:
        raise AssumeProblem("--by is empty: an assumption that names nobody cannot be taken "
                            "back to whoever made it")
    people = ((parties.parties.get(dq.DECIDER) if parties else None) or {}).get("people") or []
    if people and by not in people:
        raise AssumeProblem(f"--by {by!r} is not one of the decider's people in parties.yaml: "
                            + ", ".join(people))
    if not DATE.match(on):
        raise AssumeProblem(f"--on wants a date, YYYY-MM-DD; got {on!r}")

    ident = next_id(entries)
    entry = {
        "id": ident,
        "namespace": "AS-",
        "phase": item.get("phase"),
        "title": statement,
        dq.IF_WRONG: if_wrong,
        "evidence_ids": [],
        "assumed_for": item_id,
        "assumed_by": by,
        "assumed_on": on,
    }
    entries.append(entry)
    needs["default"] = ident
    ids = {str(e.get("id")) for e in entries if e.get("id")}
    problems = dq.validate_needs(item, ids, parties)
    if problems:
        entries.remove(entry)
        needs["default"] = None
        raise AssumeProblem("; ".join(problems))
    warnings = []
    if not dq.refresh_set(entry):
        warnings.append(f"{ident}'s if_wrong names no identifier, so its refresh set is empty and "
                        "an answer that contradicts it cannot be checked against what it corrects; "
                        "name what it feeds (" + ", ".join(needs.get("blocks") or []) + ")")
    return Assumption(entry=entry, item=item, warnings=warnings)


def document_edits(assumption: Assumption, documents: list[str]) -> list[str]:
    """What the phase document has to say for the conformance gate to agree with the register."""
    entry, item = assumption.entry, assumption.item
    where = ", ".join(documents) if documents else f"the Phase {item.get('phase')} document"
    return [
        f"{where}: the Questions row for {item['id']} - its Default cell becomes `{entry['id']}`",
        f"{where}: the Assumptions table gains `{entry['id']}` | {entry['title']} | "
        f"{entry[dq.IF_WRONG]}",
    ]
