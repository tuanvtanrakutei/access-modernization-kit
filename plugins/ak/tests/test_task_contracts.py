"""Contracts between task envelopes, role write scopes, and handoff validation.

Both defects covered here were found by actually executing a wave rather than by
reading the code: the kit asked a role for output its own write scope forbade, and
rejected a role for honestly reporting the inputs the kit itself handed it.
"""

from __future__ import annotations

import json
from pathlib import Path

import create_tasks
from validate_handoffs import validate_run_handoffs


# roles.json grants evidence/fragments only to the roles that produce phase evidence,
# and conflicts only to the two document roles. Every role was nonetheless told to
# return "evidence, gaps, conflicts, and artifacts", so a preparation role following
# its own instruction wrote outside its scope and validate_handoffs rejected it. The
# role could satisfy its instruction or its scope, never both.
def test_evidence_producing_role_is_asked_for_evidence() -> None:
    sentence = create_tasks._handoff_instruction(["work/sql_data", "evidence/fragments", "handoffs"])
    assert sentence == "Return a schema-valid handoff with evidence, gaps, and artifacts."


def test_conflict_writing_role_is_asked_for_conflicts() -> None:
    sentence = create_tasks._handoff_instruction(
        ["work/document_integration", "evidence/fragments", "conflicts", "handoffs"]
    )
    assert sentence == "Return a schema-valid handoff with evidence, gaps, conflicts, and artifacts."


def test_preparation_role_is_not_asked_for_evidence_it_cannot_write() -> None:
    sentence = create_tasks._handoff_instruction(["work/source_inventory", "handoffs"])
    assert "with gaps and artifacts." in sentence
    assert "evidence_ids empty" in sentence
    # The awkward two-item Oxford comma ("gaps, and artifacts") is not acceptable prose
    # in an instruction an agent is asked to follow literally.
    assert "gaps, and artifacts" not in sentence


def test_every_shipped_role_gets_an_instruction_matching_its_scope() -> None:
    """No role may be asked for output its own allowed_writes forbids."""
    package = Path(create_tasks.__file__).resolve().parent.parent
    data = json.loads((package / "orchestration" / "roles.json").read_text(encoding="utf-8"))
    roles = data["roles"] if isinstance(data, dict) and "roles" in data else data
    entries = roles.items() if isinstance(roles, dict) else ((r["id"], r) for r in roles)
    for role_id, role in entries:
        writes = role.get("allowed_writes") or []
        sentence = create_tasks._handoff_instruction(writes)
        if "evidence/fragments" not in writes:
            assert "with evidence" not in sentence, role_id
        if "conflicts" not in writes:
            assert "conflicts" not in sentence, role_id


# --- source_files_read vs the task's own input_paths -------------------------------

_TASK = "SYN-WAVE0_INVENTORY-SOURCE_INVENTORY"


def _write_run(tmp_path: Path, source_files_read: list[str]) -> Path:
    run = tmp_path / "run"
    (run / "tasks").mkdir(parents=True)
    (run / "handoffs").mkdir()
    (run / "work" / "source_inventory").mkdir(parents=True)
    (run / "work" / "source_inventory" / "inventory-analysis.json").write_text("{}", encoding="utf-8")
    (run / "run-state.json").write_text(json.dumps({
        "run_id": "SYN-RUN", "package_version": "2.8.0", "app_id": "SYN",
        "manifest_path": "manifest.lock.yaml", "manifest_sha256": "a" * 64,
        "runtime": "generic", "max_parallel": 1, "status": "RUNNING",
        "current_wave": "wave0_inventory", "wave_status": {"wave0_inventory": "RUNNING"},
        "phase_gates": {f"phase{n}": "PENDING" for n in range(1, 7)},
        "created_at": "2026-08-10T00:00:00Z", "updated_at": "2026-08-10T00:00:00Z",
    }), encoding="utf-8")
    (run / "source-inventory.json").write_text(json.dumps({
        "app_id": "SYN", "generated_at": "2026-08-10T00:00:00Z",
        "policy": {"ignore_file": ".investigationignore", "source_roots": [],
                   "include_patterns": [], "ignore_patterns": []},
        "files": [], "ignored": [],
    }), encoding="utf-8")
    (run / "tasks" / f"{_TASK}.json").write_text(json.dumps({
        "task_id": _TASK, "run_id": "SYN-RUN", "app_id": "SYN",
        "wave_id": "wave0_inventory", "role": "source_inventory",
        "phase_targets": [], "module_targets": [], "module_order": [], "dependencies": [],
        # Exactly what create_tasks.py hands this role: run control files, which the
        # immutable inventory - app sources only - can never contain.
        "input_paths": ["manifest.lock.yaml", "source-inventory.json"],
        "write_paths": ["work/source_inventory", "handoffs"],
        "evidence_namespace": "SYN-P0-SOURCE_INVENTORY",
        "instructions": ["x"], "status": "PENDING", "attempt": 0, "max_attempts": 2,
        "token_budget": None, "created_at": "2026-08-10T00:00:00Z",
    }), encoding="utf-8")
    (run / "handoffs" / f"{_TASK}.json").write_text(json.dumps({
        "task_id": _TASK, "run_id": "SYN-RUN", "app_id": "SYN", "role": "source_inventory",
        "agent_runtime": "generic", "agent_id": None, "status": "COMPLETED",
        "summary": "Inventoried the workspace.",
        "artifacts": ["work/source_inventory/inventory-analysis.json"],
        "evidence_ids": [], "gaps": [], "conflict_ids": [],
        "source_files_read": source_files_read,
        "completed_at": "2026-08-10T00:00:00Z",
    }), encoding="utf-8")
    return run


# The role read exactly the two input_paths the kit issued it. Validated against the
# immutable inventory alone, that honest report failed: the inventory holds app sources,
# never run control files. The role could pass only by under-reporting what it read.
def test_declared_input_paths_are_accepted_as_sources_read(tmp_path: Path) -> None:
    run = _write_run(tmp_path, ["manifest.lock.yaml", "source-inventory.json"])
    errors, checked, _ = validate_run_handoffs(run, wave="wave0_inventory", require_complete=True)
    assert errors == []
    assert checked == 1


# The relaxation is scoped to that task's own declared inputs and nothing wider: an
# arbitrary path still has to be in the inventory.
def test_undeclared_path_absent_from_inventory_is_still_rejected(tmp_path: Path) -> None:
    run = _write_run(tmp_path, ["manifest.lock.yaml", "sources/not-inventoried.sql"])
    errors, _, _ = validate_run_handoffs(run, wave="wave0_inventory", require_complete=True)
    assert any("absent from immutable inventory: sources/not-inventoried.sql" in e for e in errors)
    assert not any("manifest.lock.yaml" in e for e in errors)
