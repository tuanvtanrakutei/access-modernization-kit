#!/usr/bin/env python3
"""Write the ``import-source-manifest.yaml`` an exported source tree needs to be imported.

The imported-sources adapter deliberately refuses a bare directory: a producer
manifest is what lets it verify that every file was declared, that none appeared or
vanished, and what each file actually is. Nothing in the package could produce that
manifest, so an operator holding a perfectly good export had no way to feed it in.
This closes that gap without loosening the adapter's contract.

Classification comes from the containing directory, matching the layout this kit's own
exporters write (``tools/ExportAccessObjects.bas`` and ``scripts/extract_access.ps1``).
A file that cannot be classified is reported and the command fails, rather than being
mislabelled as generic metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import yaml

MANIFEST_NAME = "import-source-manifest.yaml"

SPEC = Path(__file__).resolve().parent.parent / "specifications" / "evidence-layout.yaml"


def _layout() -> dict[str, Any]:
    """Read the one declaration of container names and formats.

    The runtime extractor, the shipped VBA exporter and this importer used to carry
    three private copies of the same layout, which is how they drifted: a `.txt`
    written by one was classified as a stray sample by another.
    """
    return yaml.safe_load(SPEC.read_text(encoding="utf-8")) or {}


def _containers() -> dict[str, tuple[str, str]]:
    layout = _layout()
    mapping = {
        name: (str(entry["kind"]), str(entry.get("role", "interface")))
        for name, entry in (layout.get("containers") or {}).items()
    }
    # Names another producer uses for the same container, declared in the spec so it
    # is visible which tool each layout belongs to.
    for alias, target in (layout.get("container_aliases") or {}).items():
        if target in mapping:
            mapping.setdefault(alias, mapping[target])
    # Server-side exports are declared outside the Access container set.
    mapping.setdefault("sql", ("sql_server", "backend"))
    mapping.setdefault("sql-server", ("sql_server", "backend"))
    # schema/ carries the structured files declared under schema_files; the container
    # itself is metadata so an unexpected member there is still declared, not refused.
    mapping.setdefault("schema", ("metadata", "backend"))
    return mapping


def _root_files() -> dict[str, str]:
    """Files a known producer writes at the package root, recognized by name.

    export-manifest.txt belongs to this kit's own exporter, and refusing it as
    unclassified made the package its own exporter produced fail to import unless the
    operator passed a flag that also lowered the bar for everything else.
    """
    layout = _layout()
    return {
        str(entry["path"]): str(entry.get("kind", "metadata"))
        for entry in (layout.get("package_files") or {}).values()
        if entry.get("path") and entry.get("kind")
    }


CONTAINERS: dict[str, tuple[str, str]] = _containers()
ROOT_FILES: dict[str, str] = _root_files()
# Kinds the adapter decodes as text; everything else is carried by reference only.
TEXT_KINDS = {"vba", "access_sql", "sql_server", "form", "report", "macro", "metadata"}
ENCODINGS = ("utf-8-sig", "utf-8", "cp932")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Export directory that becomes the import package")
    parser.add_argument("--producer-id", required=True, help="What produced the export, for example ExportAccessObjects.bas")
    parser.add_argument("--producer-version", required=True, help="Version of that producer")
    parser.add_argument("--logical-id-prefix", required=True, help="Prefix for each file's logical id, normally the artifact id")
    parser.add_argument("--output", help=f"Manifest path (default: <source>/{MANIFEST_NAME})")
    parser.add_argument(
        "--source-database",
        help="The .mdb/.accdb this export was produced from. Its digest is recorded so a later "
             "run can tell whether the export is still current for that database. Strongly "
             "recommended: without it nothing can detect an export that has gone stale.",
    )
    parser.add_argument(
        "--allow-unclassified", action="store_true",
        help="Declare files in unrecognized directories as metadata instead of failing. Off by default: a mislabelled file is worse than a refused import.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Report the plan without writing the manifest")
    return parser.parse_args()


def detect_encoding(raw: bytes) -> str | None:
    """Return the declared encoding, or None when the bytes are not text."""
    if raw.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    for candidate in ("utf-8", "cp932"):
        try:
            raw.decode(candidate)
        except UnicodeDecodeError:
            continue
        return candidate
    return None


def classify(relative: Path) -> tuple[str, str] | None:
    """Classify by the nearest recognized container directory, or by a known root name."""
    for part in reversed(relative.parts[:-1]):
        entry = CONTAINERS.get(part.lower())
        if entry:
            return entry
    if len(relative.parts) == 1:
        kind = ROOT_FILES.get(relative.as_posix())
        if kind:
            return (kind, "documentation")
    return None


def build_manifest(source: Path, args: argparse.Namespace) -> tuple[dict[str, Any], list[str]]:
    manifest_path = Path(args.output).expanduser().resolve() if args.output else source / MANIFEST_NAME
    files: list[dict[str, Any]] = []
    unclassified: list[str] = []
    seen: set[str] = set()
    for path in sorted(source.rglob("*")):
        if not path.is_file() or path.resolve() == manifest_path.resolve():
            continue
        relative = path.relative_to(source)
        entry = classify(relative)
        if entry is None:
            unclassified.append(relative.as_posix())
            if not args.allow_unclassified:
                continue
            entry = ("metadata", "unknown")
        kind, role = entry
        raw = path.read_bytes()
        encoding = detect_encoding(raw)
        if kind in TEXT_KINDS and encoding is None:
            # Declaring a binary as text would make the adapter decode it and fail
            # much later, with a message pointing at the wrong thing.
            unclassified.append(f"{relative.as_posix()} (not decodable as {'/'.join(ENCODINGS)})")
            continue
        # The logical id has to be unique across the package and stable between runs,
        # so it is derived from the path rather than a counter.
        logical_id = f"{args.logical_id_prefix}:{kind}:{relative.as_posix()}"
        if logical_id in seen:
            raise SystemExit(f"Duplicate logical id: {logical_id}")
        seen.add(logical_id)
        item: dict[str, Any] = {
            "logical_id": logical_id,
            "path": relative.as_posix(),
            "kind": kind,
            "role": role,
            "sha256": hashlib.sha256(raw).hexdigest(),
            "object_name": path.stem,
        }
        if encoding is not None and kind in TEXT_KINDS:
            item["encoding"] = encoding
        files.append(item)
    manifest: dict[str, Any] = {
        "version": "1.0",
        "producer": {"id": args.producer_id, "version": args.producer_version},
    }
    database = getattr(args, "source_database", None)
    if database:
        path = Path(database).expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"Source database not found: {path}")
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        manifest["source_database"] = {"path": str(path), "sha256": digest.hexdigest()}
    manifest["files"] = files
    return manifest, unclassified


def main() -> int:
    args = parse_args()
    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        raise SystemExit(f"Source is not a directory: {source}")
    manifest, unclassified = build_manifest(source, args)
    if not manifest["files"]:
        raise SystemExit(f"No classifiable files under {source}")
    # The adapter requires the declared set and the actual set to match exactly, so an
    # undeclared file would fail the import later with a far less specific message.
    if unclassified and not args.allow_unclassified:
        print(json.dumps({
            "status": "UNCLASSIFIED_FILES",
            "count": len(unclassified),
            "files": unclassified[:50],
            "remedy": "Move them into a recognized directory "
                      f"({', '.join(sorted(CONTAINERS))}) or pass --allow-unclassified.",
        }, ensure_ascii=False, indent=2))
        return 2
    manifest_path = Path(args.output).expanduser().resolve() if args.output else source / MANIFEST_NAME
    summary = {
        "status": "PLANNED" if args.dry_run else "WRITTEN",
        "manifest": str(manifest_path),
        "declared_files": len(manifest["files"]),
        "kinds": {kind: sum(1 for item in manifest["files"] if item["kind"] == kind)
                  for kind in sorted({item["kind"] for item in manifest["files"]})},
        "source_database": manifest.get("source_database", None),
    }
    if "source_database" not in manifest:
        summary["advisory"] = (
            "No --source-database was declared, so nothing can detect this export going stale "
            "against the database it came from. Pass it if the .mdb is available."
        )
    if not args.dry_run:
        manifest_path.write_text(
            yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
        )
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
