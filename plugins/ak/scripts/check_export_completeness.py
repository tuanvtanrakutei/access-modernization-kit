#!/usr/bin/env python3
"""Record the shape of every object's definition text, and compare it with last time.

The gap this closes is A15: integrity was verified and completeness was not, so A05's
first export passed every gate carrying 21 of a form's 45 procedures. The reasoning
for why this is a record-and-compare rather than a check lives in
`contracts/export_completeness.py`; the short version is that one observation of a
file cannot tell you whether the exporter wrote all of it.

    $ak completeness            compare against the last record, then update it
    $ak completeness --dry-run  compare and report, write nothing

It reads the definition text the newest bundle carries and the text staging holds -
the same two places `derive_graph_facts` reads, through the same function, because two
readers disagreeing about where the text is would be a defect of exactly the kind this
file exists to find. An object present in both is compared across the routes as well:
that is the comparison that was available on A05 all along and that nobody had made.

Exit codes: 0 when nothing is reported, 1 when something is. It is a report, not a
gate - nothing in the pipeline refuses to run because of it, because a disagreement
about an object's size is a question for a person, not a verdict.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import export_completeness as completeness  # noqa: E402
import workspace as workspace_contract  # noqa: E402

import derive_graph_facts as deriver  # noqa: E402

RECORD = "object-shapes.json"


def staging_texts(space: Any) -> dict[tuple[str, str, str], str]:
    """Definition text the managed route left in staging, by (database, kind, label).

    Keyed the way the bundle is, so an object acquired both ways lines up. The kinds
    are the staging directory names; `queries` is dropped because a saved query's SQL
    has no `Begin` blocks and no procedures, and a shape record of zeros compared with
    another zero says nothing.
    """
    found: dict[tuple[str, str, str], str] = {}
    root = space.staging_root()
    if not root.is_dir():
        return found
    for kind, folder in (("form", "forms"), ("report", "reports"),
                         ("macro", "macros"), ("module", "vba")):
        for path in sorted(root.glob(f"*/*/{folder}/*.txt")):
            database = path.parts[-4]
            found[(database, kind, path.stem)] = deriver.read_text(path)
    return found


def observations(space: Any, bundle: Path | None) -> dict[str, dict[str, Any]]:
    """Every object the workspace can see text for, with its shape and where it came from."""
    seen: dict[str, dict[str, Any]] = {}
    from_bundle = deriver.bundle_texts(bundle)
    from_staging = staging_texts(space)
    for key in sorted(set(from_bundle) | set(from_staging)):
        database, kind, label = key
        entry: dict[str, Any] = {"database_id": database, "kind": kind, "name": label}
        if key in from_bundle:
            entry["bundle"] = completeness.shape_of(from_bundle[key][0]).to_json()
        if key in from_staging:
            entry["staging"] = completeness.shape_of(from_staging[key]).to_json()
        seen[f"{database}:{kind}:{label}"] = entry
    return seen


def report(current: dict[str, dict[str, Any]],
           previous: dict[str, dict[str, Any]]) -> list[str]:
    """Everything worth a person's attention, in the order they should read it."""
    lines: list[str] = []

    for key, entry in current.items():
        for route in ("bundle", "staging"):
            shape = completeness.from_json(entry.get(route))
            if shape is not None and not shape.balanced:
                lines.append(f"UNBALANCED  {key} ({route}): {shape.imbalance}")

    # The two routes reading one object. Available on A05 from the day the frontend was
    # acquired twice, and never once made.
    for key, entry in current.items():
        in_bundle = completeness.from_json(entry.get("bundle"))
        in_staging = completeness.from_json(entry.get("staging"))
        if in_bundle is None or in_staging is None:
            continue
        for problem in completeness.disagreements(in_staging, in_bundle):
            lines.append(f"ROUTES      {key}: {problem}")

    # The same object, this run against the last.
    for key, entry in current.items():
        was = previous.get(key) or {}
        for route in ("bundle", "staging"):
            before = completeness.from_json(was.get(route))
            now = completeness.from_json(entry.get(route))
            if before is None or now is None:
                continue
            for problem in completeness.disagreements(before, now):
                lines.append(f"CHANGED     {key} ({route}): {problem}")

    gone = sorted(set(previous) - set(current))
    for key in gone:
        lines.append(f"MISSING     {key}: recorded last time, no text for it now")
    return lines


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    space = workspace_contract.Workspace(args.app_root)
    bundles = workspace_contract.find_bundle_dirs(space)
    bundle = (max(bundles, key=lambda p: (p / "bundle.json").stat().st_mtime)
              if bundles else None)

    current = observations(space, bundle)
    record_path = space.extracted(RECORD)
    previous: dict[str, dict[str, Any]] = {}
    if record_path.is_file():
        try:
            previous = json.loads(record_path.read_text(encoding="utf-8")).get("objects") or {}
        except (ValueError, OSError):
            previous = {}

    if not current and not previous:
        print(f"no object definition text under {space.root}; nothing to measure")
        return 0
    # A workspace that had text and now has none is the loudest case there is, so it
    # falls through to the report rather than out of it.

    problems = report(current, previous)
    both = sum(1 for e in current.values() if "bundle" in e and "staging" in e)
    print(f"{len(current)} object(s) measured, {both} of them acquired by both routes"
          + (f", {len(previous)} compared with the last record" if previous
             else ", nothing recorded before this run"))

    for line in problems:
        print(line)
    if not problems:
        print("nothing to report: no unbalanced definition, no disagreement about size")
    elif not previous:
        # Said plainly so the first run is not read as a clean bill of health.
        print("\nThis is the first record. A single export cannot be checked for "
              "completeness - what it can do is give the next one something to "
              "disagree with.")

    if not args.dry_run:
        # An object the workspace can no longer read keeps its recorded shape. Writing
        # only what is currently readable would report the disappearance once and then
        # forget it, which is the same silence this whole file is about: the run after
        # would compare against nothing and say all is well. Removing it for good is a
        # deletion from this file, by a person who means it.
        carried = {key: value for key, value in previous.items() if key not in current}
        record_path.parent.mkdir(parents=True, exist_ok=True)
        io.open(record_path, "w", encoding="utf-8", newline="\n").write(
            json.dumps({"objects": {**carried, **current}},
                       ensure_ascii=False, indent=1) + "\n")
        print(f"\nrecorded {len(current)} shape(s) in {record_path}"
              + (f", {len(carried)} kept from a run that could still read them"
                 if carried else ""))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
