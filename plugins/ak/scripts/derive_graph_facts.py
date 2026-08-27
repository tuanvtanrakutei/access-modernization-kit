#!/usr/bin/env python3
"""Derive the relationships an Access application states literally, without an LLM.

Two problems this solves, both observed on a real application.

Graphify's AST pass produced 79 nodes and no edges from a corpus of exported query
SQL: one node per file and not a single relationship. Yet every query names the
tables it reads, in text, next to the authoritative table list the acquisition
bundle already holds. Matching one against the other is exact, free and
reproducible; asking a semantic pass to infer it costs tokens to guess at something
the source states outright.

And the corpus excluded every SaveAsText definition, on the sound argument that a
graph cannot use "this form contains a TextBox with Top=1410". True of the
coordinates - but the same file carries RecordSource, ControlSource, the ProgID of
each embedded control and the name of every event procedure, which are exactly the
relationships Phase 2 asks the graph about. So the definitions are distilled rather
than dropped: the facts enter the corpus, the property soup does not.

Node ids follow the {stem}_{entity} shape Graphify expects, with a short digest of
the original name appended. Without it every Japanese name - the norm in this kit's
target systems - normalizes to the same underscore run and distinct entities merge
into one node.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RECORD_SOURCE_RE = re.compile(r'(?<![A-Za-z])RecordSource\s*=\s*"([^"]*)"')
CONTROL_SOURCE_RE = re.compile(r'(?<![A-Za-z])ControlSource\s*=\s*"([^"]*)"')
# Not preceded by a letter: SaveAsText writes OLEClass ="<display name>" beside the
# real Class ="<ProgID>", and matching both reports a caption as a control.
CLASS_RE = re.compile(r'(?<![A-Za-z])Class\s*=\s*"([^"]+)"')
EVENT_RE = re.compile(r'(?m)^\s*(?:Private|Public)?\s*Sub\s+([A-Za-z0-9_]+_[A-Za-z0-9_]+)\s*\(')
NAME_RE = re.compile(r'(?<![A-Za-z])Name\s*=\s*"([^"]*)"')


def node_id(stem: str, entity: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "_", f"{stem}_{entity}".lower()).strip("_")
    digest = hashlib.sha1(f"{stem}|{entity}".encode("utf-8")).hexdigest()[:8]
    return f"{base}_{digest}" if base else f"n_{digest}"


def newest_bundle(app_root: Path) -> Path | None:
    acquired = app_root / "acquired"
    if not acquired.is_dir():
        return None
    bundles = [p for p in acquired.glob("bundle-*") if (p / "bundle.json").is_file()]
    if not bundles:
        return None
    return max(bundles, key=lambda p: (p / "bundle.json").stat().st_mtime)


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, OSError):
            continue
    return ""


def latest_sessions(app_root: Path) -> list[tuple[str, Path]]:
    """The newest extraction session per database, which holds the definition text."""
    staging = app_root / "acquired" / "staging"
    found: list[tuple[str, Path]] = []
    if not staging.is_dir():
        return found
    for database in sorted(staging.iterdir()):
        if not database.is_dir() or database.name.startswith("_"):
            continue
        sessions = [p for p in database.iterdir() if p.is_dir()]
        if not sessions:
            continue
        found.append((database.name, max(sessions, key=lambda p: p.stat().st_mtime)))
    return found


def distil_object(text: str, kind: str) -> dict[str, Any]:
    """Keep the facts that are relationships; drop the geometry."""
    record_sources = [v for v in RECORD_SOURCE_RE.findall(text) if v.strip()]
    control_sources = sorted({v for v in CONTROL_SOURCE_RE.findall(text) if v.strip()})
    classes = sorted({v for v in CLASS_RE.findall(text) if v.strip()})
    events = sorted(set(EVENT_RE.findall(text)))
    return {
        "kind": kind,
        "record_source": record_sources[0] if record_sources else "",
        "control_sources": control_sources,
        "activex_classes": classes,
        "event_procedures": events,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", required=True)
    parser.add_argument("--dry-run", action="store_true", help="Report counts without writing")
    args = parser.parse_args()

    app_root = Path(args.app_root).expanduser().resolve()
    bundle = newest_bundle(app_root)
    if bundle is None:
        raise SystemExit(f"No acquisition bundle under {app_root / 'acquired'}; acquire first")

    tables = json.loads((bundle / "databases" / "tables.json").read_text(encoding="utf-8"))
    table_names = {str(t.get("name")): t for t in tables if t.get("name")}

    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    facts: dict[str, dict[str, Any]] = {}
    table_node: dict[str, str] = {}

    for name, row in table_names.items():
        database = str(row.get("database_id", ""))
        identifier = node_id(f"table_{database}".lower(), name)
        table_node[name] = identifier
        nodes.append({
            "id": identifier, "label": name, "file_type": "concept",
            "source_file": f"{database}:schema/tables.json", "source_location": None,
            "source_url": None, "captured_at": None, "author": None, "contributor": None,
        })

    # Longest first, so a table whose name contains another's is attributed to the
    # longer match rather than to the substring.
    ordered_tables = sorted(table_names, key=len, reverse=True)

    object_node: dict[tuple[str, str], str] = {}
    texts: dict[tuple[str, str], tuple[Path, str, str]] = {}
    for database, session in latest_sessions(app_root):
        # The extraction receipt maps each object's real name to the file it was written
        # to. Reading the name out of the definition text instead picks up the first
        # Name = "..." in the file, which for a report is a section - so 63 reports
        # became a handful of nodes called 詳細 and ページヘッダー, colliding with each
        # other. The filename cannot be used either: it is sanitized and digest-suffixed.
        receipt = session / "access-extraction.json"
        if not receipt.is_file():
            continue
        components = json.loads(read_text(receipt) or "{}").get("components", [])
        for component in components:
            kind = str(component.get("kind", ""))
            if kind not in {"query", "module", "form", "report", "macro"}:
                continue
            label = str(component.get("name", ""))
            paths = [p for p in (component.get("source_paths") or []) if p]
            if not label or not paths:
                continue
            path = session / Path(*paths[0].split("/"))
            if not path.is_file():
                continue
            key = (database, label)
            identifier = node_id(f"{kind}_{database}".lower(), label)
            object_node[key] = identifier
            texts[key] = (path, kind, read_text(path))
            nodes.append({
                "id": identifier, "label": label,
                "file_type": "code" if kind in {"query", "module", "macro"} else "document",
                "source_file": os.path.relpath(path, app_root).replace(chr(92), "/"),
                "source_location": None, "source_url": None, "captured_at": None,
                "author": None, "contributor": None,
            })

    ordered_objects = sorted({label for _, label in object_node}, key=len, reverse=True)

    def add_edge(source: str, target: str, relation: str, source_file: str, line: int) -> None:
        edges.append({
            "source": source, "target": target, "relation": relation,
            "confidence": "EXTRACTED", "confidence_score": 1.0,
            "source_file": source_file, "source_location": f"line {line}", "weight": 1.0,
        })

    for (database, label), (path, kind, text) in texts.items():
        holder = object_node[(database, label)]
        relative = os.path.relpath(path, app_root).replace(chr(92), "/")
        seen_tables: set[str] = set()
        seen_objects: set[str] = set()
        for line_no, line in enumerate(text.split("\n"), 1):
            for table in ordered_tables:
                if table in line and table not in seen_tables:
                    seen_tables.add(table)
                    add_edge(holder, table_node[table], "references", relative, line_no)
            for other in ordered_objects:
                if other == label or other in seen_objects or other not in line:
                    continue
                target = object_node.get((database, other))
                if target:
                    seen_objects.add(other)
                    add_edge(holder, target, "references", relative, line_no)
        if kind in {"form", "report"}:
            facts[f"{database}::{label}"] = {"database_id": database, "name": label,
                                             **distil_object(text, kind)}

    payload = {
        "nodes": nodes, "edges": edges, "hyperedges": [],
        "input_tokens": 0, "output_tokens": 0,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "bundle_id": bundle.name,
    }

    if args.dry_run:
        print(json.dumps({"nodes": len(nodes), "edges": len(edges), "ui_objects": len(facts)}, indent=2))
        return 0

    extraction_path = app_root / "extracted" / "derived-extraction.json"
    extraction_path.parent.mkdir(parents=True, exist_ok=True)
    io.open(extraction_path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n")

    # One distilled file per screen, so the corpus carries a node per screen whose text
    # is relationships rather than coordinates.
    facts_dir = app_root / "extracted" / "ui-facts"
    facts_dir.mkdir(parents=True, exist_ok=True)
    for existing in facts_dir.glob("*.md"):
        existing.unlink()
    for key, fact in sorted(facts.items()):
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", key).strip("_") or "object"
        digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:8]
        lines = [
            f"# {fact['name']}",
            "",
            f"- database: {fact['database_id']}",
            f"- kind: {fact['kind']}",
            f"- record source: {fact['record_source'] or '(none declared)'}",
        ]
        if fact["control_sources"]:
            lines += ["- bound fields:"] + [f"  - {v}" for v in fact["control_sources"]]
        if fact["activex_classes"]:
            lines += ["- embedded controls:"] + [f"  - {v}" for v in fact["activex_classes"]]
        if fact["event_procedures"]:
            lines += ["- event procedures:"] + [f"  - {v}" for v in fact["event_procedures"]]
        io.open(facts_dir / f"{safe}-{digest}.md", "w", encoding="utf-8", newline="\n").write(
            "\n".join(lines) + "\n")

    print(f"derived {len(nodes)} nodes and {len(edges)} edges from {bundle.name}")
    print(f"distilled {len(facts)} UI objects into {facts_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
