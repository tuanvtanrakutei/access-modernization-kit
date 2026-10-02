#!/usr/bin/env python3
"""Build the decision queue and the question list from the identifier register (A75, slice 2).

    $ak decisions --app-root P                  write {APP}_QuestionList.md and {APP}_DecisionQueue.json
    $ak decisions --app-root P --dry-run        say what they would hold, write nothing
    $ak decisions --app-root P --party 常温庫   print one party's agenda, ready to paste, write nothing
    $ak decisions --app-root P --link Q5=5      record that Q5 was posted as Q&A 5, then build
    $ak decisions --app-root P --decide --by N  put the decider's open dispositions to them,
                                                record the answers, then build

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

Standing policy (`input/decisions/policy.yaml`, slice 3) is applied as the queue is built: a
risk whose class a decided rule covers is settled by it, leaves every agenda, and is listed
under the rule. `--decide` is the decider's turn for what policy leaves: `ok` accepts every
default, `N=<choice>` overrides one. Each answer is a row of a TARGET_INTENT record written to
`input/target-intent/` and an evidence item citing it, and the item is closed against that
evidence - an answer is evidence, never queue text.

Writes nothing but its own two outputs - the register only for `--link` and `--decide`, and
the evidence register and a target-intent record only for `--decide`, with every previous
register kept under `.ak/backups/`. It will not overwrite a QuestionList.md it did not write:
A05's was written by hand with its own question numbers, which is how A12 happened.

Exit 0 when the register is routable, 1 when it is not (an open question with no `needs`, a
reference that points nowhere), 2 when the command cannot run.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import check_interview_register as interview_register  # noqa: E402
import decision_agenda as da  # noqa: E402
import decision_batch as batch  # noqa: E402
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


def read_answers() -> str:
    try:
        return input("answers> ")
    except EOFError:
        return ""


def _schema_problems(made: list[dict[str, Any]]) -> list[str]:
    """What the new evidence items violate in the evidence schema; empty without jsonschema."""
    try:
        import jsonschema
    except ImportError:
        return []
    schema = json.loads((PACKAGE / "schemas" / "evidence.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(
        {"$schema": schema.get("$schema"), "$defs": schema["$defs"], "$ref": "#/$defs/evidenceItem"})
    return [f"{item['id']}: {error.message}" for item in made for error in validator.iter_errors(item)]


def decide(space: workspace_contract.Workspace, output: Path, register_file: Path,
           register: dict[str, Any], parties: dq.Parties | None, interviews: dict[str, Any],
           policy: dq.Policy | None, args: argparse.Namespace) -> bool:
    """The decider's batch. Returns True when the registers were written."""
    entries = register["entries"]
    app = str(register.get("app_id") or "")
    decided_by = (args.by or "").strip()
    if not decided_by:
        raise Problem("--decide needs --by NAME: a decision that names nobody cannot be taken "
                      "back to whoever made it")
    people = ((parties.parties.get(dq.DECIDER) if parties else None) or {}).get("people") or []
    if people and decided_by not in people:
        raise Problem(f"--by {decided_by!r} is not one of the decider's people in parties.yaml: "
                      + ", ".join(people))
    decided_on = args.on or date.today().isoformat()
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", decided_on):
        raise Problem(f"--on wants a date, YYYY-MM-DD; got {decided_on!r}")

    evidence_file = dr.evidence_path(output)
    evidence = dr.read_register(evidence_file)
    existing = list(evidence.get("items") or [])
    queue = da.build_queue(entries, parties, interviews=interviews, app_id=app, policy=policy,
                           evidence={str(i["id"]): i for i in existing if i.get("id")})
    texts = dr.item_texts(output, entries, args.language, dr.closed_markers())
    shown = batch.listed(queue)
    known = batch.decidable(queue)
    sys.stdout.write(batch.render_listing(shown, texts, others=len(known) - len(shown)))
    if not known:
        return False
    answers = args.answers if args.answers is not None else read_answers()
    try:
        decisions = batch.parse(answers, shown, known)
    except batch.AnswerProblem as problem:
        raise Problem(f"nothing recorded: {problem}") from None
    if not decisions:
        print("nothing decided")
        return False

    items = {i["id"]: i for i in queue["items"]}
    target = space.input_dir("target-intent")
    taken = {p.name for p in target.glob("*")} if target.is_dir() else set()
    record_path = target / batch.record_name(app, decided_on, taken)
    record_text = batch.record_markdown(app, decisions, items, texts, decided_by=decided_by,
                                        decided_on=decided_on, answers=answers)
    phases = dr.phase_documents(output)
    made = batch.evidence_items(
        app, decisions, items, texts, existing, decided_by=decided_by, decided_on=decided_on,
        created_at=datetime.now().astimezone().isoformat(timespec="seconds"),
        # Recorded after the newest phase published, as A06's later evidence was: TARGET-002
        # is P4 because Phase 4 recorded it. The phase in an id says when, not what about.
        phase=max(phases) if phases else 1,
        run_id=str((existing[-1] if existing else {}).get("run_id") or "decisions"),
        record_path=record_path.relative_to(space.root).as_posix(), record_text=record_text)
    problems = _schema_problems(made)
    if problems:
        raise Problem("nothing recorded: the evidence items would not validate: "
                      + "; ".join(problems[:3]))
    for item_id, choice in decisions.items():
        print(f"decided: {item_id} = {choice}")
    if args.dry_run:
        for evidence_item in made:
            print(f"would close: {evidence_item['attribution']['question_id']} -> {evidence_item['id']}")
        print(f"dry run: would write {record_path}, {len(made)} evidence item(s) and the register")
        return False
    for line in batch.close(entries, made):
        print(f"closes: {line}")
    target.mkdir(parents=True, exist_ok=True)
    with open(record_path, "x", encoding="utf-8", newline="\n") as handle:
        handle.write(record_text)
    print(f"wrote {record_path}")
    backup = dr.write_register(space, evidence_file, {**evidence, "items": existing + made})
    print(f"wrote {evidence_file}; the previous file is {backup}")
    backup = dr.write_register(space, register_file, register)
    print(f"wrote {register_file}; the previous file is {backup}")
    return True


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
    parser.add_argument("--decide", action="store_true",
                        help="Put the decider's open dispositions to them and record the answers.")
    parser.add_argument("--by", help="With --decide: who is deciding. Required.")
    parser.add_argument("--on", help="With --decide: the date decided, YYYY-MM-DD. Default today.")
    parser.add_argument("--answers", help="With --decide: the answers, instead of reading them "
                                          "from the terminal (`ok 3=preserve`).")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace-handwritten", action="store_true",
                        help="Overwrite a QuestionList.md this command did not write.")
    args = parser.parse_args()
    if args.decide and args.party:
        parser.error("--decide records answers and --party writes nothing; run them apart")

    space = workspace_contract.Workspace(args.app_root)
    try:
        output = space.output_dir()
        register_file = dr.register_path(output)
        register = dr.read_register(register_file)
        entries = register["entries"]
        app = str(register.get("app_id") or "")
        parties = dq.load_parties(space.input_dir("decisions") / "parties.yaml")
        policy = dq.load_policy(space.input_dir("decisions") / "policy.yaml")
        interviews = interview_register.observe(space)

        if args.link:
            changed = apply_links(entries, parse_links(args.link), interviews, parties)
            for line in changed or ["nothing to change: every link was already recorded"]:
                print(f"link: {line}")
            if changed and not args.dry_run:
                backup = dr.write_register(space, register_file, register)
                print(f"wrote {register_file}; the previous file is {backup}")

        if args.decide:
            decide(space, output, register_file, register, parties, interviews, policy, args)
            entries = register["entries"]

        problems = dq.validate_register(entries, parties)
        if parties is None and any(e.get("namespace") in ("Q", "UK-") and dq.is_open(e) for e in entries):
            problems.append("there is no input/decisions/parties.yaml, so no party can be checked")
        elif parties is not None:
            problems += [f"parties.yaml: {p}" for p in parties.problems]

        queue = da.build_queue(entries, parties, evidence=dr.evidence_index(output),
                               interviews=interviews, app_id=app, policy=policy)
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
        if policy is not None:
            print(f"{c['settled_by_policy']} settled by standing policy, "
                  f"{c['settled_once_policy_decided']} more once a proposed policy is decided")
        for party in queue["party_order"]:
            row = c["by_party"][party]
            print(f"  {party}: {row['to_ask_now']} to ask ({row['blocking']} blocking), "
                  f"{row['open'] - row['to_ask_now']} already moving"
                  + (f", {row['settled']} settled by policy" if row.get("settled") else ""))
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
