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
them open - say Q106, UK-S03 and Q120 - under `close:`, each waiting for the evidence
id that answers it. Closing an item is the same kind of act and gets the same review.

Risks join in slice 3. Each open risk is proposed as a DISPOSITION for the decider,
proceeding on its own Mitigation, waiting on the open questions that Mitigation names
(a superseded one followed to the item that replaced it), and with its `class` left
`UNDECIDED`: whether a defect is technical or a behaviour somebody relies on is the
judgement standing policy settles by, and a reading of a title is not that judgement. The
first run also drafts `policy.yaml` beside `parties.yaml`, every rule in it proposed and
none in force until the decider names themself and a date.

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
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import decision_queue as dq  # noqa: E402
import decision_register as dr  # noqa: E402
import workspace as workspace_contract  # noqa: E402

UNDECIDED = "UNDECIDED"
PROPOSAL = "needs-proposal.yaml"
APPLIED = "needs-proposal.applied.yaml"
LANGUAGE_SUFFIX = re.compile(r"_([A-Z]{2})\.md$")
PHASE_FILE = re.compile(r"Phase([1-6])_", re.IGNORECASE)


Problem = dr.RegisterProblem


def yaml_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def open_asks(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Open Q and UK entries that still need a block. An unknown a question already asks about
    (`gap`) needs none: proposing one again on every later run is noise a reviewer deletes."""
    asked = {str(e["needs"]["gap"]) for e in entries
             if isinstance(e.get("needs"), dict) and e["needs"].get("gap")}
    return [e for e in entries if e.get("namespace") in ("Q", "UK-") and dq.is_open(e)
            and not isinstance(e.get("needs"), dict)
            and not (e.get("namespace") == "UK-" and str(e["id"]) in asked)]


def open_risks(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [e for e in entries if e.get("namespace") in dq.RISK_NAMESPACES and dq.is_open(e)
            and not isinstance(e.get("needs"), dict)]


WHOLE_SPAN = re.compile(r"`([^`\n]+)`")


def named_in(text: str) -> list[str]:
    """Identifiers a Mitigation names, in prose or as a whole code span, each once.

    `find_identifiers` skips code spans, because `d31` in backticks is a column (A52). A
    Mitigation often cites an identifier the same way, "Establish whether the button is
    used (`Q12`)", and such a risk was proposed with nothing to wait on. A span that is
    one identifier and nothing else is a citation.
    The caller keeps only open Q and UK- entries in the register, so a column that merely
    looks like an identifier still names nothing.
    """
    found = dq.find_identifiers(text)
    for match in WHOLE_SPAN.finditer(text):
        token = match.group(1).strip()
        if dq.is_identifier(token) and token not in found:
            found.append(token)
    return found


def waits_on(text: str, own: str, entries: list[dict[str, Any]]) -> tuple[list[str], list[str]]:
    """(open items the text names, notes on the ones it names that are closed).

    Say RA-02 names Q108 and UK-S04. Q108 was superseded by Q103 and UK-S04 was answered,
    so what RA-02 waits on is Q103 and nothing else. An unknown a question asks about is
    reached through that question, which is the one a person is asked.
    """
    by_id = {str(e["id"]): e for e in entries if e.get("id")}
    asked_by = {str(e["needs"]["gap"]): str(e["id"]) for e in entries
                if isinstance(e.get("needs"), dict) and e["needs"].get("gap") and dq.is_open(e)}
    found: list[str] = []
    notes: list[str] = []
    for named in named_in(text):
        current, seen = named, set()
        entry = by_id.get(current)
        if entry is None or entry.get("namespace") not in ("Q", "UK-") or current == own:
            continue
        while entry is not None and entry.get("superseded_by") and current not in seen:
            seen.add(current)
            current = str(entry["superseded_by"])
            entry = by_id.get(current)
        if entry is None:
            notes.append(f"{named} leads to {current}, which is not in the register")
            continue
        if not dq.is_open(entry):
            notes.append(f"{named} is closed by {entry.get('resolved_by')}")
            continue
        if current != named:
            notes.append(f"{named} is superseded by {current}")
        current = asked_by.get(current, current)
        if current not in found:
            found.append(current)
    return found, notes


POLICY = "policy.yaml"


def draft_policy() -> str:
    """The four rules of the design's section 5, every one proposed and none in force."""
    return "\n".join([
        "# Standing policy: a rule asked once that settles a class of risks (decision queue, design section 5).",
        "# Written by `$ak backfill-needs` as a PROPOSAL, for the decider to edit.",
        "#",
        "# A rule settles nothing until it names who decided it and when (`decided_by`, `decided_on`), for the",
        "# reason every record in input/target-intent/ names both: a decision nobody can be taken back to cannot",
        "# be revisited when it turns out to cost something. Every risk a rule settles is still listed in the",
        "# question list, as settled by it, so a rule never makes a decision disappear.",
        "#",
        "#   class        technical | data | retired | behaviour, matched against each risk's needs.class",
        "#   disposition  fix (do what the risk's Mitigation says) | preserve | drop | defer",
        "#                | ask (put each risk of the class to the decider, with its Mitigation as the default)",
        "policy:",
        "  - id: P-1",
        "    class: technical",
        "    disposition: fix",
        "    decided_by: null",
        "    decided_on: null",
        "    note: \"A defect with no business behaviour behind it: missing keys, no transaction, a silent failure.\"",
        "  - id: P-2",
        "    class: retired",
        "    disposition: drop",
        "    decided_by: null",
        "    decided_on: null",
        "    note: \"Something nobody uses any more, such as a path to a device that no longer exists.\"",
        "  - id: P-3",
        "    class: data",
        "    disposition: fix",
        "    decided_by: null",
        "    decided_on: null",
        "    note: \"A defect in the data itself; its Mitigation says what is not migrated as data.\"",
        "  - id: P-4",
        "    class: behaviour",
        "    disposition: ask",
        "    decided_by: null",
        "    decided_on: null",
        "    note: \"Something an operator relies on, even when it is a defect. Asked one at a time (2026-10-01).\"",
    ]) + "\n"


def party_cell_of(entry: dict[str, Any], cells: list[str]) -> str:
    index = 3 if entry["namespace"] == "Q" else 4
    return cells[index] if len(cells) > index else ""


def draft_parties(output: Path, entries: list[dict[str, Any]]) -> str:
    """One entry per spelling found, because merging spellings is a decision."""
    markers = dr.closed_markers()
    asks = open_asks(entries)
    rows = dr.own_rows(output, entries, {str(e["id"]) for e in asks})
    spellings: Counter[str] = Counter()
    for entry in asks:
        cells, _width = rows.get(str(entry["id"]), ([], 0))
        # A row the document calls closed was rewritten when it closed, and its party cell
        # may hold an evidence id (a closed Q120 did). That is not a spelling of anybody.
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
    register = dr.read_identifiers(dr.register_path(output))
    entries = register["entries"]
    parties = dq.load_parties(space.input_dir("decisions") / "parties.yaml")
    if parties is None:
        raise Problem("no parties.yaml")
    markers = dr.closed_markers()
    asks = open_asks(entries)
    rows = dr.own_rows(output, entries, {str(e["id"]) for e in asks})

    counts = {"derived": 0, "party_todo": 0, "blocks_todo": 0, "to_close": 0,
              "risks": 0, "class_todo": 0, "assumptions": 0, "assumptions_todo": 0}
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

    risks = open_risks(entries)
    risk_rows = dr.own_rows(output, entries, {str(e["id"]) for e in risks})
    for entry in risks:
        eid = str(entry["id"])
        cells, _width = risk_rows.get(eid, ([], 0))
        row = dq.risk_cells(cells, eid) if cells else None
        mitigation = (row or {}).get("mitigation", "")
        counts["risks"] += 1
        counts["class_todo"] += 1
        severity = f" [{entry['severity']}]" if entry.get("severity") else ""
        needs_lines.append(f"  {eid}:   # {str(entry.get('title') or '')[:90]}{severity}")
        needs_lines.append("    kind: DISPOSITION")
        needs_lines.append(f"    party: {yaml_value(dq.DECIDER)}")
        if dq.has_mitigation(mitigation):
            needs_lines.append("    blocks: []   # a risk's disposition decides its own Mitigation")
            needs_lines.append(f"    default: {yaml_value(dq.MITIGATION)}   # "
                               f"{json.dumps(mitigation[:100], ensure_ascii=False)}")
        else:
            counts["blocks_todo"] += 1
            said = json.dumps(mitigation[:60], ensure_ascii=False) if row else "no row found"
            needs_lines.append(f"    blocks: {UNDECIDED}   # with no Mitigation to proceed on, name what waits on it")
            needs_lines.append(f"    default: null   # the row has no Mitigation ({said}), so it blocks")
        needs_lines.append(f"    class: {UNDECIDED}   # {' | '.join(dq.RISK_CLASSES)}: the key policy settles by")
        found, notes = waits_on(mitigation, eid, entries)
        note = f"   # {'; '.join(notes)}" if notes else ("   # named in its Mitigation" if found else "")
        needs_lines.append(f"    depends_on: {yaml_value(found)}{note}")
    wrong_lines: list[str] = []
    bare = {str(e["id"]) for e in entries if e.get("namespace") == "AS-" and dq.is_open(e)
            and dq.IF_WRONG not in e}
    said = dr.assumption_rows(output, entries, bare)
    for eid in sorted(bare):
        counts["assumptions"] += 1
        if eid in said:
            sentence = " ".join(said[eid][1].split())
            wrong_lines.append(f"  {eid}: {yaml_value(sentence)}")
        else:
            counts["assumptions_todo"] += 1
            wrong_lines.append(f"  {eid}: {UNDECIDED}   # no row in the Assumptions table of the phase that allocated it")
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
        "#",
        "# A risk is a DISPOSITION for the decider, proceeding on its own Mitigation. Its `class` decides which",
        "# rule of policy.yaml settles it: technical (no business behaviour behind it), data (the data itself),",
        "# retired (nobody uses it), behaviour (an operator relies on it, even when it is a defect).",
        "needs:",
    ]
    body = header + (needs_lines or ["  {}"]) + ["", "# Items a document already calls closed while the register has them open.",
                                                  "close:"] + (close_lines or ["  {}"]) + [
        "", "# What each assumption's own row says stops holding if it is wrong, copied as written. An answer",
        "# that contradicts the assumption is corrected by an errata entry that names what this sentence names.",
        "if_wrong:"] + (wrong_lines or ["  {}"])
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


