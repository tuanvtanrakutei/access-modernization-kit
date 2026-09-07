#!/usr/bin/env python3
"""Reclaim what a workspace no longer needs, and nothing else.

Acquisition removes its own snapshots from 2.9.0 onward, but a workspace acquired
before that keeps them, and on a real split application that is 615 MB of copies
sitting beside 587 MB of originals - a workspace holding 1.2 GB to analyse about
3 MB of text. Workspaces from before the Graphify removal also carry a `graphify-out/`
tree nothing reads any more.

Reports by default and deletes only when told to, because the whole point of the
command is that a person should see what is about to go before it goes.

What it will never touch, whatever is asked, in either layout:

  input/ (sources/)              what a person supplied. The kit does not own it.
  output/                        the published documents.
  .ak/staging/ (acquired/…)      what extraction read out. This is the evidence.
  .ak/bundles/ (acquired/…)      sealed bundles every phase reads from.
  .ak/runs/ (runs/)              run state and evidence registers.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

# Each entry: relative path, why it can go, and what would be lost - which is the
# part an operator needs in order to say yes.
RECLAIMABLE: tuple[tuple[str, str, str], ...] = (
    (
        "acquired/snapshots",
        "Disposable copies of the declared databases",
        "Nothing. The originals are in sources/, and each receipt records the "
        "snapshot's SHA-256, so a later run can still prove what was read.",
    ),
    (
        "acquired/staging/_snapshots",
        "Disposable copies, in the pre-2.9.0 location inside staging",
        "Nothing, as above. Only the copies are removed; the extraction output "
        "beside them in staging is untouched.",
    ),
    (
        ".ak/snapshots",
        "Disposable copies of the declared databases",
        "Nothing. The originals are in input/, and each receipt records the "
        "snapshot's SHA-256.",
    ),
    (
        "graphify-out",
        "Corpus and graph for a component removed in 2.9.0",
        "Nothing. No code reads this path any more.",
    ),
)

PROTECTED = (
    "sources", "acquired/staging", "acquired/bundles", "runs", "decisions", "shared-docs",
    "input", "output", ".ak/staging", ".ak/bundles", ".ak/runs",
)


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def survey(app_root: Path) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for relative, what, cost in RECLAIMABLE:
        target = app_root / relative
        if not target.is_dir():
            continue
        found.append({
            "path": relative,
            "what": what,
            "losing": cost,
            "bytes": directory_size(target),
            "files": sum(1 for item in target.rglob("*") if item.is_file()),
        })
    return found


def _is_protected(app_root: Path, target: Path) -> bool:
    """A guard against this command ever growing an entry that eats the evidence."""
    resolved = target.resolve()
    if resolved == app_root.resolve():
        return True
    for relative in PROTECTED:
        protected = (app_root / relative).resolve()
        if resolved == protected:
            return True
    return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument(
        "--delete", action="store_true",
        help="Actually remove. Without this the command only reports.",
    )
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    app_root: Path = args.app_root.expanduser().resolve()
    if not app_root.is_dir():
        print(f"error: no such workspace: {app_root}", file=sys.stderr)
        return 2

    found = survey(app_root)
    total = sum(entry["bytes"] for entry in found)
    removed: list[str] = []

    if args.delete:
        for entry in found:
            target = app_root / entry["path"]
            if _is_protected(app_root, target):
                print(f"refusing to remove protected path: {entry['path']}", file=sys.stderr)
                return 2
            shutil.rmtree(target, ignore_errors=True)
            removed.append(entry["path"])
            parent = target.parent
            if parent.is_dir() and parent != app_root and not any(parent.iterdir()):
                parent.rmdir()

    report = {
        "app_root": str(app_root),
        "reclaimable": found,
        "total_bytes": total,
        "total_mb": round(total / (1024 * 1024), 1),
        "deleted": removed,
        "mode": "deleted" if args.delete else "reported",
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif not found:
        print(f"Nothing to reclaim under {app_root}")
    else:
        verb = "Removed" if args.delete else "Would remove"
        print(f"{verb} {report['total_mb']} MB from {app_root}")
        for entry in found:
            print(f"  {entry['path']}  —  {round(entry['bytes'] / (1024 * 1024), 1)} MB, "
                  f"{entry['files']} file(s)")
            print(f"      {entry['what']}")
            print(f"      losing: {entry['losing']}")
        if not args.delete:
            print("\nNothing has been removed. Pass --delete to do it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
