from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from collaboration_helpers import (
    acceptance_receipt,
    application_package,
    candidate_task,
    impact,
    kit_package,
)


PACKAGE = Path(__file__).resolve().parents[1]
AK = PACKAGE / "scripts" / "ak.py"
CREATE_TASKS = PACKAGE / "scripts" / "create_tasks.py"


def run_cli(*args: str, expected: int = 0) -> dict:
    result = subprocess.run(
        [sys.executable, str(AK), *args],
        cwd=PACKAGE,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert result.returncode == expected, result.stdout + result.stderr
    return json.loads(result.stdout)


def write_json(path: Path, value: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
    return path


def test_package_validate_reports_digest(tmp_path: Path) -> None:
    path = write_json(tmp_path / "work-package.json", kit_package())

    data = run_cli("collaboration", "package", "validate", "--package", str(path))

    assert data["status"] == "VALID"
    assert len(data["work_package_digest"]) == 64


def test_package_conflicts_reports_write_collision(tmp_path: Path) -> None:
    first = application_package("WP_ONE")
    second = application_package("WP_TWO")
    second["write_paths"] = ["work/sql_data/module-orders/details"]
    second["expected_artifacts"][0]["path"] = (
        "work/sql_data/module-orders/details/result.json"
    )
    write_json(tmp_path / "WP_ONE" / "work-package.json", first)
    write_json(tmp_path / "WP_TWO" / "work-package.json", second)

    data = run_cli(
        "collaboration",
        "package",
        "conflicts",
        "--root",
        str(tmp_path),
        expected=2,
    )

    assert "COLLAB_WRITE_CONFLICT" in {
        conflict["code"] for conflict in data["conflicts"]
    }


def test_review_validate_accepts_scope_receipt(tmp_path: Path) -> None:
    package = application_package()
    package_path = write_json(tmp_path / "work-package.json", package)
    receipt_path = write_json(tmp_path / "receipt.json", acceptance_receipt(package))

    data = run_cli(
        "collaboration",
        "review",
        "validate",
        "--package",
        str(package_path),
        "--receipt",
        str(receipt_path),
    )

    assert data["status"] == "APPROVED"


def test_package_project_binds_matching_candidate(tmp_path: Path) -> None:
    package = application_package()
    package_path = write_json(tmp_path / "work-package.json", package)
    receipt_path = write_json(tmp_path / "receipt.json", acceptance_receipt(package))
    run = tmp_path / "run"
    task_path = write_json(run / "tasks" / "candidate.json", candidate_task())

    data = run_cli(
        "collaboration",
        "package",
        "project",
        "--package",
        str(package_path),
        "--receipt",
        str(receipt_path),
        "--run",
        str(run),
    )

    assert data["projected_tasks"] == 1
    assert json.loads(task_path.read_text(encoding="utf-8"))[
        "work_package_id"
    ] == package["package_id"]


def test_impact_validate_checks_changed_path_file(tmp_path: Path) -> None:
    package = kit_package()
    changed = ["plugins/ak/schemas/work-package.schema.json"]
    package_path = write_json(tmp_path / "work-package.json", package)
    impact_path = write_json(tmp_path / "impact.json", impact(package))
    changed_path = write_json(tmp_path / "changed-paths.json", changed)

    data = run_cli(
        "collaboration",
        "impact",
        "validate",
        "--package",
        str(package_path),
        "--impact",
        str(impact_path),
        "--changed-paths",
        str(changed_path),
    )

    assert data["status"] == "VALID"


def test_collaboration_errors_are_stable_json(tmp_path: Path) -> None:
    invalid = write_json(tmp_path / "work-package.json", {})

    data = run_cli(
        "collaboration",
        "package",
        "validate",
        "--package",
        str(invalid),
        expected=2,
    )

    assert data["status"] == "ERROR"
    assert data["code"] == "COLLAB_AUTHORITY_MISSING"


def test_create_tasks_projects_an_accepted_package(tmp_path: Path) -> None:
    run = tmp_path / "run"
    write_json(run / "run-state.json", {"run_id": "SYN-RUN", "app_id": "SYN"})
    preview = subprocess.run(
        [
            sys.executable,
            str(CREATE_TASKS),
            "--package",
            str(PACKAGE),
            "--run",
            str(run),
            "--dry-run",
        ],
        cwd=PACKAGE,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    task = next(
        item for item in json.loads(preview.stdout)["tasks"] if item["role"] == "sql_data"
    )
    package = application_package()
    package["scope"].update(
        {
            "roles": [task["role"]],
            "wave_ids": [task["wave_id"]],
            "phase_targets": task["phase_targets"],
            "module_targets": task["module_targets"],
            "profile_targets": [],
            "adapter_targets": [],
            "document_targets": [],
        }
    )
    package["input_paths"] = [
        path.removeprefix("../../") for path in task["input_paths"]
    ]
    package["write_paths"] = task["write_paths"]
    package["expected_artifacts"][0]["path"] = (
        task["write_paths"][0] + "/result.json"
    )
    package["evidence_namespace"] = task["evidence_namespace"]
    root = tmp_path / "packages"
    package_path = write_json(root / package["package_id"] / "work-package.json", package)
    receipt_path = write_json(
        root / package["package_id"] / "acceptance.json",
        acceptance_receipt(package),
    )

    result = subprocess.run(
        [
            sys.executable,
            str(CREATE_TASKS),
            "--package",
            str(PACKAGE),
            "--run",
            str(run),
            "--work-package",
            str(package_path),
            "--acceptance-receipt",
            str(receipt_path),
            "--work-package-root",
            str(root),
        ],
        cwd=PACKAGE,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    projected = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (run / "tasks").glob("*.json")
        if "work_package_id" in path.read_text(encoding="utf-8")
    ]
    assert [item["work_package_id"] for item in projected] == [package["package_id"]]
