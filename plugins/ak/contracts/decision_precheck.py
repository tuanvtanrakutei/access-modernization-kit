"""Before a person is asked, look for the answer where the kit already holds it (A58).

Q109 was put to warehouse operations: *what are the option-group values behind the two
adjustment lists?* The form definition declares exactly two, `バラのみ` at 1 and `ケースとバラ`
at 2, and the bundle had held them from the start. An interview is the one evidence class
this kit cannot generate, so a question spent on something already acquired is worse than a
question left open: the register then shows a closed question where no new evidence was
gained (backlog A58).

This module reads two places that already hold facts and flags a FACT item whose text names
something they cover:

  the screen catalogue's `Offers` column   every choice an option group presents
  `input/decisions/meanings.yaml`          what a table or column means, with its source

It flags and never answers. A name in a question is a weak signal: the same control may be
asked about for a reason the catalogue does not touch, and a flag the asker dismisses costs a
glance where a wrong withdrawal costs a closed question. So the flag says what was found and
where, and the question stays on the list. Withdrawing it is a person's decision, taken with
`resolved_by` and the evidence that answers it.

The names read are the ones a document quotes in backticks, which is how every phase writes
an object, control, table or column. A question that names nothing in backticks is not
checked, and that is a limit stated here rather than a heuristic hidden in the matcher.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import decision_queue as dq

QUOTED = re.compile(r"`([^`\n]{2,80})`")
# A name shorter than this is a column letter or a stray word, and would match half the
# catalogue as a substring.
MIN_SUBSTRING = 4
SHOWN = 3
# Naming an object is not asking what it offers: "are these two screens reachable?" says nothing
# about their option groups, and listing them there is noise a person learns to skip. A control is
# named exactly when it is the subject, so it is flagged on the name alone; an object is flagged
# only when the question is also about choices. The words are the ones A06's questions used, in
# the languages its documents are written in, and a question worded another way is missed: the
# direction that costs a question asked, not a question wrongly withdrawn.
CHOICE_WORDS = re.compile(r"option|choice|value|enumerat|toggle|default|select|choose|"
                          r"tuỳ chọn|tùy chọn|giá trị|選択|区分|値", re.IGNORECASE)
EMPTY_CELLS = ("", "—", "-", "–", "n/a")


@dataclass(frozen=True)
class Offer:
    """One control of one object that presents choices, as the catalogue lists it."""

    object: str
    control: str
    offers: str


def _bare(cell: str) -> str:
    return cell.strip().strip("`").strip()


def catalogue_offers(text: str) -> list[Offer]:
    """Every row of the catalogue's `Interactive controls` table that has something in `Offers`.

    Columns are found by their header name, not their position: the catalogue is generated
    and its column order is its own business, while the names are what a reader sees.
    """
    found: list[Offer] = []
    for table in dq.tables(text):
        header = [h.strip().strip("`").lower() for h in table.header]
        if not {"object", "control", "offers"} <= set(header):
            continue
        at = {name: header.index(name) for name in ("object", "control", "offers")}
        for row in table.rows:
            if not row.wellformed or len(row.cells) <= max(at.values()):
                continue
            offers = row.cells[at["offers"]].strip()
            if offers.lower() in EMPTY_CELLS:
                continue
            found.append(Offer(_bare(row.cells[at["object"]]), _bare(row.cells[at["control"]]), offers))
    return found


@dataclass(frozen=True)
class Meaning:
    kind: str           # "table" or "column"
    name: str
    meaning: str
    source: str


def read_meanings(path: Path) -> list[Meaning]:
    """What `meanings.yaml` already says about tables and columns. Empty when absent or unreadable."""
    if not path.is_file():
        return []
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except Exception:
        return []
    found: list[Meaning] = []
    for section, kind in (("tables", "table"), ("columns", "column")):
        body = data.get(section) if isinstance(data, dict) else None
        if not isinstance(body, dict):
            continue
        for name, entry in body.items():
            if isinstance(entry, dict) and str(entry.get("meaning") or "").strip():
                found.append(Meaning(kind, str(name), str(entry["meaning"]).strip(),
                                     str(entry.get("source") or "").strip()))
    return found


def quoted_names(text: str) -> list[str]:
    """The names a question quotes, each once, in order."""
    seen: list[str] = []
    for name in QUOTED.findall(text):
        name = name.strip()
        if name and name not in seen:
            seen.append(name)
    return seen


def _flags_for(names: Iterable[str], offers: list[Offer], meanings: list[Meaning],
               asks_choices: bool) -> list[dict[str, str]]:
    flags: list[dict[str, str]] = []
    for name in names:
        direct = [o for o in offers if o.control == name]
        if direct:
            for o in direct[:SHOWN]:
                flags.append({"kind": "offers", "name": name, "source": "ScreenCatalogue",
                              "text": f"`{o.control}` on `{o.object}` offers {o.offers}"})
            continue
        if asks_choices and len(name) >= MIN_SUBSTRING:
            # The question names a part of an object ("the adjustment list" for its print
            # screen), never the reverse: an object whose name merely sits inside a longer
            # name the question quotes is a different object.
            inside = [o for o in offers if name in o.object]
            if inside:
                shown = "; ".join(f"`{o.control}` offers {o.offers}" for o in inside[:SHOWN])
                more = f" (and {len(inside) - SHOWN} more)" if len(inside) > SHOWN else ""
                flags.append({"kind": "offers", "name": name, "source": "ScreenCatalogue",
                              "text": f"`{inside[0].object}` has option groups: {shown}{more}"})
        for m in meanings:
            if m.name == name:
                flags.append({"kind": "meaning", "name": name, "source": m.source or "meanings.yaml",
                              "text": f"meanings.yaml already says the {m.kind} `{m.name}` means: {m.meaning}"})
    return flags


def precheck(texts: dict[str, dict[str, str]], entries: list[dict[str, Any]],
             offers: list[Offer], meanings: list[Meaning]) -> dict[str, list[dict[str, str]]]:
    """Item id -> what the kit already holds about the names its question quotes.

    Only an open FACT item is checked: a disposition or a scope is a decision about the new
    system, which no catalogue of the old one can make. An item with nothing found has no key.
    """
    result: dict[str, list[dict[str, str]]] = {}
    for entry in entries:
        needs = entry.get("needs")
        if not (isinstance(needs, dict) and needs.get("kind") == "FACT" and dq.is_open(entry)):
            continue
        eid = str(entry["id"])
        said = texts.get(eid) or {}
        text = " ".join(str(v) for v in (entry.get("title"), said.get("ask"), said.get("why"), said.get("settle")) if v)
        flags = _flags_for(quoted_names(text), offers, meanings, bool(CHOICE_WORDS.search(text)))
        if flags:
            result[eid] = flags
    return result


def load(output: Path, decisions: Path, app_id: str = "") -> tuple[list[Offer], list[Meaning]]:
    """The catalogue beside the documents and meanings.yaml, each empty when absent."""
    offers: list[Offer] = []
    names = sorted(output.glob(f"{app_id}_ScreenCatalogue*.md" if app_id else "*_ScreenCatalogue*.md"))
    if names:
        offers = catalogue_offers(names[0].read_text(encoding="utf-8-sig"))
    return offers, read_meanings(decisions / "meanings.yaml")