def applied_path(proposal_path: Path) -> Path:
    """Where a reviewed proposal is kept once written: never over an earlier one.

    One workspace was backfilled twice - the questions in slice 1, the risks in slice 3 - and the second
    rename replaced the first reviewed proposal, which is the only record of what was read
    and what a person decided.
    """
    first = proposal_path.with_name(APPLIED)
    if not first.exists():
        return first
    counter = 2
    while (candidate := first.with_name(f"needs-proposal.applied.{counter}.yaml")).exists():
        counter += 1
    return candidate


def apply(space: workspace_contract.Workspace, proposal_path: Path, dry_run: bool) -> int:
    import yaml

    output = space.output_dir()
    path = dr.register_path(output)
    register = dr.read_identifiers(path)
    entries = copy.deepcopy(register["entries"])
    by_id = {str(e["id"]): e for e in entries}
    parties = dq.load_parties(space.input_dir("decisions") / "parties.yaml")
    proposal = yaml.safe_load(dr.read_text(proposal_path)) or {}
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

    written = 0
    for eid, text in (proposal.get("if_wrong") or {}).items():
        entry = by_id.get(str(eid))
        if entry is None or entry.get("namespace") != "AS-":
            problems.append(f"{eid}: `if_wrong` is for an assumption in the register")
        elif dq.IF_WRONG in entry:
            continue
        elif not isinstance(text, str) or not text.strip():
            problems.append(f"{eid}: `if_wrong` is the sentence saying what breaks if it is wrong")
        else:
            entry[dq.IF_WRONG] = text.strip()
            written += 1

    known_evidence = dr.evidence_index(output)
    known_errata = dr.errata_ids(output)
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

    problems += dq.validate_register(entries, parties, errata=dr.errata_entries(output))
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
    added = len(proposal.get("needs") or {}) - skipped
    print(f"{added} needs block(s) to write, {closed} item(s) to close, {skipped} already had one, "
          f"{written} assumption(s) to give an `if_wrong`")
    if dry_run:
        print("dry run: nothing written")
        return 0
    backup = dr.write_register(space, path, register)
    print(f"wrote {path}; the previous file is {backup}")
    applied = applied_path(proposal_path)
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
            register = dr.read_identifiers(dr.register_path(output))
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
        policy_path = decisions / POLICY
        if not policy_path.is_file():
            if args.dry_run:
                print(f"would draft {policy_path}")
            else:
                policy_path.write_text(draft_policy(), encoding="utf-8", newline="\n")
                print(f"wrote a DRAFT {policy_path}: every rule proposed, none in force")
        text, counts = propose(space)
        print(f"{counts['derived']} party(ies) derived, {counts['party_todo']} to decide, "
              f"{counts['blocks_todo']} blocks to name, {counts['to_close']} item(s) the documents call closed, "
              f"{counts['risks']} risk(s) proposed with {counts['class_todo']} class(es) to decide, "
              f"{counts['assumptions']} assumption(s) lacking `if_wrong` ({counts['assumptions_todo']} with no row to copy it from)")
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
