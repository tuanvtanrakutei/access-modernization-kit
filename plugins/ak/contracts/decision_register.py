"""Reading and writing the identifier register, and finding the documents its rows came from.

Two commands now need the same four things: `$ak backfill-needs` (slice 1) and `$ak decisions`
(slice 2). Find the register, find the evidence it cites, find the phase document that
allocated an item and read that item's row, and write the register back without changing
anything but what was asked. They were written once, inside the first command, and a second
copy inside the second would have drifted - the register's format in particular, which is
the one thing a diff of it must not disturb.

The register is written in the format it was written in: indent 1, sorted keys, a final
newline. A06's round-trips byte for byte, so a change to it is a diff of the fields changed
and nothing else, and the previous file is kept under `.ak/backups/` before every write.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import decision_queue as dq

LANGUAGE_SUFFIX = re.compile(r"_([A-Z]{2})\.md$")
PHASE_FILE = re.compile(r"Phase([1-6])_", re.IGNORECASE)


class RegisterProblem(Exception):
    """Something that stops the run and is worth saying in one line."""


def _find(output: Path, pattern: str) -> list[Path]:
    # `registers/` as well as the top level: the registers moved down a level when the
    # published set grew catalogues, and a workspace published before that keeps them up.
    return [m for where in (".", "registers") for m in sorted((output / where).glob(pattern))]


def register_path(output: Path) -> Path:
    found = _find(output, "*_Identifiers.json")
    if len(found) != 1:
        raise RegisterProblem(f"expected one *_Identifiers.json under {output}, found {len(found)}")
    return found[0]


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def read_register(path: Path) -> dict[str, Any]:
    return json.loads(read_text(path))


def read_identifiers(path: Path) -> dict[str, Any]:
    """The identifier register, with its rows under `entries` whatever the file calls them.

    A05's register predates the rename and keeps its rows under `items`, the key the
    evidence register still uses. `backfill-needs` read `register["entries"]` and stopped
    on A05 with a KeyError, while the conformance gate and the catalogues already read
    both keys. Writing it back moves the rows to `entries`, and the old file is kept
    under `.ak/backups/`.
    """
    register = read_register(path)
    if "entries" not in register and isinstance(register.get("items"), list):
        register["entries"] = register.pop("items")
    # The same register writes a namespace without its dash: `UK` for `UK-L01`, `RA` for
    # `RA-02`. The queue matches `UK-` and `RA-`, so on A05 every unknown and every risk
    # fell out of the proposal without a word. `Q` has no dash in either spelling.
    for entry in register.get("entries") or []:
        if not isinstance(entry, dict):
            continue
        namespace = str(entry.get("namespace") or "")
        if (re.fullmatch(r"[A-Z]{1,4}", namespace)
                and str(entry.get("id") or "").startswith(namespace + "-")):
            entry["namespace"] = namespace + "-"
    return register


def format_register(register: dict[str, Any]) -> str:
    return json.dumps(register, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


def atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temporary, path)


def write_register(space: Any, path: Path, register: dict[str, Any]) -> Path:
    """Write the register, keeping the previous file. Returns where the previous one went.

    The evidence register goes through here too: A06's round-trips in the same format.
    """
    backups = space.owned("backups")
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = backups / f"{path.stem}.{stamp}.json"
    # Windows' clock can return one microsecond stamp for two writes in a row, and the
    # second backup then replaced the first: CI lost a previous file this way. A stamp
    # already taken gets a counter rather than an overwrite.
    counter = 1
    while backup.exists():
        backup = backups / f"{path.stem}.{stamp}-{counter}.json"
        counter += 1
    backup.write_bytes(path.read_bytes())
    atomic_write(path, format_register(register))
    return backup


def evidence_path(output: Path) -> Path:
    found = _find(output, "*_Evidence.json")
    if len(found) != 1:
        raise RegisterProblem(f"expected one *_Evidence.json under {output}, found {len(found)}")
    return found[0]


def evidence_index(output: Path) -> dict[str, dict[str, Any]] | None:
    """Evidence id -> its item, or None when there is no readable evidence register."""
    found = _find(output, "*_Evidence.json")
    if len(found) != 1:
        return None
    try:
        items = read_register(found[0]).get("items") or []
    except (OSError, json.JSONDecodeError):
        return None
    return {str(i["id"]): i for i in items if isinstance(i, dict) and i.get("id")}


def errata_ids(output: Path) -> set[str]:
    found = _find(output, "*_Errata.json")
    if len(found) != 1:
        return set()
    try:
        entries = read_register(found[0]).get("entries") or []
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(e["id"]) for e in entries if isinstance(e, dict) and e.get("id")}


def errata_entries(output: Path) -> list[dict[str, Any]] | None:
    """The errata register's entries, or None when the project has no errata register."""
    found = _find(output, "*_Errata.json")
    if len(found) != 1:
        return None
    try:
        entries = read_register(found[0]).get("entries") or []
    except (OSError, json.JSONDecodeError):
        return None
    return [e for e in entries if isinstance(e, dict)]


