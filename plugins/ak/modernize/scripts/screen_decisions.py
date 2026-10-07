#!/usr/bin/env python3
"""List what is still undecided about one screen, from the extraction's decision queue.

Reports only. It never writes a project file - machine detects, human decides, agent
executes. Pre-flight runs it before Stage 1, so a screen is not planned over a question
the extraction raised and nobody has answered.

The queue (`{APP_ID}_DecisionQueue.json`, written by `$ak decisions`) holds every open
question, unknown and risk the five phases raised, with who can answer, what each one
blocks, and what the pipeline proceeds on meanwhile (an assumption, or the risk's own
Mitigation). An item with no default is BLOCKING and stops only what it names; one with
a default proceeds on it. This script says which of those name this screen.

An item names a screen two ways, and both are exact:

  directly        its `blocks` lists the screen's `F-` identifier, or `object:<name>`
                  with the screen's production name. The `F-` is found from the queue
                  itself: the identifier whose title is the screen's name.
  by a workflow   its `blocks` lists a `WF-` that `TraceabilityMatrix.csv` says passes
                  through the screen (its `screen` column equals the name).

Nothing here guesses that two strings mean the same screen. `LEGACY_EVIDENCE.md` 6.3
explains why: a script that matches names loosely is an unverifiable guess, and a screen
that cannot be matched is a finding to raise, not to resolve silently. So an item that
names neither this screen nor one of its workflows is not listed against it, and the
counts of those that name something else and of those that name nothing are printed, so
that "nothing found" never reads as "nothing open": a risk's disposition names nothing
until the decider settles what it blocks, and no screen sees it from here.

Exit status: 0 when no BLOCKING item names the screen directly, 1 when one does (pre-flight
stops, as it does for a blocker row in `Known_Issues.md`), 2 when an input cannot be read.
A BLOCKING item that reaches the screen only through a workflow is listed and does not stop
pre-flight: the workflow cannot be finalised, and this screen is one step of it.

Stdlib only, so it runs in a project that has installed nothing.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import unicodedata
from pathlib import Path
from typing import Any

OBJECT_PREFIX = "object:"
QUEUE_GLOB = "*_DecisionQueue.json"
MATRIX_GLOB = "*_TraceabilityMatrix.csv"


class Problem(Exception):
    """An input that cannot be read. The message says which."""


def norm(text: Any) -> str:
    """Comparable form of a name: Unicode-normalised, whitespace collapsed. Never case-folded or fuzzy."""
    return " ".join(unicodedata.normalize("NFC", str(text or "")).split())


def find_one(where: Path, pattern: str, what: str) -> Path:
    if where.is_file():
        return where
    found = sorted(where.glob(pattern)) or sorted(where.glob(f"*/{pattern}"))
    if len(found) != 1:
        raise Problem(f"{what}: expected exactly one {pattern} under {where}, found {len(found)}")
    return found[0]


def read_queue(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as error:
        raise Problem(f"{path} cannot be read: {error}") from error
    if not isinstance(data, dict) or not isinstance(data.get("items"), list):
        raise Problem(f"{path} is not a decision queue (no `items` list)")
    return data


def workflows_through(matrix: Path | None, screen: str) -> set[str]:
    """The `WF-` ids whose traceability rows name this screen, by exact name."""
    if matrix is None:
        return set()
    try:
        with matrix.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except OSError as error:
        raise Problem(f"{matrix} cannot be read: {error}") from error
    return {str(r.get("workflow_id") or "").strip() for r in rows
            if norm(r.get("screen")) == screen and str(r.get("workflow_id") or "").strip()}


def screen_ids(items: list[dict[str, Any]], screen: str) -> set[str]:
    """The `F-` identifiers the queue titles with this screen's production name."""
    found: set[str] = set()
    for item in items:
        for ref in item.get("blocks") or []:
            if isinstance(ref, dict) and str(ref.get("id") or "").startswith("F-") and norm(ref.get("title")) == screen:
                found.add(str(ref["id"]))
    return found


def link(item: dict[str, Any], screen: str, ids: set[str], workflows: set[str]) -> dict[str, Any] | None:
    """How an item names the screen, or None. Direct beats workflow when both hold."""
    via_workflow: list[str] = []
    for ref in item.get("blocks") or []:
        if not isinstance(ref, dict):
            continue
        if ref.get("id") in ids or (ref.get("object") is not None and norm(ref["object"]) == screen):
            return {"how": "directly", "through": ref.get("id") or f"{OBJECT_PREFIX}{ref['object']}"}
        if ref.get("id") in workflows:
            via_workflow.append(str(ref["id"]))
    return {"how": "by a workflow", "through": ", ".join(via_workflow)} if via_workflow else None


def describe_default(default: Any) -> str:
    if not default:
        return "none: it blocks what it names"
    if default.get("mitigation"):
        return "the risk's own Mitigation"
    text = str(default.get("id") or "")
    return f"{text} {default['title']}".strip() if default.get("title") else text


