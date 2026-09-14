#!/usr/bin/env python3
"""Reclaim what a workspace no longer needs, and nothing else.

Every command here writes into a new directory rather than over the last one, which
is correct - an acquisition that overwrote the session a published finding cites
would destroy the evidence for it - and it means that running the kit repeatedly
leaves a workspace holding one live copy of each thing and a pile of superseded
ones. Measured on the real A05 workspace on 2026-09-14: 2.4 GB across fourteen
directories, of which one staging session, one export package and two databases
were actually read by anything.

Nothing is deleted because it is old. Recency is not the question and on this
workspace it gives the wrong answer: the newest staging session for the frontend
holds four files, because that acquisition declared `skip_object_export`, while the
session every citation names is three weeks older and holds the 170 definition
texts. So the question asked of each candidate is the literal one - **does anything
cite it** - answered by reading the manifest, the evidence register, the phase
documents, the run fragments and the sealed bundles, and a candidate nothing names
is offered while a candidate something names is not, whatever its date.

Reports by default and deletes only when told to, because the whole point of the
command is that a person should see what is about to go before it goes. Anything
under `input/` needs `--include-input` on top of `--delete`: that directory is what
a person supplied, the kit does not own it, and a guarantee that weakens silently is
not one.

What it will never offer, whatever is asked, in either layout:

  input/ (sources/)              the supplied content itself. Only unreferenced
                                 leftovers beside referenced ones are offered.
  output/                        the published documents.
  .ak/staging/ (acquired/…)      the sessions something cites. This is the evidence.
  .ak/bundles/ (acquired/…)      every bundle, superseded or not - `A05_Evidence.json`
                                 cites a bundle id 26 times, and a register whose
                                 citations no longer resolve is worse than a workspace
                                 carrying 4 MB it does not read.
  .ak/runs/ (runs/)              run state and evidence registers.
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

# Whole directories that are disposable by construction, whatever a workspace cites:
# copies of a file that is still sitting in `input/`, and the output of a component
# this kit removed. Each entry: relative path, why it can go, and what would be lost -
# which is the part an operator needs in order to say yes.
DISPOSABLE: tuple[tuple[str, str, str], ...] = (
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

# Never removed, whatever a rule proposes. Checked rather than trusted, so a future
# entry cannot quietly eat the evidence.
# `.ak/snapshots` is deliberately absent: it is a DISPOSABLE entry, and the only one
# of the kit's own areas whose whole content is a copy of something still on disk.
PROTECTED: tuple[str, ...] = (
    "manifest.yaml", "sources", "acquired", "acquired/staging", "acquired/bundles",
    "runs", "decisions", "shared-docs", "input", "output",
    ".ak", ".ak/staging", ".ak/bundles", ".ak/runs", ".ak/extracted",
    *(f"input/{name}" for name in INPUT_DIRS),
    *INPUT_DIRS.values(),
    "input/exports", "sources/exports",
)

# Where a citation can be written. The evidence register is the important one - it
# names the staging file each finding was read out of - but a phase document cites
# paths in prose, a run still in progress keeps its fragments under `.ak/runs/`, and
# a sealed bundle records where each contribution came from.
CITING_GLOBS: tuple[str, ...] = (
    "manifest.yaml",
    "output/*.md", "output/**/*.md", "output/**/*.json", "output/**/*.csv",
    "runs/**/*.json", "runs/**/*.md",
    ".ak/runs/**/*.json", ".ak/runs/**/*.md",
    ".ak/bundles/**/*.json",
    "acquired/bundles/**/*.json", "acquired/bundle-*/**/*.json",
)

# A cited path is recognised by the workspace-relative root it starts from, so an
# absolute citation (`D:\Anrakutei\fresh\A05\.ak\staging\…`) and a relative one
# reduce to the same key.
TOP_SEGMENTS: tuple[str, ...] = (
    ".ak/", "input/", "output/", "sources/", "acquired/",
    "extracted/", "runs/", "staging/", "snapshots/", "bundles/",
)

# Everything a path can be made of, stopping at the characters that end one in prose,
# in JSON and in a Markdown link. Full-width brackets are deliberately absent: they
# are inside real filenames here (`品揃支援（windows11専用）.mdb`).
_PATH_TOKEN = re.compile("[^\\s\"'<>|*?,;)\\]}]+")

# Access leaves these beside a database it opened. Never cited, never input.
DROPPINGS: tuple[str, ...] = ("*.ldb", "*.laccdb", "~*.mdb", "~*.accdb", "*.tmp")


# --- what a workspace says it reads -----------------------------------------


def paths_in(text: str) -> set[str]:
    """Every workspace-relative path a piece of text names."""
    found: set[str] = set()
    for token in _PATH_TOKEN.findall(text.replace(chr(92), "/")):
        for segment in TOP_SEGMENTS:
            at = token.find(segment)
            if at == -1:
                continue
            if at and (token[at - 1].isalnum() or token[at - 1] in "-_."):
                continue  # part of a longer name, e.g. `no-input/foo`
            found.add(token[at:].rstrip("/"))
            break
    return found


def cited_paths(root: Path) -> set[str]:
    """Everything the workspace's own records point at."""
    found: set[str] = set()
    for pattern in CITING_GLOBS:
        for path in root.glob(pattern):
            if not path.is_file():
                continue
            try:
                found |= paths_in(path.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                continue
    return found


def is_cited(key: str, cited: set[str]) -> bool:
    """True when something names this path, or anything inside it."""
    return any(path == key or path.startswith(key + "/") for path in cited)


# --- candidates --------------------------------------------------------------


def relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def measure(path: Path) -> tuple[int, int]:
    if path.is_file():
        return path.stat().st_size, 1
    files = [item for item in path.rglob("*") if item.is_file()]
    return sum(item.stat().st_size for item in files), len(files)


def entry(root: Path, path: Path, what: str, losing: str, guard: str) -> dict[str, Any]:
    size, files = measure(path)
    return {
        "path": relative(root, path), "what": what, "losing": losing,
        "guard": guard, "kind": "file" if path.is_file() else "directory",
        "bytes": size, "files": files,
    }


def disposable(space: Workspace) -> list[dict[str, Any]]:
    found = []
    for name, what, losing in DISPOSABLE:
        target = space.root / name
        if target.is_dir():
            found.append(entry(space.root, target, what, losing, "kit"))
    return found


def stray_kit_dirs(space: Workspace, cited: set[str]) -> list[dict[str, Any]]:
    """A kit directory sitting at the workspace root, where no accessor looks.

    In the current layout the kit writes under `.ak/`, and `Workspace.owned()` is the
    only thing that resolves those names - so a `staging/` at the top level is not a
    second copy the code might read, it is a copy the code cannot reach. A06 acquired
    into one when `--output-root` was given the workspace root instead of `.ak/`; on
    A05 it is 587 MB. Offered only when the `.ak/` counterpart exists and holds
    something, so a half-migrated workspace - where the top-level directory is still
    the live one - is left alone.
    """
    if space.is_legacy:
        return []
    found = []
    for name in OWNED_DIRS:
        target = space.root / name
        counterpart = space.root / ".ak" / name
        if not target.is_dir() or not counterpart.is_dir():
            continue
        if not any(counterpart.iterdir()) or is_cited(relative(space.root, target), cited):
            continue
        found.append(entry(
            space.root, target,
            f"A `{name}/` outside `.ak/`, which no accessor resolves",
            f"Nothing that is read. `.ak/{name}/` is the one every command opens, and "
            "nothing cites this copy.",
            "kit",
        ))
    return found


def superseded_sessions(space: Workspace, cited: set[str]) -> list[dict[str, Any]]:
    """An extraction session under staging that nothing cites.

    A session is named for the acquisition that wrote it, so re-running acquisition
    adds one rather than replacing the last - which is right, and is why they pile
    up. Recency does not decide which is live: A05's newest frontend session holds
    four files because that run declared `skip_object_export`, while `fresh-01`, three
    weeks older, holds the 170 definition texts the register cites 30 times. A
    database's last remaining session is kept whatever the answer, so this can never
    empty staging for a database.
    """
    root = space.staging_root()
    if not root.is_dir():
        return []
    found = []
    for database in sorted(root.iterdir()):
        if not database.is_dir() or database.name.startswith("_"):
            continue
        sessions = sorted(p for p in database.iterdir() if p.is_dir())
        if len(sessions) < 2:
            continue
        loose = [p for p in sessions if not is_cited(relative(space.root, p), cited)]
        if len(loose) == len(sessions):
            # Nothing cites any of them - a workspace that has acquired but not yet
            # published. Keep the newest rather than decide for the next run.
            #
            # The name breaks a tie, and a tie is not hypothetical: Windows' clock
            # granularity is about 16ms, so two sessions written by the same command
            # can carry the same mtime, and `max` then keeps whichever the directory
            # listing happened to yield first - which can be the older one. Both
            # session naming schemes this kit writes, `acquire-NN` and the run id
            # `YYYY-MM-DD-hash`, sort with the later session last.
            loose.remove(max(loose, key=lambda p: (p.stat().st_mtime, p.name)))
        for session in loose:
            found.append(entry(
                space.root, session,
                f"A superseded extraction session for {database.name}",
                "Nothing that is read. No citation, no bundle and no manifest entry "
                f"names it, and {database.name} keeps its cited session.",
                "kit",
            ))
    return found


def package_artifact(name: str) -> str:
    """`WINDOWS11_45D0FDDD-2026-09-08` -> `WINDOWS11_45D0FDDD`."""
    return re.sub("-[0-9]{4}-[0-9]{2}-[0-9]{2}$", "", name)


def superseded_packages(space: Workspace, cited: set[str]) -> list[dict[str, Any]]:
    """An export package under `input/exports/` that nothing reads.

    `ExportAccessObjects` writes `<artifact>-<date>`, so an operator re-exporting a
    frontend leaves the previous package behind; A05 holds three for two artifacts.
    Two guards, because this is a person's directory: the newest package for an
    artifact is never offered - it is the one they have just made for the next run -
    and nothing is offered unless some package here is cited, so a workspace that has
    exported but not yet acquired keeps everything.
    """
    root = space.input_dir("exports")
    if not root.is_dir():
        return []
    packages = sorted(p for p in root.iterdir() if p.is_dir())
    if not any(is_cited(relative(space.root, p), cited) for p in packages):
        return []
    newest: dict[str, Path] = {}
    for package in packages:
        artifact = package_artifact(package.name)
        if artifact not in newest or package.name > newest[artifact].name:
            newest[artifact] = package
    found = []
    for package in packages:
        key = relative(space.root, package)
        if is_cited(key, cited) or newest[package_artifact(package.name)] == package:
            continue
        found.append(entry(
            space.root, package,
            "A superseded export package",
            "An export nothing reads. The manifest names a different package for "
            f"{package_artifact(package.name)}, and a newer one is here too. Re-exporting "
            "from the database reproduces it.",
            "input",
        ))
    return found


def unreferenced_supplied(space: Workspace, cited: set[str]) -> list[dict[str, Any]]:
    """A file in `input/access/` that no artifact declares.

    Acquisition never writes here - it snapshots into `.ak/snapshots/` - so what
    accumulates is what a person copied in: a lock file Access left behind, and the
    previous copy of a database beside the one now declared. Offered only when some
    file here *is* declared, so a freshly filled `input/access/` with no manifest yet
    is left alone, and never for a file the manifest names.
    """
    root = space.input_dir("access")
    if not root.is_dir():
        return []
    files = sorted(p for p in root.iterdir() if p.is_file())
    if not any(is_cited(relative(space.root, p), cited) for p in files):
        return []
    found = []
    for path in files:
        if is_cited(relative(space.root, path), cited):
            continue
        dropping = any(path.match(pattern) for pattern in DROPPINGS)
        found.append(entry(
            space.root, path,
            "A lock or temporary file Access left behind" if dropping
            else "A supplied file no artifact declares",
            "Nothing. Access writes it while a database is open and rebuilds it."
            if dropping else
            "The file itself. Nothing in the manifest, the register or a bundle "
            "names it - if it is a database you have not declared yet, add it to "
            "manifest.yaml before running this.",
            "input",
        ))
    return found


def survey(space: Workspace) -> list[dict[str, Any]]:
    cited = cited_paths(space.root)
    found = (
        disposable(space)
        + stray_kit_dirs(space, cited)
        + superseded_sessions(space, cited)
        + superseded_packages(space, cited)
        + unreferenced_supplied(space, cited)
    )
    return sorted(found, key=lambda item: (item["guard"] != "kit", item["path"]))


# --- removal -----------------------------------------------------------------


def is_protected(root: Path, target: Path) -> bool:
    """A guard against this command ever growing a rule that eats the evidence."""
    resolved = target.resolve()
    if resolved == root.resolve():
        return True
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return True  # outside the workspace entirely
    return any(resolved == (root / name).resolve() for name in PROTECTED)


def remove(root: Path, found: list[dict[str, Any]], include_input: bool) -> list[str]:
    removed: list[str] = []
    for item in found:
        if item["guard"] == "input" and not include_input:
            continue
        target = root / item["path"]
        if is_protected(root, target):
            raise PermissionError(item["path"])
        if target.is_file():
            target.unlink()
        else:
            shutil.rmtree(target, ignore_errors=True)
        removed.append(item["path"])
        parent = target.parent
        if parent.is_dir() and not is_protected(root, parent) and not any(parent.iterdir()):
            parent.rmdir()
    return removed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument(
        "--delete", action="store_true",
        help="Actually remove. Without this the command only reports.",
    )
    parser.add_argument(
        "--include-input", action="store_true",
        help="Also remove the leftovers under input/. Reported either way; removed "
             "only with this, because input/ is what a person supplied.",
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

    space = Workspace(app_root)
    found = survey(space)
    held_back = [item for item in found if item["guard"] == "input" and not args.include_input]
    removed: list[str] = []

    if args.delete:
        try:
            removed = remove(app_root, found, args.include_input)
        except PermissionError as refused:
            print(f"refusing to remove protected path: {refused}", file=sys.stderr)
            return 2

    total = sum(item["bytes"] for item in found)
    reclaimed = sum(item["bytes"] for item in found if item["path"] in set(removed))
    report = {
        "app_root": str(app_root),
        "reclaimable": found,
        "total_bytes": total,
        "total_mb": round(total / (1024 * 1024), 1),
        "deleted": removed,
        "deleted_mb": round(reclaimed / (1024 * 1024), 1),
        "held_back": [item["path"] for item in held_back],
        "mode": "deleted" if args.delete else "reported",
    }

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if not found:
        print(f"Nothing to reclaim under {app_root}")
        return 0

    verb = "Removed" if args.delete else "Would remove"
    shown = report["deleted_mb"] if args.delete else report["total_mb"]
    print(f"{verb} {shown} MB from {app_root}")
    for item in found:
        mark = "  (input - needs --include-input)" if item in held_back else ""
        print(f"  {item['path']}  —  {round(item['bytes'] / (1024 * 1024), 1)} MB, "
              f"{item['files']} file(s){mark}")
        print(f"      {item['what']}")
        print(f"      losing: {item['losing']}")
    if not args.delete:
        print("\nNothing has been removed. Pass --delete to do it"
              + (", and --include-input for the input/ entries." if held_back else "."))
    elif held_back:
        print(f"\n{len(held_back)} entry(s) under input/ were left. Add --include-input "
              "to remove them too.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
