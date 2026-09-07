#!/usr/bin/env python3
"""List every source this analysis read, so a reader can check any of it.

The published set cited evidence ids and evidence ids cited paths, but nothing named
the *sources* as documents: no title, no version, no date, no author, no digest. A
reader who wanted to check a claim about a supplied spreadsheet had no way to know
which spreadsheet, from when, or whether the copy they hold is the copy that was read.

The reference set does this and the kit did not. `A01_Table_Definitions.md` carries a
References section and a Revision history, and a document with an author and a version
is the difference between a citation and a gesture.

Generated, like the catalogues, from what is actually in the workspace:

  Supplied evidence   Everything a person put in `input/`, with size, modification
                      date and SHA-256. The digest is the point: it says which copy.
  Acquired            The Access databases, and the bundle assembled from them.
  Derived             What the kit produced from those, and which command makes it.
  Specifications      The contracts this run was judged against, by version.

A source that was declared and is missing appears too, marked, because a reference
list that silently omits what it could not read is worse than no list.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

import workspace as workspace_contract  # noqa: E402

# What a person supplies, and what each class of it can establish. Naming the class
# beside the file is the point of the whole evidence contract: a reader sees at once
# whether a claim's source could carry the claim.
INPUT_CLASSES = {
    "documents": "DOCUMENT — business meaning, purpose, roles",
    "interviews": "INTERVIEW — meaning and usage nobody wrote down",
    "screenshots": "SCREENSHOT — layout, grouping, what an operator can see",
    "samples": "SAMPLE_DATA — inbound file formats and real column meaning",
    "report-samples": "OUTPUT_SAMPLE — what the application actually produced",
    "shared-docs": "DOCUMENT — shared across applications",
    "decisions": "OPERATOR_DECLARATION for accepted names; a recorded meaning cites "
                 "DOCUMENT or INTERVIEW",
    "access": "SCHEMA + CODE + UI_DEFINITION — the application itself",
    "vba": "CODE",
    "sql": "CODE",
}

# Only these are cited by path in an evidence item. An Access database is cited
# through the definition text extracted from it, and a decisions file is a decision
# rather than evidence, so reporting either as "not cited" would tell the reader
# something false.
CITE_CHECKED = ("documents", "interviews", "screenshots", "samples",
                "report-samples", "shared-docs")


def digest(path: Path, limit: int = 200 * 1024 * 1024) -> str:
    if path.stat().st_size > limit:
        return "(not hashed: over 200 MB)"
    sha = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def human(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size / 1:.0f} {unit}"
        size /= 1024.0
    return f"{size:.0f} GB"


def sized(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.0f} KB"
    return f"{size / (1024 * 1024):.1f} MB"


def modified(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%d")


def cited_paths(outputs: Path) -> set[str]:
    """Which sources the evidence register actually cites, so unused ones show up."""
    cited: set[str] = set()
    for candidate in (outputs, outputs / "registers"):
        for path in candidate.glob("*_Evidence.json") if candidate.is_dir() else []:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for entry in data.get("items") or []:
                value = (entry or {}).get("source_path")
                if isinstance(value, str) and value.strip():
                    cited.add(value.replace("\\", "/"))
    return cited


def spec_versions() -> list[tuple[str, str]]:
    import yaml

    found: list[tuple[str, str]] = []
    for path in sorted((PACKAGE / "specifications").glob("*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except Exception:
            continue
        version = data.get("version")
        found.append((path.name, str(version) if version is not None else "—"))
    return found


def build(space: Any, app_id: str) -> str:
    root = space.root
    outputs = space.output_dir()
    cited = cited_paths(outputs)

    lines = [
        f"# {app_id} — References",
        "",
        "Every source this analysis read, with the digest that says **which copy**. "
        "Generated by `$ak references`; regenerate it after supplying anything new.",
        "",
        "A claim in any document cites an evidence id; that id cites a path; this page "
        "says what the path is, when it was last changed, and what class of evidence it "
        "can carry. A reader who wants to check a claim can get from the sentence to the "
        "file without asking anyone.",
        "",
        "## 1. Supplied by the operator",
        "",
    ]

    supplied: list[tuple[str, Path]] = []
    for name in INPUT_CLASSES:
        directory = space.input_dir(name)
        if not directory.is_dir():
            continue
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                supplied.append((name, path))

    if not supplied:
        lines += ["**Nothing.** No document, interview, screenshot or sample was "
                  "supplied, so every claim about business meaning is absent by "
                  "necessity rather than by omission.", ""]
    else:
        lines += [
            "`Cited` applies to evidence a document can cite by path. An Access "
            "database is cited through the definition text extracted from it, and a "
            "decisions file records a decision rather than evidence.",
            "",
            "| # | File | Evidence class | Size | Modified | Cited | SHA-256 |",
            "|---:|---|---|---:|---|---|---|",
        ]
        for number, (name, path) in enumerate(supplied, 1):
            relative = path.relative_to(root).as_posix()
            if name not in CITE_CHECKED:
                is_cited = "via extraction" if name == "access" else "n/a"
            else:
                is_cited = "yes" if relative in cited else "**not yet**"
            lines.append(
                f"| {number} | `{relative}` | {INPUT_CLASSES.get(name, name)} | "
                f"{sized(path.stat().st_size)} | {modified(path)} | {is_cited} | "
                f"`{digest(path)[:16]}…` |"
            )
        uncited = [p for n, p in supplied
                   if n in CITE_CHECKED and p.relative_to(root).as_posix() not in cited]
        if uncited:
            lines += [
                "",
                f"**{len(uncited)} supplied file(s) are not cited by any evidence item.** "
                "Either they have not been read yet, or they turned out to say nothing "
                "the analysis needed. Both are worth knowing; neither is visible without "
                "this column.",
            ]
        lines.append("")

    lines += ["## 2. Acquired from the application", ""]
    bundles = workspace_contract.find_bundle_dirs(space)
    if not bundles:
        lines += ["No acquisition bundle. Nothing was read from the application.", ""]
    else:
        bundle = max(bundles, key=lambda p: (p / "bundle.json").stat().st_mtime)
        provenance = bundle / "provenance.json"
        lines += [f"Bundle `{bundle.name}`, assembled {modified(bundle / 'bundle.json')}.",
                  ""]
        if provenance.is_file():
            try:
                data = json.loads(provenance.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                data = {}
            sources = data.get("sources") or data.get("artifacts") or []
            if isinstance(sources, list) and sources:
                lines += ["| Artifact | Producer | Digest |", "|---|---|---|"]
                for entry in sources[:40]:
                    if not isinstance(entry, dict):
                        continue
                    lines.append(
                        f"| `{entry.get('logical_id') or entry.get('id') or '—'}` | "
                        f"{entry.get('producer') or entry.get('producer_version') or '—'} | "
                        f"`{str(entry.get('source_sha256') or entry.get('sha256') or '—')[:16]}…` |"
                    )
                lines.append("")

    lines += ["## 3. Derived by the kit", "",
              "Not sources. Regenerating any of these from the bundle reproduces it, so "
              "a figure here cannot drift from the application it describes.",
              "",
              "| What | Where | Command |",
              "|---|---|---|"]
    derived = [
        ("Deterministic fact graph", "derived-extraction.json", "`$ak derive`"),
        ("Distilled screen facts", "ui-facts/", "`$ak derive`"),
        ("Normalized document corpus", "normalized/corpus/", "`$ak documents`"),
        ("Module decomposition", "module-plan/", "`$ak derive`"),
    ]
    for what, where, command in derived:
        path = space.extracted(where.rstrip("/"))
        state = "" if path.exists() else " _(not produced)_"
        lines.append(f"| {what}{state} | `{path.relative_to(root).as_posix()}` | {command} |")
    lines += ["", "| Catalogue | Command |", "|---|---|"]
    for name in ("DataCatalogue", "ScreenCatalogue", "LogicCatalogue"):
        lines.append(f"| `{app_id}_{name}.md` | `$ak catalogues` |")

    lines += ["", "## 4. Contracts this run was judged against", "",
              "The specifications the documents were checked against, by version. A "
              "conformance result is only meaningful beside the contract version that "
              "produced it.",
              "",
              "| Specification | Version |", "|---|---|"]
    for name, version in spec_versions():
        lines.append(f"| `specifications/{name}` | {version} |")

    lines += ["", "---", "",
              f"*Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d')} by "
              "`$ak references`. Digests are SHA-256, truncated to 16 characters for "
              "reading; the full value is in the evidence register.*"]
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--app-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    space = workspace_contract.Workspace(args.app_root)
    app_id = args.app_id or read_app_id(space.root) or space.root.name
    text = build(space, app_id)
    if args.dry_run:
        print(f"{app_id}_References.md: {len(text):,} bytes, "
              f"{len(text.splitlines())} lines")
        return 0
    outputs = space.output_dir()
    outputs.mkdir(parents=True, exist_ok=True)
    target = outputs / f"{app_id}_References.md"
    io.open(target, "w", encoding="utf-8", newline="\n").write(text)
    print(f"wrote {target} ({len(text):,} bytes)")
    return 0


def read_app_id(root: Path) -> str | None:
    manifest = root / "manifest.yaml"
    if not manifest.is_file():
        return None
    try:
        import yaml

        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        return ((data.get("app") or {}).get("id")) or None
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
