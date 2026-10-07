#!/usr/bin/env python3
"""Compute what one screen has to cover, from the extraction, and check a screen plan against it.

Reports only. It never writes a project file - machine detects, human decides, agent
executes.

Stage 1 used to be a business-flow document an agent wrote per screen: purpose, actors, the
flow, the business rules, what differs from the new system, and a checklist. Every one of those
is already an output of the extraction - the workflows are `TraceabilityMatrix.csv` rows, the
rules are `BR-` entries in the identifier register, the legacy defects are risks that each carry
a Mitigation, and what is undecided is the decision queue - so a second narrative was a second
copy that could drift from the first, and gate G1 measured the copy. This script computes the
scope instead, and gates G1 and G2 are read off it:

  G1  the screen has traceability rows, and every evidence item they cite is in `Evidence.json`
  G2  (with --plan) every business rule in scope is cited in the screen plan's mapping section,
      and every open decision that names the screen is cited in its gap matrix

A rule or a risk belongs to a screen in one of two ways, both exact:

  placed     a person listed the screen in the entry's `screens` (its `F-`, or `object:<name>`),
             with `$ak decisions --place`. A placement decides alone: evidence is not consulted.
  evidence   it cites an evidence item that one of the screen's traceability rows cites.

The evidence link is coarse: a module read by three screens puts every rule it yields on all
three. The scope is therefore a superset, and the direction matters: a rule listed against a
screen that does not use it costs the plan a row saying so, where a rule missing from the scope
costs a defect nobody planned for. Over-inclusion is the safe error, and the count per screen is
printed so an inflated scope is visible.

One kind of coarseness is removed (A82). An evidence item that half the matrix's screens or more
cite - a whole UI export, a screenshot set - is broad, and places nothing while the entry cites
any narrower item: the narrow one says where the entry lives. An entry whose only link is broad
is listed as cross-cutting, and its rules are not owed a mapping row on every screen it reaches;
placing it is a person's decision.

Screen names are compared exactly after Unicode normalisation, never fuzzily
(`LEGACY_EVIDENCE.md` 6.3). A screen that matches no traceability row is a finding to raise.

Exit status: 0 nothing found, 1 a finding (G1, G2, or a BLOCKING decision that names the screen
directly), 2 an input cannot be read.

Stdlib only, so it runs in a project that has installed nothing.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import screen_decisions as sd  # noqa: E402

RULE_NAMESPACE = "BR-"
RISK_NAMESPACES = ("RD-", "RA-", "RW-", "RS-")
BROAD_MIN = 3
EVIDENCE_SPLIT = re.compile(r"[,;\s]+")
RULE_ID = re.compile(r"(?<![A-Za-z0-9_-])BR-[A-Z0-9]{1,6}(?:-[0-9]{2})?[a-z]?(?![A-Za-z0-9_-])")
DECISION_ID = re.compile(r"(?<![A-Za-z0-9_-])(?:Q[0-9]{1,3}|UK-[A-Z][0-9]{2})(?![A-Za-z0-9_-])")
HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
MAPPING_HEADING = re.compile(r"legacy[- ]to[- ]new\s+mapping", re.IGNORECASE)
GAP_HEADING = re.compile(r"gap\s+matrix", re.IGNORECASE)


def optional(where: Path, pattern: str, what: str) -> Path | None:
    """The one file matching, looked for beside the queue and one directory down; None when there is none."""
    found = sorted(where.glob(pattern)) or sorted(where.glob(f"*/{pattern}"))
    if len(found) > 1:
        raise sd.Problem(f"{what}: more than one {pattern} under {where}")
    return found[0] if found else None


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise sd.Problem(f"{path} cannot be read: {error}") from error


def matrix_rows(path: Path) -> list[dict[str, str]]:
    try:
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    except OSError as error:
        raise sd.Problem(f"{path} cannot be read: {error}") from error


def cited(cell: str | None) -> list[str]:
    return [token for token in EVIDENCE_SPLIT.split(str(cell or "")) if token]


def broad_threshold(screens: int) -> int:
    """How many screens an evidence item has to be cited by before it places nothing on its own.

    Half the matrix's screens, and never fewer than BROAD_MIN: with three screens, an item two of
    them cite is still telling the planner where something lives.
    """
    return max(BROAD_MIN, -(-screens // 2))


def placement_ids(entries: list[dict[str, Any]], screen: str, screen_id: str | None) -> set[str]:
    """The identifiers a person can place an entry on this screen by: its `F-`, or `object:<name>`."""
    ids = {str(e["id"]) for e in entries
           if e.get("namespace") == "F-" and e.get("id") and sd.norm(e.get("title")) == screen}
    return ids | ({screen_id} if screen_id else set()) | {f"{sd.OBJECT_PREFIX}{screen}"}


def scope_of(entries: list[dict[str, Any]], rows: list[dict[str, str]], evidence_ids: set[str] | None,
             screen: str, screen_id: str | None = None) -> dict[str, Any]:
    mine = [r for r in rows if sd.norm(r.get("screen")) == screen]
    # Which screens cite each evidence item: an item many screens cite (a screenshot set, a shared
    # module, a whole export) links its rules and risks to all of them, and the planner should see that.
    by_evidence: dict[str, set[str]] = {}
    for row in rows:
        for token in cited(row.get("evidence_ids")):
            by_evidence.setdefault(token, set()).add(sd.norm(row.get("screen")))
    every = {sd.norm(r.get("screen")) for r in rows if sd.norm(r.get("screen"))}
    threshold = broad_threshold(len(every))
    broad = {token for token, screens in by_evidence.items() if len(screens & every) >= threshold}
    used: set[str] = set()
    workflows: dict[str, int] = {}
    for row in mine:
        used.update(cited(row.get("evidence_ids")))
        wid = str(row.get("workflow_id") or "").strip()
        if wid:
            workflows[wid] = workflows.get(wid, 0) + 1
    here = placement_ids(entries, screen, screen_id)

    def alive(entry: dict[str, Any]) -> bool:
        return not str(entry.get("superseded_by") or "").strip()

    def reaches(entry: dict[str, Any]) -> int:
        """How many screens of the matrix this entry is linked to, through any evidence it cites."""
        return len(set().union(*(by_evidence.get(t, set()) for t in entry.get("evidence_ids") or [])) & every)

    def placed(entry: dict[str, Any]) -> tuple[str, list[str]] | None:
        """(how, through) when the entry belongs to this screen, None when it does not.

        A person's placement (`screens`) decides alone. Otherwise the evidence it shares with the
        screen's rows does, and an item cited by most screens places nothing while the entry has
        any narrower one: it is the narrow one that says where the entry lives. An entry whose
        only link is broad is cross-cutting - listed, and not owed a row in this screen's plan.
        """
        declared = entry.get("screens")
        if isinstance(declared, list) and declared:
            hit = sorted(here.intersection(str(s) for s in declared))
            return ("placed", hit) if hit else None
        cites = [t for t in entry.get("evidence_ids") or [] if by_evidence.get(t)]
        shared = sorted(used.intersection(cites))
        if not shared:
            return None
        if any(t not in broad for t in cites):
            narrow = [t for t in shared if t not in broad]
            return ("evidence", narrow) if narrow else None
        return ("cross-cutting", shared)

    rules, risks, cross = [], [], []
    for e in entries:
        namespace = e.get("namespace")
        if not alive(e) or namespace not in (RULE_NAMESPACE, *RISK_NAMESPACES):
            continue
        if namespace != RULE_NAMESPACE and str(e.get("resolved_by") or "").strip():
            continue
        found = placed(e)
        if found is None:
            continue
        how, through = found
        row = {"id": e["id"], "title": e.get("title"), "through": through, "screens": reaches(e), "how": how}
        if namespace != RULE_NAMESPACE:
            row["severity"] = e.get("severity")
        (cross if how == "cross-cutting" else rules if namespace == RULE_NAMESPACE else risks).append(row)
    all_rules = sum(1 for e in entries if e.get("namespace") == RULE_NAMESPACE and alive(e))
    return {
        "rows": len(mine), "workflows": dict(sorted(workflows.items())),
        "evidence_ids": sorted(used),
        "evidence_missing": sorted(used - evidence_ids) if evidence_ids is not None else [],
        "evidence_checked": evidence_ids is not None,
        "rules": rules, "rules_in_register": all_rules, "risks": risks, "cross_cutting": cross,
        "broad_evidence": sorted(broad & used), "broad_threshold": threshold,
        "screens_in_matrix": len(every),
    }


def sections(text: str, wanted: re.Pattern[str]) -> str | None:
    """The body under the first heading matching `wanted`, up to the next heading of the same or a higher level."""
    lines = text.splitlines()
    for start, line in enumerate(lines):
        match = HEADING.match(line)
        if match and wanted.search(match.group(2)):
            level, body = len(match.group(1)), []
            for follower in lines[start + 1:]:
                nxt = HEADING.match(follower)
                if nxt and len(nxt.group(1)) <= level:
                    break
                body.append(follower)
            return "\n".join(body)
    return None


def check_plan(plan: Path, scope: dict[str, Any], decisions: dict[str, Any]) -> dict[str, Any]:
    try:
        text = plan.read_text(encoding="utf-8-sig")
    except OSError as error:
        raise sd.Problem(f"{plan} cannot be read: {error}") from error
    mapping, gap = sections(text, MAPPING_HEADING), sections(text, GAP_HEADING)
    in_mapping = set(RULE_ID.findall(mapping or ""))
    in_gap = set(DECISION_ID.findall(gap or ""))
    # A decision the screen proceeds on, or that blocks only a workflow it is a step of, has to be
    # visible in the plan as an `open` row; one a decided policy settled, and one nobody names, does not.
    owed = [i["id"] for i in decisions["proceeding_on_default"] + decisions["blocking_by_workflow"]
            if DECISION_ID.fullmatch(i["id"])]
    return {
        "mapping_section": mapping is not None, "gap_section": gap is not None,
        "rules_uncovered": [r["id"] for r in scope["rules"] if r["id"] not in in_mapping],
        "decisions_uncited": [d for d in owed if d not in in_gap],
    }


def findings_of(scope: dict[str, Any], decisions: dict[str, Any], plan: dict[str, Any] | None,
                screen: str) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []
    if scope["rows"] == 0:
        found.append({"gate": "G1", "text": f"no traceability row names `{screen}`, so there is nothing to plan the screen from; "
                      "match it to a registered screen by hand, or the screen is missing from the extraction"})
    for missing in scope["evidence_missing"]:
        found.append({"gate": "G1", "text": f"the matrix cites {missing}, which is not in Evidence.json"})
    for item in decisions["blocking_directly"]:
        found.append({"gate": "pre-flight", "text": f"{item['id']} has no default and names this screen: {item['title']}"})
    if plan is not None:
        if not plan["mapping_section"]:
            found.append({"gate": "G2", "text": "the plan has no Legacy-To-New Mapping section"})
        if not plan["gap_section"]:
            found.append({"gate": "G2", "text": "the plan has no Gap Matrix section"})
        for rid in plan["rules_uncovered"]:
            found.append({"gate": "G2", "text": f"{rid} is in this screen's scope and the mapping section does not cite it"})
        for did in plan["decisions_uncited"]:
            found.append({"gate": "G2", "text": f"{did} is open and names this screen, and the gap matrix does not cite it"})
    return found


def disposition_of(risk_id: str, queue: dict[str, Any] | None) -> str:
    """Where a risk's disposition stands, as the queue says it: the part Stage 1's
    "Legacy versus new system" section used to be written by hand."""
    if queue is None:
        return "no queue read"
    for item in queue.get("items") or []:
        if isinstance(item, dict) and item.get("id") == risk_id:
            if item.get("bucket") == "settled":
                return f"settled by {item.get('settled_by')}: {item.get('disposition')}"
            return "open, proceeding on its Mitigation" if item.get("posture") != "BLOCKING" else "open, no default"
    for item in queue.get("closed") or []:
        if isinstance(item, dict) and item.get("id") == risk_id:
            return f"decided: {item.get('disposition') or 'recorded'}"
    return "not in the queue"


def build(ak: Path, screen: str, plan: Path | None, screen_id: str | None) -> dict[str, Any]:
    register = optional(ak, "*_Identifiers.json", "register")
    matrix = optional(ak, "*_TraceabilityMatrix.csv", "matrix")
    queue = optional(ak, "*_DecisionQueue.json", "queue")
    evidence = optional(ak, "*_Evidence.json", "evidence")
    if register is None or matrix is None:
        raise sd.Problem(f"{ak} needs an Identifiers.json and a TraceabilityMatrix.csv; "
                         f"found {'no register' if register is None else 'no matrix'}")
    entries = [e for e in (read_json(register).get("entries") or []) if isinstance(e, dict)]
    ids = None
    if evidence is not None:
        ids = {str(i.get("id")) for i in (read_json(evidence).get("items") or []) if isinstance(i, dict) and i.get("id")}
    scope = scope_of(entries, matrix_rows(matrix), ids, screen, screen_id)
    empty = {"blocking_directly": [], "blocking_by_workflow": [], "proceeding_on_default": [],
             "settled_by_policy": [], "screen_ids": [], "workflows": [], "open_items_elsewhere": 0,
             "open_items_unattached": 0, "matrix_read": True}
    queue_data = sd.read_queue(queue) if queue is not None else None
    decisions = sd.build(queue_data, screen, matrix, screen_id) if queue_data is not None else empty
    for risk in scope["risks"] + [c for c in scope["cross_cutting"] if "severity" in c]:
        risk["disposition"] = disposition_of(risk["id"], queue_data)
    checked = check_plan(plan, scope, decisions) if plan is not None else None
    return {"screen": screen, "scope": scope, "decisions": decisions, "queue_present": queue is not None,
            "plan": checked, "findings": findings_of(scope, decisions, checked, screen)}


def spread(item: dict[str, Any], scope: dict[str, Any]) -> str:
    """How widely the link reaches. An item linked to most screens is a cross-cutting one the
    evidence cannot place on this screen in particular."""
    return f"(reaches {item['screens']} of {scope['screens_in_matrix']} screens)"


def placement(item: dict[str, Any], scope: dict[str, Any]) -> str:
    if item.get("how") == "placed":
        return f"(placed here by a person: {', '.join(item['through'])})"
    return f"(through {', '.join(item['through'])}) {spread(item, scope)}"


def render(report: dict[str, Any]) -> str:
    scope, decisions = report["scope"], report["decisions"]
    out = [f"Scope of `{report['screen']}`", ""]
    flows = ", ".join(f"{w} ({n} step{'s' if n != 1 else ''})" for w, n in scope["workflows"].items()) or "none"
    out.append(f"- Traceability rows: {scope['rows']}; workflows: {flows}")
    out.append(f"- Evidence cited: {len(scope['evidence_ids'])}"
               + ("" if scope["evidence_checked"] else " (no Evidence.json, so not checked)")
               + (f"; missing from Evidence.json: {', '.join(scope['evidence_missing'])}" if scope["evidence_missing"] else ""))
    out.append(f"- Business rules in scope: {len(scope['rules'])} of {scope['rules_in_register']} in the register "
               "(placed by a person, or linked by evidence specific to this screen; still a superset)")
    for rule in scope["rules"]:
        out.append(f"    {rule['id']}  {rule['title']}  {placement(rule, scope)}")
    out.append(f"- Open risks in scope: {len(scope['risks'])}")
    for risk in scope["risks"]:
        out.append(f"    {risk['id']} [{risk['severity']}]  {risk['title']}  {placement(risk, scope)} -> {risk['disposition']}")
    if scope["cross_cutting"]:
        out.append(f"- Cross-cutting, not placed on this screen: {len(scope['cross_cutting'])}. Linked only through "
                   f"evidence that {scope['broad_threshold']} or more screens cite "
                   f"({', '.join(scope['broad_evidence'])}); the plan cites one only if it applies. "
                   "Place one with `$ak decisions --place <id>=<F-id> --by <name>`")
        for item in scope["cross_cutting"]:
            tail = f" -> {item['disposition']}" if "disposition" in item else ""
            out.append(f"    {item['id']}  {item['title']}  {spread(item, scope)}{tail}")
    if report["queue_present"]:
        out.append(f"- Decisions: {len(decisions['blocking_directly'])} blocking and naming the screen, "
                   f"{len(decisions['blocking_by_workflow'])} blocking a workflow through it, "
                   f"{len(decisions['proceeding_on_default'])} proceeding on a default "
                   "(`screen_decisions.py` lists them)")
    else:
        out.append("- Decisions: no DecisionQueue.json, so none read")
    out.append("")
    if report["findings"]:
        out.append(f"## Findings ({len(report['findings'])})")
        out += [f"- {f['gate']}: {f['text']}" for f in report["findings"]]
    else:
        out.append("No findings.")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--ak", required=True, type=Path, help="the directory holding the extraction's registers (AK_RUN_DIR)")
    parser.add_argument("--screen", required=True, help="the `screen` value of Screens_Registry.md, verbatim")
    parser.add_argument("--plan", type=Path, help="Screen_plans/<screen>.md: also check gate G2 against it")
    parser.add_argument("--screen-id", help="the screen's F- identifier, when the queue never titles it")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        report = build(args.ak, sd.norm(args.screen), args.plan, args.screen_id)
    except sd.Problem as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n" if args.json
                     else render(report))
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
