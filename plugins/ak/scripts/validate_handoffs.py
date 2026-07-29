#!/usr/bin/env python3
"""Validate handoffs against task envelopes, source inventory, and write scopes."""

from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path, PurePosixPath
import sys

import jsonschema

PACKAGE = Path(__file__).resolve().parents[1]
CONTRACTS = PACKAGE / "contracts"
if str(CONTRACTS) not in sys.path:
    sys.path.insert(0, str(CONTRACTS))

from collaboration import (
    CollaborationError,
    _inside_any,
    _schema,
    _task_logical_path,
    load_work_package,
    project_task,
    work_package_digest,
)
from review import _parse_date_time, artifact_set_digest, validate_review_receipt


REQUIRED_HANDOFF_FIELDS = {
    "task_id", "run_id", "app_id", "role", "status", "summary", "artifacts",
    "evidence_ids", "gaps", "conflict_ids", "source_files_read", "completed_at",
}
PROJECTION_FIELDS = {"work_package_id", "work_package_digest", "projection_version"}
HANDOFF_COLLABORATION_FIELDS = {
    "work_package_id", "work_package_digest", "produced_revision",
    "validation_results", "review_receipt_required",
}
FORBIDDEN_SOURCE_CHARACTERS = {"<", ">", '"', "|", "?", "*", ":", "\\"}
LEGACY_BLOCKING_CONFLICT_SEVERITIES = {"HIGH", "CRITICAL"}
CONTROL_FORMAT_CHECKER = jsonschema.FormatChecker()

@CONTROL_FORMAT_CHECKER.checks("date-time")
def _is_date_time(value: object) -> bool:
    if not isinstance(value, str) or "T" not in value.upper():
        return False
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(normalized).tzinfo is not None
    except ValueError:
        return False

def _latest_date_time(values: list[str]) -> str | None:
    return max(values, key=_parse_date_time, default=None)

def _inventory_paths(inventory: dict, errors: list[str]) -> set[str]:
    grouped: dict[str, list[str]] = {}
    canonical: set[str] = set()
    for section in ("files", "ignored"):
        for item in inventory[section]:
            relative = item["relative_path"]
            normalized = relative.replace("\\", "/")
            grouped.setdefault(normalized.casefold(), []).append(relative)
            try:
                logical = _task_logical_path(
                    relative, allow_parent_prefix=False
                )
            except CollaborationError:
                errors.append(
                    f"source-inventory.json: invalid portable path: {relative}"
                )
                continue
            canonical.add(logical)
    for paths in grouped.values():
        if len(paths) > 1:
            errors.append(
                "source-inventory.json: casefold path collision: "
                + ", ".join(sorted(paths))
            )
    return canonical

def _legacy_conflict_blocks(
    conflict: dict, wave: str | None, publication_phase: int | None
) -> bool:
    return bool(
        (wave == "gate6_publish_phase6" or publication_phase == 6)
        and conflict["severity"] in LEGACY_BLOCKING_CONFLICT_SEVERITIES
    )

