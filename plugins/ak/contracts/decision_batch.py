"""The decider's turn: settle the open dispositions in one batch, in the terminal (A75, slice 3).

Every risk a phase writes carries a Mitigation, and for a legacy defect that Mitigation is a
recommended answer: what the replacement should do about it. Nobody was asked to accept any
of them. Standing policy settles whole classes of them (`policy.yaml`); what is left is
put to the decider here, all at once, with the Mitigation as the default:

    ok              accept the default of every item listed
    3=preserve      item 3 keeps the legacy behaviour instead
    RW-04=drop      an item by its id, listed or not: an item a policy settled, or one
                    waiting behind another, is the decider's to decide explicitly
    ok 3=preserve   both: every default, except item 3

An item with no default is passed over by `ok`; it has to be answered by name, because `ok`
deciding something nobody recommended would be a decision nobody made.

An answer is evidence, never queue text (design, principle 4). Each one becomes a row of a
TARGET_INTENT record in `input/target-intent/` naming who decided and when, the way that
folder's README asks of every scope record, and an evidence item citing that row; the
register's `resolved_by` then points at the evidence. Nothing here reads or writes a file:
it takes the queue and returns what to write, so every rule is testable without a workspace.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

import decision_agenda as da
import decision_queue as dq

# What each choice means, written into the record beside it. A reader of the record should
# not need this module to know what `preserve` committed them to.
MEANING = {
    "fix": "Change the legacy behaviour in the new system",
    "preserve": "Keep the legacy behaviour as it is",
    "drop": "The behaviour is not carried into the new system",
    "defer": "Not decided for this replacement; revisit it later",
}


def meaning_of(choice: str, mitigation: str) -> str:
    """What a choice commits the replacement to, in a sentence that ends once."""
    if choice == "fix" and mitigation:
        text = f"Do what its Mitigation says: {mitigation}"
    else:
        text = MEANING[choice]
    return text.rstrip(" .") + "."


EVIDENCE_TOKEN = "TARGET"


class AnswerProblem(Exception):
    """An answer that cannot be recorded. Nothing is written when one is raised."""


def listed(queue: dict[str, Any]) -> list[dict[str, Any]]:
    """What is put to the decider now: their dispositions free to decide, in agenda order.

    Not one a policy settled, and not one waiting behind another item - its interim default
    is to carry the behaviour unchanged until what it waits on is answered (design 4.3).
    Either can still be answered by id.
    """
    items = {i["id"]: i for i in queue["items"]}
    agenda = queue["agendas"].get(dq.DECIDER) or {}
    return [items[i] for bucket in ("blocking", "proceeding") for i in agenda.get(bucket, [])
            if items[i]["kind"] == "DISPOSITION"]


def decidable(queue: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every open disposition that is the decider's, whatever its bucket."""
    return {i["id"]: i for i in queue["items"]
            if i["kind"] == "DISPOSITION" and i["party"] == dq.DECIDER
            and i["bucket"] not in ("with_customer", "to_record")}


def parse(line: str, shown: list[dict[str, Any]],
          known: dict[str, dict[str, Any]]) -> dict[str, str]:
    """The decisions a line of answers makes: item id -> choice, in the order listed."""
    accept_all = False
    chosen: dict[str, str] = {}
    for token in line.replace(",", " ").split():
        if token.casefold() == "ok":
            accept_all = True
            continue
        key, separator, value = token.partition("=")
        if not separator or not key or not value:
            raise AnswerProblem(f"{token!r}: answer `ok`, or N=<choice>, or ITEM=<choice>")
        if key.isdigit():
            number = int(key)
            if not 1 <= number <= len(shown):
                raise AnswerProblem(f"{token!r}: there is no item {number}; "
                                    f"the list has {len(shown)}")
            item = shown[number - 1]
        else:
            item = known.get(key)
            if item is None:
                raise AnswerProblem(f"{token!r}: {key} is not an open disposition of the {dq.DECIDER}")
        choices = da.choices_of(item)
        if value.casefold() == "ok":
            value = da.default_choice(item) or ""
            if not value:
                raise AnswerProblem(f"{token!r}: {item['id']} has no default; choose one of "
                                    f"{', '.join(choices)}")
        elif value not in choices:
            raise AnswerProblem(f"{token!r}: {item['id']} chooses among {', '.join(choices)}")
        if chosen.get(item["id"], value) != value:
            raise AnswerProblem(f"{item['id']} is answered twice, as {chosen[item['id']]} and {value}")
        chosen[item["id"]] = value
    if accept_all:
        for item in shown:
            default = da.default_choice(item)
            if item["id"] not in chosen and default:
                chosen[item["id"]] = default
    position = {item["id"]: n for n, item in enumerate(shown)}
    return dict(sorted(chosen.items(), key=lambda kv: (position.get(kv[0], len(position)),
                                                       da.natural(kv[0]))))


