from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import jsonschema
import pytest
from collaboration import (
    CollaborationError,
    _task_logical_path,
    project_task,
    work_package_digest,
)
from collaboration_helpers import acceptance_receipt, application_package, candidate_task, kit_package, mixed_package
from review import validate_review_receipt
from validate_handoffs import in_write_scope, validate_run_handoffs


def schema(name: str) -> dict:
    path = Path(__file__).resolve().parents[1] / "schemas" / name
    return json.loads(path.read_text(encoding="utf-8"))


def legacy_handoff(task: dict) -> dict:
    return {
        "task_id": task["task_id"], "run_id": task["run_id"], "app_id": task["app_id"],
        "role": task["role"], "status": "COMPLETED", "summary": "Synthetic handoff",
        "artifacts": [], "evidence_ids": [], "gaps": [], "conflict_ids": [],
        "source_files_read": [], "completed_at": "2026-07-28T00:20:00Z",
    }


def collaboration_handoff(package: dict, task: dict) -> dict:
    return {
        **legacy_handoff(task),
        "agent_id": "implementation-agent",
        "artifacts": [
            artifact["path"]
            for artifact in package["expected_artifacts"]
            if artifact["required"]
        ],
        "work_package_id": package["package_id"],
        "work_package_digest": work_package_digest(package),
        "produced_revision": None,
        "validation_results": [
            {"command": command, "exit_code": 0, "result": "PASS"}
            for command in package["validation_commands"]
        ],
        "review_receipt_required": True,
    }


def implementation_receipt(
    package: dict,
    *,
    stage: str = "implementation",
    producer: str = "implementation-agent",
    produced_revision: str | None = None,
    produced_artifact_digest: str | None = None,
    publication_phase: int | None = None,
) -> dict:
    receipt = acceptance_receipt(package)
    receipt["review_stage"] = stage
    receipt["producer"] = producer
    receipt["reviewed_at"] = "2026-07-28T00:30:00Z"
    if stage == "publication" and publication_phase is None:
        publication_phase = 1
    if publication_phase is not None:
        receipt["publication_phase"] = publication_phase
    if produced_revision is not None:
        receipt["authority_snapshot"] = {
            **receipt["authority_snapshot"],
            "produced_revision": produced_revision,
        }
    if produced_artifact_digest is not None:
        receipt["authority_snapshot"] = {
            **receipt["authority_snapshot"],
            "produced_artifact_digest": produced_artifact_digest,
        }
    return receipt


