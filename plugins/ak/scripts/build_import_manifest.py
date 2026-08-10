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

# Directory name -> (declared kind, default role).
CONTAINERS: dict[str, tuple[str, str]] = {
    "forms": ("form", "frontend"),
    "reports": ("report", "frontend"),
    "macros": ("macro", "frontend"),
    "vba": ("vba", "frontend"),
    "modules": ("vba", "frontend"),
    "queries": ("access_sql", "backend"),
    "schema": ("metadata", "backend"),
    "sql": ("sql_server", "backend"),
    "sql-server": ("sql_server", "backend"),
    "documents": ("document", "documentation"),
    "screenshots": ("screenshot", "interface"),
    "samples": ("sample", "interface"),
}
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
    """Classify by the nearest recognized container directory."""
    for part in reversed(relative.parts[:-1]):
        entry = CONTAINERS.get(part.lower())
        if entry:
            return entry
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
    manifest = {
        "version": "1.0",
        "producer": {"id": args.producer_id, "version": args.producer_version},
        "files": files,
    }
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
    }
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
