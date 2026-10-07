"""Place a business rule or a risk on the screens it belongs to (A82).

The modernize pipeline links a rule or a risk to a screen by the evidence they share. That
link is exact and coarse, and the coarsest case is an evidence item most screens cite - a
whole UI export, a screenshot set. `screen_scope.py` now treats such an item as placing
nothing, and lists an entry linked only through it as cross-cutting. Some of those entries
belong to one screen in particular, and only a person can say which: the evidence that
would say so was never collected per screen.

`place` records that judgement as the entry's `screens`, with who made it and when. A
placement decides alone: the scope stops consulting evidence for that entry. An empty
placement removes it, and the entry goes back to being linked by evidence.
"""
from __future__ import annotations

import re
from typing import Any

import decision_queue as dq

PLACEABLE = ("BR-", "RD-", "RA-", "RW-", "RS-")
OBJECT_PREFIX = "object:"
DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")


class PlaceProblem(Exception):
    """Why nothing was written."""


def parse(specs: list[str]) -> dict[str, list[str]]:
    """`RA-03=F-001,object:受注画面` -> {RA-03: [F-001, object:受注画面]}; `RA-03=` clears."""
    found: dict[str, list[str]] = {}
    for spec in specs:
        item, separator, targets = spec.partition("=")
        if not separator or not item.strip():
            raise PlaceProblem(f"--place wants ID=F-nnn[,F-nnn], or ID= to clear; got {spec!r}")
        parts = [t.strip() for t in targets.split(",")] if targets.strip() else []
        if any(not t for t in parts):
            raise PlaceProblem(f"--place {spec!r}: an empty target between commas")
        found.setdefault(item.strip(), [])
        found[item.strip()] += parts
    return found


def place(entries: list[dict[str, Any]], placements: dict[str, list[str]], by: str, on: str,
          parties: dq.Parties | None = None) -> list[str]:
    """Write `screens` on each entry, in place, all or nothing. Returns what changed."""
    by = (by or "").strip()
    if not by:
        raise PlaceProblem("--place needs --by NAME: a placement that names nobody cannot be "
                           "taken back to whoever made it")
    people = ((parties.parties.get(dq.DECIDER) if parties else None) or {}).get("people") or []
    if people and by not in people:
        raise PlaceProblem(f"--by {by!r} is not one of the decider's people in parties.yaml: "
                           + ", ".join(people))
    if not DATE.match(on):
        raise PlaceProblem(f"--on wants a date, YYYY-MM-DD; got {on!r}")
    by_id = {str(e.get("id")): e for e in entries if e.get("id")}
    screens = {str(e["id"]) for e in entries if e.get("namespace") == "F-" and e.get("id")}
    problems: list[str] = []
    for item, targets in placements.items():
        entry = by_id.get(item)
        if entry is None:
            problems.append(f"{item}: not in the register")
            continue
        if entry.get("namespace") not in PLACEABLE:
            problems.append(f"{item}: is a {entry.get('namespace')}; only a business rule or a risk "
                            "is placed on a screen (a question names what it blocks in `needs.blocks`)")
        if str(entry.get("superseded_by") or "").strip():
            problems.append(f"{item}: is superseded by {entry['superseded_by']}; place that instead")
        for target in targets:
            if target.startswith(OBJECT_PREFIX):
                if not target[len(OBJECT_PREFIX):].strip():
                    problems.append(f"{item}: `{target}` names no object")
            elif target not in screens:
                problems.append(f"{item}: {target} is not a screen in the register (an F- entry, "
                                f"or {OBJECT_PREFIX}<production name>)")
    if problems:
        raise PlaceProblem("; ".join(problems))

    changed = []
    for item, targets in placements.items():
        entry = by_id[item]
        if targets:
            entry["screens"] = sorted(set(targets))
            entry["placed_by"], entry["placed_on"] = by, on
            changed.append(f"{item} -> {', '.join(entry['screens'])}")
        else:
            removed = [entry.pop(key, None) for key in ("screens", "placed_by", "placed_on")]
            changed.append(f"{item}: placement removed" if removed[0] else f"{item}: had no placement")
    return changed