def expected_artifact_set_digest(run: Path, artifacts: list[str]) -> str:
    entries = sorted(
        (
            artifact.casefold(),
            hashlib.sha256((run / artifact).read_bytes()).hexdigest(),
        )
        for artifact in artifacts
    )
    encoded = json.dumps(entries, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def handoff_receipt(package: dict, run: Path, handoff: dict) -> dict:
    authority_kind = package["authority"]["kind"]
    return implementation_receipt(
        package,
        producer=handoff["agent_id"],
        produced_revision=(
            handoff["produced_revision"]
            if authority_kind in {"repository_revision", "mixed"}
            else None
        ),
        produced_artifact_digest=(
            expected_artifact_set_digest(run, handoff["artifacts"])
            if authority_kind == "approved_bundle"
            else None
        ),
    )


def write_review_receipt(
    package_root: Path, receipt: dict, filename: str | None = None
) -> Path:
    reviews = package_root.parent / "reviews"
    reviews.mkdir(parents=True, exist_ok=True)
    path = reviews / (filename or f"{receipt['receipt_id']}.json")
    path.write_text(json.dumps(receipt), encoding="utf-8")
    return path


def valid_run_state() -> dict:
    return {
        "run_id": "SYN-RUN",
        "package_version": "2.8.0",
        "app_id": "SYN",
        "manifest_path": "manifest.lock.yaml",
        "manifest_sha256": "a" * 64,
        "runtime": "generic",
        "max_parallel": 1,
        "status": "RUNNING",
        "current_wave": "wave1_source_extraction",
        "wave_status": {"wave1_source_extraction": "RUNNING"},
        "phase_gates": {f"phase{number}": "PENDING" for number in range(1, 7)},
        "created_at": "2026-07-28T00:00:00Z",
        "updated_at": "2026-07-28T00:00:00Z",
    }


def valid_source_inventory() -> dict:
    return {
        "app_id": "SYN",
        "generated_at": "2026-07-28T00:00:00Z",
        "policy": {
            "ignore_file": ".investigationignore",
            "source_roots": [],
            "include_patterns": [],
            "ignore_patterns": [],
        },
        "files": [],
        "ignored": [],
    }


def inventory_file(relative_path: str) -> dict:
    return {
        "relative_path": relative_path,
        "size": 1,
        "sha256": "b" * 64,
        "source_category": "SQL",
        "human_language": "UNKNOWN",
        "programming_language": "SQL",
        "dialect": "",
        "encoding": "utf-8",
        "parser": "",
        "parser_version": "",
        "parse_status": "NOT_ATTEMPTED",
        "sensitive": False,
    }


def write_run(
    tmp_path: Path,
    package: dict,
    *,
    task_changes: dict | None = None,
    handoff_changes: dict | None = None,
    create_package: bool = True,
    create_receipt: bool = True,
) -> tuple[Path, Path, dict, dict]:
    package_root = tmp_path / "collaboration" / "work-packages"
    if create_package:
        package_path = package_root / package["package_id"] / "work-package.json"
        package_path.parent.mkdir(parents=True)
        package_path.write_text(json.dumps(package), encoding="utf-8")

    run = tmp_path / "run"
    (run / "tasks").mkdir(parents=True)
    (run / "handoffs").mkdir()
    (run / "run-state.json").write_text(json.dumps(valid_run_state()), encoding="utf-8")
    (run / "source-inventory.json").write_text(json.dumps(valid_source_inventory()), encoding="utf-8")
    task = project_task(package, candidate_task())
    task.update(task_changes or {})
    (run / "tasks" / f"{task['task_id']}.json").write_text(json.dumps(task), encoding="utf-8")
    handoff = collaboration_handoff(package, task)
    for artifact in handoff["artifacts"]:
        artifact_path = run / artifact
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("{}", encoding="utf-8")
    handoff.update(handoff_changes or {})
    for artifact in handoff["artifacts"] if isinstance(handoff.get("artifacts"), list) else []:
        try:
            logical = _task_logical_path(artifact, allow_parent_prefix=False)
        except CollaborationError:
            continue
        if in_write_scope(logical, task["write_paths"]):
            artifact_path = run / logical
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            if not artifact_path.exists():
                artifact_path.write_text("{}", encoding="utf-8")
    (run / "handoffs" / f"{task['task_id']}.json").write_text(json.dumps(handoff), encoding="utf-8")
    if (
        create_receipt
        and task_changes is None
        and handoff.get("status") == "COMPLETED"
    ):
        receipt_error = f"{package['package_id']}: implementation review receipt required"
        preflight_errors, _, _ = validate_run_handoffs(
            run, work_package_root=package_root
        )
        other_errors = [error for error in preflight_errors if error != receipt_error]
        if receipt_error in preflight_errors and all(
            error.startswith(f"{package['package_id']}: required artifact not reported:")
            for error in other_errors
        ):
            receipt = handoff_receipt(package, run, handoff)
            receipt["receipt_id"] = f"RR-IMPL-{task['task_id']}"
            write_review_receipt(package_root, receipt)
    return run, package_root, task, handoff


def write_multi_task_run(
    tmp_path: Path,
    package: dict,
    task_outputs: list[tuple[str, str, list[str], str]],
) -> tuple[Path, Path]:
    package_root = tmp_path / "collaboration" / "work-packages"
    package_path = package_root / package["package_id"] / "work-package.json"
    package_path.parent.mkdir(parents=True)
    package_path.write_text(json.dumps(package), encoding="utf-8")
    run = tmp_path / "run"
    (run / "tasks").mkdir(parents=True)
    (run / "handoffs").mkdir()
    (run / "run-state.json").write_text(
        json.dumps(valid_run_state()), encoding="utf-8"
    )
    (run / "source-inventory.json").write_text(
        json.dumps(valid_source_inventory()), encoding="utf-8"
    )
    completed_handoffs = []
    for task_id, write_path, artifacts, status in task_outputs:
        candidate = candidate_task()
        candidate["task_id"] = task_id
        candidate["write_paths"] = [write_path]
        task = project_task(package, candidate)
        handoff = collaboration_handoff(package, task)
        handoff["artifacts"] = artifacts
        handoff["status"] = status
        for artifact in artifacts:
            artifact_path = run / artifact
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text(task_id, encoding="utf-8")
        (run / "tasks" / f"{task_id}.json").write_text(
            json.dumps(task), encoding="utf-8"
        )
        (run / "handoffs" / f"{task_id}.json").write_text(
            json.dumps(handoff), encoding="utf-8"
        )
        if status == "COMPLETED":
            completed_handoffs.append((task_id, handoff))
    if completed_handoffs:
        produced_artifact_digest = (
            expected_artifact_set_digest(
                run,
                [
                    artifact
                    for _, handoff in completed_handoffs
                    for artifact in handoff["artifacts"]
                ],
            )
            if package["authority"]["kind"] == "approved_bundle"
            else None
        )
        receipt = implementation_receipt(
            package,
            producer=completed_handoffs[0][1]["agent_id"],
            produced_revision=completed_handoffs[0][1]["produced_revision"],
            produced_artifact_digest=produced_artifact_digest,
        )
        receipt["receipt_id"] = f"RR-IMPL-{package['package_id']}"
        write_review_receipt(package_root, receipt)
    return run, package_root

def conflict_record(
    *,
    conflict_id: str = "SYN-CONFLICT-001",
    status: str = "OPEN",
    reported_by_task: str | None = "SYN-W1-SQL-ORDERS",
    reported_by_work_package: str | None = None,
) -> dict:
    record = {
        "conflict_id": conflict_id,
        "run_id": "SYN-RUN",
        "app_id": "SYN",
        "topic": "Synthetic disagreement",
        "severity": "MEDIUM",
        "status": status,
        "observations": [
            {"evidence_id": "SYN-EVIDENCE-001", "statement": "First"},
            {"evidence_id": "SYN-EVIDENCE-002", "statement": "Second"},
        ],
        "owner": None,
        "created_at": "2026-07-28T00:30:00Z",
    }
    if reported_by_task is not None:
        record["reported_by_task"] = reported_by_task
    if reported_by_work_package is not None:
        record["reported_by_work_package"] = reported_by_work_package
    if status != "OPEN":
        record.update(
            {
                "resolution": "Use the reviewed evidence.",
                "decision_source": "review-record-001",
                "resolved_by_task": reported_by_task,
                "resolved_at": "2026-07-28T00:40:00Z",
            }
        )
    return record

def write_conflict(
    package_root: Path, record: dict, filename: str | None = None
) -> Path:
    conflicts = package_root.parent / "conflicts"
    conflicts.mkdir(parents=True, exist_ok=True)
    path = conflicts / (filename or f"{record['conflict_id']}.json")
    path.write_text(json.dumps(record), encoding="utf-8")
    return path


def repository_package() -> dict:
    package = kit_package()
    task = candidate_task()
    package["scope"]["roles"] = [task["role"]]
    package["scope"]["wave_ids"] = [task["wave_id"]]
    package["scope"]["phase_targets"] = task["phase_targets"]
    package["scope"]["module_targets"] = task["module_targets"]
    package["input_paths"] = ["extracted/bundles/bundle-a/code/access-sql"]
    package["write_paths"] = ["work/sql_data/module-orders"]
    package["expected_artifacts"] = [
        {
            "path": "work/sql_data/module-orders/result.json",
            "kind": "analysis_fragment",
            "required": True,
            "publication_class": "scoped",
        }
    ]
    package["evidence_namespace"] = task["evidence_namespace"]
    return package


def write_task_only_run(tmp_path: Path, contents: str) -> Path:
    run = tmp_path / "run"
    (run / "tasks").mkdir(parents=True)
    (run / "handoffs").mkdir()
    (run / "run-state.json").write_text(
        json.dumps(valid_run_state()), encoding="utf-8"
    )
    (run / "source-inventory.json").write_text(
        json.dumps(valid_source_inventory()), encoding="utf-8"
    )
    (run / "tasks" / "bad-task.json").write_text(contents, encoding="utf-8")
    return run


def run_advance(
    run: Path,
    *extra_args: str,
    wave: str = "wave1_source_extraction",
    dry_run: bool = True,
) -> subprocess.CompletedProcess[str]:
    package = Path(__file__).resolve().parents[1]
    script = package / "scripts" / "advance_run.py"
    return subprocess.run(
        [
            sys.executable,
            str(script),
            "--run",
            str(run),
            "--package",
            str(package),
            "--wave",
            wave,
            *(["--dry-run"] if dry_run else []),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def run_handoff_validation(
    run: Path, *extra_args: str
) -> subprocess.CompletedProcess[str]:
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"
    return subprocess.run(
        [sys.executable, str(script), "--run", str(run), *extra_args],
        capture_output=True,
        text=True,
        check=False,
    )


def add_handoff_inventory_case(
    run: Path, task: dict, handoff: dict, case: str
) -> str:
    handoffs = run / "handoffs"
    if case == "malformed":
        (handoffs / "extra-malformed.json").write_text("{", encoding="utf-8")
        return "extra-malformed.json: invalid handoff JSON"
    if case == "unknown":
        unknown = deepcopy(handoff)
        unknown["task_id"] = "SYN-UNKNOWN"
        (handoffs / "SYN-UNKNOWN.json").write_text(
            json.dumps(unknown), encoding="utf-8"
        )
        return "SYN-UNKNOWN.json: unknown task id SYN-UNKNOWN"
    if case == "duplicate":
        canonical = handoffs / f"{task['task_id']}.json"
        contents = canonical.read_text(encoding="utf-8")
        canonical.unlink()
        for filename in ("z-handoff.json", "a-handoff.json"):
            (handoffs / filename).write_text(contents, encoding="utf-8")
        return (
            f"duplicate handoff id {task['task_id']}: "
            "a-handoff.json, z-handoff.json"
        )
    raise AssertionError(case)


def add_future_handoff_case(
    run: Path, projected_handoff: dict, case: str
) -> str:
    task = candidate_task()
    task["task_id"] = "SYN-FUTURE"
    task["wave_id"] = "gate1_publish_phase1"
    (run / "tasks" / "SYN-FUTURE.json").write_text(
        json.dumps(task), encoding="utf-8"
    )
    if case == "mode":
        handoff = deepcopy(projected_handoff)
        handoff.update(
            {
                "task_id": task["task_id"],
                "role": task["role"],
            }
        )
        message = "SYN-FUTURE: collaboration mode mismatch"
    else:
        handoff = legacy_handoff(task)
        field = "run_id" if case == "run" else "app_id"
        handoff[field] = "OTHER"
        message = f"SYN-FUTURE: {field} mismatch"
    (run / "handoffs" / "SYN-FUTURE.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )
    return message

def add_collaboration_sibling(
    run: Path,
    package: dict,
    *,
    task_id: str,
    wave_id: str,
    status: str,
    agent_id: str,
    phase_targets: list[int] | None = None,
) -> tuple[dict, dict]:
    candidate = candidate_task()
    candidate["task_id"] = task_id
    candidate["wave_id"] = wave_id
    if phase_targets is not None:
        candidate["phase_targets"] = phase_targets
    task = project_task(package, candidate)
    handoff = collaboration_handoff(package, task)
    handoff.update(
        {
            "status": status,
            "agent_id": agent_id,
            "artifacts": [],
        }
    )
    (run / "tasks" / f"{task_id}.json").write_text(
        json.dumps(task), encoding="utf-8"
    )
    (run / "handoffs" / f"{task_id}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )
    return task, handoff


def invalid_run_controls() -> list[tuple[str, str, str]]:
    wrong_inventory_files = valid_source_inventory()
    wrong_inventory_files["files"] = {}
    return [
        ("run-state.json", "{", "run-state.json: invalid JSON"),
        ("run-state.json", "", "run-state.json: invalid JSON"),
        ("run-state.json", "{}", "run-state.json: invalid schema"),
        ("run-state.json", "[]", "run-state.json: invalid schema"),
        ("source-inventory.json", "{", "source-inventory.json: invalid JSON"),
        ("source-inventory.json", "", "source-inventory.json: invalid JSON"),
        ("source-inventory.json", "{}", "source-inventory.json: invalid schema"),
        (
            "source-inventory.json",
            json.dumps(wrong_inventory_files),
            "source-inventory.json: invalid schema",
        ),
    ]

def invalidate_control_datetime(run: Path, task_id: str, case: str) -> str:
    targets = {
        "run-state": ("run-state.json", "created_at", "run-state.json: invalid schema"),
        "inventory": (
            "source-inventory.json",
            "generated_at",
            "source-inventory.json: invalid schema",
        ),
        "task": (
            f"tasks/{task_id}.json",
            "created_at",
            f"{task_id}.json: invalid task schema",
        ),
        "handoff": (
            f"handoffs/{task_id}.json",
            "completed_at",
            f"{task_id}.json: invalid handoff schema",
        ),
    }
    relative, field, message = targets[case]
    path = run / relative
    value = json.loads(path.read_text(encoding="utf-8"))
    value[field] = "not-a-date"
    path.write_text(json.dumps(value), encoding="utf-8")
    return message


def test_handoff_schema_accepts_legacy_record() -> None:
    jsonschema.validate(legacy_handoff(candidate_task()), schema("handoff.schema.json"))

def test_legacy_handoff_schema_keeps_nullable_agent_id() -> None:
    handoff = legacy_handoff(candidate_task())
    handoff["agent_id"] = None
    jsonschema.validate(handoff, schema("handoff.schema.json"))


@pytest.mark.parametrize(("filename", "contents", "message"), invalid_run_controls())
def test_invalid_run_control_returns_file_qualified_error(
    tmp_path: Path, filename: str, contents: str, message: str
) -> None:
    run = write_task_only_run(tmp_path, json.dumps(candidate_task()))
    (run / filename).write_text(contents, encoding="utf-8")
    assert validate_run_handoffs(run) == ([message], 0, 0)


@pytest.mark.parametrize(("filename", "contents", "message"), invalid_run_controls())
def test_cli_invalid_run_control_returns_failure_without_traceback(
    tmp_path: Path, filename: str, contents: str, message: str
) -> None:
    run = write_task_only_run(tmp_path, json.dumps(candidate_task()))
    (run / filename).write_text(contents, encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--run", str(run)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert f"ERROR: {message}" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr

@pytest.mark.parametrize("case", ["run-state", "inventory", "task", "handoff"])
def test_handoff_validation_enforces_control_datetime_formats(
    tmp_path: Path, case: str
) -> None:
    package = application_package()
    run, package_root, task, _ = write_run(tmp_path, package)
    message = invalidate_control_datetime(run, task["task_id"], case)

    errors, _, _ = validate_run_handoffs(
        run, work_package_root=package_root
    )

    assert any(error.startswith(message) for error in errors)

@pytest.mark.parametrize("case", ["run-state", "inventory", "task", "handoff"])
def test_cli_enforces_control_datetime_formats_without_traceback(
    tmp_path: Path, case: str
) -> None:
    package = application_package()
    run, package_root, task, _ = write_run(tmp_path, package)
    message = invalidate_control_datetime(run, task["task_id"], case)

    completed = run_handoff_validation(
        run, "--work-package-root", str(package_root)
    )

    assert completed.returncode == 1
    assert f"ERROR: {message}" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


def test_inventory_app_id_must_match_run_state(tmp_path: Path) -> None:
    run = write_task_only_run(tmp_path, json.dumps(candidate_task()))
    inventory = valid_source_inventory()
    inventory["app_id"] = "OTHER"
    (run / "source-inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )
    assert validate_run_handoffs(run) == (
        ["source-inventory.json: app_id mismatch"],
        0,
        0,
    )


def test_unreferenced_inventory_path_cannot_escape_root(tmp_path: Path) -> None:
    run = write_task_only_run(tmp_path, json.dumps(candidate_task()))
    inventory = valid_source_inventory()
    inventory["files"] = [inventory_file("../escape.sql")]
    (run / "source-inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )

    errors, _, _ = validate_run_handoffs(run)

    assert "source-inventory.json: invalid portable path: ../escape.sql" in errors


@pytest.mark.parametrize(
    "relative_path",
    ["./legacy.sql", "../escape.sql", "/absolute.sql", "C:/absolute.sql"],
)
def test_referenced_inventory_path_must_be_portable(
    tmp_path: Path, relative_path: str
) -> None:
    task = candidate_task()
    run = write_task_only_run(tmp_path, json.dumps(task))
    inventory = valid_source_inventory()
    inventory["files"] = [inventory_file(relative_path)]
    (run / "source-inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )
    handoff = legacy_handoff(task)
    handoff["source_files_read"] = [relative_path]
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )

    errors, _, _ = validate_run_handoffs(run)

    assert (
        f"source-inventory.json: invalid portable path: {relative_path}"
        in errors
    )


def test_unreferenced_inventory_paths_must_be_casefold_unique(
    tmp_path: Path,
) -> None:
    run = write_task_only_run(tmp_path, json.dumps(candidate_task()))
    inventory = valid_source_inventory()
    inventory["files"] = [
        inventory_file("SRC/File.sql"),
        inventory_file("src/file.sql"),
    ]
    (run / "source-inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )

    errors, _, _ = validate_run_handoffs(run)

    assert (
        "source-inventory.json: casefold path collision: "
        "SRC/File.sql, src/file.sql"
    ) in errors


def test_cli_inventory_app_id_mismatch_has_no_traceback(tmp_path: Path) -> None:
    run = write_task_only_run(tmp_path, json.dumps(candidate_task()))
    inventory = valid_source_inventory()
    inventory["app_id"] = "OTHER"
    (run / "source-inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--run", str(run)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "ERROR: source-inventory.json: app_id mismatch" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


@pytest.mark.parametrize(
    ("task_changes", "message"),
    [
        ({"run_id": "OTHER-RUN"}, "run_id mismatch"),
        ({"app_id": "OTHER"}, "app_id mismatch"),
    ],
)
def test_task_identity_must_match_run_state(
    tmp_path: Path, task_changes: dict, message: str
) -> None:
    task = candidate_task()
    task.update(task_changes)
    run = write_task_only_run(tmp_path, json.dumps(task))
    assert validate_run_handoffs(run) == ([f"bad-task.json: {message}"], 0, 0)


@pytest.mark.parametrize(
    ("task_changes", "message"),
    [
        ({"run_id": "OTHER-RUN"}, "run_id mismatch"),
        ({"app_id": "OTHER"}, "app_id mismatch"),
    ],
)
def test_cli_task_identity_mismatch_has_no_traceback(
    tmp_path: Path, task_changes: dict, message: str
) -> None:
    task = candidate_task()
    task.update(task_changes)
    run = write_task_only_run(tmp_path, json.dumps(task))
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--run", str(run)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert f"ERROR: bad-task.json: {message}" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


def test_invalid_task_json_returns_file_qualified_error(tmp_path: Path) -> None:
    run = write_task_only_run(tmp_path, "{")
    errors, checked, pending = validate_run_handoffs(run)
    assert errors == ["bad-task.json: invalid task JSON"]
    assert (checked, pending) == (0, 0)


def test_task_missing_task_id_returns_file_qualified_error(tmp_path: Path) -> None:
    task = candidate_task()
    del task["task_id"]
    run = write_task_only_run(tmp_path, json.dumps(task))
    errors, checked, pending = validate_run_handoffs(run)
    assert len(errors) == 1
    assert errors[0].startswith("bad-task.json: invalid task schema:")
    assert "task_id" in errors[0]
    assert (checked, pending) == (0, 0)


def test_task_missing_wave_id_is_validated_before_wave_filter(tmp_path: Path) -> None:
    task = candidate_task()
    del task["wave_id"]
    run = write_task_only_run(tmp_path, json.dumps(task))
    errors, checked, pending = validate_run_handoffs(
        run, wave="wave1_source_extraction"
    )
    assert len(errors) == 1
    assert errors[0].startswith("bad-task.json: invalid task schema:")
    assert "wave_id" in errors[0]
    assert (checked, pending) == (0, 0)


def test_wrong_task_id_type_is_validated_before_indexing(tmp_path: Path) -> None:
    task = candidate_task()
    task["task_id"] = []
    run = write_task_only_run(tmp_path, json.dumps(task))
    errors, checked, pending = validate_run_handoffs(run)
    assert len(errors) == 1
    assert errors[0].startswith("bad-task.json: invalid task schema:")
    assert (checked, pending) == (0, 0)


def test_cli_malformed_task_returns_failure_without_traceback(tmp_path: Path) -> None:
    run = write_task_only_run(tmp_path, "{")
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--run", str(run)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "ERROR: bad-task.json: invalid task JSON" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


def test_handoff_schema_accepts_complete_collaboration_record() -> None:
    package = application_package()
    task = project_task(package, candidate_task())
    jsonschema.validate(collaboration_handoff(package, task), schema("handoff.schema.json"))

@pytest.mark.parametrize("agent_id", [None, "", "   "])
def test_collaboration_handoff_requires_nonblank_agent_id(
    agent_id: str | None,
) -> None:
    package = application_package()
    task = project_task(package, candidate_task())
    handoff = collaboration_handoff(package, task)
    if agent_id is None:
        del handoff["agent_id"]
    else:
        handoff["agent_id"] = agent_id

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(handoff, schema("handoff.schema.json"))


def test_handoff_schema_rejects_partial_collaboration_record() -> None:
    handoff = legacy_handoff(candidate_task())
    handoff["work_package_id"] = "WP_SYN_SQL"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(handoff, schema("handoff.schema.json"))


def test_scope_acceptance_receipt_approves_exact_digest() -> None:
    package = application_package()
    validate_review_receipt(package, acceptance_receipt(package))


def test_review_rejects_invalid_package_before_binding() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    package["future_field"] = True
    receipt["work_package_digest"] = work_package_digest(package)

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        validate_review_receipt(package, receipt)

def test_review_rejects_invalid_package_path_before_approval() -> None:
    package = application_package()
    package["expected_artifacts"][0]["path"] = (
        "work/sql_data/module-orders/result?.json"
    )
    receipt = acceptance_receipt(package)

    with pytest.raises(CollaborationError, match="COLLAB_PATH_ESCAPE"):
        validate_review_receipt(package, receipt)


def test_duplicate_package_commands_cannot_share_one_review_result() -> None:
    package = application_package()
    package["validation_commands"].append(package["validation_commands"][0])
    receipt = acceptance_receipt(package)
    receipt["validation_results"] = receipt["validation_results"][:1]

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        validate_review_receipt(package, receipt)


def test_scope_acceptance_rejects_spoofed_producer() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["producer"] = "spoofed-producer"
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_scope_acceptance_rejects_missing_producer() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    del receipt["producer"]
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


@pytest.mark.parametrize("stage", ["implementation", "publication"])
@pytest.mark.parametrize("expected_producer", [None, ""])
def test_change_review_requires_trusted_expected_producer(
    stage: str, expected_producer: str | None
) -> None:
    package = repository_package()
    receipt = implementation_receipt(
        package, stage=stage, produced_revision="revision-one"
    )
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(
            package,
            receipt,
            expected_producer=expected_producer,
            produced_revision="revision-one",
        )


def test_change_review_rejects_mismatched_expected_producer() -> None:
    package = repository_package()
    receipt = implementation_receipt(package, produced_revision="revision-one")
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(
            package,
            receipt,
            expected_producer="different-agent",
            produced_revision="revision-one",
        )

def test_implementation_receipt_rejects_spoofed_worker(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    receipt_path = next((package_root.parent / "reviews").glob("*.json"))
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["producer"] = package["created_by"]
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert any(
        "invalid implementation review receipt" in error
        and "producer" in error
        for error in errors
    )

def test_missing_worker_blocks_function_and_cli(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, task, handoff = write_run(tmp_path, package)
    del handoff["agent_id"]
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    completed = run_handoff_validation(
        run, "--work-package-root", str(package_root)
    )

    assert any("invalid handoff schema" in error for error in errors)
    assert completed.returncode == 1
    assert "invalid handoff schema" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr

def test_multi_agent_package_requires_deterministic_split(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root = write_multi_task_run(
        tmp_path,
        package,
        [
            (
                "SYN-W1-SQL-FIRST",
                "work/sql_data/module-orders",
                [],
                "COMPLETED",
            ),
            (
                "SYN-W1-SQL-SECOND",
                "work/sql_data/module-orders",
                [package["expected_artifacts"][0]["path"]],
                "COMPLETED",
            ),
        ],
    )
    second_path = run / "handoffs" / "SYN-W1-SQL-SECOND.json"
    second = json.loads(second_path.read_text(encoding="utf-8"))
    second["agent_id"] = "second-agent"
    second_path.write_text(json.dumps(second), encoding="utf-8")

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert "WP_SYN_SQL: multiple implementation agents; split work package" in errors

@pytest.mark.parametrize("status", ["FAILED", "BLOCKED"])
def test_cross_wave_noncompleted_sibling_must_share_package_agent(
    tmp_path: Path, status: str
) -> None:
    package = application_package()
    package["scope"]["wave_ids"].append("gate1_publish_phase1")
    run, package_root, _, _ = write_run(tmp_path, package)
    add_collaboration_sibling(
        run,
        package,
        task_id=f"SYN-FUTURE-{status}",
        wave_id="gate1_publish_phase1",
        status=status,
        agent_id="second-agent",
    )

    errors, checked, pending = validate_run_handoffs(
        run,
        wave="wave1_source_extraction",
        work_package_root=package_root,
    )

    assert "WP_SYN_SQL: multiple implementation agents; split work package" in errors
    assert (checked, pending) == (1, 0)

def test_noncompleted_package_handoffs_still_require_one_agent(
    tmp_path: Path,
) -> None:
    package = application_package()
    package["scope"]["wave_ids"].append("gate1_publish_phase1")
    run, package_root, task, handoff = write_run(
        tmp_path,
        package,
        handoff_changes={"status": "FAILED", "artifacts": []},
    )
    assert handoff["agent_id"] == "implementation-agent"
    add_collaboration_sibling(
        run,
        package,
        task_id="SYN-FUTURE-BLOCKED",
        wave_id="gate1_publish_phase1",
        status="BLOCKED",
        agent_id="second-agent",
    )

    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )

    assert "WP_SYN_SQL: multiple implementation agents; split work package" in errors
    assert (checked, pending) == (2, 0)

def test_noncompleted_sibling_same_agent_preserves_receipt_binding(
    tmp_path: Path,
) -> None:
    package = application_package()
    package["scope"]["wave_ids"].append("gate1_publish_phase1")
    run, package_root, _, _ = write_run(tmp_path, package)
    add_collaboration_sibling(
        run,
        package,
        task_id="SYN-FUTURE-BLOCKED",
        wave_id="gate1_publish_phase1",
        status="BLOCKED",
        agent_id="implementation-agent",
    )

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        2,
        0,
    )


def test_independence_uses_trusted_expected_producer() -> None:
    package = repository_package()
    receipt = implementation_receipt(
        package,
        producer="spoofed-producer",
        produced_revision="revision-one",
    )
    receipt["reviewer"] = "implementation-agent"
    package["reviewer"] = "implementation-agent"
    receipt["work_package_digest"] = work_package_digest(package)
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_NOT_INDEPENDENT"):
        validate_review_receipt(
            package,
            receipt,
            expected_producer="implementation-agent",
            produced_revision="revision-one",
        )


def test_changed_package_makes_receipt_stale() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    package["objective"] = "Changed scope"
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_authority_snapshot_change_makes_receipt_stale() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["authority_snapshot"] = deepcopy(receipt["authority_snapshot"])
    receipt["authority_snapshot"]["checksum"] = "d" * 64
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_wrong_reviewer_makes_receipt_stale() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["reviewer"] = "other-reviewer"
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_reviewer_must_be_independent() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["reviewer"] = receipt["producer"]
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_NOT_INDEPENDENT"):
        validate_review_receipt(package, receipt)


@pytest.mark.parametrize("decision", ["CHANGES_REQUESTED", "REJECTED"])
def test_non_approved_decision_cannot_pass_as_approval(decision: str) -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["decision"] = decision
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_missing_required_validation_makes_receipt_stale() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["validation_results"] = []
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_required_validation_must_pass() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["validation_results"][0]["exit_code"] = 1
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_exit_zero_with_fail_result_makes_receipt_stale() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["validation_results"][0]["result"] = "FAIL"
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_review_schema_rejects_invalid_result_string() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["validation_results"][0]["result"] = "SUCCESS"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, schema("review-receipt.schema.json"))


def test_duplicate_validation_cannot_hide_failure() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["validation_results"].append({"command": package["validation_commands"][0], "exit_code": 0, "result": "FAIL"})
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_duplicate_successful_validation_is_stale() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["validation_results"].append(deepcopy(receipt["validation_results"][0]))
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


@pytest.mark.parametrize(
    "extra_result",
    [
        {"command": "synthetic-extra", "exit_code": 1, "result": "PASS"},
        {"command": "synthetic-extra", "exit_code": 0, "result": "FAIL"},
    ],
)
def test_extra_review_validation_result_must_be_truthful(
    extra_result: dict,
) -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["validation_results"].append(extra_result)

    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_duplicate_extra_review_validation_command_is_stale() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    extra = {"command": "synthetic-extra", "exit_code": 2, "result": "FAIL"}
    receipt["validation_results"].extend([extra, deepcopy(extra)])

    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_unique_truthful_extra_review_validation_is_allowed() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["validation_results"].append(
        {"command": "synthetic-extra", "exit_code": 2, "result": "FAIL"}
    )

    validate_review_receipt(package, receipt)


@pytest.mark.parametrize("command", [" ", "\t"])
def test_review_validation_command_must_be_nonblank(command: str) -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["validation_results"].append(
        {"command": command, "exit_code": 0, "result": "PASS"}
    )

    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_review_validation_command_preserves_unicode() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["validation_results"].append(
        {
            "command": "\u691c\u8a3c \u30b3\u30de\u30f3\u30c9",
            "exit_code": 0,
            "result": "PASS",
        }
    )

    validate_review_receipt(package, receipt)


@pytest.mark.parametrize("receipt_id", [" ", "\t"])
def test_review_receipt_id_must_be_nonblank(receipt_id: str) -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["receipt_id"] = receipt_id

    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_review_receipt_id_preserves_unicode() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["receipt_id"] = "\u53d7\u9818\u7968-\u6ce8\u6587"

    validate_review_receipt(package, receipt)


@pytest.mark.parametrize("field", ["producer", "reviewer"])
@pytest.mark.parametrize("value", [" ", "	", " identity", "identity "])
def test_review_receipt_identities_must_be_nonblank(
    field: str, value: str
) -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt[field] = value

    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


@pytest.mark.parametrize("field", ["producer", "reviewer"])
@pytest.mark.parametrize("value", [" ", "	", " identity", "identity "])
def test_review_receipt_schema_rejects_blank_identities(
    field: str, value: str
) -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt[field] = value

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, schema("review-receipt.schema.json"))


def test_review_receipt_identities_preserve_unicode() -> None:
    package = application_package()
    package["created_by"] = "計画担当"
    package["reviewer"] = "査読担当"

    validate_review_receipt(package, acceptance_receipt(package))


def test_review_receipt_identity_comparison_is_case_sensitive() -> None:
    package = application_package()
    receipt = implementation_receipt(
        package, producer="Implementation-Agent", produced_artifact_digest="d" * 64
    )

    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE: producer"):
        validate_review_receipt(
            package,
            receipt,
            expected_producer="implementation-agent",
            produced_artifact_digest="d" * 64,
        )


@pytest.mark.parametrize("agent_id", [" implementation-agent", "implementation-agent "])
def test_projected_handoff_rejects_identity_whitespace(
    tmp_path: Path, agent_id: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path, package, handoff_changes={"agent_id": agent_id}
    )

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert any("invalid handoff schema" in error for error in errors)


def test_review_receipt_rejects_invalid_date_time() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["reviewed_at"] = "not-a-date-time"

    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)


def test_review_receipt_accepts_iso_date_time() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["reviewed_at"] = "2026-07-29T12:34:56+07:00"

    validate_review_receipt(package, receipt)


def test_scope_review_must_not_predate_package() -> None:
    package = application_package()
    package["created_at"] = "2026-07-28T00:20:00Z"
    receipt = acceptance_receipt(package)
    receipt["reviewed_at"] = "2026-07-28T00:10:00Z"

    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE: reviewed_at"):
        validate_review_receipt(package, receipt)


def test_implementation_review_must_follow_latest_completed_handoff(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root = write_multi_task_run(
        tmp_path,
        package,
        [
            (
                "SYN-W1-SQL-FIRST",
                "work/sql_data/module-orders",
                [],
                "COMPLETED",
            ),
            (
                "SYN-W1-SQL-SECOND",
                "work/sql_data/module-orders",
                [package["expected_artifacts"][0]["path"]],
                "COMPLETED",
            ),
        ],
    )
    latest = run / "handoffs" / "SYN-W1-SQL-SECOND.json"
    handoff = json.loads(latest.read_text(encoding="utf-8"))
    handoff["completed_at"] = "2026-07-28T00:40:00Z"
    latest.write_text(json.dumps(handoff), encoding="utf-8")

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert any(
        "invalid implementation review receipt: "
        "COLLAB_REVIEW_STALE: reviewed_at" in error
        for error in errors
    )


def test_scope_acceptance_forbids_produced_revision_argument() -> None:
    package = repository_package()
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(
            package, acceptance_receipt(package), produced_revision="revision-one"
        )


def test_scope_acceptance_schema_forbids_produced_revision_snapshot() -> None:
    package = repository_package()
    receipt = acceptance_receipt(package)
    receipt["authority_snapshot"] = {
        **receipt["authority_snapshot"],
        "produced_revision": "revision-one",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, schema("review-receipt.schema.json"))


def test_scope_acceptance_forbids_produced_artifact_digest_argument() -> None:
    package = application_package()
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(
            package,
            acceptance_receipt(package),
            produced_artifact_digest="a" * 64,
        )


def test_scope_acceptance_schema_forbids_produced_artifact_digest_snapshot() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["authority_snapshot"] = {
        **receipt["authority_snapshot"],
        "produced_artifact_digest": "a" * 64,
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, schema("review-receipt.schema.json"))


@pytest.mark.parametrize("stage", ["implementation", "publication"])
@pytest.mark.parametrize("package_factory", [repository_package, mixed_package])
@pytest.mark.parametrize("produced_revision", [None, ""])
def test_change_review_requires_expected_produced_revision(
    stage: str, package_factory, produced_revision: str | None
) -> None:
    package = package_factory()
    receipt = implementation_receipt(
        package, stage=stage, produced_revision="revision-one"
    )
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(
            package,
            receipt,
            expected_producer="implementation-agent",
            produced_revision=produced_revision,
        )


@pytest.mark.parametrize("stage", ["implementation", "publication"])
@pytest.mark.parametrize("package_factory", [repository_package, mixed_package])
def test_change_review_schema_requires_produced_revision_snapshot(
    stage: str, package_factory
) -> None:
    package = package_factory()
    receipt = implementation_receipt(package, stage=stage)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, schema("review-receipt.schema.json"))


@pytest.mark.parametrize("stage", ["implementation", "publication"])
@pytest.mark.parametrize("package_factory", [repository_package, mixed_package])
def test_repository_review_schema_forbids_artifact_digest_snapshot(
    stage: str, package_factory
) -> None:
    package = package_factory()
    receipt = implementation_receipt(
        package,
        stage=stage,
        produced_revision="revision-one",
        produced_artifact_digest="a" * 64,
    )
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, schema("review-receipt.schema.json"))


@pytest.mark.parametrize("stage", ["implementation", "publication"])
@pytest.mark.parametrize("package_factory", [repository_package, mixed_package])
def test_repository_review_forbids_artifact_digest_argument(
    stage: str, package_factory
) -> None:
    package = package_factory()
    receipt = implementation_receipt(
        package, stage=stage, produced_revision="revision-one"
    )
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(
            package,
            receipt,
            expected_producer="implementation-agent",
            produced_revision="revision-one",
            produced_artifact_digest="a" * 64,
        )


@pytest.mark.parametrize("stage", ["implementation", "publication"])
def test_approved_bundle_review_forbids_produced_revision_argument(stage: str) -> None:
    package = application_package()
    receipt = implementation_receipt(package, stage=stage)
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(
            package,
            receipt,
            expected_producer="implementation-agent",
            produced_revision="revision-one",
        )


def test_approved_bundle_schema_forbids_produced_revision_snapshot() -> None:
    package = application_package()
    receipt = implementation_receipt(package)
    receipt["authority_snapshot"] = {
        **receipt["authority_snapshot"],
        "produced_revision": "revision-one",
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, schema("review-receipt.schema.json"))


@pytest.mark.parametrize("stage", ["implementation", "publication"])
def test_approved_bundle_schema_requires_artifact_digest_snapshot(stage: str) -> None:
    package = application_package()
    receipt = implementation_receipt(package, stage=stage)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, schema("review-receipt.schema.json"))


@pytest.mark.parametrize("stage", ["implementation", "publication"])
@pytest.mark.parametrize("produced_artifact_digest", [None, ""])
def test_approved_bundle_review_requires_expected_artifact_digest(
    stage: str, produced_artifact_digest: str | None
) -> None:
    package = application_package()
    receipt = implementation_receipt(
        package, stage=stage, produced_artifact_digest="a" * 64
    )
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(
            package,
            receipt,
            expected_producer="implementation-agent",
            produced_artifact_digest=produced_artifact_digest,
        )


def test_wrong_produced_artifact_digest_makes_receipt_stale() -> None:
    package = application_package()
    receipt = implementation_receipt(
        package, produced_artifact_digest="a" * 64
    )
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(
            package,
            receipt,
            expected_producer="implementation-agent",
            produced_artifact_digest="b" * 64,
        )


def test_exact_produced_artifact_digest_is_approved() -> None:
    package = application_package()
    validate_review_receipt(
        package,
        implementation_receipt(package, produced_artifact_digest="a" * 64),
        expected_producer="implementation-agent",
        produced_artifact_digest="a" * 64,
    )


def test_wrong_produced_revision_makes_receipt_stale() -> None:
    package = repository_package()
    receipt = acceptance_receipt(package)
    receipt["review_stage"] = "implementation"
    receipt["authority_snapshot"] = {**receipt["authority_snapshot"], "produced_revision": "revision-one"}
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt, produced_revision="revision-two")


def test_exact_produced_revision_is_approved() -> None:
    package = repository_package()
    receipt = acceptance_receipt(package)
    receipt["review_stage"] = "implementation"
    receipt["producer"] = "implementation-agent"
    receipt["authority_snapshot"] = {**receipt["authority_snapshot"], "produced_revision": "revision-one"}
    validate_review_receipt(
        package,
        receipt,
        expected_producer="implementation-agent",
        produced_revision="revision-one",
    )

def test_publication_receipt_schema_requires_phase() -> None:
    package = application_package()
    receipt = implementation_receipt(
        package,
        stage="publication",
        producer=package["coordinator"],
        produced_artifact_digest="a" * 64,
    )
    del receipt["publication_phase"]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, schema("review-receipt.schema.json"))

@pytest.mark.parametrize("stage", ["scope_acceptance", "implementation"])
def test_non_publication_receipt_schema_forbids_phase(stage: str) -> None:
    package = application_package()
    receipt = (
        acceptance_receipt(package)
        if stage == "scope_acceptance"
        else implementation_receipt(
            package, produced_artifact_digest="a" * 64
        )
    )
    receipt["publication_phase"] = 1

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, schema("review-receipt.schema.json"))

@pytest.mark.parametrize("phase", [0, 7, 1.5, "1"])
def test_publication_receipt_schema_rejects_invalid_phase(phase) -> None:
    package = application_package()
    receipt = implementation_receipt(
        package,
        stage="publication",
        producer=package["coordinator"],
        produced_artifact_digest="a" * 64,
    )
    receipt["publication_phase"] = phase

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(receipt, schema("review-receipt.schema.json"))

def test_publication_review_requires_exact_expected_phase() -> None:
    package = application_package()
    receipt = implementation_receipt(
        package,
        stage="publication",
        producer=package["coordinator"],
        produced_artifact_digest="a" * 64,
        publication_phase=1,
    )

    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(
            package,
            receipt,
            expected_producer=package["coordinator"],
            produced_artifact_digest="a" * 64,
            expected_publication_phase=2,
        )


def test_artifact_set_digest_is_order_independent_and_content_bound(
    tmp_path: Path,
) -> None:
    from review import artifact_set_digest

    first = "work/a.json"
    second = "work/b.json"
    for relative, contents in ((first, "one"), (second, "two")):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents, encoding="utf-8")

    digest = artifact_set_digest(tmp_path, [second, first])

    assert digest == expected_artifact_set_digest(tmp_path, [first, second])
    (tmp_path / first).write_text("changed", encoding="utf-8")
    assert artifact_set_digest(tmp_path, [first, second]) != digest


def test_completed_handoff_requires_implementation_receipt(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path, package, create_receipt=False
    )

    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )

    assert "WP_SYN_SQL: implementation review receipt required" in errors
    assert (checked, pending) == (1, 0)


def test_scope_receipt_cannot_substitute_for_implementation(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path, package, create_receipt=False
    )
    write_review_receipt(package_root, acceptance_receipt(package))

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert "WP_SYN_SQL: implementation review receipt required" in errors

def test_multiple_completed_handoffs_share_one_package_receipt(
    tmp_path: Path,
) -> None:
    package = application_package()
    package["expected_artifacts"] = [
        {
            "path": f"work/sql_data/module-orders/{name}.json",
            "kind": "analysis_fragment",
            "required": True,
            "publication_class": "scoped",
        }
        for name in ("first", "second")
    ]
    run, package_root = write_multi_task_run(
        tmp_path,
        package,
        [
            (
                "SYN-W1-SQL-FIRST",
                "work/sql_data/module-orders",
                [package["expected_artifacts"][0]["path"]],
                "COMPLETED",
            ),
            (
                "SYN-W1-SQL-SECOND",
                "work/sql_data/module-orders",
                [package["expected_artifacts"][1]["path"]],
                "COMPLETED",
            ),
        ],
    )

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        2,
        0,
    )

