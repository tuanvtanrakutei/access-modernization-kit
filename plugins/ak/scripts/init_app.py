#!/usr/bin/env python3
"""Create or safely adopt an isolated workspace for one legacy SMS app without analyzing it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any
import yaml


APP_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,15}$")
# Folder names this kit's own extractor writes object definitions into.
_EXPORT_CONTAINERS = {"forms": "form", "reports": "report", "macros": "macro", "vba": "vba"}


# Organised by who owns it, not by which stage of the pipeline produced it. An
# operator used to meet seven top-level directories, four of which they never open,
# with the six phase documents two levels down inside runs/<run-id>/outputs/. There
# are three things here now: the file you edit, what you supply, and what you read -
# everything the kit owns is under .ak/ and is never opened by hand.
#
# Declared by the workspace section of specifications/evidence-layout.yaml, and
# resolved for both layouts by contracts/workspace.py, which is the only place that
# knows a pre-2.10.0 workspace calls these sources/, acquired/, extracted/ and runs/.
SOURCE_DIRS = (
    "input/access",
    # V2.1 declares exported sources at two fixed paths. A V2.2 project receives them
    # as a declared package under its own artifact id instead, but the legacy contract
    # still names these, so they stay as input containers.
    "input/vba",
    "input/sql",
    "input/documents",
    "input/screenshots",
    "input/samples",
    # Samples of what the application produced. `reports/` inside an export package
    # already means report definitions, and `reports-out` dodged that collision with
    # a suffix that told a reader nothing.
    "input/report-samples",
    # A recorded answer from a named person carries findings nothing else in the
    # corpus can. It had no home, so it had no shape either.
    "input/interviews",
    "input/shared-docs",
    "input/decisions",
    "output",
    ".ak/extracted/build-context",
    ".ak/extracted/module-plan",
    ".ak/runs",
)
OWNED_FILES = (
    "manifest.yaml",
    ".gitignore",
    ".investigationignore",
)


def safe_extract_zip(zip_path: Path, dest_dir: Path) -> None:
    with zipfile.ZipFile(zip_path, "r") as archive:
        for info in archive.infolist():
            member_path = PurePosixPath(info.filename.replace(chr(92), "/"))
            if member_path.is_absolute() or ".." in member_path.parts:
                raise ValueError(f"Unsafe zip member path: {info.filename}")
            target = (dest_dir / member_path).resolve()
            try:
                target.relative_to(dest_dir.resolve())
            except ValueError:
                raise ValueError(f"Zip path escape attempt: {info.filename}")
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(info) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)


def _input_root(app_root: Path) -> Path:
    """Where a person puts things: `input/`, or `sources/` in a pre-2.10.0 workspace.

    Adopting an existing workspace must not create a second plausible place to look,
    which is the defect this whole layout change is against.
    """
    legacy = app_root / "sources"
    return legacy if legacy.is_dir() and not (app_root / "input").is_dir() else app_root / "input"


def discover_sources(app_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    sources_dir = _input_root(app_root)
    if not sources_dir.exists():
        return {
            "topology": "monolith",
            "frontend_format": "exported",
            "source_availability": "exported_only",
            "backend_kinds": ["embedded_access"],
        }, []

    artifacts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    found_db = False
    found_sql = False
    frontend_fmt = "exported"

    for file_path in sorted(sources_dir.rglob("*")):
        if file_path.is_dir():
            continue
        rel_path = file_path.relative_to(app_root).as_posix()
        if rel_path in OWNED_FILES or rel_path.endswith(".yaml") or rel_path.startswith("."):
            continue
        suffix = file_path.suffix.lower()
        stem = file_path.stem

        # This kit's own extractor writes object definitions as .txt under forms/,
        # reports/, macros/ and vba/, and query SQL under queries/. Classifying by
        # extension alone dropped all of it into the catch-all "sample" bucket, so the
        # package did not recognize the output it had produced itself.
        container = file_path.parent.name.lower()
        if suffix == ".txt" and container in _EXPORT_CONTAINERS:
            kind, fmt, role, acq = "source_export", _EXPORT_CONTAINERS[container], "frontend", "imported"
        elif suffix == ".txt" and container == "schema":
            kind, fmt, role, acq = "source_export", "table_schema", "backend", "imported"
        elif suffix in (".bas", ".cls", ".vba"):
            kind, fmt, role, acq = "source_export", "vba", "frontend", "imported"
        elif suffix == ".sql":
            kind, fmt, role, acq = "source_export", "access_sql", "backend", "imported"
            # Query SQL exported out of an Access database is not evidence of a SQL
            # Server backend. Only .sql outside a queries/ folder - the V2.1 layout's
            # sources/sql/ - implies a server.
            found_sql = found_sql or container != "queries"
        elif suffix in (".form", ".fmt", ".frm"):
            kind, fmt, role, acq = "source_export", "form", "frontend", "imported"
        elif suffix in (".report", ".rpt"):
            kind, fmt, role, acq = "source_export", "report", "frontend", "imported"
        elif suffix in (".macro", ".mcr"):
            kind, fmt, role, acq = "source_export", "macro", "frontend", "imported"
        elif suffix in (".mdb", ".accdb", ".adp"):
            kind, fmt, role, acq = "access_database", suffix[1:], "frontend", "managed"
            found_db = True
            frontend_fmt = suffix[1:]
        elif suffix in (".png", ".jpg", ".jpeg", ".bmp"):
            kind, fmt, role, acq = "screenshot", suffix[1:], "interface", "imported"
        elif suffix in (".pdf", ".docx", ".xlsx", ".md"):
            kind, fmt, role, acq = "document", suffix[1:], "documentation", "imported"
        else:
            kind, fmt, role, acq = "sample", suffix[1:] if suffix else "text", "interface", "imported"

        # A Japanese name - the norm in this kit's target systems - loses every
        # character to this sanitize, so distinct objects collapsed onto the same
        # base and were then separated by an arrival-order counter: ART, ART_1,
        # ART_2, unstable between runs whenever the file order changed. A short
        # digest of the original name keeps the id unique and reproducible, the same
        # technique extract_access.ps1 already uses for its filenames.
        base_id = re.sub(r"[^A-Z0-9_]+", "_", stem.upper()).strip("_")
        if not stem.isascii() or not base_id:
            digest = hashlib.sha1(stem.encode("utf-8")).hexdigest()[:8].upper()
            base_id = f"{base_id}_{digest}" if base_id else f"ART_{digest}"
        art_id = base_id
        idx = 1
        while art_id in seen_ids:
            art_id = f"{base_id}_{idx}"
            idx += 1
        seen_ids.add(art_id)

        artifacts.append({
            "id": art_id,
            "kind": kind,
            "role": role,
            "acquisition": acq,
            "required": True,
            "format": fmt,
            "source_ref": {
                "type": "local_path",
                "value": rel_path,
            },
        })

    # More than one Access database is a split application: a frontend holding the UI
    # and code, and a separate file holding the data. Declaring it a monolith with two
    # frontends - which is what this returned for every such app - is wrong three
    # times over, and the wrong role is the costly one: nothing then declares an
    # authoritative backend, so Phase 1 can never leave BLOCKED.
    access_ids = [item["id"] for item in artifacts if item["kind"] == "access_database"]
    split = len(access_ids) > 1
    if split:
        # Which file is authoritative cannot be read off the filesystem, and guessing
        # wrong carries real rework, so the role is left explicitly unknown for a
        # human to resolve rather than assigned by filename.
        for item in artifacts:
            if item["kind"] == "access_database":
                item["role"] = "unknown"
    if found_sql or frontend_fmt == "adp":
        backend_kinds = ["sql_server"]
    elif split:
        backend_kinds = ["access_file"]
    else:
        backend_kinds = ["embedded_access"]
    source_avail = "full" if found_db else "exported_only"
    classification = {
        "topology": "split_file" if split else "monolith",
        "frontend_format": frontend_fmt,
        "source_availability": source_avail,
        "backend_kinds": backend_kinds,
    }
    return classification, artifacts


# Mirrors contracts/acquisition_preview.observed_mode. The two are pinned together by
# a test rather than shared through an import, because this script is run standalone
# from a path that does not carry the contracts package.
def acquisition_mode(artifacts: list[dict[str, Any]]) -> str:
    has_extract = any(a.get("kind") == "access_database" or a.get("acquisition") == "managed" for a in artifacts)
    has_export = any(a.get("kind") in {"source_export", "producer_export"} for a in artifacts)
    if has_extract and has_export:
        return "mixed"
    if has_extract:
        return "extract"
    return "export" if has_export else "none"


# Written above the generated YAML because the two decisions an operator must still
# make - which database is authoritative, and whether to start an Access host - are
# invisible otherwise: one shows up as the word "unknown", the other as a switch that
# could previously be discovered only by reading adapter source.
_MANIFEST_HEADER = """\
# Generated by ak.py init. Two things still need a human before acquisition:
#
#   1. role: unknown on an Access database - say which file is the frontend and
#      which is the authoritative backend. Nothing on disk states it, and guessing
#      wrong is expensive to undo later.
#
#   2. runtime.skip_object_export on each managed artifact - decides whether this
#      run starts an Access host:
#        true  - DAO tier only. Schema, queries and the object-name inventory are
#                collected. No AutoExec, no VBA project load, no modal dialog, and
#                no administrator requirement. Object definition text is not exported.
#        false - also exports object definition text, which starts an Access host and
#                needs COM activation to succeed (an executable carrying RUNASADMIN
#                fails with 0x800702E4 until the flag is removed or the run is elevated).
#
# Run `ak.py acquire plan` to see which capabilities and phases this manifest can
# reach before acquiring anything.
"""


def manifest_v22_text(
    app_id: str,
    name_en: str,
    classification: dict[str, Any],
    artifacts: list[dict[str, Any]],
) -> str:
    data = {
        "version": "2.2",
        "app": {
            "id": app_id,
            "name_en": name_en,
            "name_ja": "",
            "name_vi": "",
        },
        "project": {
            "acquisition_mode": acquisition_mode(artifacts),
            "classification": classification,
        },
        "artifacts": artifacts,
    }
    rendered = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    # safe_dump cannot carry comments, so the one field a human must resolve is marked
    # after the fact. The token is distinctive enough that this cannot hit anything else.
    rendered = rendered.replace(
        "role: unknown\n",
        "role: unknown  # TODO: set frontend or backend before acquiring\n",
    )
    return _MANIFEST_HEADER + rendered


def manifest_text(app_id: str, name_en: str, languages: list[str], runtime: str, max_parallel: int) -> str:
    language_list = ", ".join(f'"{lang}"' for lang in languages)
    return f'''version: "2.1"
app:
  id: "{app_id}"
  name_en: "{name_en}"
  name_ja: ""
  name_vi: ""
scope:
  legacy_only: true
  current_implementation: "excluded"
  notes: "Analyze legacy Access VBA and SQL Server behavior only."
sources:
  access_databases: []
  vba_exports: ["input/vba"]
  sql_server:
    exported_paths: ["input/sql"]
    live:
      enabled: false
      connection_ref: ""
  screenshots: ["input/screenshots"]
  reports: ["input/report-samples"]
  sample_files: ["input/samples"]
  app_documents: ["input/documents"]
  japanese_documents:
    operational_functions_xlsx: "input/shared-docs/Operational functions and report data list.xlsx"
    training_manual_xlsx: "input/shared-docs/SMS Basic Training Manual (From the Perspective of the Order Processing Department).xlsx"
    business_flow_pdf: "input/shared-docs/diagram sms_system_business_diagram.pdf"
    architecture_pdf: "input/shared-docs/SMS System Replacement Project Overview Attached Diagram.pdf"
analysis:
  source_policy:
    ignore_file: ".investigationignore"
    include_patterns: []
    ignore_patterns: []
  build_context:
    compilation_databases: []
    compile_flags: []
    projects: []
    execute_commands: false
  module_planning:
    enabled: true
    strategy: "hierarchical_leaf_first"
    incremental_refresh: true
shared_context:
  global_sms_graph: ""
  shared_decisions: []
outputs:
  root: "outputs"
  languages: [{language_list}]
  presentation_template: ""
  derived:
    e2e_html: true
    boundary_html: true
    presentation_pptx: false  # optional; enable only when a presentation is required
  refresh_policy: "before_each_phase"
  corpus_policy: "binary_free_normalized"
multi_agent:
  enabled: true
  preferred_runtime: "{runtime}"
  max_parallel: {max_parallel}
  coordinator_only_merge: true
  independent_qa: true
  evidence_collection_parallel: true
  phase_publication_sequential: true
  conflict_policy: "record_and_escalate"
  human_checkpoints: ["inventory", "context_extraction", "module_plan", "phase1_phase2", "phase3", "phase4_phase5", "phase6", "qa"]
'''


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    location = parser.add_mutually_exclusive_group(required=True)
    location.add_argument("--root", help="Parent directory for a new app workspace")
    location.add_argument("--app-root", help="Existing or new app workspace directory")
    parser.add_argument("--app-id", required=True, help="App identifier such as A03")
    parser.add_argument("--name-en", required=True, help="English business name")
    parser.add_argument(
        "--languages",
        default="EN",
        help="Comma-separated output languages from EN,JA,VI (default: EN)",
    )
    parser.add_argument("--source", help="Path to source directory or ZIP archive for automatic imported_sources discovery")
    parser.add_argument("--dry-run", action="store_true", help="Print planned paths only")
    parser.add_argument(
        "--adopt-existing",
        action="store_true",
        help="Allow safe initialization of a non-empty --app-root without modifying existing files",
    )
    parser.add_argument("--runtime", choices=("codex", "claude", "generic"), default="generic")
    parser.add_argument("--max-parallel", type=int, default=4)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app_id = args.app_id.upper()
    if not APP_ID_RE.fullmatch(app_id):
        raise SystemExit("Invalid --app-id. Use 2-16 uppercase letters, digits, underscores, or hyphens.")

    languages = [item.strip().upper() for item in args.languages.split(",") if item.strip()]
    invalid = sorted(set(languages) - {"EN", "JA", "VI"})
    if not languages or invalid:
        raise SystemExit(f"Invalid --languages: {invalid or 'empty list'}")
    if args.max_parallel < 1:
        raise SystemExit("--max-parallel must be at least 1")

    app_root = Path(args.app_root).expanduser().resolve() if args.app_root else Path(args.root).expanduser().resolve() / app_id
    if args.app_root and app_root.name.upper() != app_id:
        raise SystemExit("--app-root directory name must match --app-id")

    planned = [app_root / item for item in SOURCE_DIRS]
    planned += [app_root / item for item in OWNED_FILES]
    if args.dry_run:
        print(json.dumps({
            "app_root": str(app_root),
            "planned": [str(path) for path in planned],
            "adopt_existing": args.adopt_existing,
        }, indent=2))
        return 0

    existing_nonempty = app_root.exists() and any(app_root.iterdir())
    if existing_nonempty and not args.adopt_existing:
        raise SystemExit(f"Refusing to initialize non-empty directory without --adopt-existing: {app_root}")
    if existing_nonempty:
        already_initialized = [relative for relative in OWNED_FILES if (app_root / relative).exists()]
        if already_initialized:
            raise SystemExit(
                "Workspace already contains kit-owned files; use preflight instead: "
                + ", ".join(already_initialized)
            )

    for directory in SOURCE_DIRS:
        (app_root / directory).mkdir(parents=True, exist_ok=True)

    if args.source:
        src_path = Path(args.source).expanduser().resolve()
        if not src_path.exists():
            raise SystemExit(f"Source path does not exist: {src_path}")
        sources_dest = _input_root(app_root)
        sources_dest.mkdir(parents=True, exist_ok=True)
        if src_path.is_file() and (src_path.suffix.lower() == ".zip" or zipfile.is_zipfile(src_path)):
            safe_extract_zip(src_path, sources_dest)
        elif src_path.is_dir() and src_path.resolve() != sources_dest.resolve():
            for item in src_path.iterdir():
                dest_item = sources_dest / item.name
                if item.is_dir():
                    if dest_item.exists():
                        shutil.rmtree(dest_item)
                    shutil.copytree(item, dest_item)
                else:
                    shutil.copy2(item, dest_item)
        elif src_path.is_file():
            shutil.copy2(src_path, sources_dest / src_path.name)

    classification, discovered_artifacts = discover_sources(app_root)
    if discovered_artifacts:
        manifest_content = manifest_v22_text(app_id, args.name_en, classification, discovered_artifacts)
    else:
        manifest_content = manifest_text(app_id, args.name_en, languages, args.runtime, args.max_parallel)

    (app_root / "manifest.yaml").write_text(manifest_content, encoding="utf-8")
    package_root = Path(__file__).resolve().parent.parent
    for source_name, target_name in (
        ("app.gitignore", ".gitignore"),
        ("app.investigationignore", ".investigationignore"),
    ):
        shutil.copy2(package_root / "templates" / source_name, app_root / target_name)

    # The guide to input/ belongs beside the folders it describes, and it belongs to
    # the kit rather than to a project: it explains what each evidence class can
    # establish, which is the same everywhere. What a particular project still needs
    # is the evidence request in output/, which is regenerated as the run learns.
    guide = _input_root(app_root) / "README.md"
    guide.parent.mkdir(parents=True, exist_ok=True)
    if not guide.exists():
        shutil.copy2(package_root / "templates" / "input.README.md", guide)
    verb = "Adopted existing workspace" if existing_nonempty else "Initialized"
    print(f"{verb} {app_root}")
    # A role left unknown blocks Phase 1 by design, so say so here rather than letting
    # it surface much later as an unexplained readiness failure.
    undeclared = [item["id"] for item in discovered_artifacts if item.get("role") == "unknown"]
    if undeclared:
        print(
            f"Split application detected ({classification['topology']}). Set role: backend and "
            f"backend_kind on the authoritative database in manifest.yaml - Phase 1 stays BLOCKED "
            f"until one is declared. Undeclared: {', '.join(undeclared)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
