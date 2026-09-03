#!/usr/bin/env python3
"""Check that every evidence id a phase document cites actually exists.

A phase document's authority rests on its citations. A reader who cannot follow
`A05-P2-FLOW-020` back to a statement, a source file and a confidence has no way to
tell a measured figure from a remembered one - and the document reads exactly the
same either way. So an unresolvable citation is not a formatting slip; it is the
failure this pipeline exists to prevent.

Two real defects motivate the two checks here, both found in one run:

A whole phase's items were generated with a sequence continuing from the previous
phase's item count, so the first item was numbered 021 while the document, written
first, cited 001. Twenty-three citations resolved to nothing.

And a question cited the right task name at the wrong sequence - numbers that
belonged to a different task entirely. That one had survived an earlier hand-rolled
check whose pattern matched `[A-Z]+` and so never tested a task name containing an
underscore. A validator that silently skips a whole id format reports "pass" while
missing every case in it, which is worse than not running.

The reverse direction is reported but never fatal. An evidence item no document
cites is normal - the register is allowed to hold more than the prose quotes - but a
phase whose items are mostly uncited is usually a phase that was written before its
evidence, and worth seeing.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
from pathlib import Path

# Task names carry underscores and digits (TABLE_INVENTORY, DATA_TYPES). Matching
# only [A-Z]+ skips them, which is the bug described above.
CITATION_RE = re.compile(r"\b[A-Z][A-Z0-9]*-P\d+-[A-Z][A-Z0-9_]*-\d{3}\b")


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, OSError):
            continue
    return ""


def cited_in_documents(paths: list[Path]) -> dict[str, list[str]]:
    """Map each cited id to the documents citing it."""
    found: dict[str, list[str]] = {}
    for path in paths:
        for identifier in sorted(set(CITATION_RE.findall(read_text(path)))):
            found.setdefault(identifier, []).append(path.name)
    return found


def cited_in_matrix(path: Path) -> dict[str, list[str]]:
    """Read the traceability matrix's evidence_ids column, which is `;`-separated."""
    if not path.is_file():
        return {}
    found: dict[str, list[str]] = {}
    with io.open(path, encoding="utf-8", newline="") as handle:
        for row_number, row in enumerate(csv.DictReader(handle), start=2):
            for identifier in (row.get("evidence_ids") or "").split(";"):
                identifier = identifier.strip()
                if identifier:
                    found.setdefault(identifier, []).append(f"{path.name}:{row_number}")
    return found


def unresolvable_sources(items: list, workspace_root: Path) -> dict[str, str]:
    """Evidence items whose cited `source_path` names nothing on disk.

    An evidence item's value is that a reader can follow it back to the file. This
    check exists because a workspace layout migration moved every acquired file and
    left 66 of 67 items citing the old location; every other check still passed, and
    would have gone on passing, because they all read the register against the
    documents and never against the filesystem.

    A path outside the workspace, or one naming something that is not a path at all
    (`operator screenshot`), is not reported: the check is for citations that were
    meant to resolve and no longer do.
    """
    broken: dict[str, str] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        cited = (item.get("source_path") or "").strip()
        if not cited or " " in cited.rstrip("/") and "/" not in cited:
            continue
        candidate = (workspace_root / cited).resolve()
        try:
            candidate.relative_to(workspace_root)
        except ValueError:
            continue
        if not candidate.exists():
            broken[item.get("id", "?")] = cited
    return broken


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--outputs", required=True, type=Path,
        help="directory holding the phase documents and *_Evidence.json",
    )
    parser.add_argument(
        "--evidence", type=Path,
        help="evidence register; defaults to the single *_Evidence.json under --outputs",
    )
    parser.add_argument(
        "--matrix", type=Path,
        help="traceability matrix; defaults to the single *TraceabilityMatrix.csv there",
    )
    parser.add_argument(
        "--workspace", type=Path,
        help="workspace root the cited source_path values are relative to; "
             "defaults to two levels above --outputs, which is where output/ sits",
    )
    parser.add_argument(
        "--json", action="store_true", help="emit a machine-readable report",
    )
    return parser.parse_args()


def sole_match(outputs: Path, pattern: str, explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit
    matches = sorted(outputs.glob(pattern))
    return matches[0] if len(matches) == 1 else None


def main() -> int:
    args = parse_args()
    outputs: Path = args.outputs
    if not outputs.is_dir():
        print(f"error: no such directory: {outputs}", file=sys.stderr)
        return 2

    evidence_path = sole_match(outputs, "*_Evidence.json", args.evidence)
    if evidence_path is None or not evidence_path.is_file():
        print(f"error: no evidence register found under {outputs}", file=sys.stderr)
        return 2
    register = json.loads(read_text(evidence_path) or "{}")
    items = register.get("items") or []
    known = {item["id"] for item in items if isinstance(item, dict) and item.get("id")}
    phase_of = {
        item["id"]: item.get("phase")
        for item in items
        if isinstance(item, dict) and item.get("id")
    }

    documents = sorted(p for p in outputs.glob("*.md") if p.is_file())
    cited = cited_in_documents(documents)
    matrix_path = sole_match(outputs, "*TraceabilityMatrix.csv", args.matrix)
    matrix = cited_in_matrix(matrix_path) if matrix_path else {}

    everywhere: dict[str, list[str]] = {}
    for source in (cited, matrix):
        for identifier, where in source.items():
            everywhere.setdefault(identifier, []).extend(where)

    workspace_root = (args.workspace or outputs.parent).resolve()
    unresolvable = unresolvable_sources(items, workspace_root)

    dangling = {i: w for i, w in sorted(everywhere.items()) if i not in known}
    uncited = sorted(known - set(everywhere))
    by_phase: dict[str, dict[str, int]] = {}
    for identifier in known:
        phase = str(phase_of.get(identifier))
        counts = by_phase.setdefault(phase, {"items": 0, "cited": 0})
        counts["items"] += 1
        if identifier in everywhere:
            counts["cited"] += 1

    report = {
        "evidence": str(evidence_path),
        "items": len(known),
        "documents": [p.name for p in documents],
        "matrix": matrix_path.name if matrix_path else None,
        "cited": len(everywhere),
        "dangling": dangling,
        "uncited": uncited,
        "by_phase": by_phase,
        "workspace": str(workspace_root),
        "unresolvable_sources": unresolvable,
        "status": "FAIL" if dangling or unresolvable else "PASS",
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{report['status']}: {len(known)} evidence items, "
              f"{len(everywhere)} cited across {len(documents)} document(s)"
              + (f" and {matrix_path.name}" if matrix_path else ""))
        for phase in sorted(by_phase):
            counts = by_phase[phase]
            print(f"  phase {phase}: {counts['cited']} of {counts['items']} items cited")
        for identifier, where in dangling.items():
            print(f"  DANGLING {identifier} <- {', '.join(sorted(set(where)))}")
        if uncited:
            print(f"  uncited (not an error): {len(uncited)} item(s)")
        if unresolvable:
            print(f"  {len(unresolvable)} item(s) cite a path that does not exist "
                  f"under {workspace_root}:")
            for identifier, cited in sorted(unresolvable.items())[:6]:
                print(f"    {identifier} -> {cited}")

    return 1 if dangling or unresolvable else 0


if __name__ == "__main__":
    raise SystemExit(main())