def test_one_required_handoff_requires_one_package_receipt(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root = write_multi_task_run(
        tmp_path,
        package,
        [
            (
                "SYN-W1-SQL-FIRST",
                "work/sql_data/module-orders",
                package["write_paths"][:0],
                "COMPLETED",
            ),
            (
                "SYN-W1-SQL-SECOND",
                "work/sql_data/module-orders",
                [package["expected_artifacts"][0]["path"]],
                "COMPLETED",
            ),
        ],
    )
    first_path = run / "handoffs" / "SYN-W1-SQL-FIRST.json"
    first = json.loads(first_path.read_text(encoding="utf-8"))
    first["review_receipt_required"] = False
    first_path.write_text(json.dumps(first), encoding="utf-8")

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        2,
        0,
    )

def test_package_without_required_receipt_accepts_completed_handoffs(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, handoff = write_run(tmp_path, package)
    handoff["review_receipt_required"] = False
    (run / "handoffs" / f"{handoff['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )
    for path in (package_root.parent / "reviews").glob("*.json"):
        path.unlink()

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        1,
        0,
    )

def test_duplicate_package_implementation_receipts_are_invalid(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    original_path = next((package_root.parent / "reviews").glob("*.json"))
    duplicate = json.loads(original_path.read_text(encoding="utf-8"))
    duplicate["receipt_id"] = "RR-IMPL-DUPLICATE"
    write_review_receipt(package_root, duplicate)

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert "WP_SYN_SQL: duplicate implementation review receipts" in errors

def test_repository_package_aggregates_one_revision_across_handoffs(
    tmp_path: Path,
) -> None:
    package = repository_package()
    run, package_root = write_multi_task_run(
        tmp_path,
        package,
        [
            (
                "SYN-W1-SQL-FIRST",
                "work/sql_data/module-orders",
                [],
                "COMPLETED",
            ),
            (
                "SYN-W1-SQL-SECOND",
                "work/sql_data/module-orders",
                [package["expected_artifacts"][0]["path"]],
                "COMPLETED",
            ),
        ],
    )
    for path in (run / "handoffs").glob("*.json"):
        handoff = json.loads(path.read_text(encoding="utf-8"))
        handoff["produced_revision"] = "revision-one"
        path.write_text(json.dumps(handoff), encoding="utf-8")
    for path in (package_root.parent / "reviews").glob("*.json"):
        path.unlink()
    receipt = implementation_receipt(
        package,
        producer="implementation-agent",
        produced_revision="revision-one",
    )
    receipt["receipt_id"] = "RR-IMPL-WP-SYN-SQL"
    write_review_receipt(package_root, receipt)

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        2,
        0,
    )

def test_repository_package_rejects_inconsistent_aggregate_revisions(
    tmp_path: Path,
) -> None:
    package = repository_package()
    run, package_root = write_multi_task_run(
        tmp_path,
        package,
        [
            (
                "SYN-W1-SQL-FIRST",
                "work/sql_data/module-orders",
                [],
                "COMPLETED",
            ),
            (
                "SYN-W1-SQL-SECOND",
                "work/sql_data/module-orders",
                [package["expected_artifacts"][0]["path"]],
                "COMPLETED",
            ),
        ],
    )
    for revision, path in zip(
        ("revision-one", "revision-two"),
        sorted((run / "handoffs").glob("*.json")),
    ):
        handoff = json.loads(path.read_text(encoding="utf-8"))
        handoff["produced_revision"] = revision
        path.write_text(json.dumps(handoff), encoding="utf-8")

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert "WP_KIT_SCHEMA: inconsistent produced revisions" in errors


@pytest.mark.parametrize("case", ["digest", "authority"])
def test_schema_valid_stale_scope_receipt_blocks_globally(
    tmp_path: Path, case: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    receipt = acceptance_receipt(package)
    receipt["receipt_id"] = f"RR-SCOPE-STALE-{case.upper()}"
    if case == "digest":
        receipt["work_package_digest"] = "d" * 64
    else:
        receipt["authority_snapshot"] = {
            **receipt["authority_snapshot"],
            "checksum": "d" * 64,
        }
    write_review_receipt(package_root, receipt)

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert any("invalid scope_acceptance review receipt" in error for error in errors)


def test_historical_publication_receipt_outside_gate_skips_output_binding(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    receipt = implementation_receipt(
        package,
        stage="publication",
        producer=package["coordinator"],
        produced_artifact_digest="d" * 64,
    )
    receipt["receipt_id"] = "RR-PUB-STALE"
    write_review_receipt(package_root, receipt)

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    completed = run_handoff_validation(
        run, "--work-package-root", str(package_root)
    )

    assert errors == []
    assert completed.returncode == 0
    assert "Handoff validation passed: 1 checked, 0 pending" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


def test_valid_extra_scope_and_publication_receipts_are_allowed(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, handoff = write_run(tmp_path, package)
    scope = acceptance_receipt(package)
    scope["receipt_id"] = "RR-SCOPE-VALID"
    publication = implementation_receipt(
        package,
        stage="publication",
        producer=package["coordinator"],
        produced_artifact_digest=expected_artifact_set_digest(
            run, handoff["artifacts"]
        ),
    )
    publication["receipt_id"] = "RR-PUB-VALID"
    write_review_receipt(package_root, scope)
    write_review_receipt(package_root, publication)

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        1,
        0,
    )


def test_implementation_receipt_without_completed_output_is_stale(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"status": "FAILED", "artifacts": []},
    )
    receipt = implementation_receipt(
        package,
        producer=package["created_by"],
        produced_artifact_digest="d" * 64,
    )
    receipt["receipt_id"] = "RR-IMPLEMENTATION-NO-OUTPUT"
    write_review_receipt(package_root, receipt)

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert any(
        "invalid implementation review receipt" in error
        and "no completed output" in error
        for error in errors
    )


def test_publication_receipt_without_current_output_is_historical_metadata(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"status": "FAILED", "artifacts": []},
    )
    receipt = implementation_receipt(
        package,
        stage="publication",
        producer=package["coordinator"],
        produced_artifact_digest="d" * 64,
    )
    receipt["receipt_id"] = "RR-PUBLICATION-NO-CURRENT-OUTPUT"
    write_review_receipt(package_root, receipt)

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert not any("invalid publication review receipt" in error for error in errors)


def test_valid_implementation_receipt_allows_completed_handoff(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, handoff = write_run(tmp_path, package)
    receipt = handoff_receipt(package, run, handoff)
    receipt["receipt_id"] = "RR-IMPL-SYN-W1-SQL-ORDERS"
    write_review_receipt(package_root, receipt)

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        1,
        0,
    )


def test_cli_blocks_missing_implementation_receipt(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path, package, create_receipt=False
    )

    completed = run_handoff_validation(
        run, "--work-package-root", str(package_root)
    )

    assert completed.returncode == 1
    assert (
        "ERROR: WP_SYN_SQL: implementation review receipt required"
        in completed.stdout
    )
    assert "Traceback" not in completed.stdout + completed.stderr


def test_artifact_mutation_makes_implementation_receipt_stale(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, handoff = write_run(tmp_path, package)
    receipt = handoff_receipt(package, run, handoff)
    receipt["receipt_id"] = "RR-IMPL-SYN-W1-SQL-ORDERS"
    write_review_receipt(package_root, receipt)
    (run / handoff["artifacts"][0]).write_text("changed", encoding="utf-8")

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert any("invalid implementation review receipt" in error for error in errors)


def test_required_artifacts_aggregate_across_disjoint_package_tasks(
    tmp_path: Path,
) -> None:
    package = application_package()
    first = "work/sql_data/module-orders/first/result.json"
    second = "work/sql_data/module-orders/second/result.json"
    package["expected_artifacts"] = [
        {**package["expected_artifacts"][0], "path": first},
        {**package["expected_artifacts"][0], "path": second},
    ]
    run, package_root = write_multi_task_run(
        tmp_path,
        package,
        [
            ("SYN-W1-SQL-FIRST", first.rsplit("/", 1)[0], [first], "COMPLETED"),
            ("SYN-W1-SQL-SECOND", second.rsplit("/", 1)[0], [second], "COMPLETED"),
        ],
    )

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        2,
        0,
    )


def test_duplicate_cross_task_artifact_report_is_rejected(tmp_path: Path) -> None:
    package = application_package()
    artifact = package["expected_artifacts"][0]["path"]
    write_path = artifact.rsplit("/", 1)[0]
    run, package_root = write_multi_task_run(
        tmp_path,
        package,
        [
            ("SYN-W1-SQL-FIRST", write_path, [artifact], "COMPLETED"),
            ("SYN-W1-SQL-SECOND", write_path, [artifact], "COMPLETED"),
        ],
    )

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert (
        f"{package['package_id']}: required artifact reported multiple times: {artifact}"
        in errors
    )


def test_duplicate_optional_cross_task_artifact_report_is_rejected(
    tmp_path: Path,
) -> None:
    package = application_package()
    artifact = package["expected_artifacts"][0]["path"]
    package["expected_artifacts"][0]["required"] = False
    write_path = artifact.rsplit("/", 1)[0]
    run, package_root = write_multi_task_run(
        tmp_path,
        package,
        [
            ("SYN-W1-SQL-FIRST", write_path, [artifact], "COMPLETED"),
            ("SYN-W1-SQL-SECOND", write_path, [artifact], "COMPLETED"),
        ],
    )

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert f"{package['package_id']}: artifact reported multiple times: {artifact}" in errors


def test_review_root_must_be_a_directory(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path, package, create_receipt=False
    )
    reviews = package_root.parent / "reviews"
    reviews.parent.mkdir(parents=True, exist_ok=True)
    reviews.write_text("not a directory", encoding="utf-8")

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert "reviews: invalid review control entry" in errors


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("nested", "reviews/nested: invalid review control entry"),
        ("misc", "reviews/notes.txt: invalid review control entry"),
        ("non-utf8", "extra.json: invalid review JSON"),
        ("malformed", "extra.json: invalid review JSON"),
        ("schema", "extra.json: invalid review schema"),
        ("filename", "wrong.json: filename does not match receipt_id"),
        ("duplicate", "duplicate review receipt id RR-IMPL-SYN-W1-SQL-ORDERS"),
        ("unknown", "RR-UNKNOWN.json: unknown work package id WP_UNKNOWN"),
    ],
)
def test_review_directory_is_closed_and_fail_closed(
    tmp_path: Path, case: str, message: str
) -> None:
    package = application_package()
    run, package_root, _, handoff = write_run(tmp_path, package)
    receipt = handoff_receipt(package, run, handoff)
    receipt["receipt_id"] = "RR-IMPL-SYN-W1-SQL-ORDERS"
    canonical = write_review_receipt(package_root, receipt)
    reviews = canonical.parent
    if case == "nested":
        nested = reviews / "nested"
        nested.mkdir()
        (nested / "extra.json").write_text("{}", encoding="utf-8")
    elif case == "misc":
        (reviews / "notes.txt").write_text("note", encoding="utf-8")
    elif case == "non-utf8":
        (reviews / "extra.json").write_bytes(bytes([0xFF]))
    elif case == "malformed":
        (reviews / "extra.json").write_text("{", encoding="utf-8")
    elif case == "schema":
        (reviews / "extra.json").write_text("{}", encoding="utf-8")
    elif case == "filename":
        canonical.rename(reviews / "wrong.json")
    elif case == "duplicate":
        (reviews / "duplicate.json").write_text(
            json.dumps(receipt), encoding="utf-8"
        )
    elif case == "unknown":
        unknown = deepcopy(receipt)
        unknown["receipt_id"] = "RR-UNKNOWN"
        unknown["work_package_id"] = "WP_UNKNOWN"
        unknown["work_package_digest"] = "d" * 64
        write_review_receipt(package_root, unknown)
    else:
        raise AssertionError(case)

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert any(message in error for error in errors)


