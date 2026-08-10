#!/usr/bin/env python3
"""Create provider-neutral, module-aware task envelopes from V2.1 contracts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


# `../../acquired` is where acquisition actually writes: per-artifact extraction
# receipts under acquired/staging/<artifact>/<acquisition-id>/ and the canonical bundle
# under acquired/bundle-<id>/. The legacy `extracted/access` path is created by init and
# then never written by anything, so every role pointed only there was reading an empty
# directory - including sql_data, which had no other source of schema at all.
ACQUISITION_INPUT = "../../acquired"
ROLE_INPUTS = {
    "source_inventory": ["manifest.lock.yaml", "source-inventory.json"],
    "access_extractor": ["manifest.lock.yaml", "source-inventory.json", "../../sources/access", ACQUISITION_INPUT, "../../extracted/access"],
    "build_context_analyzer": ["manifest.lock.yaml", "source-inventory.json", ACQUISITION_INPUT, "../../extracted/build-context"],
    "module_decomposer": ["manifest.lock.yaml", "source-inventory.json", ACQUISITION_INPUT, "../../extracted/access", "../../extracted/module-plan"],
    "sql_data": ["manifest.lock.yaml", "source-inventory.json", ACQUISITION_INPUT, "../../extracted/access", "../../extracted/module-plan"],
    "vba_ui": ["manifest.lock.yaml", "source-inventory.json", "../../sources/screenshots", "../../sources/reports", ACQUISITION_INPUT, "../../extracted/access", "../../extracted/module-plan"],
    "japanese_documents": ["manifest.lock.yaml", "source-inventory.json", ACQUISITION_INPUT, "../../shared-docs"],
    "file_interfaces": ["manifest.lock.yaml", "source-inventory.json", "../../sources/samples", "../../sources/reports", "../../sources/screenshots", ACQUISITION_INPUT, "../../extracted/module-plan"],
    "graph_builder": ["manifest.lock.yaml", "source-inventory.json", "../../extracted/component-index.json", "../../extracted/module-plan", "../../graphify-out"],
}
MODULE_FANOUT_ROLES = {"sql_data", "vba_ui", "file_interfaces", "logic_processing"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="Run directory")
    parser.add_argument("--package", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--no-module-fanout", action="store_true", help="Keep one task per role even when a module plan exists")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--work-package")
    parser.add_argument("--acceptance-receipt")
    parser.add_argument("--work-package-root")
    return parser.parse_args()


def safe_token(value: str) -> str:
    return re.sub(r"[^A-Z0-9_-]", "_", value.upper())


def task_id(app_id: str, wave: str, role: str, module_id: str | None = None) -> str:
    parts = [app_id, wave, role]
    if module_id:
        parts.append(module_id)
    return safe_token("-".join(parts))


def module_plan(run: Path) -> tuple[list[str], list[str]]:
    path = run.parent.parent / "extracted" / "module-plan" / "processing-order.json"
    if not path.is_file():
        return [], []
    data = json.loads(path.read_text(encoding="utf-8"))
    ordered = data.get("ordered_modules", [])
    order = [item["module_id"] for item in ordered]
    affected = set(data.get("affected_modules", []))
    leaves = [item["module_id"] for item in ordered if item.get("leaf") and item.get("component_ids") and (not affected or item["module_id"] in affected)]
    if not leaves:
        leaves = [item["module_id"] for item in ordered if item.get("leaf") and item.get("component_ids")]
    return order, leaves


def _handoff_instruction(allowed_writes: list[str]) -> str:
    """Ask for exactly what this role's write scope permits.

    ``roles.json`` grants ``evidence/fragments`` only to the roles that produce phase
    evidence, and ``conflicts`` only to the two document roles. Every role was told to
    return "evidence, gaps, conflicts, and artifacts" regardless, so a preparation role
    following its own instruction wrote outside its scope and failed validation.
    """
    parts = ["gaps"]
    if "evidence/fragments" in allowed_writes:
        parts.insert(0, "evidence")
    if "conflicts" in allowed_writes:
        parts.append("conflicts")
    parts.append("artifacts")
    listed = (
        f"{parts[0]} and {parts[1]}" if len(parts) == 2
        else ", ".join(parts[:-1]) + f", and {parts[-1]}"
    )
    sentence = f"Return a schema-valid handoff with {listed}."
    if "evidence/fragments" not in allowed_writes:
        sentence += (
            " This role does not produce phase evidence: leave evidence_ids empty and "
            "record findings as gaps and work artifacts instead."
        )
    return sentence


def scoped_writes(paths: list[str], role_id: str, module_id: str | None) -> list[str]:
    if not module_id:
        return paths
    scoped: list[str] = []
    for path in paths:
        if path == f"work/{role_id}":
            scoped.append(f"{path}/{safe_token(module_id).lower()}")
        else:
            scoped.append(path)
    return scoped


def _task_path(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value)
    if path.is_absolute() or ".." in path.parts:
        return None
    return "../../" + path.as_posix()


def _v22_source_inputs(data: dict, defaults: dict[str, list[str]]) -> dict[str, list[str]]:
    """Map a V2.2 manifest's artifacts onto the source buckets the roles consume.

    This function read only the V2.1 ``sources.*`` keys, so on a V2.2 manifest - the only
    shape acquisition accepts - every bucket came back empty and the evidence roles were
    handed no source paths at all: sql_data had no SQL, japanese_documents had no
    document. A directory or zip export package feeds both the VBA and the SQL bucket,
    because one package carries modules and query SQL together.
    """
    # A per-file artifact contributes its containing directory, not the file. `init
    # --source` declares one artifact per exported object, so a real application yields
    # dozens or hundreds; listing each one would bury the role's own guidance under a
    # path list it cannot read as a whole. A directory or zip package is already the
    # right granularity and is kept as declared.
    PACKAGE_FORMATS = {"directory", "zip"}
    UI_FORMATS = {"form", "report", "macro"}
    SQL_FORMATS = {"access_sql", "table_schema"}
    buckets: dict[str, list[str]] = {key: [] for key in defaults}

    def add(bucket: str, path: str, collapse: bool) -> None:
        value = path.rsplit("/", 1)[0] if collapse and "/" in path else path
        if value not in buckets[bucket]:
            buckets[bucket].append(value)

    for artifact in data.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        value = (artifact.get("source_ref") or {}).get("value")
        path = _task_path(value) if isinstance(value, str) else None
        if not path:
            continue
        kind = str(artifact.get("kind", ""))
        fmt = str(artifact.get("format", ""))
        package = fmt in PACKAGE_FORMATS
        if kind == "source_export" and package:
            # One package carries modules and query SQL together.
            add("vba", path, False)
            add("sql", path, False)
        elif kind == "source_export" and fmt in SQL_FORMATS:
            add("sql", path, True)
        elif kind == "source_export" and (fmt == "vba" or fmt in UI_FORMATS):
            add("vba", path, True)
        elif kind == "source_export":
            add("vba", path, True)
        elif kind.startswith("sql_server"):
            add("sql", path, not package)
        elif kind == "document":
            add("documents", path, True)
    for key, fallback in defaults.items():
        if not buckets[key]:
            buckets[key] = list(fallback)
        else:
            buckets[key] = list(dict.fromkeys(buckets[key]))
    return buckets


def manifest_source_inputs(run: Path) -> dict[str, list[str]]:
    """Return task-safe source paths declared in the locked app manifest."""
    defaults = {
        "vba": ["../../sources/vba"],
        "sql": ["../../sources/sql"],
        "documents": ["../../sources/documents"],
        "japanese_documents": ["../../shared-docs"],
    }
    manifest = run / "manifest.lock.yaml"
    if not manifest.is_file():
        return defaults
    try:
        import yaml  # type: ignore[import-not-found]

        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        if str(data.get("version")) == "2.2":
            return _v22_source_inputs(data, defaults)
        sources = data.get("sources", {})
        sql_server = sources.get("sql_server", {}) or {}
        japanese = sources.get("japanese_documents", {}) or {}
        values = {
            "vba": sources.get("vba_exports", []),
            "sql": sql_server.get("exported_paths", []),
            "documents": sources.get("app_documents", []),
            "japanese_documents": list(japanese.values()) if isinstance(japanese, dict) else [],
        }
        return {
            key: [item for value in raw if (item := _task_path(value))]
            for key, raw in values.items()
        }
    except (ImportError, OSError, AttributeError, TypeError, ValueError):
        return defaults


def input_paths_for(role_id: str, manifest_sources: dict[str, list[str]]) -> list[str]:
    paths = list(ROLE_INPUTS.get(role_id, ["manifest.lock.yaml", "source-inventory.json", "evidence", "outputs", "handoffs", "../../extracted/module-plan"]))
    if role_id == "sql_data":
        paths.extend(manifest_sources["sql"])
    elif role_id == "vba_ui":
        paths.extend(manifest_sources["vba"])
    elif role_id == "japanese_documents":
        paths.extend(manifest_sources["documents"])
        paths.extend(manifest_sources["japanese_documents"])
    return list(dict.fromkeys(paths))


def main() -> int:
    args = parse_args()
    collaboration_args = (
        args.work_package,
        args.acceptance_receipt,
        args.work_package_root,
    )
    if any(collaboration_args) and not all(collaboration_args):
        raise SystemExit(
            "--work-package, --acceptance-receipt, and --work-package-root "
            "must be provided together"
        )
    run = Path(args.run).expanduser().resolve()
    package = Path(args.package).expanduser().resolve()
    state = json.loads((run / "run-state.json").read_text(encoding="utf-8"))
    roles_data = json.loads((package / "orchestration/roles.json").read_text(encoding="utf-8"))
    waves = json.loads((package / "orchestration/waves.json").read_text(encoding="utf-8"))["waves"]
    merge_policy = json.loads((package / "orchestration/merge-policy.json").read_text(encoding="utf-8"))
    roles = {item["id"]: item for item in roles_data["roles"]}
    ordered_modules, leaf_modules = module_plan(run)
    fanout = bool(leaf_modules) and not args.no_module_fanout
    manifest_sources = manifest_source_inputs(run)

    tasks: list[dict] = []
    wave_task_ids: dict[str, list[str]] = {}
    now = datetime.now(timezone.utc).isoformat()
    for wave in waves:
        dependency_ids = [identifier for dependency_wave in wave["depends_on"] for identifier in wave_task_ids[dependency_wave]]
        wave_task_ids[wave["id"]] = []
        for role_id in wave["roles"]:
            role = roles[role_id]
            targets: list[str | None] = leaf_modules if fanout and role_id in MODULE_FANOUT_ROLES else [None]
            for module_id in targets:
                identifier = task_id(state["app_id"], wave["id"], role_id, module_id)
                wave_task_ids[wave["id"]].append(identifier)
                phases = [wave["phase_context"]] if wave.get("phase_context") else role.get("phases", [])
                phase_token = phases[0] if phases else 0
                instructions = [
                    role["purpose"],
                    "Resolve ../../ paths from the run directory; source-inventory.json is the authoritative included source list.",
                    "Use extracted Access text and metadata; never open the original MDB/ACCDB/ADP.",
                    "Treat compilation database entries as read-only context and never execute command or arguments values.",
                    "Write only inside the current run directory and only to write_paths.",
                    # The closing instruction has to match what this role may actually
                    # write. It asked every role for evidence and conflicts, including the
                    # preparation roles, graph_builder, synthesis and the renderers, whose
                    # allowed_writes in roles.json deliberately exclude evidence/fragments
                    # and conflicts. Following it produced an artifact outside the declared
                    # write scope, which validate_handoffs then rejected - so the role
                    # could satisfy its instruction or its scope, never both.
                    _handoff_instruction(role["allowed_writes"]),
                ]
                if role_id == "graph_builder":
                    instructions.insert(1, "Run graphify_phase_gate.py check for this phase and require READY; the graph is navigation context, never substitute inferred edges for source-backed evidence.")
                if module_id:
                    instructions.insert(1, f"Analyze only module {module_id}; follow the global leaf-first module_order and preserve cross-module dependencies as handoff references.")
                tasks.append({
                    "task_id": identifier, "run_id": state["run_id"], "app_id": state["app_id"], "wave_id": wave["id"], "role": role_id,
                    "phase_targets": phases, "module_targets": [module_id] if module_id else [], "module_order": ordered_modules,
                    "dependencies": dependency_ids, "input_paths": input_paths_for(role_id, manifest_sources),
                    "write_paths": scoped_writes(role["allowed_writes"], role_id, module_id), "evidence_namespace": f"{state['app_id']}-P{phase_token}-{safe_token(role_id)}" + (f"-{safe_token(module_id)}" if module_id else ""),
                    "instructions": instructions, "status": "PENDING", "attempt": 0,
                    "max_attempts": merge_policy["retry_policy"]["max_attempts_per_task"], "token_budget": None, "created_at": now,
                })
    if args.dry_run:
        print(json.dumps({"task_count": len(tasks), "module_fanout": fanout, "leaf_modules": leaf_modules, "tasks": tasks}, indent=2))
        return 0
    tasks_dir = run / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    if any(tasks_dir.glob("*.json")):
        raise SystemExit(f"Refusing to overwrite existing tasks in {tasks_dir}")
    for task in tasks:
        (tasks_dir / f"{task['task_id']}.json").write_text(json.dumps(task, indent=2) + "\n", encoding="utf-8")
    if args.work_package:
        root = Path(args.work_package_root).expanduser().resolve()
        work_package = Path(args.work_package).expanduser().resolve()
        try:
            work_package.relative_to(root)
        except ValueError as exc:
            raise SystemExit("Work package must be inside --work-package-root") from exc
        from collaboration_cli import project_package

        project_package(
            work_package,
            Path(args.acceptance_receipt),
            run,
        )
    print(f"Created {len(tasks)} task envelopes in {tasks_dir}; module_fanout={fanout}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
