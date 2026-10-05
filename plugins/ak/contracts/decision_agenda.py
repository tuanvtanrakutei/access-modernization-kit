"""The queue a person works from, and the list that asks it (A75, slice 2).

Slice 1 put the fields in the register: who can answer, what waits on it, what the pipeline
proceeds on meanwhile. This turns them into the thing the end goal needs - a list of what
a person has to do, in the order to do it, that says what the machine already did for them.

Nothing here reads a file or writes one. It takes the register's entries and, optionally,
the evidence register, the Q&A register and the text of the phase documents' rows, and
returns a queue and its renderings, so every rule below is testable without a workspace and
the same inputs always give the same bytes. There is no timestamp in either output, for the
reason `$ak derive` has none: an artefact a person can diff in git is one they can trust.

Five rules, each a decision the maintainer approved with the design:

  An item with a default never waits. It is `PROCEEDS_ON_DEFAULT`; the pipeline carries
  the assumption and the answer confirms or corrects it. Only an item with no default is
  `BLOCKING`, and it blocks only the objects it names.

  Ask in dependency order. An answer that settles another item comes first, so nobody is
  asked a question that the next answer makes moot. Among items free to go, what stops
  work now comes before what merely risks rework, then what unblocks the most.

  Do not ask what has been asked. An item posted to the customer's Q&A is `with_customer`
  and stays off the list of things to ask; one whose Q&A page holds a dated answer is
  `answered_unrecorded`: the answer exists and the register does not know. A Q&A the
  customer has open that no item mentions is reported, because the queue cannot see it.

  Say what the machine did. Closed items are counted by who closed them: a person, a
  decision, or the bundle - evidence already in hand that made the question unnecessary
  (on one project, Q109 and Q120 were put to people and then answered by the code, after publication).

  Name objects, not numbers. Every identifier in `blocks` is shown with its title, so an
  `F-` is never a bare number (ID-06).

And one from slice 3. A rule asked once beats the same question asked per instance: a risk
whose class a decided policy covers is `settled` by it, leaves every agenda, and is still
listed under the policy that settled it, so nothing a policy decides disappears.
"""
from __future__ import annotations

import json
import re
from typing import Any, Iterable

import decision_queue as dq

SEVERITY = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

# Who closed an item, by the class of the evidence that closed it. An INTERVIEW or a
# DOCUMENT is a person's answer; TARGET_INTENT is a decision about the new system; every
# other class is the bundle answering on its own, which is the case this queue exists to
# make visible. OPERATOR_DECLARATION is a person's statement about the inputs.
PERSON_CLASSES = ("INTERVIEW", "DOCUMENT", "OPERATOR_DECLARATION")
DECISION_CLASSES = ("TARGET_INTENT",)

GENERATED = "<!-- generated-by: ak decisions"
BUCKETS = ("blocking", "proceeding", "waiting", "to_record", "with_customer", "settled")
ASKING = ("blocking", "proceeding", "waiting")
# What the queue routes: the asks, and the risks whose Mitigation is a recommended answer.
ROUTED = ("Q", "UK-", *dq.RISK_NAMESPACES)


def natural(identifier: str) -> tuple[tuple[int, Any], ...]:
    """Q5 before Q101, UK-D02 before UK-D10."""
    return tuple((0, int(part)) if part.isdigit() else (1, part)
                 for part in re.split(r"(\d+)", identifier) if part != "")


def closure_kind(evidence_class: str | None) -> str:
    if not evidence_class:
        return "unknown"
    if evidence_class in PERSON_CLASSES:
        return "person"
    if evidence_class in DECISION_CLASSES:
        return "decision"
    return "bundle"


def _answered(status: str) -> bool:
    return status.strip().casefold() == "answered"


def choices_of(item: dict[str, Any]) -> list[str]:
    """What a decider may choose: the item's own options, else the four dispositions."""
    if item.get("options"):
        return list(item["options"])
    return list(dq.DISPOSITIONS) if item.get("kind") == "DISPOSITION" else []