def publication_run(
    tmp_path: Path,
    phase: int = 1,
    package_phase_targets: list[int] | None = None,
) -> tuple[dict, Path, Path, dict]:
    package = application_package()
    gate = f"gate{phase}_publish_phase{phase}"
    package["scope"]["wave_ids"] = [
        "wave1_source_extraction",
        gate,
    ]
    package["scope"]["phase_targets"] = sorted(
        set(package_phase_targets or [1, phase])
    )
    run, package_root, _, handoff = write_run(
        tmp_path,
        package,
        task_changes={"wave_id": gate, "phase_targets": [phase]},
    )
    state_path = run / "run-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["current_wave"] = gate
    state["wave_status"] = {gate: "RUNNING"}
    state_path.write_text(json.dumps(state), encoding="utf-8")
    receipt = handoff_receipt(package, run, handoff)
    receipt["receipt_id"] = "RR-IMPL-SYN-W1-SQL-ORDERS"
    write_review_receipt(package_root, receipt)
    return package, run, package_root, handoff

def publication_receipt(
    package: dict, run: Path, handoff: dict, phase: int, receipt_id: str
) -> dict:
    receipt = implementation_receipt(
        package,
        stage="publication",
        producer=package["coordinator"],
        produced_artifact_digest=expected_artifact_set_digest(
            run, handoff["artifacts"]
        ),
        publication_phase=phase,
    )
    receipt["receipt_id"] = receipt_id
    return receipt

def test_publication_receipts_preserve_phase_history(tmp_path: Path) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 2)
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 1, "RR-PUB-PHASE-1"),
    )
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 2, "RR-PUB-PHASE-2"),
    )

    assert validate_run_handoffs(
        run, work_package_root=package_root, publication_phase=2
    ) == ([], 1, 0)


def test_publication_review_must_follow_all_completed_phase_handoffs(
    tmp_path: Path,
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 2)
    _, sibling = add_collaboration_sibling(
        run,
        package,
        task_id="SYN-GATE2-SQL-SECOND",
        wave_id="gate2_publish_phase2",
        status="COMPLETED",
        agent_id=handoff["agent_id"],
        phase_targets=[2],
    )
    sibling["completed_at"] = "2026-07-28T00:40:00Z"
    (run / "handoffs" / "SYN-GATE2-SQL-SECOND.json").write_text(
        json.dumps(sibling), encoding="utf-8"
    )
    implementation_path = (
        package_root.parent / "reviews" / "RR-IMPL-SYN-W1-SQL-ORDERS.json"
    )
    implementation = json.loads(implementation_path.read_text(encoding="utf-8"))
    implementation["reviewed_at"] = "2026-07-28T00:50:00Z"
    implementation_path.write_text(json.dumps(implementation), encoding="utf-8")
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 2, "RR-PUB-PHASE-2"),
    )

    errors, _, _ = validate_run_handoffs(
        run, work_package_root=package_root, publication_phase=2
    )

    assert any(
        "invalid publication review receipt: COLLAB_REVIEW_STALE: reviewed_at"
        in error
        for error in errors
    )


def test_exact_publication_review_must_follow_implementation_approval(
    tmp_path: Path,
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path)
    implementation_path = (
        package_root.parent / "reviews" / "RR-IMPL-SYN-W1-SQL-ORDERS.json"
    )
    implementation = json.loads(implementation_path.read_text(encoding="utf-8"))
    implementation["reviewed_at"] = "2026-07-28T00:50:00Z"
    implementation_path.write_text(json.dumps(implementation), encoding="utf-8")
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 1, "RR-PUB-PHASE-1"),
    )

    errors, _, _ = validate_run_handoffs(
        run, work_package_root=package_root, publication_phase=1
    )

    assert any(
        "RR-PUB-PHASE-1: invalid publication review receipt: "
        "COLLAB_REVIEW_STALE: reviewed_at" in error
        for error in errors
    )


def test_exact_publication_requires_approved_implementation_receipt(
    tmp_path: Path,
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path)
    handoff["review_receipt_required"] = False
    (run / "handoffs" / f"{handoff['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )
    (package_root.parent / "reviews" / "RR-IMPL-SYN-W1-SQL-ORDERS.json").unlink()
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 1, "RR-PUB-PHASE-1"),
    )

    errors, _, _ = validate_run_handoffs(
        run, work_package_root=package_root, publication_phase=1
    )

    assert any(
        "RR-PUB-PHASE-1: invalid publication review receipt: "
        "COLLAB_REVIEW_STALE: approved implementation review receipt required"
        in error
        for error in errors
    )


def test_publication_review_ignores_completed_handoffs_for_other_phases(
    tmp_path: Path,
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 2)
    _, sibling = add_collaboration_sibling(
        run,
        package,
        task_id="SYN-GATE2-SQL-PHASE1",
        wave_id="gate2_publish_phase2",
        status="COMPLETED",
        agent_id=handoff["agent_id"],
        phase_targets=[1],
    )
    sibling["completed_at"] = "2026-07-28T00:40:00Z"
    (run / "handoffs" / "SYN-GATE2-SQL-PHASE1.json").write_text(
        json.dumps(sibling), encoding="utf-8"
    )
    implementation_path = (
        package_root.parent / "reviews" / "RR-IMPL-SYN-W1-SQL-ORDERS.json"
    )
    implementation = json.loads(implementation_path.read_text(encoding="utf-8"))
    implementation["reviewed_at"] = "2026-07-28T00:50:00Z"
    implementation_path.write_text(json.dumps(implementation), encoding="utf-8")
    publication = publication_receipt(
        package, run, handoff, 2, "RR-PUB-PHASE-2"
    )
    publication["reviewed_at"] = "2026-07-28T01:00:00Z"
    write_review_receipt(package_root, publication)

    assert validate_run_handoffs(
        run, work_package_root=package_root, publication_phase=2
    ) == ([], 2, 0)


def test_phase2_publication_accepts_phase1_output_history_after_output_changes(
    tmp_path: Path,
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 2)
    phase1 = publication_receipt(
        package, run, handoff, 1, "RR-PUB-PHASE-1"
    )
    write_review_receipt(package_root, phase1)
    artifact = run / handoff["artifacts"][0]
    artifact.write_text('{"phase": 2}', encoding="utf-8")
    implementation = handoff_receipt(package, run, handoff)
    implementation["receipt_id"] = "RR-IMPL-SYN-W1-SQL-ORDERS"
    write_review_receipt(package_root, implementation)
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 2, "RR-PUB-PHASE-2"),
    )

    completed = run_advance(
        run,
        "--work-package-root",
        str(package_root),
        "--approve-checkpoint",
        wave="gate2_publish_phase2",
        dry_run=False,
    )

    assert completed.returncode == 0
    state = json.loads((run / "run-state.json").read_text(encoding="utf-8"))
    assert state["phase_gates"]["phase2"] == "PUBLISHED"
    assert (package_root.parent / "reviews" / "RR-PUB-PHASE-1.json").is_file()


@pytest.mark.parametrize("publication_phase", [None, 2])
def test_historical_publication_receipt_ignores_newer_current_handoff_chronology(
    tmp_path: Path, publication_phase: int | None
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 2)
    _, newer_phase1 = add_collaboration_sibling(
        run,
        package,
        task_id="SYN-W1-SQL-PHASE1-NEWER",
        wave_id="wave1_source_extraction",
        status="COMPLETED",
        agent_id=handoff["agent_id"],
        phase_targets=[1],
    )
    newer_phase1["completed_at"] = "2026-07-28T00:40:00Z"
    (run / "handoffs" / "SYN-W1-SQL-PHASE1-NEWER.json").write_text(
        json.dumps(newer_phase1), encoding="utf-8"
    )
    implementation_path = (
        package_root.parent / "reviews" / "RR-IMPL-SYN-W1-SQL-ORDERS.json"
    )
    implementation = json.loads(implementation_path.read_text(encoding="utf-8"))
    implementation["reviewed_at"] = "2026-07-28T00:50:00Z"
    implementation_path.write_text(json.dumps(implementation), encoding="utf-8")
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 1, "RR-PUB-PHASE-1"),
    )
    if publication_phase == 2:
        current = publication_receipt(
            package, run, handoff, 2, "RR-PUB-PHASE-2"
        )
        current["reviewed_at"] = "2026-07-28T01:00:00Z"
        write_review_receipt(
            package_root,
            current,
        )

    errors, _, _ = validate_run_handoffs(
        run,
        work_package_root=package_root,
        publication_phase=publication_phase,
    )

    assert errors == []


def test_current_publication_receipt_remains_exactly_output_bound(
    tmp_path: Path,
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 2)
    stale = publication_receipt(
        package, run, handoff, 2, "RR-PUB-PHASE-2"
    )
    artifact = run / handoff["artifacts"][0]
    artifact.write_text('{"phase": 2}', encoding="utf-8")
    implementation = handoff_receipt(package, run, handoff)
    implementation["receipt_id"] = "RR-IMPL-SYN-W1-SQL-ORDERS"
    write_review_receipt(package_root, implementation)
    write_review_receipt(package_root, stale)

    errors, _, _ = validate_run_handoffs(
        run, work_package_root=package_root, publication_phase=2
    )

    assert any(
        error.startswith("RR-PUB-PHASE-2: invalid publication review receipt")
        for error in errors
    )


