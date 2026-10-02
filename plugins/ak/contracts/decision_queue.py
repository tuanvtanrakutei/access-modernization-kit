"""What a person has to be asked, as the identifier register records it.

Every question this kit raises used to live in two or three places and none of them was
a place a program could read. A phase wrote a `Questions` table, an `Unknowns` table
that mostly asked the same thing again, and an `Assumptions` table naming what the
pipeline proceeded on meanwhile - and the register beside them carried an id and a
title. Measured on A06 (backlog A75): 39 open entries were about two dozen distinct
asks, twelve spellings stood for four parties, and Q120 shows what a prose table costs:
when it was marked answered its row was rewritten in place, so the Blocks column holds
the original question, the Owner column holds an evidence id, the real owner is gone,
and the register still lists it as open.

This module holds the contract that replaces that, and nothing else. An entry in
`{APP_ID}_Identifiers.json` is a queue item if and only if it carries a `needs` block:

    "needs": {
      "kind": "FACT",             FACT | DISPOSITION | SCOPE | POLICY
      "party": "常温庫",           who can answer, a name from parties.yaml
      "also": [],                 others who can
      "named": [],                people inside the party, when known
      "blocks": ["WF-001"],       what cannot be finalised without it
      "default": "AS-32",         the assumption the pipeline proceeds on meanwhile
      "gap": "UK-W01",            the unknown this question asks about (a Q only)
      "depends_on": [],           items to settle first
      "class": "behaviour",       risks only: the key into standing policy
      "options": null             DISPOSITION and SCOPE: the choices
    }

No new identifier family: `Q`, `UK-`, the risk namespaces and `AS-` keep their
addresses, because a published identifier is permanent (ID-03). Status is not stored.
An item is open until `resolved_by` or `superseded_by` is set, which is what the
register contract already said.

Three things are checked, and each is a defect this kit has already had:

  the block itself      an unknown field is refused rather than ignored, because a
                        misspelt `block` that nothing reads is a field that does
                        nothing while looking like one that works (A13, A33)
  the references        every identifier it names resolves, and `depends_on` has no
                        cycle, because an agenda ordered by dependency cannot be
                        ordered by a loop
  the document          a phase's decision table and the register agree on party,
                        blocks, default and whether the item is closed

Nothing here decides a party or a block. It records the ones a person or a phase
author chose, and refuses the ones that cannot be followed.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

KINDS = ("FACT", "DISPOSITION", "SCOPE", "POLICY")

# FACT is answered by whoever knows. The other three are decisions about the system
# being built, and a decision about the new system is the decider's: the person
# building it. One role rather than the PM / tech-lead split in `DOCS_README.md`
# section 6, which exists for a review that this queue does not replace.
DECIDER = "decider"
DECIDER_KINDS = ("DISPOSITION", "SCOPE", "POLICY")

RISK_NAMESPACES = ("RD-", "RA-", "RW-", "RS-")
RISK_CLASSES = ("technical", "data", "retired", "behaviour")

# A disposition's default is the Mitigation its own risk already carries. That is not an
# assumption, so it cannot be an `AS-` id; this literal says where to read it from.
MITIGATION = "mitigation"
OBJECT_PREFIX = "object:"

NEEDS_KEYS = ("kind", "party", "also", "named", "blocks", "default", "gap",
              "depends_on", "class", "options")
PARTY_KEYS = ("aliases", "people", "source", "note")

SPEC = Path(__file__).resolve().parents[1] / "specifications" / "identifier-scheme.yaml"

# The scheme is the authority on what an identifier looks like, and this module reads it
# rather than keeping a second list. The finder below is deliberately permissive - the
# same split `validate_phase_conformance` makes, for the same reason: a finder as strict
# as the scheme makes a malformed identifier invisible instead of reported (A54).
_FINDER_BODY = (
    r"(?:(?:OB|F|BR|WF|DISC|RD|RA|RW|RS|UK|AS|E)-[A-Z0-9]{1,6}(?:-[0-9]{2})?[a-z]?"
    r"|Q[0-9]{1,3}|[dr][0-9]{2})"
)
FINDER = re.compile(rf"(?<![A-Za-z0-9_-]){_FINDER_BODY}(?![A-Za-z0-9_-])")
_LEADING = re.compile(rf"{_FINDER_BODY}(?![A-Za-z0-9_-])")
CODE_SPAN = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)
OBJECT_REF = re.compile(r"object:\s*([^,;、，；\n|]+)")


@lru_cache(maxsize=1)
def scheme_patterns() -> dict[str, re.Pattern[str]]:
    """Namespace key -> the scheme's own pattern. Empty when the scheme cannot be read."""
    try:
        import yaml

        data = yaml.safe_load(SPEC.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    return {name: re.compile(body["pattern"])
            for name, body in (data.get("namespaces") or {}).items()
            if isinstance(body, dict) and body.get("pattern")}


def is_identifier(token: str) -> bool:
    patterns = scheme_patterns()
    if not patterns:
        return bool(re.fullmatch(_FINDER_BODY, token))
    return any(pattern.fullmatch(token) for pattern in patterns.values())


def _is(namespace: str, token: str, fallback: str) -> bool:
    pattern = scheme_patterns().get(namespace)
    return bool((pattern or re.compile(fallback)).fullmatch(token))


def is_assumption(token: str) -> bool:
    return _is("AS", token, r"AS-[0-9]{2}")


def is_unknown(token: str) -> bool:
    return _is("UK", token, r"UK-[A-Z][0-9]{2}")


def is_open(entry: dict[str, Any]) -> bool:
    """Open until a closing field is set. Status is derived, never stored."""
    return (not str(entry.get("resolved_by") or "").strip()
            and not str(entry.get("superseded_by") or "").strip())


def find_identifiers(text: str) -> list[str]:
    """Identifiers in prose, in order, each once. Code spans are columns, not identifiers.

    A52: `d31` is a column in a real table and exactly the shape of the `d-` namespace.
    """
    blanked = CODE_SPAN.sub(lambda m: " " * len(m.group(0)), text)
    seen: list[str] = []
    for token in FINDER.findall(blanked):
        if token not in seen:
            seen.append(token)
    return seen


# --- parties -----------------------------------------------------------------

_BLANK = {"", "-", "–", "—", "―", "n/a", "na", "none", "なし", "無し"}


def _norm(text: Any) -> str:
    """Compare names the way a reader does: width, case, markup and spacing ignored."""
    value = unicodedata.normalize("NFKC", str(text if text is not None else ""))
    value = re.sub(r"[`*]", "", value)
    value = re.sub(r"\s+", " ", value).strip().strip(".:;,")
    return value.casefold()


def is_blank_cell(text: Any) -> bool:
    return _norm(text) in _BLANK


def split_parties(raw: str) -> list[str]:
    return [part for part in re.split(
        r"\s*(?:/|／|,|、|，|;|；|＋|\+|&|\band\b)\s*", raw, flags=re.IGNORECASE) if part.strip()]


@dataclass
class Parties:
    """Who can be asked, under one canonical name each.

    Twelve spellings stood for four parties on A06: the same department was `常温庫`,
    "Warehouse operations" and `常温庫 / システム課`, and an agenda keyed by the raw cell
    would have been twelve agendas. The file is written by the kit and edited by a person,
    like `glossary.yaml` beside it, and an alias is how a spelling already in a published
    document is brought under a name without rewriting the document.
    """

    parties: dict[str, dict[str, Any]] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    _index: dict[str, str] = field(default_factory=dict, repr=False)
    _people: dict[str, str] = field(default_factory=dict, repr=False)

    @classmethod
    def from_mapping(cls, data: Any) -> "Parties":
        result = cls()
        raw = (data or {}).get("parties") if isinstance(data, dict) else None
        if raw is None:
            raw = {}
        if not isinstance(raw, dict):
            result.problems.append("`parties` must be a mapping of canonical name to its entry")
            raw = {}
        entries: dict[str, dict[str, Any]] = {}
        for name, body in raw.items():
            body = body if isinstance(body, dict) else {}
            unknown = sorted(set(body) - set(PARTY_KEYS))
            if unknown:
                result.problems.append(
                    f"{name}: unknown field(s) {unknown}; allowed: {list(PARTY_KEYS)}")
            entries[str(name)] = body
        # The decider needs no declaration: every project has one, and a file that forgot
        # to name it would otherwise make every disposition unroutable.
        entries.setdefault(DECIDER, {})
        for name, body in entries.items():
            aliases = [str(a) for a in (body.get("aliases") or [])]
            people = [str(p) for p in (body.get("people") or [])]
            result.parties[name] = {"aliases": aliases, "people": people,
                                    "source": body.get("source"), "note": body.get("note")}
            for label in [name, *aliases]:
                key = _norm(label)
                if not key:
                    continue
                other = result._index.get(key)
                if other is not None and other != name:
                    result.problems.append(
                        f"{label!r} names both {other} and {name}; one spelling, one party")
                result._index[key] = name
            for person in people:
                key = _norm(person)
                other = result._people.get(key)
                if other is not None and other != name:
                    result.problems.append(f"{person} is listed under both {other} and {name}")
                result._people[key] = name
        return result

    def lookup(self, text: str) -> str | None:
        """The canonical name a spelling stands for, or None."""
        for candidate in (text, re.sub(r"\([^)]*\)|（[^）]*）", "", text)):
            hit = self._index.get(_norm(candidate))
            if hit:
                return hit
        return None

    def is_canonical(self, name: str) -> bool:
        return name in self.parties

    def resolve(self, text: Any) -> tuple[list[str], list[str]]:
        """(canonical names, spellings that are not a party). A dash resolves to nothing."""
        raw = str(text if text is not None else "")
        if is_blank_cell(raw):
            return [], []
        whole = self.lookup(raw)
        if whole:
            return [whole], []
        resolved: list[str] = []
        unresolved: list[str] = []
        for part in split_parties(raw):
            hit = self.lookup(part)
            if hit:
                if hit not in resolved:
                    resolved.append(hit)
            else:
                unresolved.append(part.strip())
        return resolved, unresolved

    def person_party(self, person: str) -> str | None:
        return self._people.get(_norm(person))


def load_parties(path: Path) -> Parties | None:
    """None when the file does not exist; a Parties carrying `problems` when it is wrong."""
    if not path.is_file():
        return None
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except Exception as error:      # unreadable is a finding about the file, not a crash
        broken = Parties()
        broken.problems.append(f"{path.name} cannot be read: {error}")
        return broken
    return Parties.from_mapping(data)


# --- the needs block -----------------------------------------------------------

def _as_list(value: Any) -> list[Any] | None:
    if value is None:
        return []
    return value if isinstance(value, list) else None


def validate_needs(entry: dict[str, Any], ids: set[str],
                   parties: Parties | None) -> list[str]:
    """Everything wrong with one entry's `needs` block. Empty when it has none or is sound."""
    eid = str(entry.get("id") or "?")
    needs = entry.get("needs")
    if needs is None:
        return []
    if not isinstance(needs, dict):
        return [f"{eid}: `needs` must be an object"]
    problems: list[str] = []

    unknown = sorted(set(needs) - set(NEEDS_KEYS))
    if unknown:
        problems.append(f"{eid}: unknown `needs` field(s) {unknown}; allowed: {list(NEEDS_KEYS)}")

    kind = needs.get("kind")
    if kind not in KINDS:
        problems.append(f"{eid}: `kind` must be one of {list(KINDS)}, got {kind!r}")

    namespace = str(entry.get("namespace") or "")
    is_risk = namespace in RISK_NAMESPACES

    party = needs.get("party")
    if not isinstance(party, str) or not party.strip():
        problems.append(f"{eid}: `party` is required")
    elif parties is not None:
        if not parties.is_canonical(party):
            hit = parties.lookup(party)
            problems.append(
                f"{eid}: party {party!r} is an alias of {hit!r}; the register keeps the canonical name"
                if hit else f"{eid}: party {party!r} is not in parties.yaml")
        elif kind in DECIDER_KINDS and party != DECIDER:
            problems.append(f"{eid}: a {kind} is the {DECIDER}'s to settle, not {party!r}'s")

    also = _as_list(needs.get("also"))
    if also is None:
        problems.append(f"{eid}: `also` must be a list")
    elif parties is not None:
        for other in also:
            if not isinstance(other, str) or not parties.is_canonical(other):
                problems.append(f"{eid}: `also` names {other!r}, which is not a party in parties.yaml")
            elif other == party:
                problems.append(f"{eid}: `also` repeats the party {other!r}")

    named = _as_list(needs.get("named"))
    if named is None or any(not isinstance(n, str) or not n.strip() for n in named):
        problems.append(f"{eid}: `named` must be a list of names")
    elif parties is not None:
        for person in named:
            if parties.person_party(person) is None:
                problems.append(f"{eid}: {person!r} is named but listed under no party in parties.yaml")

    blocks = _as_list(needs.get("blocks"))
    if blocks is None or any(not isinstance(b, str) or not b.strip() for b in blocks):
        problems.append(f"{eid}: `blocks` must be a list of identifiers or `object:` references")
    else:
        if not blocks and kind != "POLICY":
            problems.append(
                f"{eid}: `blocks` is empty. A question that blocks nothing identified has no "
                "reason to be asked; name the narrowest thing that waits on it")
        if len(set(blocks)) != len(blocks):
            problems.append(f"{eid}: `blocks` repeats an entry")
        for target in blocks:
            if target.startswith(OBJECT_PREFIX):
                if not target[len(OBJECT_PREFIX):].strip():
                    problems.append(f"{eid}: `blocks` has an empty `object:` reference")
            elif not is_identifier(target):
                problems.append(f"{eid}: `blocks` entry {target!r} is neither an identifier nor `object:<name>`")
            elif target not in ids:
                problems.append(f"{eid}: `blocks` entry {target} is not in the register")
            elif target == eid:
                problems.append(f"{eid}: blocks itself")

    default = needs.get("default")
    if default is not None:
        if default == MITIGATION:
            if not (is_risk and kind == "DISPOSITION"):
                problems.append(
                    f"{eid}: `default: mitigation` reads the Mitigation of a risk, "
                    "so it belongs on a DISPOSITION anchored on one")
        elif not isinstance(default, str) or not is_assumption(default):
            problems.append(f"{eid}: `default` must be an AS- identifier, got {default!r}")
        elif default not in ids:
            problems.append(f"{eid}: `default` {default} is not in the register")

    gap = needs.get("gap")
    if gap is not None:
        if namespace != "Q":
            problems.append(f"{eid}: `gap` belongs on a Q, which asks about the unknown it names")
        elif not isinstance(gap, str) or not is_unknown(gap):
            problems.append(f"{eid}: `gap` must be a UK- identifier, got {gap!r}")
        elif gap not in ids:
            problems.append(f"{eid}: `gap` {gap} is not in the register")

    depends = _as_list(needs.get("depends_on"))
    if depends is None or any(not isinstance(d, str) for d in depends):
        problems.append(f"{eid}: `depends_on` must be a list of identifiers")
    else:
        for target in depends:
            if target == eid:
                problems.append(f"{eid}: depends on itself")
            elif target not in ids:
                problems.append(f"{eid}: `depends_on` {target} is not in the register")

    klass = needs.get("class")
    if klass is not None:
        if not is_risk:
            problems.append(f"{eid}: `class` is for risks, which policy settles by class")
        elif klass not in RISK_CLASSES:
            problems.append(f"{eid}: `class` must be one of {list(RISK_CLASSES)}, got {klass!r}")

    options = needs.get("options")
    if options is not None:
        if kind not in ("DISPOSITION", "SCOPE"):
            problems.append(f"{eid}: `options` are the choices of a DISPOSITION or a SCOPE")
        elif (not isinstance(options, list) or len(options) < 2 or len(set(map(str, options))) != len(options)
              or any(not isinstance(o, str) or not o.strip() for o in options)):
            problems.append(f"{eid}: `options` needs at least two distinct choices")
    return problems


def _cycles(entries: Iterable[dict[str, Any]]) -> list[list[str]]:
    """Loops in `depends_on`. An agenda ordered by dependency cannot be ordered by a loop."""
    graph: dict[str, list[str]] = {}
    for entry in entries:
        needs = entry.get("needs")
        if isinstance(needs, dict) and isinstance(needs.get("depends_on"), list):
            graph[str(entry.get("id"))] = [str(d) for d in needs["depends_on"]]
    found: list[list[str]] = []
    colour: dict[str, int] = {node: 0 for node in graph}      # 0 unseen, 1 on the path, 2 done

    def visit(node: str, path: list[str]) -> None:
        colour[node] = 1
        path.append(node)
        for nxt in graph[node]:
            if nxt not in graph:
                continue            # depends on nothing itself, so it cannot close a loop
            if colour[nxt] == 1:
                found.append(path[path.index(nxt):] + [nxt])
            elif colour[nxt] == 0:
                visit(nxt, path)
        path.pop()
        colour[node] = 2

    for node in sorted(graph):
        if colour[node] == 0:
            visit(node, [])
    return found


def validate_register(entries: list[dict[str, Any]], parties: Parties | None,
                      phase: int | None = None) -> list[str]:
    """ID-07 to ID-09 over one phase's allocations, or the whole register when phase is None."""
    ids = {str(e.get("id")) for e in entries if e.get("id")}
    mine = [e for e in entries if phase is None or e.get("phase") == phase]
    problems: list[str] = []
    for entry in mine:
        problems += validate_needs(entry, ids, parties)

    asked = {str(e["needs"]["gap"]) for e in entries
             if isinstance(e.get("needs"), dict) and e["needs"].get("gap")}
    for entry in mine:
        eid = str(entry.get("id"))
        namespace = str(entry.get("namespace") or "")
        if not is_open(entry) or isinstance(entry.get("needs"), dict):
            continue
        if namespace == "Q":
            problems.append(f"{eid}: an open question with no `needs`; nothing can route, rank or block on it")
        elif namespace == "UK-" and eid not in asked:
            problems.append(f"{eid}: an open unknown that no Q asks about (`gap`) and that carries no `needs`")

    mine_ids = {str(e.get("id")) for e in mine}
    for loop in _cycles(entries):
        if mine_ids.intersection(loop):
            problems.append("depends_on cycle: " + " -> ".join(loop))
    return problems


# --- the document side -----------------------------------------------------------

@dataclass
class Row:
    cells: list[str]
    line: int
    identifier: str | None
    columns: int            # the header's width: a row of any other width is mis-split

    @property
    def wellformed(self) -> bool:
        return len(self.cells) == self.columns


@dataclass
class Table:
    heading: str
    header: list[str]
    rows: list[Row]
    line: int


def _mask(text: str) -> str:
    """Blank comments and fences, keeping every newline so line numbers stay true.

    A template's guidance comments carry example tables, and a published document is not
    supposed to have the comments at all - but a checker that parses them would report
    the template's example rows as the document's.
    """
    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", "", match.group(0))

    text = re.sub(r"<!--.*?-->", blank, text, flags=re.DOTALL)
    return re.sub(r"^```[^\n]*\n.*?^```[^\n]*$", blank, text, flags=re.DOTALL | re.MULTILINE)


def split_row(line: str) -> list[str]:
    """Cells of one table row. `\\|` is a pipe in the text, as GitHub renders it."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|") and not body.endswith("\\|"):
        body = body[:-1]
    cells: list[str] = []
    current: list[str] = []
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\" and index + 1 < len(body) and body[index + 1] == "|":
            current.append("|")
            index += 2
            continue
        if char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    cells.append("".join(current).strip())
    return cells


_DELIMITER = re.compile(r"^\|?\s*:?-{1,}:?\s*(?:\|\s*:?-{1,}:?\s*)*\|?\s*$")


def leading_identifier(cell: str) -> str | None:
    """The identifier a cell opens with: `Q117`, `**Q117**`, and `RD-01 — Missing keys`.

    Phase 1 of A06 writes its risk rows as `| RD-01 — Missing primary keys | HIGH | ... |`:
    no ID column, the identifier inside the first cell and every other column shifted
    one to the left of where the template puts it. A reader sees a risk table; a parser
    that wanted the ID in cell zero on its own sees seven rows with no identifier.
    """
    stripped = re.sub(r"^[\s*_`\[(]+", "", cell)
    match = _LEADING.match(stripped)
    return match.group(0) if match else None


def tables(text: str) -> list[Table]:
    lines = _mask(text).split("\n")
    found: list[Table] = []
    heading = ""
    index = 0
    while index < len(lines):
        line = lines[index]
        if re.match(r"^#{1,6}\s", line):
            heading = line.lstrip("#").strip()
        if (line.lstrip().startswith("|") and index + 1 < len(lines)
                and lines[index + 1].lstrip().startswith("|")
                and _DELIMITER.match(lines[index + 1].strip())
                and len(split_row(line)) == len(split_row(lines[index + 1]))):
            header = split_row(line)
            rows: list[Row] = []
            cursor = index + 2
            while cursor < len(lines) and lines[cursor].lstrip().startswith("|"):
                cells = split_row(lines[cursor])
                rows.append(Row(cells, cursor + 1, leading_identifier(cells[0]) if cells else None,
                                len(header)))
                cursor += 1
            found.append(Table(heading, header, rows, index + 1))
            index = cursor
            continue
        index += 1
    return found


_SEPARATORS = re.compile(r"[\s,;、，；/／+＋&]+|\band\b", re.IGNORECASE)


def _only_identifiers(text: str, found: Iterable[str]) -> bool:
    """True when nothing but the identifiers and their separators is in the text.

    A cell that merely mentions an identifier is prose. A06's Q117 blocks cell reads
    "Reproducing the day boundary - the `参考日` half of this is Q115", and treating Q115 as
    what it blocks would report a contradiction against a register that is right.
    """
    rest = text
    for token in sorted(found, key=len, reverse=True):
        rest = rest.replace(token, " ")
    rest = _SEPARATORS.sub(" ", rest)
    return not re.search(r"\w", rest)


def cell_blocks(cell: str) -> set[str] | None:
    """The identifiers and `object:` references a Blocks cell consists of; None when prose.

    A dash is a statement - it blocks nothing - and so is not prose. Prose is a cell with
    anything else in it, which every published A06 phase has, and which is counted rather
    than compared.
    """
    if is_blank_cell(cell):
        return set()
    plain = cell.replace("`", "")
    objects = [m.strip() for m in OBJECT_REF.findall(plain)]
    remainder = OBJECT_REF.sub(" ", plain)
    found = find_identifiers(remainder)
    if not (found or objects) or not _only_identifiers(remainder, found):
        return None
    return set(found) | {OBJECT_PREFIX + name for name in objects}


def cell_default(cell: str) -> tuple[bool, str | None]:
    """(structured, the AS- identifier or None). A dash says there is no default."""
    if is_blank_cell(cell):
        return True, None
    named = [i for i in find_identifiers(cell) if is_assumption(i)]
    if len(named) == 1 and _only_identifiers(cell.replace("`", ""), named):
        return True, named[0]
    return False, None


def starts_closed(text: str, markers: tuple[str, ...]) -> bool:
    opening = unicodedata.normalize("NFC", re.sub(r"^[\s*_`>]+", "", text)).casefold()
    return any(opening.startswith(unicodedata.normalize("NFC", m).casefold()) for m in markers)


@dataclass
class Comparison:
    findings: list[str] = field(default_factory=list)
    compared: int = 0
    unstructured: int = 0


def compare_document(text: str, phase: int, entries: list[dict[str, Any]],
                     parties: Parties | None,
                     closed_markers: tuple[str, ...] = ()) -> Comparison:
    """Does this phase's decision tables say what the register says?

    Only this phase's own allocations are compared. A phase's `Carried forward` table
    opens with earlier phases' identifiers and has a different shape, and reading it as a
    Questions table would report the carrying as a contradiction.

    Columns are read by position, not by header text, because the documents are written in
    three languages (`Câu hỏi | Chặn cái gì | Chủ sở hữu` is the same table as `Question |
    Blocks | Owner`). Where a cell is prose that names nothing a program can follow, it is
    counted and not compared: a document published before this contract is not wrong for
    having been written before it, and a count in the result keeps the skipped rows
    visible rather than reading as a pass.
    """
    result = Comparison()
    own = {str(e["id"]): e for e in entries
           if e.get("phase") == phase and e.get("namespace") in ("Q", "UK-") and e.get("id")}
    asked_by: dict[str, list[str]] = {}
    for entry in entries:
        needs = entry.get("needs")
        if isinstance(needs, dict) and needs.get("gap"):
            asked_by.setdefault(str(needs["gap"]), []).append(str(entry.get("id")))

    for table in tables(text):
        for row in table.rows:
            entry = own.get(row.identifier or "")
            if entry is None:
                continue
            kind = entry["namespace"]
            minimum = 4 if kind == "Q" else 5
            if len(table.header) < minimum:
                continue            # not a Questions / Unknowns table: a differently shaped mention
            eid = str(entry["id"])
            where = f"line {row.line}: {eid}"
            if not row.wellformed:
                result.findings.append(
                    f"{where} has {len(row.cells)} cells under a {row.columns}-column header. "
                    "An unescaped `|` inside a cell shifts every column after it; write `\\|`")
                continue
            body = row.cells[1]
            if is_open(entry) and closed_markers and starts_closed(body, closed_markers):
                result.findings.append(
                    f"{where} is marked closed in the document and is open in the register; "
                    "set `resolved_by` (or `superseded_by`) when a document says it is answered")
            needs = entry.get("needs")
            touched = False
            if kind == "UK-" and len(row.cells) >= 6:
                # Whether a Q asks about this unknown is a fact about the Q's `gap`, so it
                # is checked even when the unknown carries no `needs` of its own.
                touched = True
                structured = (is_blank_cell(row.cells[5])
                              or _only_identifiers(row.cells[5],
                                                   find_identifiers(row.cells[5])))
                register_asked = set(asked_by.get(eid, []))
                if not structured:
                    result.unstructured += 1
                else:
                    doc_asked = {i for i in find_identifiers(row.cells[5]) if i.startswith("Q")}
                    if doc_asked != register_asked:
                        result.findings.append(
                            f"{where} asked as: the document says {sorted(doc_asked) or ['(none)']}, "
                            f"the register's `gap` links say {sorted(register_asked) or ['(none)']}")
            if not isinstance(needs, dict):
                result.compared += 1 if touched else 0
                continue
            touched = True
            result.compared += 1
            party_cell = row.cells[3] if kind == "Q" else row.cells[4]
            if parties is not None:
                resolved, unresolved = parties.resolve(party_cell)
                declared = [d for d in [needs.get("party"), *(needs.get("also") or [])] if d]
                if unresolved:
                    result.findings.append(
                        f"{where} names {unresolved} as its party, which parties.yaml does not know")
                elif set(resolved) != set(declared):
                    result.findings.append(
                        f"{where} party: the document says {resolved or ['(none)']}, "
                        f"the register says {declared or ['(none)']}")
            if kind == "Q":
                doc_blocks = cell_blocks(row.cells[2])
                register_blocks = set(needs.get("blocks") or [])
                if doc_blocks is None:
                    result.unstructured += 1
                elif doc_blocks != register_blocks:
                    result.findings.append(
                        f"{where} blocks: only in the document {sorted(doc_blocks - register_blocks)}, "
                        f"only in the register {sorted(register_blocks - doc_blocks)}")
                if len(row.cells) >= 5:
                    structured_default, doc_default = cell_default(row.cells[4])
                    if not structured_default:
                        result.unstructured += 1
                    elif doc_default != needs.get("default"):
                        result.findings.append(
                            f"{where} default: the document says {doc_default or '(none)'}, "
                            f"the register says {needs.get('default') or '(none)'}")
    return result