def _validator(schema_name: str) -> jsonschema.Draft202012Validator:
    return jsonschema.Draft202012Validator(
        _schema(schema_name), format_checker=CONTROL_FORMAT_CHECKER
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--wave")
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--work-package-root")
    parser.add_argument("--publication-phase", type=int, choices=range(1, 7))
    return parser.parse_args()


def inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def in_write_scope(
    relative: str, write_paths: list[str], *, portable_casefold: bool = False
) -> bool:
    normalized = relative.replace("\\", "/")
    candidate = PurePosixPath(
        normalized.casefold() if portable_casefold else normalized
    )
    if candidate.is_absolute() or ".." in candidate.parts:
        return False
    for declared in write_paths:
        normalized = declared.replace("\\", "/")
        allowed = PurePosixPath(
            normalized.casefold() if portable_casefold else normalized
        )
        if candidate == allowed or allowed in candidate.parents:
            return True
    return False


def load_run_control(
    run: Path,
    filename: str,
    schema_name: str,
    errors: list[str],
) -> dict | None:
    try:
        value = json.loads((run / filename).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        errors.append(f"{filename}: invalid JSON")
        return None
    try:
        _validator(schema_name).validate(value)
    except jsonschema.ValidationError:
        errors.append(f"{filename}: invalid schema")
        return None
    return value


def load_projected_package(
    task_id: str,
    task: dict,
    work_package_root: Path | None,
    errors: list[str],
) -> dict | None:
    if work_package_root is None:
        errors.append(f"{task_id}: work package root required")
        return None

    root = Path(work_package_root).expanduser().resolve()
    package_path = root / task["work_package_id"] / "work-package.json"
    if not inside(root, package_path):
        errors.append(f"{task_id}: invalid work package id")
        return None
    if not package_path.is_file():
        errors.append(f"{task_id}: work package file missing")
        return None
    try:
        package = load_work_package(package_path)
    except (
        CollaborationError,
        json.JSONDecodeError,
        OSError,
        TypeError,
        UnicodeError,
    ):
        errors.append(f"{task_id}: invalid work package")
        return None

    if package["package_id"] != task["work_package_id"]:
        errors.append(f"{task_id}: task work package id mismatch")
        valid_binding = False
    else:
        valid_binding = True
    if work_package_digest(package) != task["work_package_digest"]:
        errors.append(f"{task_id}: task work package digest mismatch")
        valid_binding = False
    if not valid_binding:
        return None
    try:
        project_task(package, task)
    except CollaborationError as exc:
        errors.append(f"{task_id}: invalid task projection: {exc}")
        return None
    return package


def load_handoff_inventory(
    run: Path,
    known_task_ids: set[str],
    errors: list[str],
) -> dict[str, dict]:
    grouped: dict[str, list[tuple[str, dict]]] = {}
    handoff_validator = _validator("handoff.schema.json")
    root = run / "handoffs"
    paths = sorted(
        root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()
    )
    for path in paths:
        relative = path.relative_to(root).as_posix()
        if path.parent != root or not path.is_file() or path.suffix != ".json":
            errors.append(
                f"handoffs/{relative}: invalid handoff control entry"
            )
            continue
        try:
            handoff = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append(f"{relative}: invalid handoff JSON")
            continue
        try:
            handoff_validator.validate(handoff)
        except jsonschema.ValidationError as exc:
            errors.append(
                f"{relative}: invalid handoff schema: {exc.message}"
            )
            continue
        grouped.setdefault(handoff["task_id"], []).append((relative, handoff))

    handoffs: dict[str, dict] = {}
    for task_id in sorted(grouped):
        records = grouped[task_id]
        if len(records) != 1:
            filenames = ", ".join(sorted(name for name, _ in records))
            errors.append(f"duplicate handoff id {task_id}: {filenames}")
            continue
        filename, handoff = records[0]
        if task_id not in known_task_ids:
            errors.append(f"{filename}: unknown task id {task_id}")
            continue
        if filename != f"{task_id}.json":
            errors.append(
                f"{filename}: filename does not match task_id {task_id}"
            )
            continue
        handoffs[task_id] = handoff
    return handoffs


def load_review_inventory(
    work_package_root: Path | None,
    known_package_ids: set[str],
    errors: list[str],
) -> list[dict]:
    if work_package_root is None:
        return []
    root = work_package_root.expanduser().resolve().parent / "reviews"
    if not root.exists():
        return []
    if not root.is_dir():
        errors.append("reviews: invalid review control entry")
        return []
    grouped: dict[str, list[tuple[str, dict]]] = {}
    validator = _validator("review-receipt.schema.json")
    for path in sorted(
        root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
    ):
        relative = path.relative_to(root).as_posix()
        if path.parent != root or not path.is_file() or path.suffix != ".json":
            errors.append(f"reviews/{relative}: invalid review control entry")
            continue
        try:
            receipt = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append(f"{relative}: invalid review JSON")
            continue
        try:
            validator.validate(receipt)
        except jsonschema.ValidationError as exc:
            errors.append(f"{relative}: invalid review schema: {exc.message}")
            continue
        grouped.setdefault(receipt["receipt_id"], []).append((relative, receipt))

    receipts: list[dict] = []
    for receipt_id in sorted(grouped):
        records = grouped[receipt_id]
        if len(records) != 1:
            filenames = ", ".join(sorted(name for name, _ in records))
            errors.append(
                f"duplicate review receipt id {receipt_id}: {filenames}"
            )
            continue
        filename, receipt = records[0]
        if receipt["work_package_id"] not in known_package_ids:
            errors.append(
                f"{filename}: unknown work package id {receipt['work_package_id']}"
            )
            continue
        if filename != f"{receipt_id}.json":
            errors.append(
                f"{filename}: filename does not match receipt_id {receipt_id}"
            )
            continue
        receipts.append(receipt)
    return receipts

def load_conflict_inventory(
    work_package_root: Path | None,
    known_task_ids: set[str],
    known_package_ids: set[str],
    state: dict,
    errors: list[str],
) -> dict[str, dict]:
    if work_package_root is None:
        return {}
    root = work_package_root.expanduser().resolve().parent / "conflicts"
    if not root.exists():
        return {}
    if not root.is_dir():
        errors.append("conflicts: invalid conflict control entry")
        return {}
    grouped: dict[str, list[tuple[str, dict]]] = {}
    validator = _validator("conflict.schema.json")
    for path in sorted(
        root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
    ):
        relative = path.relative_to(root).as_posix()
        if path.parent != root or not path.is_file() or path.suffix != ".json":
            errors.append(f"conflicts/{relative}: invalid conflict control entry")
            continue
        try:
            conflict = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append(f"{relative}: invalid conflict JSON")
            continue
        try:
            validator.validate(conflict)
        except jsonschema.ValidationError as exc:
            errors.append(f"{relative}: invalid conflict schema: {exc.message}")
            continue
        if (
            conflict["status"] != "OPEN"
            and _parse_date_time(conflict["resolved_at"])
            < _parse_date_time(conflict["created_at"])
        ):
            errors.append(f"{relative}: resolved_at predates created_at")
            continue
        grouped.setdefault(conflict["conflict_id"], []).append(
            (relative, conflict)
        )

    conflicts: dict[str, dict] = {}
    for conflict_id in sorted(grouped):
        records = grouped[conflict_id]
        if len(records) != 1:
            filenames = ", ".join(sorted(name for name, _ in records))
            errors.append(f"duplicate conflict id {conflict_id}: {filenames}")
            continue
        filename, conflict = records[0]
        if filename != f"{conflict_id}.json":
            errors.append(
                f"{filename}: filename does not match conflict_id {conflict_id}"
            )
            continue
        valid = True
        for field in ("run_id", "app_id"):
            if conflict[field] != state[field]:
                errors.append(f"{filename}: {field} mismatch")
                valid = False
        reported_task = conflict.get("reported_by_task")
        reported_package = conflict.get("reported_by_work_package")
        reported_task = reported_task.strip() if reported_task is not None else None
        reported_package = (
            reported_package.strip() if reported_package is not None else None
        )
        if reported_task is not None and reported_task not in known_task_ids:
            errors.append(
                f"{filename}: unknown reported_by_task {reported_task}"
            )
            valid = False
        if (
            reported_package is not None
            and reported_package not in known_package_ids
        ):
            errors.append(
                f"{filename}: unknown reported_by_work_package "
                f"{reported_package}"
            )
            valid = False
        resolved_task = conflict.get("resolved_by_task")
        resolved_package = conflict.get("resolved_by_work_package")
        resolved_task = resolved_task.strip() if resolved_task is not None else None
        resolved_package = (
            resolved_package.strip() if resolved_package is not None else None
        )
        if resolved_task is not None and resolved_task not in known_task_ids:
            errors.append(
                f"{filename}: unknown resolved_by_task {resolved_task}"
            )
            valid = False
        if (
            resolved_package is not None
            and resolved_package not in known_package_ids
        ):
            errors.append(
                f"{filename}: unknown resolved_by_work_package "
                f"{resolved_package}"
            )
            valid = False
        if valid:
            conflicts[conflict_id] = conflict
    return conflicts


def validate_run_handoffs(
    run: Path,
    wave: str | None = None,
    require_complete: bool = False,
    work_package_root: Path | None = None,
    publication_phase: int | None = None,
) -> tuple[list[str], int, int]:
    run = run.expanduser().resolve()
    errors: list[str] = []
    state = load_run_control(
        run, "run-state.json", "run-state.schema.json", errors
    )
    inventory = load_run_control(
        run, "source-inventory.json", "source-inventory.schema.json", errors
    )
    if state is None or inventory is None:
        return errors, 0, 0
    if inventory["app_id"] != state["app_id"]:
        return ["source-inventory.json: app_id mismatch"], 0, 0
    task_files: dict[str, list[tuple[str, dict]]] = {}
    declared_task_ids: set[str] = set()
    task_validator = _validator("task.schema.json")
    for path in sorted((run / "tasks").glob("*.json")):
        try:
            task = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            errors.append(f"{path.name}: invalid task JSON")
            continue
        if isinstance(task, dict) and isinstance(task.get("task_id"), str):
            declared_task_ids.add(task["task_id"])
        try:
            task_validator.validate(task)
        except jsonschema.ValidationError as exc:
            errors.append(f"{path.name}: invalid task schema: {exc.message}")
            continue
        identity_mismatch = False
        for field in ("run_id", "app_id"):
            if task[field] != state[field]:
                errors.append(f"{path.name}: {field} mismatch")
                identity_mismatch = True
        if identity_mismatch:
            continue
        task_files.setdefault(task["task_id"], []).append((path.name, task))

    all_tasks: dict[str, dict] = {}
    tasks: dict[str, dict] = {}
    for task_id in sorted(task_files):
        records = task_files[task_id]
        if len(records) != 1:
            filenames = ", ".join(sorted(name for name, _ in records))
            errors.append(f"duplicate task id {task_id}: {filenames}")
            continue
        task = records[0][1]
        all_tasks[task_id] = task
        if not wave or task["wave_id"] == wave:
            tasks[task_id] = task

    known_package_ids = {
        task["work_package_id"]
        for task in all_tasks.values()
        if PROJECTION_FIELDS <= set(task)
    }
    receipts = load_review_inventory(work_package_root, known_package_ids, errors)
    handoffs = load_handoff_inventory(run, declared_task_ids, errors)
    inventory_paths = _inventory_paths(inventory, errors)
    task_packages: dict[str, dict] = {}
    packages_by_id: dict[str, dict] = {}
    for task_id, task in all_tasks.items():
        if PROJECTION_FIELDS <= set(task):
            package = load_projected_package(
                task_id, task, work_package_root, errors
            )
            if package is not None:
                task_packages[task_id] = package
                packages_by_id[package["package_id"]] = package
    conflicts = load_conflict_inventory(
        work_package_root,
        set(all_tasks),
        set(packages_by_id),
        state,
        errors,
    )
    checked = 0
    completed_records: list[dict] = []
    collaboration_package_ids: set[str] = set()
    package_agents: dict[str, set[str]] = {}
    for task_id, task in all_tasks.items():
        selected = task_id in tasks
        handoff = handoffs.get(task_id)
        if handoff is None:
            if selected and require_complete:
                errors.append(f"Missing handoff: {task_id}")
            continue
        if selected:
            checked += 1
        task_mode = (
            "collaboration" if PROJECTION_FIELDS <= set(task) else "legacy"
        )
        handoff_mode = (
            "collaboration"
            if HANDOFF_COLLABORATION_FIELDS <= set(handoff)
            else "legacy"
        )
        if task_mode != handoff_mode:
            errors.append(
                f"{task_id}: collaboration mode mismatch: "
                f"task={task_mode} handoff={handoff_mode}"
            )
            continue
        handoff_error_start = len(errors)
        if handoff_mode == "collaboration":
            validation_commands: set[str] = set()
            for result in handoff["validation_results"]:
                command = result["command"]
                if command in validation_commands:
                    errors.append(
                        f"{task_id}: duplicate validation result: {command}"
                    )
                validation_commands.add(command)
                expected = "PASS" if result["exit_code"] == 0 else "FAIL"
                if result["result"] != expected:
                    errors.append(
                        f"{task_id}: inconsistent validation result: {command}"
                    )
        missing = REQUIRED_HANDOFF_FIELDS - set(handoff)
        if missing:
            errors.append(f"{task_id}: missing fields {sorted(missing)}")
            continue
        package = None
        if task_mode == "collaboration":
            package = task_packages.get(task_id)
            if package is None:
                continue
            collaboration_package_ids.add(package["package_id"])
            package_agents.setdefault(package["package_id"], set()).add(
                handoff["agent_id"].strip()
            )
        for field in ("task_id", "run_id", "app_id", "role"):
            expected = task[field] if field in task else state[field]
            if handoff[field] != expected:
                errors.append(f"{task_id}: {field} mismatch")
        if handoff["status"] not in {"COMPLETED", "FAILED", "BLOCKED"}:
            errors.append(f"{task_id}: invalid status {handoff['status']}")
        if selected and require_complete and handoff["status"] != "COMPLETED":
            errors.append(
                f"{task_id}: handoff status is {handoff['status']!r}"
            )
        logical_artifacts: list[str] = []
        artifact_identities: set[str] = set()
        for artifact in handoff["artifacts"]:
            try:
                logical_artifact = _task_logical_path(
                    artifact, allow_parent_prefix=False
                )
            except CollaborationError:
                errors.append(f"{task_id}: invalid artifact path: {artifact!r}")
                continue
            identity = logical_artifact.casefold()
            if identity in artifact_identities:
                errors.append(f"{task_id}: duplicate artifact entry: {artifact}")
                continue
            artifact_identities.add(identity)
            artifact_path = run / logical_artifact
            artifact_valid = (
                artifact_path.is_file()
                if task_mode == "collaboration"
                else artifact_path.exists()
            )
            if not inside(run, artifact_path):
                errors.append(
                    f"{task_id}: artifact escapes run directory: {artifact}"
                )
            elif not in_write_scope(
                logical_artifact,
                task["write_paths"],
                portable_casefold=task_mode == "collaboration",
            ):
                errors.append(
                    f"{task_id}: artifact outside declared write_paths: {artifact}"
                )
            elif (
                task_mode == "collaboration"
                and artifact_path.exists()
                and not artifact_valid
            ):
                errors.append(
                    f"{task_id}: artifact is not a regular file: {artifact}"
                )
            elif handoff["status"] == "COMPLETED" and not artifact_valid:
                description = (
                    "artifact missing"
                    if task_mode == "collaboration"
                    else "completed artifact missing"
                )
                errors.append(f"{task_id}: {description}: {artifact}")
            elif artifact_valid:
                logical_artifacts.append(logical_artifact)
        if package is not None:
            if handoff["work_package_id"] != package["package_id"]:
                errors.append(f"{task_id}: work package id mismatch")
            if handoff["work_package_digest"] != work_package_digest(package):
                errors.append(f"{task_id}: work package digest mismatch")
            if handoff["status"] == "COMPLETED":
                for command in package["validation_commands"]:
                    matches = [
                        result
                        for result in handoff["validation_results"]
                        if result["command"] == command
                    ]
                    if (
                        len(matches) != 1
                        or matches[0]["exit_code"] != 0
                        or matches[0]["result"] != "PASS"
                    ):
                        errors.append(
                            f"{task_id}: required validation failed: {command}"
                        )
            authority_kind = package["authority"]["kind"]
            produced_revision = handoff["produced_revision"]
            if (
                handoff["status"] == "COMPLETED"
                and authority_kind in {"repository_revision", "mixed"}
                and (
                    not isinstance(produced_revision, str)
                    or not produced_revision.strip()
                )
            ):
                errors.append(f"{task_id}: produced revision required")
            if authority_kind == "approved_bundle" and produced_revision is not None:
                errors.append(f"{task_id}: produced revision must be null")
        namespace = task["evidence_namespace"]
        if namespace is None:
            for evidence_id in handoff["evidence_ids"]:
                errors.append(f"{task_id}: evidence id without namespace: {evidence_id}")
        else:
            prefix = namespace + "-"
            for evidence_id in handoff["evidence_ids"]:
                if not evidence_id.startswith(prefix):
                    errors.append(f"{task_id}: evidence id outside namespace: {evidence_id}")
        for conflict_id in handoff["conflict_ids"]:
            if not conflict_id.startswith(f"{state['app_id']}-CONFLICT-"):
                errors.append(f"{task_id}: conflict id outside app namespace: {conflict_id}")
            if package is None:
                continue
            conflict = conflicts.get(conflict_id)
            if conflict is None:
                errors.append(f"{task_id}: unknown conflict id {conflict_id}")
                continue
            matches_task = conflict.get("reported_by_task") == task_id
            matches_package = (
                package is not None
                and conflict.get("reported_by_work_package")
                == package["package_id"]
            )
            if not matches_task and not matches_package:
                errors.append(
                    f"{task_id}: conflict {conflict_id} does not match task/package"
                )
        task_input_scope = None
        if package is not None:
            task_input_scope = [
                _task_logical_path(path, allow_parent_prefix=True)
                for path in task["input_paths"]
            ]
        for source in handoff["source_files_read"]:
            if any(
                ord(character) < 32
                or ord(character) == 127
                or character in FORBIDDEN_SOURCE_CHARACTERS
                for character in source
            ):
                errors.append(
                    f"{task_id}: invalid canonical source path: {source!r}"
                )
                continue
            normalized = source.replace("\\", "/")
            if Path(source).is_absolute() or ".." in Path(source).parts:
                errors.append(f"{task_id}: source path must be app-relative: {source}")
            elif normalized not in inventory_paths:
                errors.append(f"{task_id}: source is absent from immutable inventory: {source}")
            elif task_input_scope is not None:
                try:
                    in_scope = _inside_any(
                        normalized, task_input_scope, allow_parent_prefix=False
                    )
                except CollaborationError:
                    errors.append(
                        f"{task_id}: invalid canonical source path: {source!r}"
                    )
                    continue
                if not in_scope:
                    errors.append(
                        f"{task_id}: source outside task input scope: {source}"
                    )
        if package is not None and handoff["status"] == "COMPLETED":
            record = {
                "task_id": task_id,
                "package": package,
                "artifacts": logical_artifacts,
                "produced_revision": handoff["produced_revision"],
                "completed_at": handoff["completed_at"],
                "phase_targets": task["phase_targets"],
                "review_receipt_required": handoff["review_receipt_required"],
                "receipt_eligible": len(errors) == handoff_error_start,
            }
            completed_records.append(record)

    if publication_phase is not None:
        for task_id, task in sorted(all_tasks.items()):
            if (
                task_id not in task_packages
                or publication_phase not in task["phase_targets"]
            ):
                continue
            handoff = handoffs.get(task_id)
            if handoff is None:
                message = f"Missing handoff: {task_id}"
            elif handoff["status"] != "COMPLETED":
                message = f"{task_id}: handoff status is {handoff['status']!r}"
            else:
                continue
            if message not in errors:
                errors.append(message)

    for conflict_id, conflict in sorted(conflicts.items()):
        if conflict["status"] != "OPEN":
            continue
        reporter = conflict.get("reported_by_task")
        reported_package = conflict.get("reported_by_work_package")
        collaboration_conflict = (
            reporter in task_packages or reported_package in packages_by_id
        )
        if collaboration_conflict:
            blocker = reporter if reporter is not None else reported_package
        elif _legacy_conflict_blocks(conflict, wave, publication_phase):
            blocker = reporter
        else:
            continue
        errors.append(f"{blocker}: open conflict {conflict_id}")

    records_by_package: dict[str, list[dict]] = {}
    for record in completed_records:
        package_id = record["package"]["package_id"]
        records_by_package.setdefault(package_id, []).append(record)
    for package_id in sorted(collaboration_package_ids):
        package = packages_by_id[package_id]
        reported: dict[str, list[tuple[str, str]]] = {}
        for record in records_by_package.get(package_id, []):
            for artifact in record["artifacts"]:
                reported.setdefault(artifact.casefold(), []).append(
                    (record["task_id"], artifact)
                )
        expected_by_identity = {
            artifact["path"].casefold(): artifact
            for artifact in package["expected_artifacts"]
        }
        for identity, reports in sorted(reported.items()):
            expected = expected_by_identity.get(identity)
            if len(reports) > 1 and not (expected and expected["required"]):
                errors.append(
                    f"{package_id}: artifact reported multiple times: "
                    f"{expected['path'] if expected else reports[0][1]}"
                )
        for artifact in package["expected_artifacts"]:
            if not artifact["required"]:
                continue
            reporters = reported.get(artifact["path"].casefold(), [])
            if not reporters:
                errors.append(
                    f"{package_id}: required artifact not reported: {artifact['path']}"
                )
            elif len(reporters) != 1:
                errors.append(
                    f"{package_id}: required artifact reported multiple times: "
                    f"{artifact['path']}"
                )

    implementation_workers: dict[str, str] = {}
    for package_id, agents in sorted(package_agents.items()):
        if len(agents) != 1:
            errors.append(
                f"{package_id}: multiple implementation agents; split work package"
            )
            continue
        implementation_workers[package_id] = next(iter(agents))

    output_contexts: dict[str, dict[str, str | None]] = {}
    for package_id, records in sorted(records_by_package.items()):
        if package_id not in implementation_workers:
            continue
        eligible = [record for record in records if record["receipt_eligible"]]
        if not eligible:
            continue
        package = packages_by_id[package_id]
        if package["authority"]["kind"] == "approved_bundle":
            try:
                output_contexts[package_id] = {
                    "produced_revision": None,
                    "produced_artifact_digest": artifact_set_digest(
                        run,
                        [
                            artifact
                            for record in eligible
                            for artifact in record["artifacts"]
                        ],
                    ),
                }
            except CollaborationError as exc:
                errors.append(f"{package_id}: {exc}")
        else:
            revisions = {record["produced_revision"] for record in eligible}
            if len(revisions) != 1:
                errors.append(f"{package_id}: inconsistent produced revisions")
            else:
                output_contexts[package_id] = {
                    "produced_revision": revisions.pop(),
                    "produced_artifact_digest": None,
                }

    receipts_by_package_stage: dict[tuple[str, str, int | None], list[dict]] = {}
    for receipt in receipts:
        package_id = receipt["work_package_id"]
        stage = receipt["review_stage"]
        receipt_phase = (
            receipt["publication_phase"] if stage == "publication" else None
        )
        receipts_by_package_stage.setdefault(
            (package_id, stage, receipt_phase), []
        ).append(receipt)

    for receipt in receipts:
        package_id = receipt["work_package_id"]
        stage = receipt["review_stage"]
        receipt_phase = (
            receipt["publication_phase"] if stage == "publication" else None
        )
        package = packages_by_id.get(package_id)
        if package is None:
            continue
        try:
            if stage == "scope_acceptance":
                validate_review_receipt(package, receipt)
            else:
                exact_publication_gate = (
                    stage == "publication"
                    and publication_phase is not None
                    and receipt_phase == publication_phase
                )
                bind_current_output = (
                    stage == "implementation" or exact_publication_gate
                )
                if (
                    stage == "publication"
                    and publication_phase is not None
                    and receipt_phase > publication_phase
                ):
                    raise CollaborationError(
                        "COLLAB_REVIEW_STALE", "publication phase"
                    )
                output_context = output_contexts.get(package_id)
                if output_context is None and bind_current_output:
                    raise CollaborationError(
                        "COLLAB_REVIEW_STALE", "no completed output"
                    )
                completed = (
                    records_by_package.get(package_id, [])
                    if bind_current_output
                    else []
                )
                if exact_publication_gate:
                    implementation_receipts = receipts_by_package_stage.get(
                        (package_id, "implementation", None), []
                    )
                    if (
                        len(implementation_receipts) != 1
                        or implementation_receipts[0]["decision"] != "APPROVED"
                    ):
                        raise CollaborationError(
                            "COLLAB_REVIEW_STALE",
                            "approved implementation review receipt required",
                        )
                    implementation_receipt = implementation_receipts[0]
                    try:
                        validate_review_receipt(
                            package,
                            implementation_receipt,
                            expected_producer=implementation_workers.get(package_id),
                            require_exact_output_binding=True,
                            review_not_before=_latest_date_time(
                                [record["completed_at"] for record in completed]
                            ),
                            **output_context,
                        )
                    except CollaborationError as exc:
                        raise CollaborationError(
                            "COLLAB_REVIEW_STALE",
                            "approved implementation review receipt required",
                        ) from exc
                    completed = [
                        record
                        for record in completed
                        if receipt_phase in record["phase_targets"]
                    ]
                review_not_before_values = [
                    record["completed_at"] for record in completed
                ]
                if exact_publication_gate:
                    review_not_before_values.append(
                        implementation_receipt["reviewed_at"]
                    )
                review_not_before = _latest_date_time(review_not_before_values)
                validate_review_receipt(
                    package,
                    receipt,
                    expected_producer=(
                        implementation_workers.get(package_id)
                        if stage == "implementation"
                        else package["coordinator"]
                    ),
                    expected_publication_phase=(
                        receipt_phase if stage == "publication" else None
                    ),
                    require_exact_output_binding=bind_current_output,
                    review_not_before=review_not_before,
                    **(output_context or {}),
                )
                if (
                    stage == "publication"
                    and receipt_phase not in package["scope"]["phase_targets"]
                ):
                    raise CollaborationError(
                        "COLLAB_REVIEW_STALE", "publication phase"
                    )
        except CollaborationError as exc:
            errors.append(
                f"{receipt['receipt_id']}: invalid {stage} review receipt: {exc}"
            )

    for package_id, records in sorted(records_by_package.items()):
        required = any(
            record["receipt_eligible"] and record["review_receipt_required"]
            for record in records
        )
        candidates = receipts_by_package_stage.get(
            (package_id, "implementation", None), []
        )
        if required and not candidates:
            errors.append(
                f"{package_id}: implementation review receipt required"
            )
        if len(candidates) > 1:
            errors.append(f"{package_id}: duplicate implementation review receipts")

    for (package_id, stage, phase), candidates in sorted(
        receipts_by_package_stage.items()
    ):
        if stage == "publication" and len(candidates) > 1:
            errors.append(
                f"{package_id}: duplicate publication review receipts "
                f"for phase {phase}"
            )

    if publication_phase is not None:
        for package_id, records in sorted(records_by_package.items()):
            package = packages_by_id[package_id]
            if publication_phase not in package["scope"]["phase_targets"]:
                continue
            eligible = [record for record in records if record["receipt_eligible"]]
            if not eligible:
                continue
            candidates = receipts_by_package_stage.get(
                (package_id, "publication", publication_phase), []
            )
            if not candidates:
                errors.append(
                    f"{package_id}: publication review receipt required "
                    f"for phase {publication_phase}"
                )

    return errors, checked, len(tasks) - checked


def main() -> int:
    args = parse_args()
    errors, checked, pending = validate_run_handoffs(
        Path(args.run),
        args.wave,
        args.require_complete,
        Path(args.work_package_root) if args.work_package_root else None,
        args.publication_phase,
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Handoff validation failed: {len(errors)} error(s), {checked} checked")
        return 1
    print(f"Handoff validation passed: {checked} checked, {pending} pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