@pytest.mark.parametrize(
    "case",
    [
        "package_id",
        "package_digest",
        "phase",
        "authority",
        "producer",
        "reviewer",
        "decision",
        "validation",
        "schema",
        "output_missing",
        "output_format",
    ],
)
def test_historical_publication_receipt_still_validates_contract_fields(
    tmp_path: Path, case: str
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 2)
    historical = publication_receipt(
        package, run, handoff, 1, "RR-PUB-PHASE-1"
    )
    if case == "package_id":
        historical["work_package_id"] = "WP_UNKNOWN"
    elif case == "package_digest":
        historical["work_package_digest"] = "d" * 64
    elif case == "phase":
        historical["publication_phase"] = 0
    elif case == "authority":
        historical["authority_snapshot"]["checksum"] = "d" * 64
    elif case == "producer":
        historical["producer"] = "implementation-agent"
    elif case == "reviewer":
        historical["reviewer"] = "other-reviewer"
    elif case == "decision":
        historical["decision"] = "CHANGES_REQUESTED"
    elif case == "validation":
        historical["validation_results"][0] = {
            "command": package["validation_commands"][0],
            "exit_code": 1,
            "result": "FAIL",
        }
    elif case == "schema":
        historical["schema_version"] = "2.0"
    elif case == "output_missing":
        del historical["authority_snapshot"]["produced_artifact_digest"]
    elif case == "output_format":
        historical["authority_snapshot"]["produced_artifact_digest"] = "bad"
    else:
        raise AssertionError(case)
    write_review_receipt(package_root, historical)
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 2, "RR-PUB-PHASE-2"),
    )

    errors, _, _ = validate_run_handoffs(
        run, work_package_root=package_root, publication_phase=2
    )

    assert errors


def test_future_publication_receipt_fails_closed_at_current_gate(
    tmp_path: Path,
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 2)
    package["scope"]["phase_targets"].append(3)
    package_path = package_root / package["package_id"] / "work-package.json"
    package_path.write_text(json.dumps(package), encoding="utf-8")
    for path in (run / "tasks").glob("*.json"):
        task = json.loads(path.read_text(encoding="utf-8"))
        task["work_package_digest"] = work_package_digest(package)
        path.write_text(json.dumps(task), encoding="utf-8")
    for path in (run / "handoffs").glob("*.json"):
        bound = json.loads(path.read_text(encoding="utf-8"))
        bound["work_package_digest"] = work_package_digest(package)
        path.write_text(json.dumps(bound), encoding="utf-8")
    implementation = handoff_receipt(package, run, handoff)
    implementation["receipt_id"] = "RR-IMPL-SYN-W1-SQL-ORDERS"
    write_review_receipt(package_root, implementation)
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 2, "RR-PUB-PHASE-2"),
    )
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 3, "RR-PUB-PHASE-3"),
    )

    errors, _, _ = validate_run_handoffs(
        run, work_package_root=package_root, publication_phase=2
    )

    assert any(
        error.startswith("RR-PUB-PHASE-3: invalid publication review receipt")
        and "publication phase" in error
        for error in errors
    )


def test_duplicate_publication_receipts_for_same_phase_are_invalid(
    tmp_path: Path,
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 2)
    for receipt_id in ("RR-PUB-PHASE-2-A", "RR-PUB-PHASE-2-B"):
        write_review_receipt(
            package_root,
            publication_receipt(package, run, handoff, 2, receipt_id),
        )

    errors, _, _ = validate_run_handoffs(
        run, work_package_root=package_root, publication_phase=2
    )

    assert "WP_SYN_SQL: duplicate publication review receipts for phase 2" in errors

def test_publication_gate_requires_current_phase_receipt(tmp_path: Path) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 2)
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 1, "RR-PUB-PHASE-1"),
    )

    errors, _, _ = validate_run_handoffs(
        run, work_package_root=package_root, publication_phase=2
    )

    assert "WP_SYN_SQL: publication review receipt required for phase 2" in errors


@pytest.mark.parametrize("status", [None, "FAILED", "BLOCKED"])
def test_publication_function_requires_completed_same_phase_sibling(
    tmp_path: Path, status: str | None
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 1)
    task, _ = add_collaboration_sibling(
        run,
        package,
        task_id="SYN-PHASE-1-SIBLING",
        wave_id="wave1_source_extraction",
        status=status or "COMPLETED",
        agent_id="implementation-agent",
        phase_targets=[1],
    )
    if status is None:
        (run / "handoffs" / f"{task['task_id']}.json").unlink()
        expected = f"Missing handoff: {task['task_id']}"
    else:
        expected = f"{task['task_id']}: handoff status is {status!r}"
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 1, "RR-PUB-PHASE-1"),
    )

    errors, _, _ = validate_run_handoffs(
        run,
        wave="gate1_publish_phase1",
        require_complete=True,
        work_package_root=package_root,
        publication_phase=1,
    )

    assert expected in errors


def test_publication_cli_requires_completed_cross_wave_phase_sibling(
    tmp_path: Path,
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 1)
    task, _ = add_collaboration_sibling(
        run,
        package,
        task_id="SYN-PHASE-1-SIBLING",
        wave_id="wave1_source_extraction",
        status="FAILED",
        agent_id="implementation-agent",
        phase_targets=[1],
    )
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 1, "RR-PUB-PHASE-1"),
    )

    completed = run_handoff_validation(
        run,
        "--wave",
        "gate1_publish_phase1",
        "--require-complete",
        "--work-package-root",
        str(package_root),
        "--publication-phase",
        "1",
    )

    assert completed.returncode == 1
    assert f"ERROR: {task['task_id']}: handoff status is 'FAILED'" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


def test_publication_advance_blocks_same_agent_cross_wave_phase_sibling(
    tmp_path: Path,
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 1)
    task, _ = add_collaboration_sibling(
        run,
        package,
        task_id="SYN-PHASE-1-SIBLING",
        wave_id="wave1_source_extraction",
        status="BLOCKED",
        agent_id="implementation-agent",
        phase_targets=[1],
    )
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 1, "RR-PUB-PHASE-1"),
    )

    completed = run_advance(
        run,
        "--work-package-root",
        str(package_root),
        "--approve-checkpoint",
        wave="gate1_publish_phase1",
        dry_run=False,
    )

    assert completed.returncode == 1
    assert f"ERROR: {task['task_id']}: handoff status is 'BLOCKED'" in completed.stdout
    state = json.loads((run / "run-state.json").read_text(encoding="utf-8"))
    assert state["phase_gates"]["phase1"] != "PUBLISHED"


def test_publication_ignores_sibling_exclusively_targeting_future_phase(
    tmp_path: Path,
) -> None:
    package, run, package_root, handoff = publication_run(
        tmp_path, 1, package_phase_targets=[1, 2]
    )
    add_collaboration_sibling(
        run,
        package,
        task_id="SYN-PHASE-2-SIBLING",
        wave_id="wave1_source_extraction",
        status="BLOCKED",
        agent_id="implementation-agent",
        phase_targets=[2],
    )
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 1, "RR-PUB-PHASE-1"),
    )

    assert validate_run_handoffs(
        run,
        wave="gate1_publish_phase1",
        require_complete=True,
        work_package_root=package_root,
        publication_phase=1,
    ) == ([], 1, 0)


def test_publication_advance_blocks_cross_wave_failed_sibling_agent(
    tmp_path: Path,
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, 1)
    write_review_receipt(
        package_root,
        publication_receipt(package, run, handoff, 1, "RR-PUB-PHASE-1"),
    )
    add_collaboration_sibling(
        run,
        package,
        task_id="SYN-W1-SQL-FAILED",
        wave_id="wave1_source_extraction",
        status="FAILED",
        agent_id="second-agent",
    )

    completed = run_advance(
        run,
        "--work-package-root",
        str(package_root),
        "--approve-checkpoint",
        wave="gate1_publish_phase1",
        dry_run=False,
    )

    assert completed.returncode == 1
    assert (
        "WP_SYN_SQL: multiple implementation agents; split work package"
        in completed.stdout
    )
    state = json.loads((run / "run-state.json").read_text(encoding="utf-8"))
    assert state["phase_gates"]["phase1"] != "PUBLISHED"


@pytest.mark.parametrize("phase", range(1, 7))
def test_publication_advance_blocks_without_publication_receipt(
    tmp_path: Path, phase: int
) -> None:
    _, run, package_root, _ = publication_run(tmp_path, phase)

    completed = run_advance(
        run,
        "--work-package-root",
        str(package_root),
        "--approve-checkpoint",
        wave=f"gate{phase}_publish_phase{phase}",
        dry_run=False,
    )

    assert completed.returncode == 1
    assert "publication review receipt required" in completed.stdout
    state = json.loads((run / "run-state.json").read_text(encoding="utf-8"))
    assert state["phase_gates"][f"phase{phase}"] != "PUBLISHED"


@pytest.mark.parametrize("phase", range(1, 7))
def test_publication_advance_publishes_with_exact_publication_receipt(
    tmp_path: Path, phase: int
) -> None:
    package, run, package_root, handoff = publication_run(tmp_path, phase)
    receipt = implementation_receipt(
        package,
        stage="publication",
        producer=package["coordinator"],
        publication_phase=phase,
        produced_artifact_digest=expected_artifact_set_digest(
            run, handoff["artifacts"]
        ),
    )
    receipt["receipt_id"] = "RR-PUB-WP-SYN-SQL"
    write_review_receipt(package_root, receipt)

    completed = run_advance(
        run,
        "--work-package-root",
        str(package_root),
        "--approve-checkpoint",
        wave=f"gate{phase}_publish_phase{phase}",
        dry_run=False,
    )

    assert completed.returncode == 0
    state = json.loads((run / "run-state.json").read_text(encoding="utf-8"))
    assert state["phase_gates"][f"phase{phase}"] == "PUBLISHED"


def test_publication_validation_reports_duplicate_artifacts_without_exception(
    tmp_path: Path,
) -> None:
    package = application_package()
    artifact = package["expected_artifacts"][0]["path"]
    write_path = artifact.rsplit("/", 1)[0]
    run, package_root = write_multi_task_run(
        tmp_path,
        package,
        [
            ("SYN-W1-SQL-FIRST", write_path, [artifact], "COMPLETED"),
            ("SYN-W1-SQL-SECOND", write_path, [artifact], "COMPLETED"),
        ],
    )

    errors, _, _ = validate_run_handoffs(
        run, work_package_root=package_root, publication_phase=1
    )

    assert any("required artifact reported multiple times" in error for error in errors)
    assert any("duplicate artifact" in error for error in errors)


def test_completed_handoff_requires_reported_required_artifact(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path, package, handoff_changes={"artifacts": []}
    )

    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )

    assert errors == [
        "WP_SYN_SQL: required artifact not reported: "
        "work/sql_data/module-orders/result.json"
    ]
    assert (checked, pending) == (1, 0)


def test_duplicate_artifact_entry_fails_deterministically(tmp_path: Path) -> None:
    package = application_package()
    artifact = package["expected_artifacts"][0]["path"]
    run, package_root, _, _ = write_run(
        tmp_path, package, handoff_changes={"artifacts": [artifact, artifact]}
    )

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert errors == [
        f"SYN-W1-SQL-ORDERS: duplicate artifact entry: {artifact}"
    ]


@pytest.mark.parametrize(
    ("first_name", "second_name"),
    [("result.json", "result.JSON"), ("straße.json", "STRASSE.json")],
)
def test_casefold_artifact_collision_fails_deterministically(
    tmp_path: Path, first_name: str, second_name: str
) -> None:
    package = application_package()
    required_artifact = package["expected_artifacts"][0]["path"]
    parent = required_artifact.rsplit("/", 1)[0]
    first = f"{parent}/{first_name}"
    second = f"{parent}/{second_name}"
    artifacts = [required_artifact, first, second]
    artifacts = list(dict.fromkeys(artifacts))
    run, package_root, _, _ = write_run(
        tmp_path, package, handoff_changes={"artifacts": artifacts}
    )
    for artifact in artifacts:
        (run / artifact).write_text("{}", encoding="utf-8")

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert errors == [
        f"SYN-W1-SQL-ORDERS: duplicate artifact entry: {second}"
    ]


def test_case_only_artifact_variant_satisfies_required_identity(
    tmp_path: Path,
) -> None:
    package = application_package()
    required_artifact = package["expected_artifacts"][0]["path"]
    variant = required_artifact.replace("result.json", "result.JSON")
    run, package_root, _, _ = write_run(
        tmp_path, package, handoff_changes={"artifacts": [variant]}
    )
    (run / variant).write_text("{}", encoding="utf-8")

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        1,
        0,
    )


def test_distinct_artifact_names_remain_valid(tmp_path: Path) -> None:
    package = application_package()
    required_artifact = package["expected_artifacts"][0]["path"]
    distinct = required_artifact.replace("result.json", "result-summary.JSON")
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"artifacts": [required_artifact, distinct]},
    )
    (run / distinct).write_text("{}", encoding="utf-8")

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        1,
        0,
    )


def test_completed_handoff_may_omit_optional_artifact(tmp_path: Path) -> None:
    package = application_package()
    package["expected_artifacts"].append(
        {
            "path": "work/sql_data/module-orders/optional.json",
            "kind": "analysis_fragment",
            "required": False,
            "publication_class": "scoped",
        }
    )
    run, package_root, _, _ = write_run(tmp_path, package)

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        1,
        0,
    )


@pytest.mark.parametrize("status", ["FAILED", "BLOCKED"])
def test_non_completed_handoff_does_not_satisfy_required_artifact(
    tmp_path: Path, status: str
) -> None:
    package = application_package()
    artifact = package["expected_artifacts"][0]["path"]
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"status": status, "artifacts": []},
    )
    (run / artifact).unlink()

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [f"WP_SYN_SQL: required artifact not reported: {artifact}"],
        1,
        0,
    )


def test_cli_blocks_unreported_required_artifact(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path, package, handoff_changes={"artifacts": []}
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--run",
            str(run),
            "--work-package-root",
            str(package_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert (
        "ERROR: WP_SYN_SQL: required artifact not reported: "
        "work/sql_data/module-orders/result.json" in completed.stdout
    )
    assert "Traceback" not in completed.stdout + completed.stderr


def test_cli_blocks_case_variant_artifact_duplicate(tmp_path: Path) -> None:
    package = application_package()
    required_artifact = package["expected_artifacts"][0]["path"]
    variant = required_artifact.replace("result.json", "result.JSON")
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"artifacts": [required_artifact, variant]},
    )
    (run / variant).write_text("{}", encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"

    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--run",
            str(run),
            "--work-package-root",
            str(package_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 1
    assert (
        f"ERROR: SYN-W1-SQL-ORDERS: duplicate artifact entry: {variant}"
        in completed.stdout
    )
    assert "Traceback" not in completed.stdout + completed.stderr


def test_projected_handoff_requires_work_package_root(tmp_path: Path) -> None:
    package = application_package()
    run, _, _, _ = write_run(tmp_path, package)
    errors, _, _ = validate_run_handoffs(run)
    assert any("work package root required" in error for error in errors)


def test_projected_handoff_requires_package_file(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package, create_package=False)
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert any("work package file missing" in error for error in errors)


def test_non_utf8_work_package_returns_deterministic_error(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    package_path = package_root / package["package_id"] / "work-package.json"
    package_path.write_bytes(b"\xff")
    assert validate_run_handoffs(run, work_package_root=package_root) == (
        ["SYN-W1-SQL-ORDERS: invalid work package"],
        1,
        0,
    )


def test_cli_non_utf8_work_package_has_no_traceback(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    package_path = package_root / package["package_id"] / "work-package.json"
    package_path.write_bytes(b"\xff")
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--run",
            str(run),
            "--work-package-root",
            str(package_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "ERROR: SYN-W1-SQL-ORDERS: invalid work package" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


def test_projected_task_rejects_stale_package_digest(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package, task_changes={"work_package_digest": "e" * 64})
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert any("task work package digest mismatch" in error for error in errors)


@pytest.mark.parametrize(
    ("task_changes", "handoff_changes", "field"),
    [
        (
            {"write_paths": ["work/unauthorized"]},
            {"artifacts": ["work/unauthorized/result.json"]},
            "write_paths",
        ),
        ({"input_paths": ["../../extracted/unauthorized"]}, {}, "input_paths"),
        (
            {"evidence_namespace": "SYN-UNAUTHORIZED"},
            {"evidence_ids": ["SYN-UNAUTHORIZED-1"]},
            "evidence_namespace",
        ),
        ({"module_targets": ["module-unauthorized"]}, {}, "module_targets"),
        ({"phase_targets": [2]}, {}, "phase_targets"),
    ],
)
def test_projected_task_is_revalidated_against_canonical_package(
    tmp_path: Path,
    task_changes: dict,
    handoff_changes: dict,
    field: str,
) -> None:
    package = application_package()
    run, package_root, _, handoff = write_run(
        tmp_path,
        package,
        task_changes=task_changes,
        handoff_changes=handoff_changes,
    )
    for artifact in handoff["artifacts"]:
        artifact_path = run / artifact
        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text("unauthorized", encoding="utf-8")
    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )
    assert errors == [
        f"SYN-W1-SQL-ORDERS: invalid task projection: "
        f"COLLAB_PROJECTION_EXPANDED: {field}"
    ]
    assert (checked, pending) == (1, 0)


@pytest.mark.parametrize(
    "artifact",
    [
        "work/sql_data/module-orders/result.json:secret",
        "work/sql_data/module-orders/result<.json",
        "work/sql_data/module-orders/result>.json",
        'work/sql_data/module-orders/result".json',
        "work/sql_data/module-orders/result|.json",
        "work/sql_data/module-orders/result?.json",
        "work/sql_data/module-orders/result*.json",
        "work/sql_data/module-orders/CON/result.json",
        "work/sql_data/module-orders/" + chr(1) + "result.json",
        "work/sql_data/module-orders/./result.json",
        "work/sql_data/module-orders/result.json.",
        "work/sql_data/module-orders/../result.json",
        "work"
        + chr(92)
        + "sql_data"
        + chr(92)
        + "module-orders"
        + chr(92)
        + "result.json",
        "D:/work/sql_data/module-orders/result.json",
    ],
)
def test_artifact_paths_must_be_canonical(
    tmp_path: Path, artifact: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path, package, handoff_changes={"artifacts": [artifact]}
    )

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert any("invalid artifact path" in error for error in errors)


def test_utf8_artifact_path_remains_valid(tmp_path: Path) -> None:
    package = application_package()
    artifact = "work/sql_data/module-orders/結果.json"
    required_artifact = package["expected_artifacts"][0]["path"]
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"artifacts": [required_artifact, artifact]},
    )
    artifact_path = run / artifact
    assert artifact_path.is_file()

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        1,
        0,
    )


def test_source_read_must_be_inside_projected_task_input_scope(tmp_path: Path) -> None:
    package = application_package()
    source = "sources/outside.sql"
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"source_files_read": [source]},
    )
    inventory = valid_source_inventory()
    inventory["files"] = [inventory_file(source)]
    (run / "source-inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )
    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )
    assert errors == [
        "SYN-W1-SQL-ORDERS: source outside task input scope: sources/outside.sql"
    ]
    assert (checked, pending) == (1, 0)


