#!/usr/bin/env python3
"""Validate handoffs against task envelopes, source inventory, and write scopes."""

from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath


REQUIRED_HANDOFF_FIELDS = {
    "task_id", "run_id", "app_id", "role", "status", "summary", "artifacts",
    "evidence_ids", "gaps", "conflict_ids", "source_files_read", "completed_at",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--wave")
    parser.add_argument("--require-complete", action="store_true")
    return parser.parse_args()


def inside(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def in_write_scope(relative: str, write_paths: list[str]) -> bool:
    candidate = PurePosixPath(relative.replace("\\", "/"))
    if candidate.is_absolute() or ".." in candidate.parts:
        return False
    for declared in write_paths:
        allowed = PurePosixPath(declared.replace("\\", "/"))
        if candidate == allowed or allowed in candidate.parents:
            return True
    return False


def validate_run_handoffs(run: Path, wave: str | None = None, require_complete: bool = False) -> tuple[list[str], int, int]:
    run = run.expanduser().resolve()
    state = json.loads((run / "run-state.json").read_text(encoding="utf-8"))
    inventory = json.loads((run / "source-inventory.json").read_text(encoding="utf-8"))
    inventory_paths = {item["relative_path"].replace("\\", "/") for item in inventory["files"]}
    tasks: dict[str, dict] = {}
    for path in sorted((run / "tasks").glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        if wave and task["wave_id"] != wave:
            continue
        tasks[task["task_id"]] = task

    errors: list[str] = []
    checked = 0
    for task_id, task in tasks.items():
        path = run / "handoffs" / f"{task_id}.json"
        if not path.is_file():
            if require_complete:
                errors.append(f"Missing handoff: {task_id}")
            continue
        checked += 1
        try:
            handoff = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Invalid JSON {path.name}: {exc}")
            continue
        missing = REQUIRED_HANDOFF_FIELDS - set(handoff)
        if missing:
            errors.append(f"{task_id}: missing fields {sorted(missing)}")
            continue
        for field in ("task_id", "run_id", "app_id", "role"):
            expected = task[field] if field in task else state[field]
            if handoff[field] != expected:
                errors.append(f"{task_id}: {field} mismatch")
        if handoff["status"] not in {"COMPLETED", "FAILED", "BLOCKED"}:
            errors.append(f"{task_id}: invalid status {handoff['status']}")
        for list_field in ("artifacts", "evidence_ids", "gaps", "conflict_ids", "source_files_read"):
            if not isinstance(handoff[list_field], list):
                errors.append(f"{task_id}: {list_field} must be a list")
                continue
            if not all(isinstance(item, str) for item in handoff[list_field]):
                errors.append(f"{task_id}: {list_field} must contain only strings")
        for artifact in handoff["artifacts"]:
            artifact_path = run / artifact
            if Path(artifact).is_absolute() or not inside(run, artifact_path):
                errors.append(f"{task_id}: artifact escapes run directory: {artifact}")
            elif not in_write_scope(artifact, task["write_paths"]):
                errors.append(f"{task_id}: artifact outside declared write_paths: {artifact}")
            elif handoff["status"] == "COMPLETED" and not artifact_path.exists():
                errors.append(f"{task_id}: completed artifact missing: {artifact}")
        prefix = task["evidence_namespace"] + "-"
        for evidence_id in handoff["evidence_ids"]:
            if not evidence_id.startswith(prefix):
                errors.append(f"{task_id}: evidence id outside namespace: {evidence_id}")
        for conflict_id in handoff["conflict_ids"]:
            if not conflict_id.startswith(f"{state['app_id']}-CONFLICT-"):
                errors.append(f"{task_id}: conflict id outside app namespace: {conflict_id}")
        for source in handoff["source_files_read"]:
            normalized = source.replace("\\", "/")
            if Path(source).is_absolute() or ".." in Path(source).parts:
                errors.append(f"{task_id}: source path must be app-relative: {source}")
            elif normalized not in inventory_paths:
                errors.append(f"{task_id}: source is absent from immutable inventory: {source}")

    return errors, checked, len(tasks) - checked


def main() -> int:
    args = parse_args()
    errors, checked, pending = validate_run_handoffs(Path(args.run), args.wave, args.require_complete)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Handoff validation failed: {len(errors)} error(s), {checked} checked")
        return 1
    print(f"Handoff validation passed: {checked} checked, {pending} pending")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
