#!/usr/bin/env python3
"""Create provider-neutral, module-aware task envelopes from V2.1 contracts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


ROLE_INPUTS = {
    "source_inventory": ["manifest.lock.yaml", "source-inventory.json"],
    "access_extractor": ["manifest.lock.yaml", "source-inventory.json", "../../sources/access", "../../extracted/access"],
    "build_context_analyzer": ["manifest.lock.yaml", "source-inventory.json", "../../extracted/build-context"],
    "module_decomposer": ["manifest.lock.yaml", "source-inventory.json", "../../extracted/access", "../../extracted/module-plan"],
    "sql_data": ["manifest.lock.yaml", "source-inventory.json", "../../sources/sql", "../../extracted/access", "../../extracted/module-plan"],
    "vba_ui": ["manifest.lock.yaml", "source-inventory.json", "../../sources/vba", "../../sources/screenshots", "../../sources/reports", "../../extracted/access", "../../extracted/module-plan"],
    "japanese_documents": ["manifest.lock.yaml", "source-inventory.json", "../../shared-docs"],
    "file_interfaces": ["manifest.lock.yaml", "source-inventory.json", "../../sources/samples", "../../sources/reports", "../../sources/screenshots", "../../extracted/module-plan"],
}
MODULE_FANOUT_ROLES = {"sql_data", "vba_ui", "file_interfaces", "logic_processing"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, help="Run directory")
    parser.add_argument("--package", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--no-module-fanout", action="store_true", help="Keep one task per role even when a module plan exists")
    parser.add_argument("--dry-run", action="store_true")
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


def main() -> int:
    args = parse_args()
    run = Path(args.run).expanduser().resolve()
    package = Path(args.package).expanduser().resolve()
    state = json.loads((run / "run-state.json").read_text(encoding="utf-8"))
    roles_data = json.loads((package / "orchestration/roles.json").read_text(encoding="utf-8"))
    waves = json.loads((package / "orchestration/waves.json").read_text(encoding="utf-8"))["waves"]
    merge_policy = json.loads((package / "orchestration/merge-policy.json").read_text(encoding="utf-8"))
    roles = {item["id"]: item for item in roles_data["roles"]}
    ordered_modules, leaf_modules = module_plan(run)
    fanout = bool(leaf_modules) and not args.no_module_fanout

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
                phases = role.get("phases", [])
                phase_token = phases[0] if phases else 0
                instructions = [
                    role["purpose"],
                    "Resolve ../../ paths from the run directory; source-inventory.json is the authoritative included source list.",
                    "Use extracted Access text and metadata; never open the original MDB/ACCDB/ADP.",
                    "Treat compilation database entries as read-only context and never execute command or arguments values.",
                    "Write only inside the current run directory and only to write_paths.",
                    "Return a schema-valid handoff with evidence, gaps, conflicts, and artifacts.",
                ]
                if module_id:
                    instructions.insert(1, f"Analyze only module {module_id}; follow the global leaf-first module_order and preserve cross-module dependencies as handoff references.")
                tasks.append({
                    "task_id": identifier, "run_id": state["run_id"], "app_id": state["app_id"], "wave_id": wave["id"], "role": role_id,
                    "phase_targets": phases, "module_targets": [module_id] if module_id else [], "module_order": ordered_modules,
                    "dependencies": dependency_ids, "input_paths": ROLE_INPUTS.get(role_id, ["manifest.lock.yaml", "source-inventory.json", "evidence", "outputs", "handoffs", "../../extracted/module-plan"]),
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
    print(f"Created {len(tasks)} task envelopes in {tasks_dir}; module_fanout={fanout}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