def test_runtime_prefixed_task_input_accepts_in_scope_source(tmp_path: Path) -> None:
    package = application_package()
    source = "extracted/bundles/bundle-a/code/access-sql/query.sql"
    run, package_root, task, handoff = write_run(
        tmp_path,
        package,
        handoff_changes={"source_files_read": [source]},
        create_receipt=False,
    )
    inventory = valid_source_inventory()
    inventory["files"] = [inventory_file(source)]
    (run / "source-inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )
    receipt = handoff_receipt(package, run, handoff)
    receipt["receipt_id"] = f"RR-IMPL-{task['task_id']}"
    write_review_receipt(package_root, receipt)
    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        1,
        0,
    )


@pytest.mark.parametrize("source", ["", "CON", "folder/name."])
def test_nonportable_inventory_source_returns_deterministic_errors(
    tmp_path: Path, source: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"source_files_read": [source]},
    )
    inventory = valid_source_inventory()
    inventory["files"] = [inventory_file(source)]
    (run / "source-inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )
    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )
    assert errors == [
        f"source-inventory.json: invalid portable path: {source}",
        f"SYN-W1-SQL-ORDERS: source is absent from immutable inventory: {source}",
    ]
    assert (checked, pending) == (1, 0)


@pytest.mark.parametrize("source", ["", "CON", "folder/name."])
def test_cli_nonportable_inventory_source_has_no_traceback(
    tmp_path: Path, source: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"source_files_read": [source]},
    )
    inventory = valid_source_inventory()
    inventory["files"] = [inventory_file(source)]
    (run / "source-inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--run",
            str(run),
            "--work-package-root",
            str(package_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert (
        f"ERROR: source-inventory.json: invalid portable path: {source}"
        in completed.stdout
    )
    assert (
        f"ERROR: SYN-W1-SQL-ORDERS: source is absent from immutable inventory: {source}"
        in completed.stdout
    )
    assert "Traceback" not in completed.stdout + completed.stderr


@pytest.mark.parametrize(
    "filename",
    ["nul\x00.sql", "line\nbreak.sql", "bad*.sql", "bad?.sql", "bad<.sql", "bad|.sql"],
)
def test_forbidden_inventory_source_character_returns_deterministic_error(
    tmp_path: Path, filename: str
) -> None:
    package = application_package()
    source = f"extracted/bundles/bundle-a/code/access-sql/{filename}"
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"source_files_read": [source]},
    )
    inventory = valid_source_inventory()
    inventory["files"] = [inventory_file(source)]
    (run / "source-inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )
    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )
    assert errors == [
        f"source-inventory.json: invalid portable path: {source}",
        f"SYN-W1-SQL-ORDERS: invalid canonical source path: {source!r}",
    ]
    assert (checked, pending) == (1, 0)


@pytest.mark.parametrize(
    "filename",
    ["nul\x00.sql", "line\nbreak.sql", "bad*.sql", "bad?.sql", "bad<.sql", "bad|.sql"],
)
def test_cli_forbidden_inventory_source_character_has_no_traceback(
    tmp_path: Path, filename: str
) -> None:
    package = application_package()
    source = f"extracted/bundles/bundle-a/code/access-sql/{filename}"
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"source_files_read": [source]},
    )
    inventory = valid_source_inventory()
    inventory["files"] = [inventory_file(source)]
    (run / "source-inventory.json").write_text(
        json.dumps(inventory), encoding="utf-8"
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--run",
            str(run),
            "--work-package-root",
            str(package_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert (
        f"ERROR: source-inventory.json: invalid portable path: {source}"
        in completed.stdout
    )
    assert (
        f"ERROR: SYN-W1-SQL-ORDERS: invalid canonical source path: {source!r}"
        in completed.stdout
    )
    assert "Traceback" not in completed.stdout + completed.stderr


def test_japanese_inventory_source_path_remains_valid(tmp_path: Path) -> None:
    package = application_package()
    source = "extracted/bundles/bundle-a/code/access-sql/\u6ce8\u6587\u7167\u4f1a.sql"
    run, package_root, task, handoff = write_run(
        tmp_path,
        package,
        handoff_changes={"source_files_read": [source]},
        create_receipt=False,
    )
    inventory = valid_source_inventory()
    inventory["files"] = [inventory_file(source)]
    (run / "source-inventory.json").write_text(
        json.dumps(inventory, ensure_ascii=False), encoding="utf-8"
    )
    receipt = handoff_receipt(package, run, handoff)
    receipt["receipt_id"] = f"RR-IMPL-{task['task_id']}"
    write_review_receipt(package_root, receipt)
    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        1,
        0,
    )


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"work_package_id": "WP_OTHER"}, "work package id mismatch"),
        ({"work_package_digest": "f" * 64}, "work package digest mismatch"),
    ],
)
def test_projected_handoff_rejects_package_binding_mismatch(tmp_path: Path, changes: dict, message: str) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package, handoff_changes=changes)
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert any(message in error for error in errors)


def test_projected_handoff_rejects_invalid_schema(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package, handoff_changes={"unexpected": True})
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert any("invalid handoff schema" in error for error in errors)


@pytest.mark.parametrize(
    ("filename", "contents", "message"),
    [
        ("extra-invalid-json.json", b"{", "invalid handoff JSON"),
        ("extra-non-utf8.json", bytes([0xFF]), "invalid handoff JSON"),
        ("extra-invalid-schema.json", b"{}", "invalid handoff schema"),
    ],
)
def test_every_extra_handoff_file_is_validated(
    tmp_path: Path, filename: str, contents: bytes, message: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    (run / "handoffs" / filename).write_bytes(contents)

    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )

    assert any(error.startswith(f"{filename}: {message}") for error in errors)
    assert (checked, pending) == (1, 0)


def test_extra_handoff_file_errors_follow_sorted_filenames(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    (run / "handoffs" / "z-invalid.json").write_bytes(b"{")
    (run / "handoffs" / "a-invalid.json").write_bytes(bytes([0xFF]))

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    extra_errors = [error for error in errors if error.endswith("invalid handoff JSON")]
    assert extra_errors == [
        "a-invalid.json: invalid handoff JSON",
        "z-invalid.json: invalid handoff JSON",
    ]


@pytest.mark.parametrize("case", ["nested", "misc"])
def test_handoff_directory_rejects_non_control_entries(
    tmp_path: Path, case: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    if case == "nested":
        nested = run / "handoffs" / "nested"
        nested.mkdir()
        (nested / "extra.json").write_text("{}", encoding="utf-8")
        expected = [
            "handoffs/nested: invalid handoff control entry",
            "handoffs/nested/extra.json: invalid handoff control entry",
        ]
    else:
        (run / "handoffs" / "notes.txt").write_text("note", encoding="utf-8")
        expected = ["handoffs/notes.txt: invalid handoff control entry"]

    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )

    for message in expected:
        assert message in errors
    assert (checked, pending) == (1, 0)


@pytest.mark.parametrize("case", ["run", "app", "mode"])
def test_wave_filter_still_validates_future_handoff_binding(
    tmp_path: Path, case: str
) -> None:
    package = application_package()
    run, package_root, _, handoff = write_run(tmp_path, package)
    message = add_future_handoff_case(run, handoff, case)

    errors, checked, pending = validate_run_handoffs(
        run,
        wave="wave1_source_extraction",
        work_package_root=package_root,
    )

    assert any(message in error for error in errors)
    assert (checked, pending) == (1, 0)


def test_duplicate_handoff_ids_report_all_sorted_filenames(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, task, handoff = write_run(tmp_path, package)
    message = add_handoff_inventory_case(run, task, handoff, "duplicate")

    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )

    assert message in errors
    assert (checked, pending) == (0, 1)


def test_unknown_task_handoff_is_rejected(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, task, handoff = write_run(tmp_path, package)
    message = add_handoff_inventory_case(run, task, handoff, "unknown")

    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )

    assert message in errors
    assert (checked, pending) == (1, 0)


def test_handoff_filename_must_match_task_id(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, task, _ = write_run(
        tmp_path, package, create_receipt=False
    )
    canonical = run / "handoffs" / f"{task['task_id']}.json"
    canonical.rename(run / "handoffs" / "renamed-handoff.json")

    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )

    assert (
        f"renamed-handoff.json: filename does not match task_id {task['task_id']}"
        in errors
    )
    assert (checked, pending) == (0, 1)


@pytest.mark.parametrize(
    ("filename", "contents", "message"),
    [
        ("extra-invalid-json.json", b"{", "invalid handoff JSON"),
        ("extra-non-utf8.json", bytes([0xFF]), "invalid handoff JSON"),
        ("extra-invalid-schema.json", b"{}", "invalid handoff schema"),
    ],
)
def test_cli_validates_every_extra_handoff_file(
    tmp_path: Path, filename: str, contents: bytes, message: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    (run / "handoffs" / filename).write_bytes(contents)

    completed = run_handoff_validation(
        run, "--work-package-root", str(package_root)
    )

    assert completed.returncode == 1
    assert f"ERROR: {filename}: {message}" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


@pytest.mark.parametrize("case", ["unknown", "duplicate"])
def test_cli_rejects_unmatched_or_duplicate_handoffs(
    tmp_path: Path, case: str
) -> None:
    package = application_package()
    run, package_root, task, handoff = write_run(tmp_path, package)
    message = add_handoff_inventory_case(run, task, handoff, case)

    completed = run_handoff_validation(
        run, "--work-package-root", str(package_root)
    )

    assert completed.returncode == 1
    assert f"ERROR: {message}" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


def test_cli_rejects_handoff_filename_task_id_mismatch(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, task, _ = write_run(tmp_path, package)
    canonical = run / "handoffs" / f"{task['task_id']}.json"
    canonical.rename(run / "handoffs" / "renamed-handoff.json")

    completed = run_handoff_validation(
        run, "--work-package-root", str(package_root)
    )

    assert completed.returncode == 1
    assert (
        "ERROR: renamed-handoff.json: filename does not match task_id "
        f"{task['task_id']}" in completed.stdout
    )
    assert "Traceback" not in completed.stdout + completed.stderr


@pytest.mark.parametrize("case", ["nested", "misc"])
def test_cli_rejects_non_control_handoff_entries(
    tmp_path: Path, case: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    if case == "nested":
        nested = run / "handoffs" / "nested"
        nested.mkdir()
        (nested / "extra.json").write_text("{}", encoding="utf-8")
        message = "handoffs/nested: invalid handoff control entry"
    else:
        (run / "handoffs" / "notes.txt").write_text("note", encoding="utf-8")
        message = "handoffs/notes.txt: invalid handoff control entry"

    completed = run_handoff_validation(
        run, "--work-package-root", str(package_root)
    )

    assert completed.returncode == 1
    assert f"ERROR: {message}" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


@pytest.mark.parametrize("case", ["run", "app", "mode"])
def test_cli_wave_filter_still_validates_future_handoff_binding(
    tmp_path: Path, case: str
) -> None:
    package = application_package()
    run, package_root, _, handoff = write_run(tmp_path, package)
    message = add_future_handoff_case(run, handoff, case)

    completed = run_handoff_validation(
        run,
        "--wave",
        "wave1_source_extraction",
        "--work-package-root",
        str(package_root),
    )

    assert completed.returncode == 1
    assert message in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


def test_handoff_schema_rejects_invalid_result_string() -> None:
    package = application_package()
    task = project_task(package, candidate_task())
    handoff = collaboration_handoff(package, task)
    handoff["validation_results"][0]["result"] = "SUCCESS"
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(handoff, schema("handoff.schema.json"))


@pytest.mark.parametrize("command", [" ", "\t"])
def test_handoff_validation_command_must_be_nonblank(command: str) -> None:
    package = application_package()
    task = project_task(package, candidate_task())
    handoff = collaboration_handoff(package, task)
    handoff["validation_results"].append(
        {"command": command, "exit_code": 0, "result": "PASS"}
    )

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(handoff, schema("handoff.schema.json"))


def test_handoff_validation_command_preserves_unicode(tmp_path: Path) -> None:
    package = application_package()
    validation_results = [
        {
            "command": package["validation_commands"][0],
            "exit_code": 0,
            "result": "PASS",
        },
        {
            "command": "\u691c\u8a3c \u30b3\u30de\u30f3\u30c9",
            "exit_code": 0,
            "result": "PASS",
        },
    ]
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"validation_results": validation_results},
    )

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        1,
        0,
    )


@pytest.mark.parametrize(
    "validation_results",
    [
        [],
        [{"command": "python -m pytest plugins/ak/tests/test_collaboration.py -q", "exit_code": 1, "result": "FAIL"}],
        [{"command": "python -m pytest plugins/ak/tests/test_collaboration.py -q", "exit_code": 0, "result": "FAIL"}],
        [
            {"command": "python -m pytest plugins/ak/tests/test_collaboration.py -q", "exit_code": 0, "result": "PASS"},
            {"command": "python -m pytest plugins/ak/tests/test_collaboration.py -q", "exit_code": 0, "result": "FAIL"},
        ],
        [
            {"command": "python -m pytest plugins/ak/tests/test_collaboration.py -q", "exit_code": 0, "result": "PASS"},
            {"command": "python -m pytest plugins/ak/tests/test_collaboration.py -q", "exit_code": 0, "result": "PASS"},
        ],
    ],
)
def test_projected_handoff_requires_successful_unique_validation_results(tmp_path: Path, validation_results: list[dict]) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package, handoff_changes={"validation_results": validation_results})
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert any("required validation failed" in error for error in errors)


@pytest.mark.parametrize(
    ("status", "validation_results"),
    [
        ("BLOCKED", []),
        (
            "FAILED",
            [
                {
                    "command": "python -m pytest plugins/ak/tests/test_collaboration.py -q",
                    "exit_code": 1,
                    "result": "FAIL",
                }
            ],
        ),
    ],
)
def test_non_completed_handoff_allows_truthful_validation_results(
    tmp_path: Path, status: str, validation_results: list[dict]
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={
            "status": status,
            "validation_results": validation_results,
        },
    )
    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [
            "WP_SYN_SQL: required artifact not reported: "
            "work/sql_data/module-orders/result.json"
        ],
        1,
        0,
    )


@pytest.mark.parametrize("status", ["BLOCKED", "FAILED"])
@pytest.mark.parametrize(
    "validation_result",
    [
        {"command": "synthetic", "exit_code": 1, "result": "PASS"},
        {"command": "synthetic", "exit_code": 0, "result": "FAIL"},
    ],
)
def test_non_completed_handoff_rejects_contradictory_validation_result(
    tmp_path: Path, status: str, validation_result: dict
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={
            "status": status,
            "validation_results": [validation_result],
        },
    )
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert any("inconsistent validation result" in error for error in errors)


@pytest.mark.parametrize("status", ["BLOCKED", "FAILED"])
def test_non_completed_handoff_accepts_truthful_failed_result(
    tmp_path: Path, status: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={
            "status": status,
            "validation_results": [
                {"command": "synthetic", "exit_code": 2, "result": "FAIL"}
            ],
        },
    )
    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [
            "WP_SYN_SQL: required artifact not reported: "
            "work/sql_data/module-orders/result.json"
        ],
        1,
        0,
    )


@pytest.mark.parametrize("status", ["FAILED", "BLOCKED"])
def test_require_complete_requires_completed_handoff_status(
    tmp_path: Path, status: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path, package, handoff_changes={"status": status}
    )

    errors, checked, pending = validate_run_handoffs(
        run,
        wave="wave1_source_extraction",
        require_complete=True,
        work_package_root=package_root,
    )

    assert f"SYN-W1-SQL-ORDERS: handoff status is '{status}'" in errors
    assert (checked, pending) == (1, 0)


