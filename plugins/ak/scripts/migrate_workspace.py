#!/usr/bin/env python3
"""Move a workspace from the pre-2.10.0 layout to the one organised by owner.

The layout changed in 2.10.0 and `contracts/workspace.py` reads both, so nothing
broke and nothing was migrated. A person opening a workspace created before the
change still meets six directories and still finds the documents two levels down in
`runs/<run-id>/outputs/`, which is the thing the new layout exists to stop. Reading
both layouts keeps a run in progress alive; it does not do the move, and no command
did until this one.

What moves:

    sources/<name>/     ->  input/<name>/       renaming reports-out to report-samples
    decisions/          ->  input/decisions/
    shared-docs/        ->  input/shared-docs/
    acquired/staging/   ->  .ak/staging/
    acquired/snapshots/ ->  .ak/snapshots/
    acquired/bundle-*/  ->  .ak/bundles/<name>/ folding the older flat bundle naming in
    extracted/          ->  .ak/extracted/
    runs/               ->  .ak/runs/
    .ak/runs/<newest>/outputs/*  ->  output/

Only the newest run's documents move to `output/`, because `output/` means "the
newest run" and a run-id in the path is a question a reader cannot answer. An older
run keeps its own `outputs/` under `.ak/runs/<id>/`, so nothing is lost - the newest
run's working state stays there too, minus the rendered documents that are now the
top-level `output/`.

Two rewrites come with the move, and skipping either leaves a workspace that reads
as migrated but does not work:

  - `manifest.yaml` source_ref paths still say `sources/...`, and the manifest may
    still carry a `graphify:` block, which the schema no longer accepts at all. Such
    a manifest fails validation whether or not it is migrated; the block is dropped
    here because leaving it means the first command after the move fails on
    something the move was supposed to finish.
  - `.gitignore` and `.investigationignore` name `runs/`, `outputs/`, `graphify-out/`
    and `sources/access/*.mdb`. Left alone they would stop ignoring the raw
    databases - which is what keeps production data out of a commit.

Plans by default and prints what it would do. `--apply` performs it.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

from workspace import INPUT_DIRS, OWNED_DIRS, Workspace  # noqa: E402

# The old `.graphifyignore` describes a tool the kit no longer runs.
DEAD_FILES = (".graphifyignore",)

IGNORE_REWRITES: tuple[tuple[str, str], ...] = (
    ("runs/", ".ak/"),
    ("outputs/drafts/", "output/drafts/"),
    ("outputs/render-cache/", "output/render-cache/"),
    ("!outputs/", "!output/"),
    ("outputs/", "output/"),
    ("sources/access/", "input/access/"),
    ("!extracted/**", "!.ak/extracted/**"),
)


# Every legacy prefix an evidence item, a document or the traceability matrix may
# cite, longest first so `acquired/bundles/` is not eaten by `acquired/bundle`.
#
# This exists because the first version of this script did not. It moved a real
# workspace and left 66 of 67 evidence items citing paths that no longer resolved -
# defeating the one thing the layout docstring says the design rests on, that a cited
# path resolves whether or not the directory sorts near the top of a listing. Moving
# the files is the easy half; the citations are the half that matters.
CITATION_REWRITES: tuple[tuple[str, str], ...] = (
    ("acquired/snapshots/", ".ak/snapshots/"),
    ("acquired/bundles/", ".ak/bundles/"),
    ("acquired/bundle-", ".ak/bundles/bundle-"),
    ("acquired/staging/", ".ak/staging/"),
    ("acquired/bundle", ".ak/bundles"),
    # Bare, with no trailing slash: an item that cites a directory rather than a file.
    ("acquired/staging", ".ak/staging"),
    ("acquired/snapshots", ".ak/snapshots"),
    ("sources/reports-out/", "input/report-samples/"),
    ("sources/", "input/"),
    ("extracted/", ".ak/extracted/"),
)

CITED_RUN_OUTPUTS = re.compile(r"runs/[A-Za-z0-9_.-]+/outputs/")


def rewrite_citation(text: str) -> str:
    """Point a cited path at where the file now is."""
    text = CITED_RUN_OUTPUTS.sub("output/", text)
    for old, new in CITATION_REWRITES:
        text = text.replace(old, new)
    return text


def rewrite_published_citations(root: Path) -> list[str]:
    """Rewrite cited paths across everything in output/.

    Separate from the move, and idempotent, because a workspace someone migrated by
    hand needs this and nothing else.
    """
    published = root / "output"
    if not published.is_dir():
        return []
    changed: list[str] = []
    for path in sorted(published.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in (".json", ".md", ".csv", ".html"):
            continue
        before = path.read_text(encoding="utf-8")
        after = rewrite_citation(before)
        if after != before:
            path.write_text(after, encoding="utf-8", newline="\n")
            changed.append(path.name)
    return changed


def plan(root: Path) -> dict[str, Any]:
    workspace = Workspace(root)
    report: dict[str, Any] = {
        "workspace": str(workspace.root),
        "is_legacy": workspace.is_legacy,
        "moves": [],
        "deletes": [],
        "manifest": [],
        "ignore_files": [],
        "blockers": [],
    }
    if not workspace.is_legacy:
        report["blockers"].append(
            "input/ already exists, so this workspace is already in the current layout"
        )
        return report

    def move(source: Path, destination: Path) -> None:
        if not source.exists():
            return
        if destination.exists() and any(destination.iterdir()):
            report["blockers"].append(
                f"{destination.relative_to(root)} already exists and is not empty"
            )
            return
        report["moves"].append({
            "from": str(source.relative_to(root)),
            "to": str(destination.relative_to(root)),
        })

    # The kit's own areas first. Creating .ak/ does not change how the layout reads;
    # only input/ does, which is why it is planned - and applied - last.
    for name, legacy in OWNED_DIRS.items():
        move(root / legacy, root / ".ak" / name)
    for bundle in sorted((root / "acquired").glob("bundle-*")):
        if (bundle / "bundle.json").is_file():
            move(bundle, root / ".ak" / "bundles" / bundle.name)

    # The newest run's documents become the top-level output/.
    newest = newest_run(root)
    if newest is not None:
        report["moves"].append({
            "from": f"{newest.relative_to(root)}/outputs/*",
            "to": "output/",
            "note": f"run {newest.name}; its working state stays under .ak/runs/{newest.name}/",
        })

    for name, legacy in INPUT_DIRS.items():
        move(root / legacy, root / "input" / name)

    for name in DEAD_FILES:
        if (root / name).is_file():
            report["deletes"].append({"path": name, "why": "describes a tool the kit no longer runs"})

    manifest = root / "manifest.yaml"
    if manifest.is_file():
        text = manifest.read_text(encoding="utf-8")
        if "sources/" in text:
            report["manifest"].append("rewrite source_ref paths from sources/ to input/")
        if re.search(r"^graphify:", text, re.MULTILINE):
            report["manifest"].append(
                "drop the graphify block - the manifest schema no longer accepts it, so "
                "the manifest does not validate until it is gone"
            )

    for name in (".gitignore", ".investigationignore"):
        path = root / name
        if path.is_file() and rewrite_ignore(path.read_text(encoding="utf-8")) != path.read_text(
            encoding="utf-8"
        ):
            report["ignore_files"].append(name)
    return report


def newest_run(root: Path) -> Path | None:
    runs = [p for p in (root / "runs").glob("*") if (p / "outputs").is_dir()]
    if not runs:
        return None
    return max(runs, key=lambda p: (p / "outputs").stat().st_mtime)


def rewrite_ignore(text: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("graphify-out") or "Graphify" in line:
            if stripped.startswith("graphify-out"):
                continue
            line = line.replace(" and Graphify", "")
        for old, new in IGNORE_REWRITES:
            if stripped == old or stripped.startswith(old):
                line = line.replace(old, new, 1)
                break
        lines.append(line)
    return "\n".join(lines) + "\n"


def rewrite_manifest(text: str) -> str:
    text = re.sub(r"(\bvalue:\s*)sources/", r"\1input/", text)
    text = re.sub(r"(\bvalue:\s*)sources\\\\", r"\1input" + chr(92) + chr(92), text)
    # Drop the graphify block: from its key to the next top-level key or end of file.
    text = re.sub(r"^graphify:\n(?:[ \t].*\n|\n)*", "", text, flags=re.MULTILINE)
    return text


def apply(root: Path, report: dict[str, Any]) -> list[str]:
    done: list[str] = []
    newest = newest_run(root)
    outputs = sorted((newest / "outputs").iterdir()) if newest is not None else []

    for entry in report["moves"]:
        if entry["to"] == "output/":
            continue
        source, destination = root / entry["from"], root / entry["to"]
        if not source.exists():
            continue
        # input/ is created last: the layout reads as current the moment it exists,
        # and a half-filled input/ would shadow the sources still waiting to move.
        if entry["to"].startswith("input/"):
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        done.append(f"moved {entry['from']} -> {entry['to']}")

    if outputs:
        published = root / "output"
        published.mkdir(parents=True, exist_ok=True)
        moved_run = root / ".ak" / "runs" / newest.name / "outputs"
        for item in sorted(moved_run.iterdir()) if moved_run.is_dir() else outputs:
            shutil.move(str(item), str(published / item.name))
        if moved_run.is_dir() and not any(moved_run.iterdir()):
            moved_run.rmdir()
        done.append(f"published {len(outputs)} document(s) to output/")

    manifest = root / "manifest.yaml"
    if manifest.is_file():
        before = manifest.read_text(encoding="utf-8")
        after = rewrite_manifest(before)
        if after != before:
            manifest.write_text(after, encoding="utf-8", newline="\n")
            done.append("rewrote manifest.yaml")

    for name in (".gitignore", ".investigationignore"):
        path = root / name
        if not path.is_file():
            continue
        before = path.read_text(encoding="utf-8")
        after = rewrite_ignore(before)
        if after != before:
            path.write_text(after, encoding="utf-8", newline="\n")
            done.append(f"rewrote {name}")

    for entry in report["deletes"]:
        target = root / entry["path"]
        if target.is_file():
            target.unlink()
            done.append(f"removed {entry['path']}")

    repointed = rewrite_published_citations(root)
    if repointed:
        done.append(f"repointed cited paths in {len(repointed)} published file(s)")

    # Last, and only now: the move that makes the workspace read as current.
    for entry in report["moves"]:
        if not entry["to"].startswith("input/"):
            continue
        source, destination = root / entry["from"], root / entry["to"]
        if not source.exists():
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        done.append(f"moved {entry['from']} -> {entry['to']}")

    # A workspace created before the guide existed gets one now. Never overwritten:
    # an operator may have edited it.
    guide = root / "input" / "README.md"
    if guide.parent.is_dir() and not guide.exists():
        template = PACKAGE / "templates" / "input.README.md"
        if template.is_file():
            shutil.copy2(template, guide)
            done.append("added input/README.md")

    for leftover in ("sources", "acquired"):
        path = root / leftover
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
            done.append(f"removed the empty {leftover}/")
    return done


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path)
    parser.add_argument("--apply", action="store_true", help="perform the move; default plans only")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    root = args.workspace.expanduser().resolve()
    if not root.is_dir():
        print(f"no such workspace: {root}")
        return 2

    report = plan(root)
    if args.apply and not report["blockers"]:
        report["applied"] = apply(root, report)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 1 if report["blockers"] else 0

    print(f"workspace: {report['workspace']}")
    if report["blockers"]:
        for blocker in report["blockers"]:
            print(f"  BLOCKED: {blocker}")
        return 1
    verb = "moved" if args.apply else "would move"
    for entry in report["moves"]:
        note = f"   ({entry['note']})" if entry.get("note") else ""
        print(f"  {verb}  {entry['from']}  ->  {entry['to']}{note}")
    for entry in report["manifest"]:
        print(f"  manifest: {entry}")
    for name in report["ignore_files"]:
        print(f"  rewrite: {name}")
    for entry in report["deletes"]:
        print(f"  remove:  {entry['path']} - {entry['why']}")
    if not args.apply:
        print("\nplan only. Re-run with --apply to perform it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
