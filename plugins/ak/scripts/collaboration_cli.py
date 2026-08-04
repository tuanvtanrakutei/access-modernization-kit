from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


PACKAGE = Path(__file__).resolve().parents[1]
CONTRACTS = PACKAGE / "contracts"
if str(CONTRACTS) not in sys.path:
    sys.path.insert(0, str(CONTRACTS))

from collaboration import (  # noqa: E402
    CollaborationError,
    find_collaboration_conflicts,
    load_work_package,
    project_task,
    work_package_digest,
)
from contract_impact import validate_contract_impact  # noqa: E402
from review import validate_review_receipt  # noqa: E402
from validate_handoffs import validate_run_handoffs  # noqa: E402


def _read_json(path: Path, code: str) -> Any:
    try:
        return json.loads(path.expanduser().resolve().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollaborationError(code, path.name) from exc


def validate_package(path: Path) -> dict[str, Any]:
    package = load_work_package(path.expanduser().resolve())
    return {
        "status": "VALID",
        "package_id": package["package_id"],
        "work_package_digest": work_package_digest(package),
    }


def scan_conflicts(root: Path) -> dict[str, Any]:
    paths = sorted(root.expanduser().resolve().glob("*/work-package.json"))
    packages = [load_work_package(path) for path in paths]
    conflicts = find_collaboration_conflicts(packages)
    return {
        "status": "CONFLICT" if conflicts else "VALID",
        "packages": len(packages),
        "conflicts": conflicts,
    }


def validate_review(package_path: Path, receipt_path: Path) -> dict[str, Any]:
    package = load_work_package(package_path.expanduser().resolve())
    receipt = _read_json(receipt_path, "COLLAB_REVIEW_STALE")
    validate_review_receipt(package, receipt)
    return {"status": receipt["decision"], "receipt_id": receipt["receipt_id"]}


def validate_impact(
    package_path: Path,
    impact_path: Path,
    changed_paths_path: Path,
) -> dict[str, Any]:
    package = load_work_package(package_path.expanduser().resolve())
    impact = _read_json(impact_path, "COLLAB_IMPACT_REQUIRED")
    changed_paths = _read_json(changed_paths_path, "COLLAB_IMPACT_REQUIRED")
    validate_contract_impact(package, impact, changed_paths)
    return {"status": "VALID", "impact_id": impact["impact_id"]}


def validate_handoff(run: Path, work_package_root: Path) -> dict[str, Any]:
    errors, validated, completed = validate_run_handoffs(
        run, work_package_root=work_package_root
    )
    if errors:
        raise CollaborationError("COLLAB_HANDOFF_INVALID", errors[0], detail=errors)
    return {"status": "VALID", "validated": validated, "completed": completed}


def project_run_tasks(
    package: dict[str, Any],
    receipt: dict[str, Any],
    run: Path,
) -> dict[str, Any]:
    validate_review_receipt(package, receipt)
    if receipt["review_stage"] != "scope_acceptance" or receipt["decision"] != "APPROVED":
        raise CollaborationError("COLLAB_REVIEW_STALE", "scope acceptance")
    projected: list[tuple[Path, dict[str, Any]]] = []
    tasks_dir = run.expanduser().resolve() / "tasks"
    for path in sorted(tasks_dir.glob("*.json")):
        task = _read_json(path, "COLLAB_PROJECTION_EXPANDED")
        scope = package["scope"]
        if (
            task.get("role") not in scope["roles"]
            or task.get("wave_id") not in scope["wave_ids"]
            or not set(task.get("phase_targets", [])).issubset(scope["phase_targets"])
            or not set(task.get("module_targets", [])).issubset(scope["module_targets"])
        ):
            continue
        bound = project_task(package, task)
        projected.append((path, bound))
    if not projected:
        raise CollaborationError("COLLAB_PROJECTION_EXPANDED", "no matching task")
    for path, bound in projected:
        path.write_text(
            json.dumps(bound, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return {"status": "PROJECTED", "projected_tasks": len(projected)}


def project_package(
    package_path: Path,
    receipt_path: Path,
    run: Path,
) -> dict[str, Any]:
    package = load_work_package(package_path.expanduser().resolve())
    receipt = _read_json(receipt_path, "COLLAB_REVIEW_STALE")
    return project_run_tasks(package, receipt, run)