@pytest.mark.parametrize("status", ["COMPLETED", "FAILED", "BLOCKED"])
@pytest.mark.parametrize(
    "extra_result",
    [
        {"command": "synthetic-extra", "exit_code": 1, "result": "PASS"},
        {"command": "synthetic-extra", "exit_code": 0, "result": "FAIL"},
    ],
)
def test_extra_handoff_validation_result_must_be_truthful(
    tmp_path: Path, status: str, extra_result: dict
) -> None:
    package = application_package()
    validation_results = [
        {
            "command": package["validation_commands"][0],
            "exit_code": 0,
            "result": "PASS",
        },
        extra_result,
    ]
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={
            "status": status,
            "validation_results": validation_results,
        },
    )
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert any("inconsistent validation result" in error for error in errors)


@pytest.mark.parametrize("status", ["COMPLETED", "FAILED", "BLOCKED"])
def test_duplicate_extra_handoff_validation_command_is_rejected(
    tmp_path: Path, status: str
) -> None:
    package = application_package()
    extra = {"command": "synthetic-extra", "exit_code": 2, "result": "FAIL"}
    validation_results = [
        {
            "command": package["validation_commands"][0],
            "exit_code": 0,
            "result": "PASS",
        },
        extra,
        deepcopy(extra),
    ]
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={
            "status": status,
            "validation_results": validation_results,
        },
    )
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert any("duplicate validation result" in error for error in errors)


@pytest.mark.parametrize("status", ["COMPLETED", "FAILED", "BLOCKED"])
def test_unique_truthful_extra_handoff_validation_is_allowed(
    tmp_path: Path, status: str
) -> None:
    package = application_package()
    validation_results = [
        {
            "command": package["validation_commands"][0],
            "exit_code": 0,
            "result": "PASS",
        },
        {"command": "synthetic-extra", "exit_code": 2, "result": "FAIL"},
    ]
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={
            "status": status,
            "validation_results": validation_results,
        },
    )
    expected = [] if status == "COMPLETED" else [
        "WP_SYN_SQL: required artifact not reported: "
        "work/sql_data/module-orders/result.json"
    ]
    assert validate_run_handoffs(run, work_package_root=package_root) == (
        expected,
        1,
        0,
    )


@pytest.mark.parametrize(
    "handoff_changes",
    [
        {"artifacts": 7},
        {"work_package_id": 7},
        {"validation_results": [{"command": "synthetic"}]},
    ],
)
def test_malformed_projected_handoff_returns_schema_error(
    tmp_path: Path, handoff_changes: dict
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path, package, handoff_changes=handoff_changes
    )
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert len(errors) == 1
    assert "invalid handoff schema" in errors[0]


def test_non_string_projected_task_package_id_returns_file_qualified_schema_error(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path, package, task_changes={"work_package_id": 7}
    )
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert len(errors) == 1
    assert errors[0].startswith("SYN-W1-SQL-ORDERS.json: invalid task schema:")


def test_repository_handoff_requires_produced_revision(tmp_path: Path) -> None:
    package = repository_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert any("produced revision required" in error for error in errors)


@pytest.mark.parametrize("package_factory", [repository_package, mixed_package])
def test_revision_authority_required_artifact_must_be_regular_file(
    tmp_path: Path, package_factory
) -> None:
    package = package_factory()
    run, package_root, task, handoff = write_run(
        tmp_path,
        package,
        handoff_changes={"produced_revision": "revision-one"},
    )
    artifact = run / handoff["artifacts"][0]
    artifact.unlink()
    artifact.mkdir()

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert (
        f"{task['task_id']}: artifact is not a regular file: "
        f"{handoff['artifacts'][0]}"
    ) in errors


@pytest.mark.parametrize("package_factory", [repository_package, mixed_package])
def test_completed_repository_handoff_rejects_whitespace_produced_revision(
    tmp_path: Path, package_factory
) -> None:
    package = package_factory()
    run, package_root, _, _ = write_run(
        tmp_path, package, handoff_changes={"produced_revision": " \t"}
    )
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert len(errors) == 1
    assert "invalid handoff schema" in errors[0]


@pytest.mark.parametrize("package_factory", [repository_package, mixed_package])
def test_cli_completed_repository_handoff_rejects_whitespace_produced_revision(
    tmp_path: Path, package_factory
) -> None:
    package = package_factory()
    run, package_root, _, _ = write_run(
        tmp_path, package, handoff_changes={"produced_revision": " \t"}
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--run",
            str(run),
            "--work-package-root",
            str(package_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "invalid handoff schema" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


def test_artifact_only_handoff_rejects_produced_revision(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package, handoff_changes={"produced_revision": "revision-one"})
    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    assert any("produced revision must be null" in error for error in errors)


def test_projected_task_rejects_legacy_handoff_mode(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, task, _ = write_run(
        tmp_path, package, create_receipt=False
    )
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(legacy_handoff(task)), encoding="utf-8"
    )
    errors, checked, pending = validate_run_handoffs(
        run, work_package_root=package_root
    )
    assert errors == [
        "SYN-W1-SQL-ORDERS: collaboration mode mismatch: task=collaboration handoff=legacy"
    ]
    assert (checked, pending) == (1, 0)


def test_legacy_task_rejects_collaboration_handoff_mode(tmp_path: Path) -> None:
    package = application_package()
    run, _, task, handoff = write_run(tmp_path, package)
    (run / "tasks" / f"{task['task_id']}.json").write_text(
        json.dumps(candidate_task()), encoding="utf-8"
    )
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )
    errors, checked, pending = validate_run_handoffs(run)
    assert errors == [
        "SYN-W1-SQL-ORDERS: collaboration mode mismatch: task=legacy handoff=collaboration"
    ]
    assert (checked, pending) == (1, 0)


def test_cli_mode_mismatch_returns_failure_without_traceback(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, task, _ = write_run(tmp_path, package)
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(legacy_handoff(task)), encoding="utf-8"
    )
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--run",
            str(run),
            "--work-package-root",
            str(package_root),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert "collaboration mode mismatch" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


def test_duplicate_task_ids_report_all_sorted_filenames(tmp_path: Path) -> None:
    task = candidate_task()
    run = write_task_only_run(tmp_path, json.dumps(task))
    (run / "tasks" / "bad-task.json").rename(run / "tasks" / "z-task.json")
    (run / "tasks" / "a-task.json").write_text(json.dumps(task), encoding="utf-8")
    errors, checked, pending = validate_run_handoffs(run)
    assert errors == [
        "duplicate task id SYN-W1-SQL-ORDERS: a-task.json, z-task.json"
    ]
    assert (checked, pending) == (0, 0)


def test_cli_duplicate_task_ids_returns_failure_without_traceback(tmp_path: Path) -> None:
    task = candidate_task()
    run = write_task_only_run(tmp_path, json.dumps(task))
    (run / "tasks" / "bad-task.json").rename(run / "tasks" / "z-task.json")
    (run / "tasks" / "a-task.json").write_text(json.dumps(task), encoding="utf-8")
    script = Path(__file__).resolve().parents[1] / "scripts" / "validate_handoffs.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--run", str(run)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 1
    assert (
        "ERROR: duplicate task id SYN-W1-SQL-ORDERS: a-task.json, z-task.json"
        in completed.stdout
    )
    assert "Traceback" not in completed.stdout + completed.stderr


def test_legacy_handoff_validation_path_remains_valid(tmp_path: Path) -> None:
    run = tmp_path / "run"
    (run / "tasks").mkdir(parents=True)
    (run / "handoffs").mkdir()
    (run / "run-state.json").write_text(json.dumps(valid_run_state()), encoding="utf-8")
    (run / "source-inventory.json").write_text(json.dumps(valid_source_inventory()), encoding="utf-8")
    task = candidate_task()
    (run / "tasks" / f"{task['task_id']}.json").write_text(json.dumps(task), encoding="utf-8")
    (run / "handoffs" / f"{task['task_id']}.json").write_text(json.dumps(legacy_handoff(task)), encoding="utf-8")
    assert validate_run_handoffs(run) == ([], 1, 0)


def test_write_scope_casing_differs_for_legacy_and_projected_tasks(
    tmp_path: Path,
) -> None:
    case_variant = "WORK/sql_data/module-orders/result.json"
    legacy_task = candidate_task()
    legacy_run = write_task_only_run(tmp_path / "legacy", json.dumps(legacy_task))
    legacy_artifact = legacy_run / case_variant
    legacy_artifact.parent.mkdir(parents=True)
    legacy_artifact.write_text("{}", encoding="utf-8")
    legacy = legacy_handoff(legacy_task)
    legacy["artifacts"] = [case_variant]
    (legacy_run / "handoffs" / f"{legacy_task['task_id']}.json").write_text(
        json.dumps(legacy), encoding="utf-8"
    )

    package = application_package()
    projected_run, package_root, _, projected = write_run(
        tmp_path / "projected",
        package,
        handoff_changes={"artifacts": [case_variant]},
        create_receipt=False,
    )
    projected_artifact = projected_run / case_variant
    projected_artifact.parent.mkdir(parents=True, exist_ok=True)
    projected_artifact.write_text("{}", encoding="utf-8")
    receipt = handoff_receipt(package, projected_run, projected)
    receipt["receipt_id"] = "RR-IMPL-WP-SCOPE-CASE"
    write_review_receipt(package_root, receipt)

    legacy_errors, _, _ = validate_run_handoffs(legacy_run)
    projected_errors, _, _ = validate_run_handoffs(
        projected_run, work_package_root=package_root
    )

    assert (
        "SYN-W1-SQL-ORDERS: artifact outside declared write_paths: "
        f"{case_variant}"
    ) in legacy_errors
    assert projected_errors == []


def test_artifact_file_type_policy_differs_for_legacy_and_collaboration(
    tmp_path: Path,
) -> None:
    artifact = "work/sql_data/module-orders/result.json"
    legacy_task = candidate_task()
    legacy_run = write_task_only_run(tmp_path / "legacy", json.dumps(legacy_task))
    (legacy_run / artifact).mkdir(parents=True)
    legacy = legacy_handoff(legacy_task)
    legacy["artifacts"] = [artifact]
    (legacy_run / "handoffs" / f"{legacy_task['task_id']}.json").write_text(
        json.dumps(legacy), encoding="utf-8"
    )

    package = application_package()
    collaboration_run, package_root, task, handoff = write_run(
        tmp_path / "collaboration", package
    )
    collaboration_artifact = collaboration_run / handoff["artifacts"][0]
    collaboration_artifact.unlink()
    collaboration_artifact.mkdir()

    legacy_errors, _, _ = validate_run_handoffs(legacy_run)
    collaboration_errors, _, _ = validate_run_handoffs(
        collaboration_run, work_package_root=package_root
    )

    assert legacy_errors == []
    assert (
        f"{task['task_id']}: artifact is not a regular file: "
        f"{handoff['artifacts'][0]}"
    ) in collaboration_errors


@pytest.mark.parametrize("status", ["COMPLETED", "FAILED", "BLOCKED"])
def test_collaboration_existing_artifact_must_be_regular_file_for_all_statuses(
    tmp_path: Path, status: str
) -> None:
    package = application_package()
    run, package_root, task, handoff = write_run(
        tmp_path, package, handoff_changes={"status": status}
    )
    artifact = run / handoff["artifacts"][0]
    artifact.unlink()
    artifact.mkdir()

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert (
        f"{task['task_id']}: artifact is not a regular file: "
        f"{handoff['artifacts'][0]}"
    ) in errors


@pytest.mark.parametrize("status", ["FAILED", "BLOCKED"])
def test_legacy_noncompleted_missing_artifact_matches_base_behavior(
    tmp_path: Path, status: str
) -> None:
    task = candidate_task()
    run = write_task_only_run(tmp_path, json.dumps(task))
    handoff = legacy_handoff(task)
    handoff["status"] = status
    handoff["artifacts"] = ["work/sql_data/module-orders/intended.json"]
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )

    errors, _, _ = validate_run_handoffs(run)
    cli = run_handoff_validation(run)
    advance = run_advance(run)

    assert errors == []
    assert cli.returncode == 0
    assert advance.returncode == 1
    assert f"handoff status is {status!r}" in advance.stdout
    assert "artifact missing" not in advance.stdout


def test_legacy_completed_missing_artifact_keeps_base_error(tmp_path: Path) -> None:
    task = candidate_task()
    run = write_task_only_run(tmp_path, json.dumps(task))
    handoff = legacy_handoff(task)
    handoff["artifacts"] = ["work/sql_data/module-orders/missing.json"]
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )

    errors, _, _ = validate_run_handoffs(run)
    cli = run_handoff_validation(run)

    message = (
        "SYN-W1-SQL-ORDERS: completed artifact missing: "
        "work/sql_data/module-orders/missing.json"
    )
    assert message in errors
    assert cli.returncode == 1
    assert f"ERROR: {message}" in cli.stdout


@pytest.mark.parametrize("status", ["FAILED", "BLOCKED"])
def test_collaboration_noncompleted_missing_artifact_keeps_contract_checks(
    tmp_path: Path, status: str
) -> None:
    package = application_package()
    run, package_root, task, handoff = write_run(
        tmp_path, package, handoff_changes={"status": status}
    )
    artifact = run / handoff["artifacts"][0]
    artifact.unlink()

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert f"{task['task_id']}: artifact missing" not in errors
    assert (
        "WP_SYN_SQL: required artifact not reported: "
        "work/sql_data/module-orders/result.json"
    ) in errors


def test_advance_run_projected_dry_run_accepts_work_package_root(
    tmp_path: Path,
) -> None:
    run, package_root, _, _ = write_run(tmp_path, application_package())

    completed = run_advance(run, "--work-package-root", str(package_root))

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["completed_wave"] == "wave1_source_extraction"
    assert "Traceback" not in completed.stdout + completed.stderr