def build(queue: dict[str, Any], screen: str, matrix: Path | None, screen_id: str | None = None) -> dict[str, Any]:
    items = [i for i in queue["items"] if isinstance(i, dict)]
    ids = screen_ids(items, screen) | ({screen_id} if screen_id else set())
    workflows = workflows_through(matrix, screen)
    listed: list[dict[str, Any]] = []
    elsewhere = unattached = 0
    for item in items:
        if item.get("bucket") == "settled":
            continue
        found = link(item, screen, ids, workflows)
        if found is None:
            if any(isinstance(r, dict) and (r.get("id") or r.get("object")) for r in item.get("blocks") or []):
                elsewhere += 1
            else:
                unattached += 1
            continue
        listed.append({
            "id": item["id"], "kind": item.get("kind"), "title": item.get("title"),
            "posture": item.get("posture"), "bucket": item.get("bucket"),
            "named": found["how"], "through": found["through"],
            "default": describe_default(item.get("default")),
            "party": item.get("party"), "if_wrong": (item.get("default") or {}).get("if_wrong"),
            "precheck": item.get("precheck") or [],
        })
    settled = [{"id": i["id"], "settled_by": i.get("settled_by"), "disposition": i.get("disposition"),
                "named": link(i, screen, ids, workflows)["how"]}
               for i in items if i.get("bucket") == "settled" and link(i, screen, ids, workflows)]
    return {
        "screen": screen, "screen_ids": sorted(ids), "workflows": sorted(workflows),
        "blocking_directly": [i for i in listed if i["posture"] == "BLOCKING" and i["named"] == "directly"],
        "blocking_by_workflow": [i for i in listed if i["posture"] == "BLOCKING" and i["named"] != "directly"],
        "proceeding_on_default": [i for i in listed if i["posture"] != "BLOCKING"],
        "settled_by_policy": settled,
        "open_items_elsewhere": elsewhere, "open_items_unattached": unattached,
        "matrix_read": matrix is not None,
    }


def render(report: dict[str, Any]) -> str:
    out = [f"Decisions about `{report['screen']}`", ""]
    if not report["screen_ids"]:
        out.append("- No F- identifier carries this name in the queue, so only `object:` references name it.")
    else:
        out.append(f"- Screen identifier: {', '.join(report['screen_ids'])}")
    out.append("- Workflows through it: " + (", ".join(report["workflows"]) if report["workflows"] else
               ("none in the traceability matrix" if report["matrix_read"] else "not read (no TraceabilityMatrix.csv given)")))
    out.append("")
    sections = (("BLOCKING and naming this screen: pre-flight stops", "blocking_directly"),
                ("BLOCKING through a workflow: listed, pre-flight proceeds", "blocking_by_workflow"),
                ("Proceeding on a default", "proceeding_on_default"))
    for heading, key in sections:
        rows = report[key]
        out.append(f"## {heading} ({len(rows)})")
        for row in rows:
            out.append(f"- {row['id']} [{row['kind']}] {row['title']}  (named {row['named']} by {row['through']}; "
                       f"default: {row['default']}; ask: {row['party']})")
            if row["if_wrong"]:
                out.append(f"    if the default is wrong: {row['if_wrong']}")
            for flag in row["precheck"]:
                out.append(f"    check before asking: {flag.get('text')}")
        if key == "blocking_directly" and rows:
            # The stop is right - there is nothing to proceed on - and it is not a dead end.
            out.append("To plan before it is answered, the decider records what to proceed on: "
                       "`$ak decisions --assume <id> --that <assumption> --if-wrong <what changes> "
                       "--by <name>`. The item stays open, and its answer is checked against it.")
        out.append("")
    if report["settled_by_policy"]:
        out.append(f"## Settled by standing policy ({len(report['settled_by_policy'])})")
        for row in report["settled_by_policy"]:
            out.append(f"- {row['id']}: {row['settled_by']} -> {row['disposition']} (named {row['named']})")
        out.append("")
    out.append(f"Not listed here: {report['open_items_elsewhere']} open item(s) that name something else, and "
               f"{report['open_items_unattached']} that name nothing at all (a risk's disposition does, until its "
               "decider says what it blocks) and so reach no screen from here.")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--queue", required=True, type=Path, help="a DecisionQueue.json, or the directory that holds one")
    parser.add_argument("--screen", required=True, help="the `screen` value of Screens_Registry.md, verbatim")
    parser.add_argument("--matrix", type=Path, help="a TraceabilityMatrix.csv, or the directory that holds one; "
                        "default: the one beside the queue, if any")
    parser.add_argument("--screen-id", help="the screen's F- identifier, when the queue never titles it")
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    args = parser.parse_args(argv)
    # A production name is Japanese. A Windows console or a pipe falls back to the locale's
    # encoding, which cannot print it and turns it into mojibake or an exception.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        queue_path = find_one(args.queue, QUEUE_GLOB, "queue")
        queue = read_queue(queue_path)
        matrix = None
        if args.matrix is not None:
            matrix = find_one(args.matrix, MATRIX_GLOB, "matrix")
        else:
            beside = sorted(queue_path.parent.glob(MATRIX_GLOB)) or sorted(queue_path.parent.parent.glob(MATRIX_GLOB))
            matrix = beside[0] if len(beside) == 1 else None
        report = build(queue, norm(args.screen), matrix, args.screen_id)
    except Problem as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n" if args.json
                     else render(report))
    return 1 if report["blocking_directly"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
