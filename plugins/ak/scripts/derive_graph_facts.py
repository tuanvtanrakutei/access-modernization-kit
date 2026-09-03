#!/usr/bin/env python3
"""Derive the relationships an Access application states literally, without an LLM.

Two problems this solves, both observed on a real application.

An LLM-backed graph pass produced 79 nodes and no edges from a corpus of exported query
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

Node ids follow a {stem}_{entity} shape, with a short digest of
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
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "contracts"))

import workspace as workspace_contract  # noqa: E402

# An escaped quote inside the value must not end it. Access writes a record source
# containing an `IN "path"` clause as `RecordSource ="select ... IN \"L:\...\"..."`,
# and a pattern that stops at the first quote captured only `select ... IN \` - so the
# `IN` clause was truncated away on 35 of 51 A05 forms, and the boundary it declares
# was invisible to every later reader. The symptom was visible in the catalogue as a
# record source ending in `IN \` and was not chased.
RECORD_SOURCE_RE = re.compile(
    r'(?<![A-Za-z])RecordSource\s*=\s*"((?:[^"\\]|\\.)*)"'
)
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
    bundles = workspace_contract.find_bundle_dirs(workspace_contract.Workspace(app_root))
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
    staging = workspace_contract.Workspace(app_root).staging_root()
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


# Characters a filesystem genuinely refuses, and nothing else. Replacing everything
# outside [A-Za-z0-9_.-] is the sanitiser this project already had to fix once, in
# extract_access.ps1: it turned 共通ルーチン into _____ and merged distinct objects onto
# one filename, in a kit whose whole target population is Japanese. The rule there is
# the rule here - keep the name, alter it only when the filesystem forces it, and
# append a digest whenever it was altered so an alteration can never silently collide.
# Characters Windows genuinely refuses, and nothing else. No regex: the escaping
# needed to express a backslash and a control range inside a pattern is exactly how
# this line acquired a literal NUL byte and stopped the module importing at all.
_FORBIDDEN_CHARS = set('<>:"/|?*' + chr(92)) | {chr(c) for c in range(32)}


def fact_filename(database_id: str, name: str, kind: str = "") -> str:
    """`<database>-<kind>-<object name>.md`, readable by the person who has to open it.

    The kind is in the name because Access permits a form and a report to share one,
    and this application does it four times - 酒アイテム別確認表, 青果アイテム別確認表,
    雑貨Ⅱアイテム別確認表 and 冷凍品引渡表 each exist as both in the frontend. Keyed on
    (database, name) alone, one silently overwrote the other and four objects' distilled
    facts left the corpus without a word.
    """
    cleaned = "".join("_" if ch in _FORBIDDEN_CHARS else ch for ch in name).rstrip(". ")
    prefix = f"{database_id}-{kind}" if kind else database_id
    stem = f"{prefix}-{cleaned or 'object'}"
    if cleaned == name and len(stem.encode("utf-8")) <= 180:
        return f"{stem}.md"
    digest = hashlib.sha1(f"{database_id}|{name}".encode("utf-8")).hexdigest()[:8]
    return f"{_clip(stem, 180)}-{digest}.md"


def _clip(text: str, limit: int) -> str:
    """Trim to a byte budget without splitting a character.

    The limit a filesystem enforces is on bytes, and a character slice against it
    does nothing for the names it was written for: 120 Japanese characters is 360
    bytes. Same units mistake, same population, as the sanitiser above.
    """
    encoded = text.encode("utf-8")[:limit]
    return encoded.decode("utf-8", errors="ignore")


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
        space = workspace_contract.Workspace(app_root)
        raise SystemExit(f"No acquisition bundle under {space.bundles_root()}; acquire first")

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

    object_node: dict[tuple[str, str, str], str] = {}
    by_label: dict[tuple[str, str], list[str]] = {}
    texts: dict[tuple[str, str, str], tuple[Path, str, str]] = {}
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
            # Keyed by kind as well as name: Access permits a form and a report to
            # share one, and this application does it four times. Keyed on
            # (database, name) alone the second silently replaced the first, and four
            # objects left the derived corpus without a word about it.
            key = (database, kind, label)
            identifier = node_id(f"{kind}_{database}".lower(), label)
            object_node[key] = identifier
            by_label.setdefault((database, label), []).append(identifier)
            texts[key] = (path, kind, read_text(path))
            nodes.append({
                "id": identifier, "label": label,
                "file_type": "code" if kind in {"query", "module", "macro"} else "document",
                # `DATABASE_ID:path`, the same shape the table nodes use. It used to
                # be the bare path here and `DATABASE_ID:schema/tables.json` there, so
                # a consumer reading the database out of a node got it for tables and
                # an empty string for every form, report, query and module - which is
                # how the first screen catalogue reported all 118 objects as referenced
                # by nothing, against the 37 Phase 2 had established.
                "source_file": f"{database}:"
                               + os.path.relpath(path, app_root).replace(chr(92), "/"),
                "source_location": None, "source_url": None, "captured_at": None,
                "author": None, "contributor": None,
            })

    ordered_objects = sorted({label for _, _, label in object_node}, key=len, reverse=True)

    def add_edge(source: str, target: str, relation: str, source_file: str, line: int) -> None:
        edges.append({
            "source": source, "target": target, "relation": relation,
            "confidence": "EXTRACTED", "confidence_score": 1.0,
            "source_file": source_file, "source_location": f"line {line}", "weight": 1.0,
        })

    for (database, kind_key, label), (path, kind, text) in texts.items():
        holder = object_node[(database, kind_key, label)]
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
                # A name shared by a form and a report is genuinely ambiguous in text:
                # the line says the name and both objects bear it. Both edges are
                # recorded rather than one guessed at.
                targets = [t for t in by_label.get((database, other), []) if t != holder]
                if targets:
                    seen_objects.add(other)
                    for target in targets:
                        add_edge(holder, target, "references", relative, line_no)
        if kind in {"form", "report"}:
            facts[f"{database}::{kind}::{label}"] = {"database_id": database, "name": label,
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

    space = workspace_contract.Workspace(app_root)
    extraction_path = space.extracted("derived-extraction.json")
    extraction_path.parent.mkdir(parents=True, exist_ok=True)
    io.open(extraction_path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(payload, ensure_ascii=False, indent=1) + "\n")

    # One distilled file per screen, so the corpus carries a node per screen whose text
    # is relationships rather than coordinates.
    facts_dir = space.extracted("ui-facts")
    facts_dir.mkdir(parents=True, exist_ok=True)
    for existing in facts_dir.glob("*.md"):
        existing.unlink()
    for key, fact in sorted(facts.items()):
        safe = fact_filename(fact["database_id"], fact["name"], fact["kind"])
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
        io.open(facts_dir / safe, "w", encoding="utf-8", newline="\n").write(
            "\n".join(lines) + "\n")

    print(f"derived {len(nodes)} nodes and {len(edges)} edges from {bundle.name}")
    print(f"distilled {len(facts)} UI objects into {facts_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