def render_listing(shown: list[dict[str, Any]], texts: dict[str, dict[str, str]],
                   others: int = 0) -> str:
    """The batch as the decider reads it before answering."""
    if not shown:
        lines = ["Nothing is waiting for the decider's disposition."]
    else:
        lines = [f"{len(shown)} disposition(s) for the decider. Each proceeds on its default until "
                 "decided; `ok` accepts every default."]
    for number, item in enumerate(shown, start=1):
        default = da.default_choice(item)
        mitigation = da.clean_mitigation((texts.get(item["id"]) or {}).get("mitigation") or "")
        severity = f" [{item['severity']}]" if item.get("severity") else ""
        lines += ["", f"{number}. {item['id']}{severity} {item['title']}"]
        if mitigation:
            lines.append(f"   Mitigation: {mitigation}")
        if item.get("would_settle"):
            lines.append(f"   {item['would_settle']} would settle it once that policy is decided")
        lines.append("   Choices: " + " / ".join(
            f"[{c}]" if c == default else c for c in da.choices_of(item))
            + ("" if default else "   (no default: answer it by number)"))
    by_rule = sum(1 for item in shown if item.get("would_settle"))
    if by_rule:
        lines += ["", f"{by_rule} of these would be settled by a proposed policy. Deciding "
                      "policy.yaml first answers them as a class, once, instead of one by one here."]
    if others:
        lines += ["", f"{others} more can be answered by id: settled by policy, or waiting behind "
                      "another item."]
    if shown or others:
        lines += ["", "Answer: ok | N=<choice> | ITEM=<choice>, separated by spaces. "
                      "An empty line decides nothing."]
    return "\n".join(lines) + "\n"


def record_name(app: str, decided_on: str, taken: set[str]) -> str:
    """`{APP}_Decisions_{date}.md`, numbered when a second batch is recorded the same day."""
    base = f"{app}_Decisions_{decided_on}"
    name, counter = f"{base}.md", 2
    while name in taken:
        name, counter = f"{base}-{counter}.md", counter + 1
    return name


def record_markdown(app: str, decisions: dict[str, str], items: dict[str, dict[str, Any]],
                    texts: dict[str, dict[str, str]], *, decided_by: str, decided_on: str,
                    answers: str) -> str:
    """The TARGET_INTENT record: who decided, when, from what, and each decision."""
    rows = []
    for item_id, choice in decisions.items():
        item = items[item_id]
        meaning = meaning_of(choice, da.clean_mitigation((texts.get(item_id) or {}).get("mitigation") or ""))
        rows.append(f"| {item_id} | {da._cell(item['title'])} | {choice} | {da._cell(meaning)} |")
    return "\n".join([
        f"# {app} — dispositions decided",
        "",
        "A decision about the system being built, not about the one being replaced (EC-07): for each",
        "item, what the replacement does about a behaviour of the legacy application. Recorded by",
        "`$ak decisions --decide`; each row is cited by one evidence item, and the item it answers is",
        "closed against that evidence.",
        "",
        "| | |",
        "|---|---|",
        f"| Decided by | {da._cell(decided_by)} ({dq.DECIDER}) |",
        f"| Decided on | {decided_on} |",
        f"| Source | answers given at `$ak decisions --decide`: `{da._cell(answers.strip())}` |",
        "",
        "| Item | About | Decision | What that means |",
        "|---|---|---|---|",
        *rows,
        "",
    ])


def next_serial(evidence_items: list[dict[str, Any]], app: str, token: str = EVIDENCE_TOKEN) -> int:
    """The class's next number. A run numbers per class across phases: TARGET-001 is Phase 1's,
    TARGET-002 Phase 4's, so the next is 003 whatever phase records it."""
    pattern = re.compile(rf"^{re.escape(app)}-P[1-6]-{re.escape(token)}-([0-9]{{3,}})$")
    numbers = [int(m.group(1)) for i in evidence_items
               if (m := pattern.match(str(i.get("id") or "")))]
    return max(numbers, default=0) + 1


def evidence_items(app: str, decisions: dict[str, str], items: dict[str, dict[str, Any]],
                   texts: dict[str, dict[str, str]], existing: list[dict[str, Any]], *,
                   decided_by: str, decided_on: str, created_at: str, phase: int, run_id: str,
                   record_path: str, record_text: str) -> list[dict[str, Any]]:
    """One TARGET_INTENT item per decision, each citing its row of the record."""
    digest = hashlib.sha256(record_text.encode("utf-8")).hexdigest()
    serial = next_serial(existing, app)
    made: list[dict[str, Any]] = []
    for offset, (item_id, choice) in enumerate(decisions.items()):
        item = items[item_id]
        meaning = meaning_of(choice, da.clean_mitigation((texts.get(item_id) or {}).get("mitigation") or ""))
        made.append({
            "agent_id": None, "agent_runtime": None, "app_id": app,
            "attribution": {"person": decided_by, "recorded_on": decided_on,
                            "role": dq.DECIDER, "question_id": item_id},
            "claim_kind": "SCOPE", "confidence": 1.0, "created_at": created_at,
            "evidence_class": "TARGET_INTENT",
            "id": f"{app}-P{phase}-{EVIDENCE_TOKEN}-{serial + offset:03d}",
            "notes": (f"The decider's disposition of {item_id} ({item['title']}). It says what the "
                      "replacement does, and nothing about what the legacy application does (EC-07)."),
            "phase": phase, "related_nodes": [], "role": "disposition of a legacy behaviour",
            "run_id": run_id, "source_language": "EN", "source_location": f"row {item_id}",
            "source_path": record_path, "source_sha256": digest,
            "source_type": "STAKEHOLDER_DECISION",
            "statement": dq.disposition_statement(item_id, choice, meaning),
            "status": "EXTRACTED", "task_id": "decisions",
        })
    return made


def close(entries: list[dict[str, Any]], made: list[dict[str, Any]]) -> list[str]:
    """Set `resolved_by` on each decided item, in place. Returns what changed."""
    by_id = {str(e["id"]): e for e in entries if e.get("id")}
    changed = []
    for evidence in made:
        item_id = evidence["attribution"]["question_id"]
        entry = by_id[item_id]
        if not dq.is_open(entry):
            raise AnswerProblem(f"{item_id} is already closed")
        entry["resolved_by"] = evidence["id"]
        changed.append(f"{item_id} -> {evidence['id']}")
    return changed