def test_advance_run_allows_historical_publication_receipt_outside_gate(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    receipt = implementation_receipt(
        package,
        stage="publication",
        producer=package["coordinator"],
        produced_artifact_digest="d" * 64,
    )
    receipt["receipt_id"] = "RR-PUB-STALE"
    write_review_receipt(package_root, receipt)

    completed = run_advance(run, "--work-package-root", str(package_root))

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["completed_wave"] == "wave1_source_extraction"
    assert "Traceback" not in completed.stdout + completed.stderr


def test_advance_run_blocks_unreported_required_artifact(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(
        tmp_path, package, handoff_changes={"artifacts": []}
    )

    completed = run_advance(run, "--work-package-root", str(package_root))

    assert completed.returncode == 1
    assert (
        "ERROR: WP_SYN_SQL: required artifact not reported: "
        "work/sql_data/module-orders/result.json" in completed.stdout
    )
    assert "Traceback" not in completed.stdout + completed.stderr


def test_advance_run_blocks_case_variant_artifact_duplicate(
    tmp_path: Path,
) -> None:
    package = application_package()
    required_artifact = package["expected_artifacts"][0]["path"]
    variant = required_artifact.replace("result.json", "result.JSON")
    run, package_root, _, _ = write_run(
        tmp_path,
        package,
        handoff_changes={"artifacts": [required_artifact, variant]},
    )
    (run / variant).write_text("{}", encoding="utf-8")

    completed = run_advance(run, "--work-package-root", str(package_root))

    assert completed.returncode == 1
    assert (
        f"ERROR: SYN-W1-SQL-ORDERS: duplicate artifact entry: {variant}"
        in completed.stdout
    )
    assert "Traceback" not in completed.stdout + completed.stderr


def test_advance_run_projected_without_root_is_deterministically_blocked(
    tmp_path: Path,
) -> None:
    run, _, _, _ = write_run(tmp_path, application_package())

    completed = run_advance(run)

    assert completed.returncode == 1
    assert "ERROR: SYN-W1-SQL-ORDERS: work package root required" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


def test_advance_run_validator_error_skips_raw_task_reread(tmp_path: Path) -> None:
    run = write_task_only_run(tmp_path, "{")

    completed = run_advance(run)

    assert completed.returncode == 1
    assert "ERROR: bad-task.json: invalid task JSON" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


@pytest.mark.parametrize("case", ["malformed", "unknown", "duplicate"])
def test_advance_run_blocks_on_invalid_extra_handoff_inventory(
    tmp_path: Path, case: str
) -> None:
    package = application_package()
    run, package_root, task, handoff = write_run(tmp_path, package)
    message = add_handoff_inventory_case(run, task, handoff, case)

    completed = run_advance(
        run, "--work-package-root", str(package_root)
    )

    assert completed.returncode == 1
    assert f"ERROR: {message}" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


@pytest.mark.parametrize("case", ["nested", "misc"])
def test_advance_run_blocks_on_non_control_handoff_entries(
    tmp_path: Path, case: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    if case == "nested":
        nested = run / "handoffs" / "nested"
        nested.mkdir()
        (nested / "extra.json").write_text("{}", encoding="utf-8")
        message = "handoffs/nested: invalid handoff control entry"
    else:
        (run / "handoffs" / "notes.txt").write_text("note", encoding="utf-8")
        message = "handoffs/notes.txt: invalid handoff control entry"

    completed = run_advance(
        run, "--work-package-root", str(package_root)
    )

    assert completed.returncode == 1
    assert f"ERROR: {message}" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


@pytest.mark.parametrize("case", ["run", "app", "mode"])
def test_advance_run_blocks_on_invalid_future_handoff_binding(
    tmp_path: Path, case: str
) -> None:
    package = application_package()
    run, package_root, _, handoff = write_run(tmp_path, package)
    message = add_future_handoff_case(run, handoff, case)

    completed = run_advance(
        run, "--work-package-root", str(package_root)
    )

    assert completed.returncode == 1
    assert message in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


@pytest.mark.parametrize(
    ("filename", "contents", "message"),
    [
        ("run-state.json", b"{", "run-state.json: invalid JSON"),
        ("run-state.json", bytes([0xFF]), "run-state.json: invalid JSON"),
        ("run-state.json", b"{}", "run-state.json: invalid schema"),
        ("source-inventory.json", b"{", "source-inventory.json: invalid JSON"),
        (
            "source-inventory.json",
            bytes([0xFF]),
            "source-inventory.json: invalid JSON",
        ),
        ("source-inventory.json", b"{}", "source-inventory.json: invalid schema"),
    ],
)
def test_advance_run_invalid_controls_fail_without_traceback(
    tmp_path: Path, filename: str, contents: bytes, message: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    (run / filename).write_bytes(contents)

    completed = run_advance(
        run, "--work-package-root", str(package_root)
    )

    assert completed.returncode == 1
    assert f"ERROR: {message}" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr

@pytest.mark.parametrize(
    ("case", "contents", "message"),
    [
        ("missing", None, "waves.json: invalid JSON"),
        ("non-utf8", bytes([0xFF]), "waves.json: invalid JSON"),
        ("malformed", b"{", "waves.json: invalid JSON"),
        (
            "invalid-structure",
            json.dumps({"waves": [{"id": "wave1_source_extraction"}]}).encode(),
            "waves.json: invalid structure",
        ),
    ],
)
def test_advance_run_invalid_waves_fail_without_traceback(
    tmp_path: Path, case: str, contents: bytes | None, message: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    package_copy = tmp_path / "plugin"
    orchestration = package_copy / "orchestration"
    orchestration.mkdir(parents=True)
    if contents is not None:
        (orchestration / "waves.json").write_bytes(contents)

    completed = run_advance(
        run,
        "--work-package-root",
        str(package_root),
        "--package",
        str(package_copy),
    )

    assert completed.returncode == 1
    assert f"ERROR: {message}" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr

@pytest.mark.parametrize("case", ["run-state", "inventory", "task", "handoff"])
def test_advance_run_enforces_control_datetime_formats_without_traceback(
    tmp_path: Path, case: str
) -> None:
    package = application_package()
    run, package_root, task, _ = write_run(tmp_path, package)
    message = invalidate_control_datetime(run, task["task_id"], case)

    completed = run_advance(
        run, "--work-package-root", str(package_root)
    )

    assert completed.returncode == 1
    assert f"ERROR: {message}" in completed.stdout
    assert "Traceback" not in completed.stdout + completed.stderr


def test_advance_run_legacy_dry_run_still_needs_no_package_root(
    tmp_path: Path,
) -> None:
    task = candidate_task()
    run = write_task_only_run(tmp_path, json.dumps(task))
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(legacy_handoff(task)), encoding="utf-8"
    )

    completed = run_advance(run)

    assert completed.returncode == 0
    assert json.loads(completed.stdout)["completed_wave"] == "wave1_source_extraction"


def test_legacy_conflict_ids_keep_base_namespace_only_behavior(
    tmp_path: Path,
) -> None:
    task = candidate_task()
    run = write_task_only_run(tmp_path, json.dumps(task))
    handoff = legacy_handoff(task)
    handoff["conflict_ids"] = ["SYN-CONFLICT-001"]
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )
    package_root = tmp_path / "collaboration" / "work-packages"
    package_root.mkdir(parents=True)
    write_conflict(package_root, conflict_record())

    errors, _, _ = validate_run_handoffs(
        run, work_package_root=package_root
    )
    cli = run_handoff_validation(
        run, "--work-package-root", str(package_root)
    )
    advance = run_advance(
        run, "--work-package-root", str(package_root)
    )

    assert errors == []
    assert cli.returncode == 0
    assert advance.returncode == 0


def test_low_legacy_and_package_open_conflicts_use_different_policies(
    tmp_path: Path,
) -> None:
    legacy_task = candidate_task()
    legacy_run = write_task_only_run(
        tmp_path / "legacy", json.dumps(legacy_task)
    )
    legacy_handoff_record = legacy_handoff(legacy_task)
    legacy_handoff_record["conflict_ids"] = ["SYN-CONFLICT-LOW"]
    (legacy_run / "handoffs" / f"{legacy_task['task_id']}.json").write_text(
        json.dumps(legacy_handoff_record), encoding="utf-8"
    )
    legacy_package_root = tmp_path / "legacy-controls" / "work-packages"
    legacy_package_root.mkdir(parents=True)
    legacy_conflict = conflict_record(conflict_id="SYN-CONFLICT-LOW")
    legacy_conflict["severity"] = "LOW"
    write_conflict(legacy_package_root, legacy_conflict)

    package = application_package()
    collaboration_run, package_root, _, _ = write_run(
        tmp_path / "collaboration", package
    )
    package_conflict = conflict_record(
        conflict_id="SYN-CONFLICT-PACKAGE",
        reported_by_task=None,
        reported_by_work_package=package["package_id"],
    )
    package_conflict["severity"] = "LOW"
    write_conflict(package_root, package_conflict)

    legacy_errors, _, _ = validate_run_handoffs(
        legacy_run,
        wave="gate6_publish_phase6",
        work_package_root=legacy_package_root,
        publication_phase=6,
    )
    collaboration_errors, _, _ = validate_run_handoffs(
        collaboration_run, work_package_root=package_root
    )

    assert not any("open conflict SYN-CONFLICT-LOW" in error for error in legacy_errors)
    assert (
        "WP_SYN_SQL: open conflict SYN-CONFLICT-PACKAGE"
        in collaboration_errors
    )


@pytest.mark.parametrize("severity", ["HIGH", "CRITICAL"])
def test_legacy_high_severity_conflict_blocks_phase6_gate_for_earlier_task(
    tmp_path: Path, severity: str
) -> None:
    task = candidate_task()
    run = write_task_only_run(tmp_path, json.dumps(task))
    handoff = legacy_handoff(task)
    handoff["conflict_ids"] = ["SYN-CONFLICT-PHASE6"]
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )
    package_root = tmp_path / "collaboration" / "work-packages"
    package_root.mkdir(parents=True)
    record = conflict_record(conflict_id="SYN-CONFLICT-PHASE6")
    record["severity"] = severity
    write_conflict(package_root, record)

    errors, _, _ = validate_run_handoffs(
        run,
        wave="gate6_publish_phase6",
        work_package_root=package_root,
        publication_phase=6,
    )

    assert "SYN-W1-SQL-ORDERS: open conflict SYN-CONFLICT-PHASE6" in errors


def test_legacy_phase6_conflict_does_not_block_whole_run_validation(
    tmp_path: Path,
) -> None:
    task = candidate_task()
    task["wave_id"] = "gate6_publish_phase6"
    task["phase_targets"] = [6]
    run = write_task_only_run(tmp_path, json.dumps(task))
    handoff = legacy_handoff(task)
    handoff["conflict_ids"] = ["SYN-CONFLICT-PHASE6"]
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )
    package_root = tmp_path / "collaboration" / "work-packages"
    package_root.mkdir(parents=True)
    record = conflict_record(conflict_id="SYN-CONFLICT-PHASE6")
    record["severity"] = "HIGH"
    write_conflict(package_root, record)

    errors, _, _ = validate_run_handoffs(
        run, work_package_root=package_root
    )

    assert not any(
        "open conflict SYN-CONFLICT-PHASE6" in error for error in errors
    )


def test_legacy_conflict_id_still_requires_app_namespace(tmp_path: Path) -> None:
    task = candidate_task()
    run = write_task_only_run(tmp_path, json.dumps(task))
    handoff = legacy_handoff(task)
    handoff["conflict_ids"] = ["OTHER-CONFLICT-001"]
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )

    errors, _, _ = validate_run_handoffs(run)
    cli = run_handoff_validation(run)

    message = (
        "SYN-W1-SQL-ORDERS: conflict id outside app namespace: "
        "OTHER-CONFLICT-001"
    )
    assert message in errors
    assert cli.returncode == 1
    assert f"ERROR: {message}" in cli.stdout


def test_referenced_open_conflict_blocks_function_cli_and_advance(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, task, handoff = write_run(tmp_path, package)
    record = conflict_record()
    write_conflict(package_root, record)
    handoff["conflict_ids"] = [record["conflict_id"]]
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    cli = run_handoff_validation(
        run, "--work-package-root", str(package_root)
    )
    advance = run_advance(
        run, "--work-package-root", str(package_root)
    )

    assert "SYN-W1-SQL-ORDERS: open conflict SYN-CONFLICT-001" in errors
    assert cli.returncode == 1
    assert "open conflict SYN-CONFLICT-001" in cli.stdout
    assert advance.returncode == 1
    assert "open conflict SYN-CONFLICT-001" in advance.stdout

def test_unreferenced_relevant_open_conflict_blocks_package(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    write_conflict(
        package_root,
        conflict_record(
            reported_by_task=None,
            reported_by_work_package=package["package_id"],
        ),
    )

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert "WP_SYN_SQL: open conflict SYN-CONFLICT-001" in errors

@pytest.mark.parametrize(
    "status", ["RESOLVED", "ACCEPTED_RISK", "OUT_OF_SCOPE"]
)
def test_closed_conflict_statuses_do_not_block(
    tmp_path: Path, status: str
) -> None:
    package = application_package()
    run, package_root, task, handoff = write_run(tmp_path, package)
    record = conflict_record(status=status)
    write_conflict(package_root, record)
    handoff["conflict_ids"] = [record["conflict_id"]]
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )

    assert validate_run_handoffs(run, work_package_root=package_root) == (
        [],
        1,
        0,
    )


@pytest.mark.parametrize(
    ("case", "expected"),
    [
        ("open_resolution", "invalid conflict schema"),
        ("missing_resolution", "invalid conflict schema"),
        ("blank_resolution", "invalid conflict schema"),
        ("missing_decision_source", "invalid conflict schema"),
        ("blank_decision_source", "invalid conflict schema"),
        ("missing_resolved_at", "invalid conflict schema"),
        ("missing_resolver", "invalid conflict schema"),
        ("both_resolvers", "invalid conflict schema"),
        ("unknown_resolver", "unknown resolved_by_task SYN-W1-SQL-UNKNOWN"),
    ],
)
def test_conflict_resolution_evidence_fails_closed(
    tmp_path: Path, case: str, expected: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    record = conflict_record(status="RESOLVED")
    if case == "open_resolution":
        record = conflict_record()
        record["resolution"] = "Not allowed while open."
    elif case == "missing_resolution":
        del record["resolution"]
    elif case == "blank_resolution":
        record["resolution"] = " "
    elif case == "missing_decision_source":
        del record["decision_source"]
    elif case == "blank_decision_source":
        record["decision_source"] = " "
    elif case == "missing_resolved_at":
        record["resolved_at"] = None
    elif case == "missing_resolver":
        del record["resolved_by_task"]
    elif case == "both_resolvers":
        record["resolved_by_work_package"] = package["package_id"]
    elif case == "unknown_resolver":
        record["resolved_by_task"] = "SYN-W1-SQL-UNKNOWN"
    else:
        raise AssertionError(case)
    write_conflict(package_root, record)

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert any(expected in error for error in errors)


def test_closed_conflict_resolution_must_not_predate_creation(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    record = conflict_record(status="RESOLVED")
    record["created_at"] = "2026-07-28T00:50:00Z"
    record["resolved_at"] = "2026-07-28T00:40:00Z"
    write_conflict(package_root, record)

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert any(
        "SYN-CONFLICT-001.json: resolved_at predates created_at" in error
        for error in errors
    )


@pytest.mark.parametrize(
    ("status", "field"),
    [
        ("OPEN", "reported_by_task"),
        ("RESOLVED", "resolved_by_task"),
    ],
)
@pytest.mark.parametrize("value", [" SYN-W1-SQL-ORDERS", "SYN-W1-SQL-ORDERS "])
def test_conflict_identity_whitespace_fails_closed(
    tmp_path: Path, status: str, field: str, value: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    record = conflict_record(status=status)
    record[field] = value
    write_conflict(package_root, record)

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert any("invalid conflict schema" in error for error in errors)

def test_unknown_handoff_conflict_id_is_invalid(tmp_path: Path) -> None:
    package = application_package()
    run, package_root, task, handoff = write_run(tmp_path, package)
    handoff["conflict_ids"] = ["SYN-CONFLICT-UNKNOWN"]
    (run / "handoffs" / f"{task['task_id']}.json").write_text(
        json.dumps(handoff), encoding="utf-8"
    )

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert "SYN-W1-SQL-ORDERS: unknown conflict id SYN-CONFLICT-UNKNOWN" in errors

def test_handoff_conflict_must_match_its_task_or_package(
    tmp_path: Path,
) -> None:
    package = application_package()
    run, package_root = write_multi_task_run(
        tmp_path,
        package,
        [
            (
                "SYN-W1-SQL-FIRST",
                "work/sql_data/module-orders",
                [],
                "COMPLETED",
            ),
            (
                "SYN-W1-SQL-SECOND",
                "work/sql_data/module-orders",
                [package["expected_artifacts"][0]["path"]],
                "COMPLETED",
            ),
        ],
    )
    record = conflict_record(
        status="RESOLVED", reported_by_task="SYN-W1-SQL-FIRST"
    )
    write_conflict(package_root, record)
    second_path = run / "handoffs" / "SYN-W1-SQL-SECOND.json"
    second = json.loads(second_path.read_text(encoding="utf-8"))
    second["conflict_ids"] = [record["conflict_id"]]
    second_path.write_text(json.dumps(second), encoding="utf-8")

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert (
        "SYN-W1-SQL-SECOND: conflict SYN-CONFLICT-001 "
        "does not match task/package"
    ) in errors

@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("nested", "conflicts/nested/extra.json: invalid conflict control entry"),
        ("misc", "conflicts/notes.txt: invalid conflict control entry"),
        ("non-utf8", "extra.json: invalid conflict JSON"),
        ("malformed", "extra.json: invalid conflict JSON"),
        ("schema", "extra.json: invalid conflict schema"),
        ("datetime", "extra.json: invalid conflict schema"),
        ("filename", "wrong.json: filename does not match conflict_id SYN-CONFLICT-001"),
        (
            "duplicate",
            "duplicate conflict id SYN-CONFLICT-001: SYN-CONFLICT-001.json, duplicate.json",
        ),
    ],
)
def test_conflict_inventory_is_closed_and_deterministic(
    tmp_path: Path, case: str, message: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    record = conflict_record(status="RESOLVED")
    canonical = write_conflict(package_root, record)
    conflicts = canonical.parent
    if case == "nested":
        nested = conflicts / "nested"
        nested.mkdir()
        (nested / "extra.json").write_text("{}", encoding="utf-8")
    elif case == "misc":
        (conflicts / "notes.txt").write_text("note", encoding="utf-8")
    elif case == "non-utf8":
        (conflicts / "extra.json").write_bytes(bytes([0xFF]))
    elif case == "malformed":
        (conflicts / "extra.json").write_text("{", encoding="utf-8")
    elif case == "schema":
        (conflicts / "extra.json").write_text("{}", encoding="utf-8")
    elif case == "datetime":
        invalid = conflict_record(
            conflict_id="SYN-CONFLICT-DATETIME", status="RESOLVED"
        )
        invalid["created_at"] = "not-a-date"
        write_conflict(package_root, invalid, "extra.json")
    elif case == "filename":
        canonical.rename(conflicts / "wrong.json")
    elif case == "duplicate":
        (conflicts / "duplicate.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
    else:
        raise AssertionError(case)

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)
    cli = run_handoff_validation(
        run, "--work-package-root", str(package_root)
    )

    assert any(message in error for error in errors)
    assert cli.returncode == 1
    assert message in cli.stdout
    assert "Traceback" not in cli.stdout + cli.stderr

@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"run_id": "OTHER-RUN"}, "run_id mismatch"),
        ({"app_id": "OTHER"}, "app_id mismatch"),
        ({"reported_by_task": "SYN-UNKNOWN"}, "unknown reported_by_task"),
        (
            {"reported_by_task": None, "reported_by_work_package": "WP_UNKNOWN"},
            "unknown reported_by_work_package",
        ),
    ],
)
def test_stale_conflict_records_block_globally(
    tmp_path: Path, change: dict, message: str
) -> None:
    package = application_package()
    run, package_root, _, _ = write_run(tmp_path, package)
    record = conflict_record(status="RESOLVED")
    for field, value in change.items():
        if value is None:
            record.pop(field, None)
        else:
            record[field] = value
    write_conflict(package_root, record)

    errors, _, _ = validate_run_handoffs(run, work_package_root=package_root)

    assert any(message in error for error in errors)