def phase_documents(output: Path, language: str | None = None) -> dict[int, Path]:
    """One document per phase: the requested language, else EN, else whichever there is.

    A request for a language a phase was never written in degrades to the English one
    rather than to nothing. Reporting a phase as having no questions because nobody has
    translated it would be a defect in the reader, not a fact about the phase.
    """
    wanted = [language.upper()] if language else []
    wanted.append("EN")
    found: dict[int, dict[str, Path]] = {}
    for path in sorted(output.glob("*.md")):
        match = PHASE_FILE.search(path.name)
        if not match:
            continue
        suffix = LANGUAGE_SUFFIX.search(path.name)
        found.setdefault(int(match.group(1)), {})[suffix.group(1) if suffix else "EN"] = path
    chosen: dict[int, Path] = {}
    for phase, variants in found.items():
        for candidate in wanted:
            if candidate in variants:
                chosen[phase] = variants[candidate]
                break
        else:
            chosen[phase] = variants[sorted(variants)[0]]
    return chosen


def rows_by_id(text: str, wanted: set[str]) -> dict[str, tuple[list[str], int]]:
    """The first decision-table row for each wanted identifier: (cells, header width)."""
    found: dict[str, tuple[list[str], int]] = {}
    for table in dq.tables(text):
        for row in table.rows:
            if (row.identifier in wanted and row.identifier not in found and row.wellformed
                    and len(table.header) >= 4):
                found[row.identifier] = (row.cells, len(table.header))
    return found


def own_rows(output: Path, entries: list[dict[str, Any]], wanted: set[str],
             language: str | None = None) -> dict[str, tuple[list[str], int]]:
    """Each wanted identifier's row, read from the document of the phase that allocated it.

    A later phase's carried-forward table mentions it too, in a shape that is not this one.
    """
    phases = {str(e["id"]): e.get("phase") for e in entries}
    rows: dict[str, tuple[list[str], int]] = {}
    for phase, path in sorted(phase_documents(output, language).items()):
        for identifier, found in rows_by_id(read_text(path), wanted).items():
            if phases.get(identifier) == phase:
                rows.setdefault(identifier, found)
    return rows


def closed_markers() -> tuple[str, ...]:
    """The phrases a row opens with when it says it is closed, in every output language."""
    try:
        import yaml

        spec = yaml.safe_load((Path(__file__).resolve().parents[1] / "specifications"
                               / "language-support.yaml").read_text(encoding="utf-8")) or {}
        languages = spec["human_languages"]["conformance_signals"]["closed_item"]
    except Exception:
        return ()
    return tuple(phrase for phrases in languages.values() for phrase in phrases)


def item_texts(output: Path, entries: list[dict[str, Any]], language: str | None = None,
               markers: tuple[str, ...] = ()) -> dict[str, dict[str, str]]:
    """What each open Q, UK and risk says in its phase document, for the list that asks it.

    The register holds a title; the person being asked needs the sentence, why it matters
    and what would settle it, and those are in the document's row. A row that opens by
    saying it is closed is skipped: it was rewritten when it closed and says nothing about
    the question any more.
    """
    by_id = {str(e["id"]): e for e in entries if e.get("id")}
    wanted = {i for i, e in by_id.items()
              if e.get("namespace") in ("Q", "UK-", *dq.RISK_NAMESPACES) and dq.is_open(e)}
    texts: dict[str, dict[str, str]] = {}
    for identifier, (cells, _width) in own_rows(output, entries, wanted, language).items():
        if by_id[identifier]["namespace"] in dq.RISK_NAMESPACES:
            # A risk's row says why it matters and what it recommends; the recommendation is
            # the default its disposition proceeds on, so the decider is shown it verbatim.
            risk = dq.risk_cells(cells, identifier)
            if risk is not None:
                texts[identifier] = {"why": risk["detail"], "mitigation": risk["mitigation"]}
            continue
        if markers and dq.starts_closed(cells[1], markers):
            continue
        if by_id[identifier]["namespace"] == "Q":
            blocks = cells[2] if len(cells) > 2 else ""
            texts[identifier] = {"ask": cells[1],
                                 "blocks_prose": "" if dq.cell_blocks(blocks) is not None else blocks}
        else:
            texts[identifier] = {"ask": cells[1], "why": cells[2] if len(cells) > 2 else "",
                                 "settle": cells[3] if len(cells) > 3 else ""}
    return texts


def assumption_rows(output: Path, entries: list[dict[str, Any]], wanted: set[str],
                    language: str | None = None) -> dict[str, tuple[str, str]]:
    """Each wanted assumption's (text, "If wrong") cells, from the phase that allocated it.

    The Assumptions table has three columns where the decision tables have four or more, so
    `rows_by_id` does not see it. A later phase's carried-forward table names the same ids in
    a shape of its own and is not read.
    """
    phases = {str(e["id"]): e.get("phase") for e in entries}
    found: dict[str, tuple[str, str]] = {}
    for phase, path in sorted(phase_documents(output, language).items()):
        for table in dq.tables(read_text(path)):
            if len(table.header) != 3:
                continue
            for row in table.rows:
                if (row.identifier in wanted and row.wellformed and phases.get(row.identifier) == phase
                        and row.identifier not in found):
                    found[row.identifier] = (row.cells[1], row.cells[2])
    return found
