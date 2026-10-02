#!/usr/bin/env python3
"""Build the decision queue and the question list from the identifier register (A75, slice 2).

    $ak decisions --app-root P                  write {APP}_QuestionList.md and {APP}_DecisionQueue.json
    $ak decisions --app-root P --dry-run        say what they would hold, write nothing
    $ak decisions --app-root P --party 常温庫   print one party's agenda, ready to paste, write nothing
    $ak decisions --app-root P --link Q5=5      record that Q5 was posted as Q&A 5, then build

The register already says who can answer each open item, what waits on it, and what the
pipeline proceeds on meanwhile (slice 1). This puts that in the order a person works in:
one agenda per party, dependencies first, what stops work before what merely risks rework,
and the three things the machine has already done for them - items closed by evidence
already in hand, items already with the customer, items the customer has answered and
nobody has recorded.

Two outputs. `{APP}_QuestionList.md` is read by a person: the developer relaying questions
and the party each agenda is addressed to. `{APP}_DecisionQueue.json` is read by agents and
sits beside the other registers. Neither carries a date, so the same register gives the
same bytes and a change to either is a change to the register.

Reads the Q&A register fresh rather than the record `$ak interviews` stored, because the
record is a snapshot and the customer's register is not: A06's was five rows when the CSV
beside it had six.

Writes nothing but its own two outputs - and the register itself only for `--link`, with the
previous file kept under `.ak/backups/`. It will not overwrite a QuestionList.md it did not
write: A05's was written by hand with its own question numbers, which is how A12 happened.

Exit 0 when the register is routable, 1 when it is not (an open question with no `needs`, a
reference that points nowhere), 2 when the command cannot run.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import check_interview_register as interview_register  # noqa: E402
import decision_agenda as da  # noqa: E402
import decision_queue as dq  # noqa: E402
import decision_register as dr  # noqa: E402
import workspace as workspace_contract  # noqa: E402

Problem = dr.RegisterProblem


def parse_links(specs: list[str]) -> dict[str, list[int]]:
    links: dict[str, list[int]] = {}
    for spec in specs:
        item, separator, numbers = spec.partition("=")
        if not separator or not item.strip() or not numbers.strip():
            raise Problem(f"--link wants ITEM=ID[,ID], for example Q5=5; got {spec!r}")
        try:
            wanted = [int(n) for n in re.split(r"[,\s]+", numbers.strip()) if n]
        except ValueError:
            raise Problem(f"--link {spec!r}: the Q&A ids are the register's numbers") from None
        links.setdefault(item.strip(), []).extend(wanted)
    return links


def apply_links(entries: list[dict[str, Any]], links: dict[str, list[int]],
                interviews: dict[str, Any], parties: dq.Parties | None) -> list[str]:
    """Set `needs.qa` in place. Returns what changed; raises on anything that cannot be linked."""
    by_id = {str(e["id"]): e for e in entries if e.get("id")}
    ids = set(by_id)
    known = {str(r.get("id")) for r in interviews.get("register") or []}
    changed: list[str] = []
    for item, numbers in links.items():
        entry = by_id.get(item)
        if entry is None:
            raise Problem(f"{item}: not in the register")
        if not isinstance(entry.get("needs"), dict):
            raise Problem(f"{item}: has no `needs`, so there is nothing to link a Q&A to "
                          "(`$ak backfill-needs`)")
        missing = [n for n in numbers if known and str(n) not in known]
        if missing:
            raise Problem(f"{item}: Q&A {missing} is not in the Q&A register, so the link would "
                          "point at nothing")
        merged = sorted(set(entry["needs"].get("qa") or []) | set(numbers))
        if merged != list(entry["needs"].get("qa") or []):
            entry["needs"]["qa"] = merged
            changed.append(f"{item} -> Q&A {merged}")
        found = dq.validate_needs(entry, ids, parties)
        if found:
            raise Problem("; ".join(found))
    return changed


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--language", help="Which phase documents the question text is read from "
                                           "(EN, JA, VI); a phase not written in it falls back to EN.")
    parser.add_argument("--party", help="Print only this party's agenda and write nothing.")
    parser.add_argument("--link", action="append", default=[], metavar="ITEM=ID[,ID]",
                        help="Record that an item was posted as these Q&A register ids.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace-handwritten", action="store_true",
                        help="Overwrite a QuestionList.md this command did not write.")
    args = parser.parse_args()

    space = workspace_contract.Workspace(args.app_root)
    try:
        output = space.output_dir()
        register_file = dr.register_path(output)
        register = dr.read_register(register_file)
        entries = register["entries"]
        app = str(register.get("app_id") or "")
        parties = dq.load_parties(space.input_dir("decisions") / "parties.yaml")
        interviews = interview_register.observe(space)

        if args.link:
            changed = apply_links(entries, parse_links(args.link), interviews, parties)
            for line in changed or ["nothing to change: every link was already recorded"]:
                print(f"link: {line}")
            if changed and not args.dry_run:
                backup = dr.write_register(space, register_file, register)
                print(f"wrote {register_file}; the previous file is {backup}")

        problems = dq.validate_register(entries, parties)
        if parties is None and any(e.get("namespace") in ("Q", "UK-") and dq.is_open(e) for e in entries):
            problems.append("there is no input/decisions/parties.yaml, so no party can be checked")
        elif parties is not None:
            problems += [f"parties.yaml: {p}" for p in parties.problems]

        queue = da.build_queue(entries, parties, evidence=dr.evidence_index(output),
                               interviews=interviews, app_id=app)
        texts = dr.item_texts(output, entries, args.language, dr.closed_markers())

        if args.party:
            name = (parties.lookup(args.party) if parties else None) or args.party
            sys.stdout.write(da.render_markdown(queue, parties=parties, texts=texts,
                                                source=register_file.name, only=name))
            return 0

        markdown = da.render_markdown(queue, parties=parties, texts=texts, source=register_file.name)
        document = da.render_json(queue)
        language = (args.language or "EN").upper()
        list_path = output / f"{app}_QuestionList{'' if language == 'EN' else '_' + language}.md"
        queue_path = register_file.parent / f"{app}_DecisionQueue.json"

        if (list_path.exists() and not dr.read_text(list_path).startswith(da.GENERATED)
                and not args.replace_handwritten):
            raise Problem(f"{list_path.name} exists and this command did not write it; move it "
                          "aside, or pass --replace-handwritten")

        c = queue["counts"]
        print(f"{c['open']} open item(s): {c['blocking']} blocking, {c['proceeding_on_default']} "
              f"proceeding on a default, {c['with_customer']} with the customer, "
              f"{c['answered_not_recorded']} answered and not recorded")
        closed = c["closed"]
        print(f"{closed['total']} closed: {closed['by_person']} by a person, {closed['by_bundle']} by the "
              f"bundle, {closed['by_decision']} by a decision, {closed['superseded']} superseded")
        for party in queue["party_order"]:
            row = c["by_party"][party]
            print(f"  {party}: {row['to_ask_now']} to ask ({row['blocking']} blocking), "
                  f"{row['open'] - row['to_ask_now']} already moving")
        if queue["untracked_qa"]:
            print(f"{len(queue['untracked_qa'])} Q&A open with the customer in no item: "
                  + ", ".join(q["id"] for q in queue["untracked_qa"]))
        for problem in problems + queue["problems"]:
            print(f"  PROBLEM {problem}")

        if args.dry_run:
            print(f"dry run: would write {list_path} and {queue_path}")
        else:
            for path, text in ((list_path, markdown), (queue_path, document)):
                same = path.is_file() and dr.read_text(path) == text
                if not same:
                    dr.atomic_write(path, text)
                print(f"{'unchanged' if same else 'wrote'} {path}")
        return 1 if problems or queue["problems"] else 0
    except Problem as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