def default_choice(item: dict[str, Any]) -> str | None:
    """The choice `ok` stands for. `fix` is doing what the risk's own Mitigation says; an item
    with no default has none, and `ok` passes over it rather than deciding it for anyone."""
    default = item.get("default")
    if isinstance(default, dict) and default.get("mitigation") and "fix" in choices_of(item):
        return "fix"
    return None


def _customer(item_id: str, qa: list[int], interviews: dict[str, Any] | None,
              problems: list[str]) -> dict[str, Any] | None:
    """Where the customer stands on the Q&A pages this item was posted as."""
    if not qa:
        return None
    rows = {str(r.get("id")): r for r in ((interviews or {}).get("register") or [])}
    if not rows:
        problems.append(f"{item_id}: names Q&A {qa}, and there is no Q&A register to read them from")
        return {"state": "unknown", "qa": [{"id": q, "listed": False} for q in qa]}
    pages = {str(p.get("id")): p for p in ((interviews or {}).get("pages") or [])}
    seen: list[dict[str, Any]] = []
    for number in qa:
        row = rows.get(str(number))
        if row is None:
            problems.append(f"{item_id}: names Q&A {number}, which the Q&A register does not list")
            seen.append({"id": number, "listed": False})
            continue
        answers = (pages.get(str(number)) or {}).get("answers") or []
        seen.append({
            "id": number, "listed": True, "status": str(row.get("status") or ""),
            "asked": str(row.get("ask_date") or ""), "respondent": str(row.get("respondent") or ""),
            "answered_on": [str(a.get("recorded_on")) for a in answers],
            "marked_answered": _answered(str(row.get("status") or "")),
        })
    if any(not s["listed"] for s in seen):
        state = "unknown"
    elif any(s["answered_on"] for s in seen):
        state = "answered_unrecorded"
    elif any(s["marked_answered"] for s in seen):
        state = "answer_missing"
    else:
        state = "with_customer"
    return {"state": state, "qa": seen}


def _bucket(item: dict[str, Any]) -> str:
    if item.get("settled_by"):
        return "settled"
    state = (item["customer"] or {}).get("state")
    if state in ("answered_unrecorded", "answer_missing"):
        return "to_record"
    if state == "with_customer":
        return "with_customer"
    if item["waiting_on"]:
        return "waiting"
    return "blocking" if item["posture"] == "BLOCKING" else "proceeding"


def _rank(item: dict[str, Any]) -> tuple[Any, ...]:
    # A risk's own severity counts as well as the severities it names: a risk's disposition
    # usually names nothing, because what waits on it is the risk's own Mitigation.
    severity = max([SEVERITY.get(str(b.get("severity")), 0) for b in item["blocks"]]
                   + [SEVERITY.get(str(item.get("severity")), 0)])
    # Severity before the count: a block list is whatever a phase author could name, and a
    # broad guess ("every workflow") would otherwise outrank the one question that decides
    # a HIGH risk. What the analysis itself called HIGH is the better signal.
    return (0 if item["posture"] == "BLOCKING" else 1, -len(item["dependents"]),
            -severity, -len(item["blocks"]), natural(item["id"]))


def _order(items: dict[str, dict[str, Any]], problems: list[str]) -> list[str]:
    """Dependencies first; among items free to go, the best-ranked first."""
    waiting = {i: set(item["waiting_on"]) for i, item in items.items()}
    ready = sorted((i for i, w in waiting.items() if not w), key=lambda i: _rank(items[i]))
    order: list[str] = []
    while ready:
        current = ready.pop(0)
        order.append(current)
        for follower in items[current]["dependents"]:
            waiting[follower].discard(current)
            if not waiting[follower] and follower not in order and follower not in ready:
                ready.append(follower)
        ready.sort(key=lambda i: _rank(items[i]))
    stuck = sorted((i for i in items if i not in order), key=lambda i: _rank(items[i]))
    if stuck:
        problems.append(f"{', '.join(stuck)} cannot be ordered: they wait on each other")
    return order + stuck


