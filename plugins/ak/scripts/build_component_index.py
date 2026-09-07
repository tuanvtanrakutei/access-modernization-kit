#!/usr/bin/env python3
"""Combine Access extraction indexes and text sources into one deterministic app component index."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import re
from datetime import datetime, timezone
from pathlib import Path


def _workspace(app_root):
    """The layout resolver; one place knows a pre-2.10.0 workspace names things
    differently, so every caller asks instead of assuming."""
    contracts = str(Path(__file__).resolve().parent.parent / "contracts")
    if contracts not in sys.path:
        sys.path.insert(0, contracts)
    from workspace import Workspace

    return Workspace(app_root)



TEXT_SUFFIXES = {".bas", ".cls", ".frm", ".vb", ".sql", ".txt", ".csv", ".md", ".ps1", ".vbs", ".bat", ".cmd", ".py", ".js", ".ts", ".c", ".cpp", ".h", ".hpp", ".cs", ".java"}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def app_id_from_manifest(app_root: Path) -> str:
    text = (app_root / "manifest.yaml").read_text(encoding="utf-8")
    match = re.search(r"(?m)^\s*id:\s*[\"']?([A-Z][A-Z0-9_-]{1,15})", text)
    if not match:
        raise SystemExit("Cannot read app.id from manifest.yaml")
    return match.group(1)


def kind_for(path: Path) -> str:
    if path.suffix.lower() in {".bas", ".cls", ".frm", ".vb"}:
        return "vba_source"
    if path.suffix.lower() == ".sql":
        return "sql_source"
    if path.suffix.lower() in {".ps1", ".vbs", ".bat", ".cmd"}:
        return "automation_source"
    return "source_file"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", required=True)
    parser.add_argument("--output", help="Default: the workspace's own extracted/component-index.json")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app_root = Path(args.app_root).expanduser().resolve()
    app_id = app_id_from_manifest(app_root)
    components: dict[str, dict] = {}
    referenced: set[str] = set()
    # Acquisition writes its per-artifact component index under
    # acquired/staging/<artifact>/<acquisition-id>/, and nothing ever writes
    # extracted/access. Reading only the legacy root produced an index with zero table
    # components on every real project, so module decomposition - and the leaf-first
    # processing order the whole pipeline follows - was computed with no schema at all.
    space = _workspace(app_root)
    access_roots = [space.staging_root(), app_root / "extracted" / "access"]
    selected_indexes: list[Path] = []
    for database_dir in sorted(
        path for root in access_roots if root.is_dir()
        for path in root.glob("*") if path.is_dir()
    ):
        direct = database_dir / "component-index.json"
        # Newest session, not last alphabetically. Acquisition ids are operator-chosen
        # and need not sort chronologically - on a workspace holding a05-evid-01 beside
        # a05-prov-02, name order selected the older run and indexed a stale extraction.
        candidates = sorted(
            database_dir.glob("*/component-index.json"),
            key=lambda path: (path.stat().st_mtime, path.as_posix()),
        )
        if direct.is_file():
            selected_indexes.append(direct)
        elif candidates:
            selected_indexes.append(candidates[-1])
    for index_path in selected_indexes:
        data = json.loads(index_path.read_text(encoding="utf-8-sig"))
        base = index_path.parent.relative_to(app_root).as_posix()
        for raw in data.get("components", []):
            item = dict(raw)
            item["source_paths"] = [f"{base}/{value}" for value in raw.get("source_paths", [])]
            referenced.update(item["source_paths"])
            existing = components.get(item["id"])
            if existing is not None and existing != item:
                raise SystemExit(f"Conflicting component id: {item['id']}")
            components[item["id"]] = item

    space = _workspace(app_root)
    roots = [space.input_root(), space.extracted("build-context")]
    for path in sorted({candidate for root in roots if root.exists() for candidate in root.rglob("*") if candidate.is_file() and candidate.suffix.lower() in TEXT_SUFFIXES}):
        relative = path.relative_to(app_root).as_posix()
        if relative in referenced:
            continue
        digest = sha256(path)
        component_id = f"file:{digest[:20]}"
        container = path.parent.name or "root"
        item = {
            "id": component_id, "kind": kind_for(path), "name": path.name, "container": container,
            "module_hint": container, "source_paths": [relative], "depends_on": [], "metadata": {"sha256": digest},
        }
        existing = components.get(component_id)
        if existing is not None and existing != item:
            raise SystemExit(f"Hash-based component collision: {component_id}")
        components[component_id] = item
    result = {
        "schema_version": "2.1", "app_id": app_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        # Which extraction sessions this index was built from. Without it there is no way
        # to tell whether the schema half of the index came from the current acquisition
        # or an older one left in the workspace.
        "extraction_indexes": [path.relative_to(app_root).as_posix() for path in selected_indexes],
        "components": [components[key] for key in sorted(components)],
    }
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.dry_run:
        print(rendered, end="")
        return 0
    output = (Path(args.output).expanduser().resolve() if args.output
              else _workspace(app_root).extracted("component-index.json"))
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Built deterministic app component index with {len(components)} components at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
