#!/usr/bin/env python3
"""Give a workspace's open questions the `needs` block the decision queue reads (A75).

A workspace published before the block existed has its owners, blocks and defaults as
prose in the phase documents, and a register that knows none of them. This reads the
documents, proposes what it can derive, and writes nothing into the register until a
person has looked at the proposal:

    $ak backfill-needs --app-root P             propose (and draft parties.yaml first)
    $ak backfill-needs --app-root P --apply     validate the reviewed proposal and write it

Two steps because most of a `needs` block is a judgement. The party is in the document's
Owner cell, but which department a name belongs to is not. What an item blocks is in
prose, and which identifier that prose means is a reading. Which assumption a question
proceeds on is a link nobody wrote. So the proposal marks every field it could not read
`UNDECIDED`, and `--apply` refuses a proposal that still carries one: a half-filled block that
validates is a field that does nothing while looking like one that works.

It also lists the items a document already calls answered while the register still has
them open - A06's Q106, UK-S03 and Q120 - under `close:`, each waiting for the evidence
id that answers it. Closing an item is the same kind of act and gets the same review.

The register is rewritten in the format it was written in (indent 1, sorted keys, final
newline), so a backfill is a diff of the `needs` blocks and nothing else. The previous
file is kept under `.ak/backups/`.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import decision_queue as dq  # noqa: E402
import workspace as workspace_contract  # noqa: E402

UNDECIDED = "UNDECIDED"
PROPOSAL = "needs-proposal.yaml"
APPLIED = "needs-proposal.applied.yaml"
LANGUAGE_SUFFIX = re.compile(r"_([A-Z]{2})\.md$")
PHASE_FILE = re.compile(r"Phase([1-6])_", re.IGNORECASE)


class Problem(Exception):
    """Something that stops the run and is worth saying in one line."""


def register_path(output: Path) -> Path:
    found = [m for where in (".", "registers") for m in sorted((output / where).glob("*_Identifiers.json"))]
    if len(found) != 1:
        raise Problem(f"expected one *_Identifiers.json under {output}, found {len(found)}")
    return found[0]


def evidence_ids(output: Path) -> set[str] | None:
    found = [m for where in (".", "registers") for m in sorted((output / where).glob("*_Evidence.json"))]
    if len(found) != 1:
        return None
    try:
        items = json.loads(found[0].read_text(encoding="utf-8-sig")).get("items") or []
    except (OSError, json.JSONDecodeError):
        return None
    return {str(i["id"]) for i in items if isinstance(i, dict) and i.get("id")}


def errata_ids(output: Path) -> set[str]:
    found = [m for where in (".", "registers") for m in sorted((output / where).glob("*_Errata.json"))]
    if len(found) != 1:
        return set()
    try:
        entries = json.loads(found[0].read_text(encoding="utf-8-sig")).get("entries") or []
    except (OSError, json.JSONDecodeError):
        return set()
    return {str(e["id"]) for e in entries if isinstance(e, dict) and e.get("id")}


def phase_documents(output: Path) -> dict[int, Path]:
    """One document per phase, the EN one when there are several."""
    chosen: dict[int, Path] = {}
    for path in sorted(output.glob("*.md")):
        match = PHASE_FILE.search(path.name)
        if not match:
            continue
        phase = int(match.group(1))
        suffix = LANGUAGE_SUFFIX.search(path.name)
        if phase not in chosen or (suffix and suffix.group(1) == "EN"):
            chosen[phase] = path
    return chosen


def closed_markers() -> tuple[str, ...]:
    try:
        import yaml

        spec = yaml.safe_load((PACKAGE / "specifications" / "language-support.yaml")
                              .read_text(encoding="utf-8")) or {}
        langs = spec["human_languages"]["conformance_signals"]["closed_item"]
    except Exception:
        return ()
    return tuple(p for phrases in langs.values() for p in phrases)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def rows_by_id(text: str, wanted: set[str]) -> dict[str, tuple[list[str], int]]:
    """The first decision-table row for each wanted identifier: (cells, header width)."""
    found: dict[str, tuple[list[str], int]] = {}
    for table in dq.tables(text):
        for row in table.rows:
            if row.identifier in wanted and row.identifier not in found and row.wellformed \
                    and len(table.header) >= 4:
                found[row.identifier] = (row.cells, len(table.header))
    return found


def yaml_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def open_asks(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in entries if e.get("namespace") in ("Q", "UK-") and dq.is_open(e)
            and not isinstance(e.get("needs"), dict)]


def own_rows(output: Path, entries: list[dict[str, Any]],
             wanted: set[str]) -> dict[str, tuple[list[str], int]]:
    """Each wanted identifier's decision-table row, read from the document of the phase
    that allocated it. A later phase's carried-forward table mentions it too, in a shape
    that is not this one."""
    phases = {str(e["id"]): e.get("phase") for e in entries}
    rows: dict[str, tuple[list[str], int]] = {}
    for phase, path in sorted(phase_documents(output).items()):
        for identifier, found in rows_by_id(read_text(path), wanted).items():
            if phases.get(identifier) == phase:
                rows.setdefault(identifier, found)
    return rows


def party_cell_of(entry: dict[str, Any], cells: list[str]) -> str:
    index = 3 if entry["namespace"] == "Q" else 4
    return cells[index] if len(cells) > index else ""


def draft_parties(output: Path, entries: list[dict[str, Any]]) -> str:
    """One entry per spelling found, because merging spellings is a decision."""
    markers = closed_markers()
    asks = open_asks(entries)
    rows = own_rows(output, entries, {str(e["id"]) for e in asks})
    spellings: Counter[str] = Counter()
    for entry in asks:
        cells, _width = rows.get(str(entry["id"]), ([], 0))
        # A row the document calls closed was rewritten when it closed, and its party cell
        # may hold an evidence id (A06's Q120). That is not a spelling of anybody.
        if not cells or (markers and dq.starts_closed(cells[1], markers)):
            continue
        cell = party_cell_of(entry, cells)
        if dq.is_blank_cell(cell):
            continue
        for part in dq.split_parties(cell):
            name = re.sub(r"[`*]", "", part).strip()
            if name and not name.startswith("["):
                spellings[name] += 1
    lines = [
        "# Who can answer, under one canonical name each. Written by `$ak backfill-needs`, edited by a person.",
        "#",
        "# This is a DRAFT: one entry per spelling found in the open questions' owner cells, with how often",
        "# it appears. Spellings that name one party are merged by moving them under `aliases`; people",
        "# who sit inside a department go under its `people`. The `decider` needs no entry. It is the",
        "# person building the new system, and every disposition and scope decision is theirs.",
        "parties:",
    ]
    for name, count in spellings.most_common():
        lines += [f"  {yaml_value(name)}:   # {count} cell(s)",
                  "    aliases: []",
                  "    people: []",
                  f"    source: {yaml_value('spelling found in the phase documents')}"]
    if not spellings:
        lines.append("  {}")
    return "\n".join(lines) + "\n"


def propose(space: workspace_contract.Workspace) -> tuple[str, dict[str, int]]:
    output = space.output_dir()
    register = json.loads(register_path(output).read_text(encoding="utf-8-sig"))
    entries = register["entries"]
    parties = dq.load_parties(space.input_dir("decisions") / "parties.yaml")
    if parties is None:
        raise Problem("no parties.yaml")
    markers = closed_markers()
    asks = open_asks(entries)
    rows = own_rows(output, entries, {str(e["id"]) for e in asks})

    counts = {"derived": 0, "party_todo": 0, "blocks_todo": 0, "to_close": 0}
    needs_lines: list[str] = []
    close_lines: list[str] = []
    for entry in asks:
        eid = str(entry["id"])
        cells, width = rows.get(eid, ([], 0))
        title = str(entry.get("title") or "")[:90]
        is_q = entry["namespace"] == "Q"
        if cells and dq.is_open(entry) and markers and dq.starts_closed(cells[1], markers):
            counts["to_close"] += 1
            cited = sorted(set(re.findall(r"\[([A-Z0-9]+-P[1-6]-[A-Z_]+-\d{3})\]", " ".join(cells))))
            close_lines.append(
                f"  {eid}: {UNDECIDED}   # the document opens {json.dumps(cells[1][:70], ensure_ascii=False)}"
                + (f"; it cites {', '.join(cited)}" if cited else "")
                + ". The evidence id that answers it:")
            continue
        party_cell = party_cell_of(entry, cells)
        resolved, unresolved = parties.resolve(party_cell) if party_cell else ([], [])
        block_cell = cells[2] if is_q and len(cells) > 2 else ""
        blocks = dq.cell_blocks(block_cell) if block_cell else None
        needs_lines.append(f"  {eid}:   # {title}")
        needs_lines.append("    kind: FACT")
        if resolved and not unresolved:
            needs_lines.append(f"    party: {yaml_value(resolved[0])}")
            if len(resolved) > 1:
                needs_lines.append(f"    also: {yaml_value(resolved[1:])}")
            counts["derived"] += 1
        else:
            counts["party_todo"] += 1
            needs_lines.append(f"    party: {UNDECIDED}   # the document says "
                               f"{json.dumps(party_cell, ensure_ascii=False)}")
        if is_q:
            if blocks:
                needs_lines.append(f"    blocks: {yaml_value(sorted(blocks))}")
            else:
                counts["blocks_todo"] += 1
                needs_lines.append(f"    blocks: {UNDECIDED}   # the document says "
                                   f"{json.dumps(block_cell[:100], ensure_ascii=False)}")
            needs_lines.append(f"    default: {UNDECIDED}   # an AS- id, or null when the question should block what it names")
            needs_lines.append(f"    gap: null   # the UK- this asks about, if one does")
        else:
            counts["blocks_todo"] += 1
            needs_lines.append(f"    blocks: {UNDECIDED}   # an unknown nobody asks about needs its own; delete this entry if a Q's `gap` names it")
    header = [
        f"# Proposed `needs` blocks for {register.get('app_id', '?')}. Written by `$ak backfill-needs`; nothing has been applied.",
        "#",
        "# Edit, then run `$ak backfill-needs --app-root <PATH> --apply`.",
        f"#   {UNDECIDED}   could not be derived from the documents. --apply refuses a proposal that still has one.",
        "#   a comment is what the document said, so you can see what was read and what was not.",
        "#",
        "# `gap` links a question to the unknown it asks about. Both are kept on purpose (the unknown is the",
        "# gap in the document, the question is the action). A UK named by a `gap` needs no block of its own;",
        "# delete its entry below.",
        "needs:",
    ]
    body = header + (needs_lines or ["  {}"]) + ["", "# Items a document already calls closed while the register has them open.",
                                                  "close:"] + (close_lines or ["  {}"])
    return "\n".join(body) + "\n", counts


def contains_todo(node: Any, path: str = "") -> list[str]:
    where: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            where += contains_todo(value, f"{path}/{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            where += contains_todo(value, f"{path}[{index}]")
    elif node == UNDECIDED:
        where.append(path)
    return where


def atomic_write(path: Path, text: str) -> None:
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    os.replace(temporary, path)


def apply(space: workspace_contract.Workspace, proposal_path: Path, dry_run: bool) -> int:
    import yaml

    output = space.output_dir()
    path = register_path(output)
    register = json.loads(path.read_text(encoding="utf-8-sig"))
    entries = copy.deepcopy(register["entries"])
    by_id = {str(e["id"]): e for e in entries}
    parties = dq.load_parties(space.input_dir("decisions") / "parties.yaml")
    proposal = yaml.safe_load(read_text(proposal_path)) or {}
    problems: list[str] = []

    pending = contains_todo(proposal)
    if pending:
        problems.append(f"{len(pending)} field(s) still say {UNDECIDED}: {pending[:6]}")

    skipped = 0
    for eid, block in (proposal.get("needs") or {}).items():
        entry = by_id.get(str(eid))
        if entry is None:
            problems.append(f"{eid}: not in the register")
        elif isinstance(entry.get("needs"), dict):
            skipped += 1
        else:
            entry["needs"] = block

    known_evidence = evidence_ids(output)
    known_errata = errata_ids(output)
    closed = 0
    for eid, evidence in (proposal.get("close") or {}).items():
        entry = by_id.get(str(eid))
        if entry is None:
            problems.append(f"{eid}: not in the register")
        elif not dq.is_open(entry):
            continue
        elif not isinstance(evidence, str) or evidence == UNDECIDED:
            problems.append(f"{eid}: close needs the evidence id that answers it")
        elif known_evidence is not None and evidence not in known_evidence:
            hint = " (that is an errata entry; resolved_by names evidence)" if evidence in known_errata else ""
            problems.append(f"{eid}: {evidence} is not in the evidence register{hint}")
        else:
            entry["resolved_by"] = evidence
            closed += 1

    problems += dq.validate_register(entries, parties)
    if parties is None:
        problems.append("there is no input/decisions/parties.yaml")
    elif parties.problems:
        problems += [f"parties.yaml: {p}" for p in parties.problems]

    if problems:
        print(f"nothing written: {len(problems)} problem(s)")
        for problem in problems[:40]:
            print(f"  {problem}")
        return 1
    register["entries"] = entries
    text = json.dumps(register, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    added = len(proposal.get("needs") or {}) - skipped
    print(f"{added} needs block(s) to write, {closed} item(s) to close, {skipped} already had one")
    if dry_run:
        print("dry run: nothing written")
        return 0
    backups = space.owned("backups")
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = backups / f"{path.stem}.{stamp}.json"
    backup.write_bytes(path.read_bytes())
    atomic_write(path, text)
    print(f"wrote {path}; the previous file is {backup}")
    applied = proposal_path.with_name(APPLIED)
    os.replace(proposal_path, applied)
    print(f"proposal kept as {applied}")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--apply", action="store_true",
                        help="Write the reviewed proposal into the register. Without it the command only proposes.")
    parser.add_argument("--dry-run", action="store_true", help="Say what would be written; write nothing.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite an existing proposal. Refused by default: it may hold a reviewer's edits.")
    args = parser.parse_args()

    space = workspace_contract.Workspace(args.app_root)
    decisions = space.input_dir("decisions")
    proposal_path = decisions / PROPOSAL
    try:
        if args.apply:
            if not proposal_path.is_file():
                raise Problem(f"no {proposal_path}; run without --apply first")
            return apply(space, proposal_path, args.dry_run)

        output = space.output_dir()
        parties_path = decisions / "parties.yaml"
        if not parties_path.is_file():
            register = json.loads(register_path(output).read_text(encoding="utf-8-sig"))
            draft = draft_parties(output, register["entries"])
            if args.dry_run:
                print(draft)
                return 0
            decisions.mkdir(parents=True, exist_ok=True)
            parties_path.write_text(draft, encoding="utf-8", newline="\n")
            print(f"wrote a DRAFT {parties_path}")
            print("Merge the spellings that name one party, then run this command again.")
            return 0
        if proposal_path.exists() and not args.force and not args.dry_run:
            raise Problem(f"{proposal_path} exists and may hold edits; use --force to replace it, or --apply")
        text, counts = propose(space)
        print(f"{counts['derived']} party(ies) derived, {counts['party_todo']} to decide, "
              f"{counts['blocks_todo']} blocks to name, {counts['to_close']} item(s) the documents call closed")
        if args.dry_run:
            print(text)
            return 0
        proposal_path.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {proposal_path}")
        print("Edit every UNDECIDED, then run again with --apply.")
        return 0
    except Problem as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
