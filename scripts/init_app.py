#!/usr/bin/env python3
"""Create an isolated workspace for one legacy SMS app without analyzing it."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


APP_ID_RE = re.compile(r"^[A-Z][A-Z0-9_-]{1,15}$")
SOURCE_DIRS = (
    "sources/vba",
    "sources/sql",
    "sources/access",
    "sources/screenshots",
    "sources/reports",
    "sources/samples",
    "sources/documents",
    "shared-docs",
    "extracted/access",
    "extracted/build-context",
    "extracted/module-plan",
    "decisions",
    "evidence",
    "outputs",
    "graphify-out",
    "runs",
)


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
  vba_exports: ["sources/vba"]
  sql_server:
    exported_paths: ["sources/sql"]
    live:
      enabled: false
      connection_ref: ""
  screenshots: ["sources/screenshots"]
  reports: ["sources/reports"]
  sample_files: ["sources/samples"]
  app_documents: ["sources/documents"]
  japanese_documents:
    operational_functions_xlsx: "shared-docs/Operational functions and report data list.xlsx"
    training_manual_xlsx: "shared-docs/SMS Basic Training Manual (From the Perspective of the Order Processing Department).xlsx"
    business_flow_pdf: "shared-docs/diagram sms_system_business_diagram.pdf"
    architecture_pdf: "shared-docs/SMS System Replacement Project Overview Attached Diagram.pdf"
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
  global_sms_graph: "shared/graphify-out/graph.json"
  shared_decisions: []
outputs:
  root: "outputs"
  languages: [{language_list}]
  presentation_template: ""
  derived:
    e2e_html: true
    boundary_html: true
    presentation_pptx: true
graphify:
  enabled: true
  mode: "standard"
  output_dir: "graphify-out"
  link_shared_nodes: true
  input_policy: "extracted_text_and_supported_sources"
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
    parser.add_argument("--root", required=True, help="Parent directory for app workspaces")
    parser.add_argument("--app-id", required=True, help="App identifier such as A03")
    parser.add_argument("--name-en", required=True, help="English business name")
    parser.add_argument(
        "--languages",
        default="EN",
        help="Comma-separated output languages from EN,JA,VI (default: EN)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned paths only")
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

    app_root = Path(args.root).expanduser().resolve() / app_id
    planned = [app_root / item for item in SOURCE_DIRS]
    planned += [app_root / "manifest.yaml", app_root / "evidence/evidence.json", app_root / ".gitignore", app_root / ".graphifyignore", app_root / ".investigationignore"]

    if args.dry_run:
        print(json.dumps({"app_root": str(app_root), "planned": [str(p) for p in planned]}, indent=2))
        return 0

    if app_root.exists() and any(app_root.iterdir()):
        raise SystemExit(f"Refusing to initialize non-empty directory: {app_root}")

    for directory in SOURCE_DIRS:
        (app_root / directory).mkdir(parents=True, exist_ok=True)

    (app_root / "manifest.yaml").write_text(
        manifest_text(app_id, args.name_en, languages, args.runtime, args.max_parallel), encoding="utf-8"
    )
    evidence = {
        "app_id": app_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": [],
    }
    (app_root / "evidence/evidence.json").write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    package_root = Path(__file__).resolve().parent.parent
    for source_name, target_name in (
        ("app.gitignore", ".gitignore"),
        ("app.graphifyignore", ".graphifyignore"),
        ("app.investigationignore", ".investigationignore"),
    ):
        shutil.copy2(package_root / "templates" / source_name, app_root / target_name)
    print(f"Initialized {app_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