def build_queue(entries: list[dict[str, Any]], parties: dq.Parties | None = None, *,
                evidence: dict[str, dict[str, Any]] | None = None,
                interviews: dict[str, Any] | None = None,
                app_id: str = "", policy: dq.Policy | None = None,
                prechecks: dict[str, list[dict[str, str]]] | None = None) -> dict[str, Any]:
    by_id = {str(e["id"]): e for e in entries if e.get("id")}
    problems: list[str] = []
    if policy is not None and policy.problems:
        problems.append(f"policy.yaml has {len(policy.problems)} problem(s), so no policy settles "
                        f"anything until it is fixed; first: {policy.problems[0]}")

    def ref(identifier: str) -> dict[str, Any]:
        entry = by_id.get(identifier) or {}
        found: dict[str, Any] = {"id": identifier, "title": str(entry.get("title") or "")}
        if entry.get("severity"):
            found["severity"] = str(entry["severity"])
        if entry.get(dq.IF_WRONG):
            # What an answer that contradicts this assumption has to refresh (design 4.4).
            found["if_wrong"] = str(entry[dq.IF_WRONG])
            found["refresh"] = dq.refresh_set(entry)
        return found

    raw: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for entry in entries:
        needs = entry.get("needs")
        if isinstance(needs, dict) and dq.is_open(entry):
            raw[str(entry["id"])] = (entry, needs)

    # Which rule would settle each item, before anything waits on it: an item a decided policy
    # has settled is not something another item waits behind.
    rules: dict[str, dict[str, Any] | None] = {
        i: (policy.applies(entry) if policy is not None else None) for i, (entry, _n) in raw.items()}
    settled = {i for i, rule in rules.items() if rule is not None and dq.Policy.in_force(rule)}
    pending = {i for i in raw if i not in settled}

    dependents: dict[str, list[str]] = {i: [] for i in raw}
    for identifier, (_entry, needs) in raw.items():
        for dependency in needs.get("depends_on") or []:
            if dependency in pending:
                dependents[dependency].append(identifier)

    items: dict[str, dict[str, Any]] = {}
    for identifier, (entry, needs) in raw.items():
        default = needs.get("default")
        rule = rules[identifier]
        item = {
            "id": identifier, "namespace": entry.get("namespace"), "phase": entry.get("phase"),
            "title": str(entry.get("title") or ""),
            "kind": needs.get("kind"), "party": needs.get("party"),
            "also": list(needs.get("also") or []), "named": list(needs.get("named") or []),
            "blocks": [{"object": b[len(dq.OBJECT_PREFIX):].strip()} if b.startswith(dq.OBJECT_PREFIX)
                       else ref(b) for b in needs.get("blocks") or []],
            "default": ({"mitigation": True} if default == dq.MITIGATION
                        else ref(default) if default else None),
            "gap": ref(needs["gap"]) if needs.get("gap") else None,
            "depends_on": list(needs.get("depends_on") or []),
            "waiting_on": [d for d in needs.get("depends_on") or [] if d in pending],
            "dependents": sorted(dependents[identifier], key=natural),
            "qa": list(needs.get("qa") or []), "class": needs.get("class"),
            "options": needs.get("options"),
            "evidence_ids": list(entry.get("evidence_ids") or []),
            "severity": str(entry["severity"]) if entry.get("severity") else None,
            "settled_by": rule["id"] if identifier in settled else None,
            "disposition": rule["disposition"] if identifier in settled else None,
            "would_settle": rule["id"] if rule is not None and identifier not in settled else None,
        }
        if prechecks and prechecks.get(identifier):
            item["precheck"] = prechecks[identifier]       # A58: found before it is asked, never a verdict
        item["posture"] = "BLOCKING" if item["default"] is None else "PROCEEDS_ON_DEFAULT"
        item["customer"] = _customer(identifier, item["qa"], interviews, problems)
        item["bucket"] = _bucket(item)
        items[identifier] = item

    order = _order(items, problems)
    for position, identifier in enumerate(order, start=1):
        items[identifier]["order"] = position

    closed: list[dict[str, Any]] = []
    for entry in entries:
        if entry.get("namespace") not in ROUTED or dq.is_open(entry):
            continue
        resolved = str(entry.get("resolved_by") or "").strip()
        base = {"id": str(entry["id"]), "namespace": entry.get("namespace"),
                "phase": entry.get("phase"), "title": str(entry.get("title") or "")}
        if resolved:
            found = (evidence or {}).get(resolved)
            klass = (found or {}).get("evidence_class")
            closed.append({**base, "how": "resolved", "by": resolved, "by_class": klass,
                           "by_kind": closure_kind(klass),
                           "disposition": dq.recorded_disposition(found)})
        else:
            closed.append({**base, "how": "superseded", "by": str(entry.get("superseded_by")),
                           "by_class": None, "by_kind": "item", "disposition": None})
    closed.sort(key=lambda c: natural(c["id"]))

    asked = {str(e["needs"]["gap"]) for e in entries
             if isinstance(e.get("needs"), dict) and e["needs"].get("gap")}
    unrouted = sorted((str(e["id"]) for e in entries
                       if e.get("namespace") in ROUTED and dq.is_open(e)
                       and not isinstance(e.get("needs"), dict)
                       and not (e.get("namespace") == "UK-" and str(e["id"]) in asked)),
                      key=natural)

    linked = {str(n) for e in entries if isinstance(e.get("needs"), dict)
              for n in (e["needs"].get("qa") or [])}
    untracked = [{"id": str(r.get("id")), "title": str(r.get("title") or ""),
                  "status": str(r.get("status") or ""), "asked": str(r.get("ask_date") or ""),
                  "respondent": str(r.get("respondent") or "")}
                 for r in ((interviews or {}).get("register") or [])
                 if not _answered(str(r.get("status") or "")) and str(r.get("id")) not in linked]

    agendas: dict[str, dict[str, list[str]]] = {}
    also_for: dict[str, list[str]] = {}
    for identifier in order:
        item = items[identifier]
        agendas.setdefault(str(item["party"]), {b: [] for b in BUCKETS})[item["bucket"]].append(identifier)
        for other in item["also"]:
            if item["bucket"] != "settled":
                also_for.setdefault(other, []).append(identifier)

    def to_ask(party: str) -> int:
        return sum(len(agendas[party][b]) for b in ASKING)

    party_order = sorted(agendas, key=lambda p: (p == dq.DECIDER, -to_ask(p), p))

    undecided = [i for i in items.values() if i["bucket"] != "settled"]
    by_bucket = {b: sum(1 for i in items.values() if i["bucket"] == b) for b in BUCKETS}
    by_closure: dict[str, int] = {}
    for c in closed:
        by_closure[c["by_kind"]] = by_closure.get(c["by_kind"], 0) + 1
    rules_listed = _policy_summary(policy, items)
    counts = {
        "open": len(undecided),
        "blocking": sum(1 for i in undecided if i["posture"] == "BLOCKING"),
        "proceeding_on_default": sum(1 for i in undecided if i["posture"] == "PROCEEDS_ON_DEFAULT"),
        "waiting_on_another_item": by_bucket["waiting"],
        "with_customer": by_bucket["with_customer"],
        "answered_not_recorded": by_bucket["to_record"],
        "to_ask_now": sum(by_bucket[b] for b in ASKING),
        "settled_by_policy": by_bucket["settled"],
        "settled_once_policy_decided": sum(1 for i in undecided if i["would_settle"]),
        "closed": {"total": len(closed), "by_person": by_closure.get("person", 0),
                   "by_bundle": by_closure.get("bundle", 0),
                   "by_decision": by_closure.get("decision", 0),
                   "superseded": by_closure.get("item", 0),
                   "unknown": by_closure.get("unknown", 0)},
        "unrouted": len(unrouted),
        "untracked_qa": len(untracked),
        "by_kind": {k: sum(1 for i in undecided if i["kind"] == k)
                    for k in dq.KINDS if any(i["kind"] == k for i in undecided)},
        "by_party": {p: {"open": sum(len(agendas[p][b]) for b in BUCKETS if b != "settled"),
                         "to_ask_now": to_ask(p),
                         "blocking": len(agendas[p]["blocking"]),
                         "settled": len(agendas[p]["settled"])} for p in party_order},
    }
    if any(i.get("precheck") for i in items.values()):
        counts["prechecked"] = sum(1 for i in undecided if i.get("precheck"))
    return {
        "app_id": app_id, "counts": counts, "party_order": party_order,
        "agendas": agendas, "also_for": also_for,
        "items": [items[i] for i in order], "closed": closed, "policy": rules_listed,
        "unrouted": unrouted, "untracked_qa": untracked, "problems": problems,
    }


def _policy_summary(policy: dq.Policy | None,
                    items: dict[str, dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Each rule, whether it is in force, and what it settles or would settle."""
    if policy is None:
        return None
    listed = []
    for rule in policy.entries:
        listed.append({
            "id": rule["id"], "class": rule["class"], "disposition": rule["disposition"],
            "in_force": dq.Policy.in_force(rule) and not policy.problems,
            "decided_by": rule["decided_by"], "decided_on": rule["decided_on"],
            "settles": sorted((i for i, item in items.items() if item["settled_by"] == rule["id"]),
                              key=natural),
            "would_settle": sorted((i for i, item in items.items() if item["would_settle"] == rule["id"]),
                                   key=natural),
        })
    return listed


def render_json(queue: dict[str, Any]) -> str:
    return json.dumps(queue, indent=1, sort_keys=True, ensure_ascii=False) + "\n"


# --- the list ----------------------------------------------------------------

def _label(ref: dict[str, Any]) -> str:
    """An identifier with its title. An `F-` keeps its whole name (ID-06); the rest are cut
    short, because a block list of six workflows is a line, not a paragraph."""
    if "object" in ref:
        return f"`{ref['object']}` (object)"
    title = ref["title"]
    if not ref["id"].startswith("F-") and len(title) > 72:
        title = title[:71].rstrip() + "…"
    return f"{ref['id']} {title}".strip()


def _party_heading(name: str, parties: dq.Parties | None) -> str:
    entry = (parties.parties.get(name) if parties else None) or {}
    aliases = [a for a in entry.get("aliases") or [] if a]
    shown = ", ".join(aliases[:2]) + (", …" if len(aliases) > 2 else "")
    return f"{name} ({shown})" if aliases else name


# What a phase document puts in a question that the person asked has no use for: the
# evidence ids it cites (listed under "Evidence already read") and the bold marker saying
# which correction raised it ("Raised by E-11." / "Dựng lên từ E-11.").
CITATION = re.compile(r"\s*\[[A-Z][A-Z0-9_]{1,15}-P[1-6]-[A-Z][A-Z0-9_]*-\d{3,}\]")
ORIGIN_MARKER = re.compile(r"^\*\*[^*]*\bE-\d{2}\b[^*]*\*\*\s*")


def _clean(text: str, origin: bool = True) -> str:
    """The sentence without its citations, and without the marker saying which correction
    raised it. A Mitigation keeps that marker: a run's RA-10 opened with **E-05: confirmed - do
    not carry it forward.**, and without it the default reads as a quotation and nothing else."""
    if origin:
        text = ORIGIN_MARKER.sub("", text)
    return re.sub(r"\s+", " ", CITATION.sub("", text)).strip()


def clean_mitigation(text: str) -> str:
    return _clean(text, origin=False).replace("**", "")


def _cell(text: Any) -> str:
    """Text for a table cell: a pipe inside it would shift every column after it."""
    return str(text).replace("|", chr(92) + "|").replace("\n", " ")


def _same(a: str, b: str) -> bool:
    key = lambda t: re.sub(r"[\W_]+", "", t).casefold()      # noqa: E731
    return not a or key(a) == key(b) or key(b).startswith(key(a)) or key(a).startswith(key(b))


def _qa_parts(q: dict[str, Any]) -> tuple[str, str]:
    """(label, where one Q&A page stands)."""
    label = f"Q&A {q['id']}"
    if not q.get("listed"):
        return label, "not in the Q&A register"
    detail = f"{q['status'] or 'status unknown'}, asked {q['asked'] or 'date unknown'}"
    if q["respondent"]:
        detail += f", respondent {q['respondent']}"
    if q["answered_on"]:
        detail += f"; dated answer {', '.join(q['answered_on'])}"
    elif q["marked_answered"]:
        detail += "; marked answered, no answer in its page"
    return label, detail


def _qa_phrase(q: dict[str, Any]) -> str:
    label, detail = _qa_parts(q)
    return f"{label}: {detail}"


def _item_block(number: int, item: dict[str, Any], texts: dict[str, dict[str, str]],
                parties: dq.Parties | None) -> list[str]:
    own = texts.get(item["id"]) or {}
    gap_text = texts.get(item["gap"]["id"]) if item["gap"] else {}
    gap_text = gap_text or {}
    ask = _clean(own.get("ask") or gap_text.get("ask") or "")
    why = _clean(gap_text.get("why") or own.get("why") or own.get("blocks_prose") or "")
    settle = _clean(gap_text.get("settle") or "")
    mitigation = clean_mitigation(own.get("mitigation") or "")
    lines = [f"#### {number}. {item['id']} — {item['title']}", ""]
    if ask and not _same(ask, item["title"]):
        lines += [f"> {ask}", ""]
    posture = "blocking" if item["posture"] == "BLOCKING" else "proceeding on a default"
    head = f"- **Kind:** {item['kind']} · **{posture.capitalize()}**"
    if item["severity"]:
        head += f" · **Severity:** {item['severity']}"
    if item["class"]:
        head += f" · **Class:** {item['class']}"
    lines.append(head)
    if item["blocks"]:
        lines.append("- **Blocks:** " + "; ".join(_label(b) for b in item["blocks"]))
    if why:
        lines.append(f"- **Why it matters:** {why}")
    default = item["default"]
    if default and "mitigation" in default:
        lines.append("- **Proceeding on its Mitigation:** "
                     + (mitigation or "the mitigation its risk already carries"))
    elif default:
        lines.append(f"- **Proceeding on:** {_label(default)}")
        if default.get("if_wrong"):
            refresh = default.get("refresh") or []
            lines.append(f"- **If that is wrong:** {_clean(default['if_wrong'])}"
                         + (f" (refresh: {', '.join(refresh)})" if refresh else ""))
    for flag in item.get("precheck") or []:
        lines.append(f"- **Check before asking:** {_clean(flag['text'])} ({flag['source']})")
    if item["gap"]:
        lines.append(f"- **About the unknown:** {_label(item['gap'])}")
    if settle:
        lines.append(f"- **What would settle it:** {settle}")
    choices = choices_of(item)
    if choices:
        lines.append("- **Choices:** " + " / ".join(
            f"{c} (the default)" if c == default_choice(item) else c for c in choices))
    if item["would_settle"]:
        lines.append(f"- **Standing policy:** {item['would_settle']} would settle it, once someone "
                     "decides that policy")
    if item["waiting_on"]:
        lines.append("- **Waits behind:** " + ", ".join(item["waiting_on"]))
    if item["dependents"]:
        lines.append("- **Settles first for:** " + ", ".join(item["dependents"]))
    if item["also"]:
        lines.append("- **Also can answer:** " + ", ".join(_party_heading(p, parties) for p in item["also"]))
    if item["named"]:
        lines.append("- **Named:** " + ", ".join(item["named"]))
    customer = item["customer"]
    if customer:
        for q in customer["qa"]:
            label, detail = _qa_parts(q)
            lines.append(f"- **{label}:** {detail}")
    if item["evidence_ids"]:
        lines.append("- **Evidence already read:** " + ", ".join(item["evidence_ids"]))
    return lines + [""]


def _policy_section(rules: list[dict[str, Any]]) -> list[str]:
    lines = ["## Standing policy", "",
             "Read from `input/decisions/policy.yaml`. A rule settles a class of risks once, and settles "
             "nothing until it names who decided it and when.", ""]
    if not rules:
        return lines + ["The file holds no rule, so every disposition is asked.", ""]
    lines += ["| Policy | Class | Disposition | Status | Items |", "|---|---|---|---|---|"]
    for rule in rules:
        if rule["disposition"] == "ask":
            status, listed = "each item is put to the decider", "—"
        elif rule["in_force"]:
            status = f"decided by {rule['decided_by']} on {rule['decided_on']}"
            listed = ", ".join(rule["settles"]) or "none open"
        else:
            status = "proposed: settles nothing until `decided_by` and `decided_on` are set"
            listed = ("would settle " + ", ".join(rule["would_settle"])) if rule["would_settle"] else "none open"
        lines.append(f"| {rule['id']} | {rule['class']} | {rule['disposition']} | {_cell(status)} | {_cell(listed)} |")
    return lines + [""]


def render_markdown(queue: dict[str, Any], *, parties: dq.Parties | None = None,
                    texts: dict[str, dict[str, str]] | None = None,
                    source: str = "the identifier register",
                    only: str | None = None) -> str:
    """The list. With `only`, just that party's agenda: what a person pastes to ask it."""
    texts = texts or {}
    app = queue["app_id"] or "App"
    c = queue["counts"]
    items = {i["id"]: i for i in queue["items"]}
    out = [
        f"{GENERATED} -->",
        f"# {app} — Question list",
        "",
        f"What is still open, who can settle it, and the order to ask. Generated by `$ak decisions` "
        f"from {source}; edit the register, not this file. It has no date on purpose: the same "
        "register gives the same file.",
        "",
        "**Read this if** you relay questions to the customer or settle decisions for the new system. "
        "Each agenda is addressed to one party. A question with a default does not stop work; it "
        "is carried as an assumption until answered.",
        "",
    ]
    if only is None:
        out += [
            "## Where things stand",
            "",
            "| | |",
            "|---|---:|",
            f"| Open items | {c['open']} |",
            f"| blocking: no default, so what they name waits | {c['blocking']} |",
            f"| proceeding on a default | {c['proceeding_on_default']} |",
            f"| waiting behind another item | {c['waiting_on_another_item']} |",
            f"| already with the customer (posted to Q&A) | {c['with_customer']} |",
            f"| answered by the customer, not yet recorded | {c['answered_not_recorded']} |",
        ]
        if queue.get("policy") is not None:
            out.append(f"| settled by standing policy, listed and not asked | {c['settled_by_policy']} |")
        out += [f"| closed in the register | {c['closed']['total']} |", ""]
    closed = c["closed"]
    if only is None and closed["total"]:
        parts = [f"{closed[k]} by {label}" for k, label in
                 (("by_person", "a person"), ("by_bundle", "the bundle, with nobody asked"),
                  ("by_decision", "a decision")) if closed[k]]
        parts += [f"{closed[k]} {label}" for k, label in
                  (("superseded", "superseded by another item"), ("unknown", "closed by evidence not in the register"))
                  if closed[k]]
        out += ["Closed: " + "; ".join(parts) + ".", ""]

    def section(party: str) -> None:
        agenda = queue["agendas"][party]
        asking = sum(len(agenda[b]) for b in ASKING)
        decider = party == dq.DECIDER
        out.extend([f"## {'Decisions for the ' + party if decider else 'Agenda: ' + _party_heading(party, parties)}",
                    "", f"{asking} to {'decide' if decider else 'ask'}."
                    + (f" {len(agenda['with_customer'])} already with the customer."
                       if agenda["with_customer"] else "")
                    + (f" {len(agenda['to_record'])} answered and waiting to be recorded."
                       if agenda["to_record"] else "")
                    + (f" {len(agenda['settled'])} settled by standing policy."
                       if agenda["settled"] else ""), ""])
        number = 0
        for bucket, heading in (
                ("blocking", "Blocks work now"),
                ("proceeding", "Work continues on an assumption; the answer confirms or corrects it"),
                ("waiting", "Waits behind another item")):
            if not agenda[bucket]:
                continue
            out.extend([f"### {heading}", ""])
            for identifier in agenda[bucket]:
                number += 1
                out.extend(_item_block(number, items[identifier], texts, parties))
        if agenda["settled"]:
            # Settled, so not asked - and listed, so a policy never makes a decision disappear.
            out.extend(["### Settled by standing policy, not asked", ""])
            for identifier in agenda["settled"]:
                item = items[identifier]
                waits = (f"; what it does still waits on {', '.join(item['waiting_on'])}"
                         if item["waiting_on"] else "")
                out.append(f"- {item['id']} {item['title']} — {item['settled_by']} "
                           f"({item['class']}): {item['disposition']}{waits}")
            out.append("")
        if only is not None:
            # The full list keeps these as two tables across every party. One agenda pasted on
            # its own would otherwise say "0 to ask" and nothing about why.
            for bucket, heading in (("with_customer", "Already with the customer"),
                                    ("to_record", "Answered by the customer and not yet recorded")):
                if agenda[bucket]:
                    out.extend([f"### {heading}", ""])
                    for identifier in agenda[bucket]:
                        item = items[identifier]
                        out.append(f"- {item['id']} {item['title']} — "
                                   + "; ".join(_qa_phrase(q) for q in item["customer"]["qa"]))
                    out.append("")
        if queue["also_for"].get(party):
            out.extend(["### Also addressed to you", ""])
            for identifier in queue["also_for"][party]:
                out.append(f"- {identifier} {items[identifier]['title']} "
                           f"(primarily {items[identifier]['party']})")
            out.append("")

    if only is not None:
        if only in queue["agendas"]:
            section(only)
        else:
            out += [f"## {only}", "", "Nothing is open for this party.", ""]
        return "\n".join(out).rstrip("\n") + "\n"

    for party in queue["party_order"]:
        if party != dq.DECIDER:
            section(party)
    if dq.DECIDER in queue["agendas"]:
        section(dq.DECIDER)
    if queue.get("policy") is not None:
        out.extend(_policy_section(queue["policy"]))

    waiting_for_customer = [i for i in queue["items"] if i["bucket"] == "with_customer"]
    if waiting_for_customer:
        out += ["## Already with the customer", "",
                "| Item | Q&A | Status | Asked | Respondent |", "|---|---|---|---|---|"]
        for item in waiting_for_customer:
            for q in item["customer"]["qa"]:
                out.append(f"| {_cell(item['id'] + ' ' + item['title'])} | {q['id']} | "
                           f"{_cell(q.get('status', ''))} | {_cell(q.get('asked', ''))} | "
                           f"{_cell(q.get('respondent', ''))} |")
        out.append("")
    to_record = [i for i in queue["items"] if i["bucket"] == "to_record"]
    if to_record:
        out += ["## Answered by the customer and not yet recorded", "",
                "Record the answer as INTERVIEW evidence, then set `resolved_by` on the item.", ""]
        for item in to_record:
            states = "; ".join(_qa_phrase(q) for q in item["customer"]["qa"])
            out.append(f"- {item['id']} {item['title']} — {states}")
        out.append("")
    if queue["untracked_qa"]:
        out += ["## Open with the customer and in no item", "",
                "These are in the customer's Q&A register and no item names them (`$ak decisions --link`), "
                "so this list cannot say what they block.", ""]
        for q in queue["untracked_qa"]:
            out.append(f"- Q&A {q['id']} — {q['title']} ({q['status']}, asked {q['asked'] or 'date unknown'}"
                       + (f", respondent {q['respondent']}" if q['respondent'] else "") + ")")
        out.append("")
    if queue["closed"]:
        out += ["## Closed", "", "| Item | Closed by | Evidence class |", "|---|---|---|"]
        for entry in queue["closed"]:
            how = (f"resolved by {entry['by']}" if entry["how"] == "resolved"
                   else f"superseded by {entry['by']}")
            if entry.get("disposition"):
                how += f": {entry['disposition']}"
            klass = entry["by_class"] or ("another item" if entry["how"] == "superseded"
                                          else "not in the evidence register")
            out.append(f"| {_cell(entry['id'] + ' ' + entry['title'])} | {_cell(how)} | {_cell(klass)} |")
        out.append("")
    if queue["unrouted"] or queue["problems"]:
        out += ["## Problems", ""]
        for identifier in queue["unrouted"]:
            out.append(f"- {identifier} is open and carries no `needs`, so nothing can route it "
                       "(`$ak backfill-needs`).")
        for problem in queue["problems"]:
            out.append(f"- {problem}")
        out.append("")
    return "\n".join(out).rstrip("\n") + "\n"
