# Collaboration Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one immutable human/agent work-package contract that safely projects into existing AK runtime tasks, binds reviews to exact authority and validation evidence, and supports multi-developer kit or application work without committing production bundles.

**Architecture:** Add a small pure-Python collaboration contract layer under `plugins/ak/contracts/`. `work-package.json` is the only authored scope model; current task/handoff/conflict records remain runtime projections and receipts. Existing orchestration, bundle approval, coordinator publication, and provider-neutral runtime adapters stay authoritative. Collaboration commands validate local JSON records only and never perform Git, network, Access, SQL Server, acquisition, or checkpoint approval actions.

**Tech Stack:** Python 3.11, stdlib (`argparse`, `hashlib`, `json`, `pathlib`), JSON Schema Draft 2020-12 via `jsonschema`, pytest. Fixtures contain invented data only.

**Design Spec:** `docs/superpowers/specs/2026-07-28-collaboration-foundation-design.md`

---

## Boundaries

In scope: canonical work packages; semantic digest; repository/bundle/mixed authority; path, evidence, dependency, publication, and reviewer conflicts; task projection; handoff binding; review receipts; contract-impact records; enriched bundle locks; deterministic collaboration CLI; English-canonical collaboration docs; synthetic two-contributor fixture; Windows/Linux validation; AK 2.7.2 release metadata.

Out of scope: SQL/VBA/UI analyzers; stable analysis model; Graphify migration; Data Model/Data Dictionary generation; Refactoring Handoff production; live Access/ADP/SQL Server; artifact-store clients; GitHub/Jira APIs; branch, commit, push, merge, release, or checkpoint automation. Those remain Plan 3B or external operator actions.

## Compatibility Invariants

- V2.1 and V2.2 manifests remain unchanged and readable.
- Existing task, handoff, conflict, bundle-lock, and bundle-approval records remain schema-valid through explicit legacy variants.
- Existing `create_tasks.py` behavior remains available when no collaboration package is supplied.
- Existing provider-neutral runtime adapters and orchestration waves remain unchanged.
- Canonical Phase publication remains coordinator-only.
- Baseline verified July 28, 2026 with the repository virtual environment: `92 passed, 1 warning`.
- No real database binaries, credentials, proprietary exports, production rows, absolute machine paths, or signed artifact URLs enter fixtures or Git.

## Target File Map

Create:

- `plugins/ak/schemas/{work-package,review-receipt,contract-impact}.schema.json`
- `plugins/ak/contracts/{collaboration,review,contract_impact}.py`
- `plugins/ak/scripts/collaboration_cli.py`
- `plugins/ak/tests/collaboration_helpers.py`
- `plugins/ak/tests/test_{collaboration,collaboration_projection,collaboration_review,contract_impact,cli_collaboration,collaboration_integration}.py`
- `plugins/ak/fixtures/collaboration/two-contributor/`
- `docs/collaboration/{contributor-workflow,application-team-workflow,contract-changes}.md`

Modify:

- `plugins/ak/schemas/{task,handoff,conflict,bundle-lock}.schema.json`
- `plugins/ak/contracts/bundle.py`
- `plugins/ak/scripts/{create_tasks,validate_handoffs,ak,validate_structure}.py`
- `plugins/ak/templates/{task-envelope,agent-handoff}.json`
- `plugins/ak/tests/{test_bundle,test_package_smoke}.py`
- `plugins/ak/specifications/package.json`
- `plugins/ak/.codex-plugin/plugin.json`
- `plugins/ak/.claude-plugin/plugin.json`
- `plugins/ak/skills/ak/SKILL.md`
- `.github/CODEOWNERS`
- `CHANGELOG.md`

## Shared APIs

- `collaboration.py`: `CollaborationError`, `work_package_digest`, `validate_work_package`, `load_work_package`, `find_collaboration_conflicts`, `integration_order`, and `project_task`.
- `review.py`: `validate_review_receipt`.
- `contract_impact.py`: `contract_impact_required` and `validate_contract_impact`.

Later tasks import these functions and do not redefine their behavior or signatures.

---

### Task 1: Canonical work-package schema and digest

**Files:**
- Create: `plugins/ak/schemas/work-package.schema.json`
- Create: `plugins/ak/contracts/collaboration.py`
- Create: `plugins/ak/tests/collaboration_helpers.py`
- Create: `plugins/ak/tests/test_collaboration.py`
- Modify: `plugins/ak/scripts/validate_structure.py`

- [ ] **Step 1: Write shared synthetic package builders**

```python
# plugins/ak/tests/collaboration_helpers.py
from copy import deepcopy

def kit_package(package_id: str = "WP_KIT_SCHEMA") -> dict:
    return {
        "schema_version": "1.0", "package_id": package_id,
        "title": "Add collaboration schema", "objective": "Add one validated work-package contract.",
        "work_kind": "kit_contract",
        "authority": {"kind": "repository_revision", "repository": "access-modernization-kit", "base_revision": "8b9f7e0"},
        "scope": {"roles": [], "wave_ids": [], "phase_targets": [], "module_targets": [], "profile_targets": [], "adapter_targets": [], "document_targets": []},
        "dependencies": [], "input_paths": ["plugins/ak/schemas/task.schema.json"],
        "write_paths": ["plugins/ak/schemas/work-package.schema.json"],
        "expected_artifacts": [{"path": "plugins/ak/schemas/work-package.schema.json", "kind": "schema", "required": True, "publication_class": "scoped"}],
        "evidence_namespace": None,
        "validation_commands": ["python -m pytest plugins/ak/tests/test_collaboration.py -q"],
        "coordinator": "maintainer", "reviewer": "contract-reviewer", "publication_policy": "scoped_only",
        "security_constraints": {"network": False, "live_access": False, "live_sql_server": False, "production_data": False},
        "created_by": "planner", "created_at": "2026-07-28T00:00:00Z",
    }

def application_package(package_id: str = "WP_SYN_SQL") -> dict:
    value = deepcopy(kit_package(package_id))
    value.update({
        "title": "Analyze synthetic SQL evidence", "objective": "Produce one scoped SQL evidence fragment.",
        "work_kind": "application_evidence",
        "authority": {"kind": "approved_bundle", "app_id": "SYN", "bundle_id": "bundle-" + "a" * 64, "checksum": "b" * 64, "bundle_lock_digest": "c" * 64, "approval_record_id": "AP-SYN-1", "distribution_policy": "artifact_store", "artifact_reference": "artifact_store://fixture/SYN/bundle-a"},
        "scope": {"roles": ["sql_data"], "wave_ids": ["wave1_source_extraction"], "phase_targets": [1], "module_targets": ["module-orders"], "profile_targets": [], "adapter_targets": [], "document_targets": []},
        "input_paths": ["extracted/bundles/bundle-a/code/access-sql"],
        "write_paths": ["work/sql_data/module-orders", "evidence/fragments"],
        "expected_artifacts": [{"path": "work/sql_data/module-orders/result.json", "kind": "analysis_fragment", "required": True, "publication_class": "scoped"}],
        "evidence_namespace": "SYN-P1-SQL_DATA-ORDERS",
    })
    return value

def mixed_package(package_id: str = "WP_SYN_PILOT") -> dict:
    value = application_package(package_id)
    value["work_kind"] = "mixed_pilot"
    value["authority"].update({"kind": "mixed", "repository": "access-modernization-kit", "base_revision": "8b9f7e0"})
    return value
```

- [ ] **Step 2: Write failing validation tests**

```python
# plugins/ak/tests/test_collaboration.py
import pytest
from collaboration import CollaborationError, validate_work_package, work_package_digest
from collaboration_helpers import application_package, kit_package, mixed_package

def test_kit_and_application_packages_validate() -> None:
    validate_work_package(kit_package())
    validate_work_package(application_package())
    validate_work_package(mixed_package())

def test_digest_ignores_created_at_and_dict_order() -> None:
    first = kit_package()
    second = dict(reversed(list(first.items())))
    second["created_at"] = "2030-01-01T00:00:00Z"
    assert work_package_digest(first) == work_package_digest(second)

@pytest.mark.parametrize("bad_path", ["D:/secret/file", "../escape", "/etc/passwd"])
def test_paths_must_be_relative_and_confined(bad_path: str) -> None:
    package = kit_package()
    package["write_paths"] = [bad_path]
    with pytest.raises(CollaborationError, match="COLLAB_PATH_ESCAPE"):
        validate_work_package(package)

def test_worker_cannot_claim_canonical_phase_output() -> None:
    package = application_package()
    package["write_paths"].append("outputs/SYN_Phase1_DataUnderstanding_EN.md")
    with pytest.raises(CollaborationError, match="COLLAB_PUBLICATION_FORBIDDEN"):
        validate_work_package(package)

def test_missing_authority_has_stable_code() -> None:
    package = kit_package()
    del package["authority"]
    with pytest.raises(CollaborationError, match="COLLAB_AUTHORITY_MISSING"):
        validate_work_package(package)

@pytest.mark.parametrize("path", ["sources/live.mdb", "sources/backup.bak", "secrets/password.env"])
def test_prohibited_binary_or_secret_reference_is_blocked(path: str) -> None:
    package = kit_package()
    package["input_paths"] = [path]
    with pytest.raises(CollaborationError, match="COLLAB_SECRET_OR_BINARY_PROHIBITED"):
        validate_work_package(package)
```

- [ ] **Step 3: Run RED**

Run: `python -m pytest plugins/ak/tests/test_collaboration.py -q`

Expected: FAIL with `ModuleNotFoundError: No module named 'collaboration'`.

- [ ] **Step 4: Add the closed JSON Schema**

Use Draft 2020-12 and top-level `additionalProperties: false`. Require every design field. Use `oneOf` for `repository_revision`, `approved_bundle`, and `mixed` authority. Closed enums:

```json
{
  "work_kind": ["kit_code", "kit_contract", "kit_docs", "application_evidence", "application_docs", "application_qa", "mixed_pilot"],
  "publication_policy": ["scoped_only", "document_owner", "coordinator_only"],
  "distribution_policy": ["local_only", "shared_path", "artifact_store", "git_allowed"]
}
```

Require all scope arrays even when empty. `package_id` uses `^[A-Z0-9_-]+$`; SHA-256 values use `^[a-f0-9]{64}$`.

- [ ] **Step 5: Implement minimal validation and digest**

```python
# plugins/ak/contracts/collaboration.py
from __future__ import annotations
import hashlib, json
from pathlib import Path, PurePosixPath
from typing import Any
import jsonschema

PACKAGE = Path(__file__).resolve().parents[1]
CANONICAL_OUTPUT_MARKERS = tuple(f"_Phase{number}_" for number in range(1, 7))
FORBIDDEN_SUFFIXES = {".mdb", ".accdb", ".adp", ".mde", ".accde", ".bak", ".mdf", ".ldf", ".dsn", ".env"}

class CollaborationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")

def _schema(name: str) -> dict[str, Any]:
    return json.loads((PACKAGE / "schemas" / name).read_text(encoding="utf-8"))

def work_package_digest(value: dict[str, Any]) -> str:
    scoped = {key: item for key, item in value.items() if key != "created_at"}
    encoded = json.dumps(scoped, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()

def _validate_relative(path: str) -> None:
    normalized = PurePosixPath(path.replace("\\", "/"))
    if normalized.is_absolute() or ".." in normalized.parts or not normalized.parts:
        raise CollaborationError("COLLAB_PATH_ESCAPE", path)

def validate_work_package(value: dict[str, Any]) -> None:
    if "authority" not in value:
        raise CollaborationError("COLLAB_AUTHORITY_MISSING", "authority")
    try:
        jsonschema.validate(value, _schema("work-package.schema.json"))
    except jsonschema.ValidationError as exc:
        raise CollaborationError("COLLAB_PACKAGE_INVALID", exc.message) from exc
    for path in value["input_paths"] + value["write_paths"] + [item["path"] for item in value["expected_artifacts"]]:
        _validate_relative(path)
        if PurePosixPath(path.lower()).suffix in FORBIDDEN_SUFFIXES or "secrets/" in path.lower():
            raise CollaborationError("COLLAB_SECRET_OR_BINARY_PROHIBITED", path)
    if value["publication_policy"] == "scoped_only":
        for path in value["write_paths"]:
            if path.startswith("outputs/") and any(marker in path for marker in CANONICAL_OUTPUT_MARKERS):
                raise CollaborationError("COLLAB_PUBLICATION_FORBIDDEN", path)

def load_work_package(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_work_package(value)
    return value
```

- [ ] **Step 6: Register files, run GREEN, commit**

```bash
python -m pytest plugins/ak/tests/test_collaboration.py -q
python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .
git add plugins/ak/schemas/work-package.schema.json plugins/ak/contracts/collaboration.py plugins/ak/tests/collaboration_helpers.py plugins/ak/tests/test_collaboration.py plugins/ak/scripts/validate_structure.py
git commit -m "feat(collaboration): add canonical work packages"
```

---

### Task 2: Path, evidence, dependency, authority, and publication conflicts

**Files:**
- Modify: `plugins/ak/contracts/collaboration.py`
- Modify: `plugins/ak/schemas/work-package.schema.json`
- Modify: `plugins/ak/schemas/conflict.schema.json`
- Modify: `plugins/ak/tests/test_collaboration.py`

- [ ] **Step 1: Add failing conflict tests**

```python
from collaboration import find_collaboration_conflicts, integration_order

def codes(packages: list[dict]) -> set[str]:
    return {item["code"] for item in find_collaboration_conflicts(packages)}

def test_overlapping_write_paths_are_blocked() -> None:
    first, second = application_package("WP_ONE"), application_package("WP_TWO")
    second["write_paths"] = ["work/sql_data/module-orders/details"]
    assert "COLLAB_WRITE_CONFLICT" in codes([first, second])

def test_overlapping_evidence_prefixes_are_blocked() -> None:
    first, second = application_package("WP_ONE"), application_package("WP_TWO")
    second["evidence_namespace"] = first["evidence_namespace"] + "-CHILD"
    assert "COLLAB_EVIDENCE_CONFLICT" in codes([first, second])

def test_mismatched_bundle_authority_is_blocked() -> None:
    first, second = application_package("WP_ONE"), application_package("WP_TWO")
    second["authority"]["bundle_id"] = "bundle-" + "d" * 64
    assert "COLLAB_AUTHORITY_MISMATCH" in codes([first, second])

def test_dependency_cycle_is_blocked() -> None:
    first, second = kit_package("WP_ONE"), kit_package("WP_TWO")
    first["dependencies"], second["dependencies"] = ["WP_TWO"], ["WP_ONE"]
    assert "COLLAB_DEPENDENCY_CYCLE" in codes([first, second])

def test_integration_order_is_dependency_stable() -> None:
    first, second = kit_package("WP_ONE"), kit_package("WP_TWO")
    second["dependencies"] = ["WP_ONE"]
    assert integration_order([second, first]) == ["WP_ONE", "WP_TWO"]

def test_integrated_predecessor_allows_sequential_overlap() -> None:
    first, second = kit_package("WP_ONE"), kit_package("WP_TWO")
    first["write_paths"] = ["docs/collaboration"]
    second["write_paths"] = ["docs/collaboration/contributor-workflow.md"]
    second["dependencies"] = ["WP_ONE"]
    conflicts = find_collaboration_conflicts([first, second], integrated_package_ids={"WP_ONE"})
    assert "COLLAB_WRITE_CONFLICT" not in {item["code"] for item in conflicts}
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest plugins/ak/tests/test_collaboration.py -q`

Expected: FAIL because `find_collaboration_conflicts` is missing.

- [ ] **Step 3: Extend schemas backward-compatibly**

Keep lifecycle state outside immutable work packages. In `conflict.schema.json`, replace required `reported_by_task` with `oneOf` requiring exactly one of `reported_by_task` or `reported_by_work_package`. Add optional `resolved_by_work_package`. Keep existing task-reported conflict records valid.

- [ ] **Step 4: Implement deterministic conflict detection**

```python
def _contains(parent: str, child: str) -> bool:
    left = PurePosixPath(parent.replace("\\", "/"))
    right = PurePosixPath(child.replace("\\", "/"))
    return left == right or left in right.parents

def _authority_key(package: dict[str, Any]) -> tuple:
    authority = package["authority"]
    if authority["kind"] == "repository_revision":
        return ("repo", authority["repository"], authority["base_revision"])
    if authority["kind"] == "mixed":
        return ("mixed", authority["repository"], authority["base_revision"], authority["bundle_id"], authority["checksum"])
    return ("bundle", authority["bundle_id"], authority["checksum"])

def integration_order(packages: list[dict[str, Any]]) -> list[str]:
    by_id = {item["package_id"]: item for item in packages}
    visiting: set[str] = set()
    visited: set[str] = set()
    ordered: list[str] = []
    def visit(package_id: str) -> None:
        if package_id in visiting:
            raise CollaborationError("COLLAB_DEPENDENCY_CYCLE", package_id)
        if package_id in visited:
            return
        visiting.add(package_id)
        for dependency in sorted(by_id[package_id]["dependencies"]):
            if dependency in by_id:
                visit(dependency)
        visiting.remove(package_id)
        visited.add(package_id)
        ordered.append(package_id)
    for package_id in sorted(by_id):
        visit(package_id)
    return ordered

def find_collaboration_conflicts(packages: list[dict[str, Any]], *, integrated_package_ids: set[str] | None = None) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    integrated = integrated_package_ids or set()
    try:
        integration_order(packages)
    except CollaborationError as exc:
        issues.append({"code": exc.code, "packages": [str(exc).split(": ", 1)[-1]]})
    ordered = sorted(packages, key=lambda item: item["package_id"])
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            sequential = left["package_id"] in right.get("dependencies", []) and left["package_id"] in integrated
            if not sequential and any(_contains(a, b) or _contains(b, a) for a in left["write_paths"] for b in right["write_paths"]):
                issues.append({"code": "COLLAB_WRITE_CONFLICT", "packages": [left["package_id"], right["package_id"]]})
            left_ns, right_ns = left.get("evidence_namespace"), right.get("evidence_namespace")
            if left_ns and right_ns and (left_ns == right_ns or left_ns.startswith(right_ns + "-") or right_ns.startswith(left_ns + "-")):
                issues.append({"code": "COLLAB_EVIDENCE_CONFLICT", "packages": [left["package_id"], right["package_id"]]})
            if not sequential and _authority_key(left) != _authority_key(right):
                issues.append({"code": "COLLAB_AUTHORITY_MISMATCH", "packages": [left["package_id"], right["package_id"]]})
    return sorted(issues, key=lambda item: (item["code"], item["packages"]))
```

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m pytest plugins/ak/tests/test_collaboration.py plugins/ak/tests/test_package_smoke.py -q
git add plugins/ak/contracts/collaboration.py plugins/ak/schemas/work-package.schema.json plugins/ak/schemas/conflict.schema.json plugins/ak/tests/test_collaboration.py
git commit -m "feat(collaboration): detect scoped work conflicts"
```

---

### Task 3: Deterministic runtime task projection

**Files:**
- Modify: `plugins/ak/contracts/collaboration.py`
- Modify: `plugins/ak/schemas/task.schema.json`
- Modify: `plugins/ak/templates/task-envelope.json`
- Create: `plugins/ak/tests/test_collaboration_projection.py`
- Modify: `plugins/ak/scripts/validate_structure.py`

- [ ] **Step 1: Add the runtime candidate builder and failing projection tests**

```python
# append to plugins/ak/tests/collaboration_helpers.py
def candidate_task() -> dict:
    return {
        "task_id": "SYN-W1-SQL-ORDERS", "run_id": "SYN-RUN", "app_id": "SYN",
        "wave_id": "wave1_source_extraction", "role": "sql_data", "phase_targets": [1],
        "module_targets": ["module-orders"], "module_order": ["module-orders"], "dependencies": [],
        "input_paths": ["../../extracted/bundles/bundle-a/code/access-sql"],
        "write_paths": ["work/sql_data/module-orders"],
        "evidence_namespace": "SYN-P1-SQL_DATA-ORDERS", "instructions": [],
        "status": "PENDING", "attempt": 0, "max_attempts": 2, "token_budget": None,
        "created_at": "2026-07-28T00:00:00Z",
    }
```

```python
# plugins/ak/tests/test_collaboration_projection.py
import pytest
from collaboration import CollaborationError, project_task, work_package_digest
from collaboration_helpers import application_package, candidate_task

def test_projection_binds_task_to_package_digest() -> None:
    package = application_package()
    task = project_task(package, candidate_task())
    assert task["work_package_id"] == package["package_id"]
    assert task["work_package_digest"] == work_package_digest(package)
    assert task["projection_version"] == "1.0"

def test_projection_rejects_role_expansion() -> None:
    package, task = application_package(), candidate_task()
    task["role"] = "vba_ui"
    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)

def test_projection_rejects_write_expansion() -> None:
    package, task = application_package(), candidate_task()
    task["write_paths"] = ["outputs/SYN_Phase1_DataUnderstanding_EN.md"]
    with pytest.raises(CollaborationError, match="COLLAB_PROJECTION_EXPANDED"):
        project_task(package, task)

def test_projection_allows_narrower_module_and_paths() -> None:
    package, task = application_package(), candidate_task()
    package["scope"]["module_targets"].append("module-products")
    package["write_paths"].append("work/sql_data/module-products")
    assert project_task(package, task)["module_targets"] == ["module-orders"]
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest plugins/ak/tests/test_collaboration_projection.py -q`

Expected: FAIL because `project_task` is missing.

- [ ] **Step 3: Extend the task schema as legacy-or-projected**

Add optional `work_package_id`, `work_package_digest`, and `projection_version`. Add an `allOf` condition: when any projection field exists, require all three. Keep legacy tasks with none of the three valid. Update `task-envelope.json` with a complete projected example.

- [ ] **Step 4: Implement scope-narrowing projection**

```python
def _task_logical_path(path: str) -> str:
    parts = PurePosixPath(path.replace("\\", "/")).parts
    if parts[:2] == ("..", "..") and ".." not in parts[2:]:
        return PurePosixPath(*parts[2:]).as_posix()
    if ".." in parts or PurePosixPath(path).is_absolute():
        raise CollaborationError("COLLAB_PROJECTION_EXPANDED", "task path")
    return PurePosixPath(*parts).as_posix()

def _inside_any(path: str, allowed: list[str]) -> bool:
    logical = _task_logical_path(path)
    return any(_contains(parent, logical) for parent in allowed)

def project_task(package: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    validate_work_package(package)
    scope = package["scope"]
    checks = (
        (task["role"] in scope["roles"], "role"),
        (task["wave_id"] in scope["wave_ids"], "wave_id"),
        (set(task.get("phase_targets", [])).issubset(scope["phase_targets"]), "phase_targets"),
        (set(task.get("module_targets", [])).issubset(scope["module_targets"]), "module_targets"),
        (all(_inside_any(path, package["input_paths"]) for path in task["input_paths"]), "input_paths"),
        (all(_inside_any(path, package["write_paths"]) for path in task["write_paths"]), "write_paths"),
        (task["evidence_namespace"] == package["evidence_namespace"] or task["evidence_namespace"].startswith(package["evidence_namespace"] + "-"), "evidence_namespace"),
    )
    for valid, field in checks:
        if not valid:
            raise CollaborationError("COLLAB_PROJECTION_EXPANDED", field)
    projected = dict(task)
    projected.update({
        "work_package_id": package["package_id"],
        "work_package_digest": work_package_digest(package),
        "projection_version": "1.0",
    })
    return projected
```

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m pytest plugins/ak/tests/test_collaboration_projection.py plugins/ak/tests/test_package_smoke.py -q
git add plugins/ak/contracts/collaboration.py plugins/ak/schemas/task.schema.json plugins/ak/templates/task-envelope.json plugins/ak/tests/test_collaboration_projection.py plugins/ak/scripts/validate_structure.py
git commit -m "feat(collaboration): project scoped runtime tasks"
```

---

### Task 4: Review receipts and handoff binding

**Files:**
- Create: `plugins/ak/schemas/review-receipt.schema.json`
- Create: `plugins/ak/contracts/review.py`
- Modify: `plugins/ak/schemas/handoff.schema.json`
- Modify: `plugins/ak/templates/agent-handoff.json`
- Modify: `plugins/ak/scripts/validate_handoffs.py`
- Modify: `plugins/ak/tests/collaboration_helpers.py`
- Create: `plugins/ak/tests/test_collaboration_review.py`
- Modify: `plugins/ak/scripts/validate_structure.py`

- [ ] **Step 1: Add a receipt helper and failing review tests**

```python
# append to collaboration_helpers.py
from collaboration import work_package_digest

def acceptance_receipt(package: dict) -> dict:
    return {
        "schema_version": "1.0", "receipt_id": "RR-" + package["package_id"],
        "work_package_id": package["package_id"], "work_package_digest": work_package_digest(package),
        "review_stage": "scope_acceptance", "authority_snapshot": package["authority"],
        "producer": package["created_by"], "reviewer": package["reviewer"],
        "review_scope": ["schema", "authority", "paths", "dependencies", "security"],
        "validation_results": [{"command": command, "exit_code": 0, "result": "PASS"} for command in package["validation_commands"]],
        "findings": [], "decision": "APPROVED", "reviewed_at": "2026-07-28T00:10:00Z",
    }
```

```python
# plugins/ak/tests/test_collaboration_review.py
import json
import pytest
from collaboration import CollaborationError, project_task
from collaboration_helpers import acceptance_receipt, application_package, candidate_task
from review import validate_review_receipt
from validate_handoffs import validate_run_handoffs

def test_scope_acceptance_receipt_approves_exact_digest() -> None:
    package = application_package()
    validate_review_receipt(package, acceptance_receipt(package))

def test_changed_package_makes_receipt_stale() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    package["objective"] = "Changed scope"
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)

def test_reviewer_must_be_independent() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["reviewer"] = receipt["producer"]
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_NOT_INDEPENDENT"):
        validate_review_receipt(package, receipt)

def test_required_validation_must_pass() -> None:
    package = application_package()
    receipt = acceptance_receipt(package)
    receipt["validation_results"][0]["exit_code"] = 1
    with pytest.raises(CollaborationError, match="COLLAB_REVIEW_STALE"):
        validate_review_receipt(package, receipt)

def test_projected_handoff_rejects_package_digest_mismatch(tmp_path) -> None:
    package = application_package()
    package_root = tmp_path / "packages" / package["package_id"]
    package_root.mkdir(parents=True)
    (package_root / "work-package.json").write_text(json.dumps(package), encoding="utf-8")
    run = tmp_path / "run"
    (run / "tasks").mkdir(parents=True)
    (run / "handoffs").mkdir()
    (run / "run-state.json").write_text(json.dumps({"run_id": "SYN-RUN", "app_id": "SYN"}), encoding="utf-8")
    (run / "source-inventory.json").write_text(json.dumps({"files": []}), encoding="utf-8")
    task = project_task(package, candidate_task())
    (run / "tasks" / f"{task['task_id']}.json").write_text(json.dumps(task), encoding="utf-8")
    handoff = {
        "task_id": task["task_id"], "run_id": "SYN-RUN", "app_id": "SYN", "role": "sql_data",
        "work_package_id": package["package_id"], "work_package_digest": "f" * 64,
        "produced_revision": None, "validation_results": [], "review_receipt_required": True,
        "status": "COMPLETED", "summary": "Synthetic handoff", "artifacts": [], "evidence_ids": [],
        "gaps": [], "conflict_ids": [], "source_files_read": [], "completed_at": "2026-07-28T00:20:00Z",
    }
    (run / "handoffs" / f"{task['task_id']}.json").write_text(json.dumps(handoff), encoding="utf-8")
    errors, _, _ = validate_run_handoffs(run, work_package_root=tmp_path / "packages")
    assert any("work package digest mismatch" in error for error in errors)
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest plugins/ak/tests/test_collaboration_review.py -q`

Expected: FAIL because `review.py` is missing.

- [ ] **Step 3: Add closed review and handoff schema variants**

`review-receipt.schema.json` requires the exact design fields; review stage is `scope_acceptance|implementation|publication`; decision is `APPROVED|CHANGES_REQUESTED|REJECTED`; every validation result requires command, integer exit code, and result.

Extend `handoff.schema.json` with optional `work_package_id`, `work_package_digest`, `produced_revision`, `validation_results`, and `review_receipt_required`. Use the same legacy-or-collaboration conditional pattern as the task schema. Update the handoff template with a complete projected example.

- [ ] **Step 4: Implement review validation**

```python
# plugins/ak/contracts/review.py
from __future__ import annotations
from typing import Any
import jsonschema
from collaboration import CollaborationError, _schema, work_package_digest

def validate_review_receipt(package: dict[str, Any], receipt: dict[str, Any], *, produced_revision: str | None = None, contract_impact: dict[str, Any] | None = None) -> None:
    try:
        jsonschema.validate(receipt, _schema("review-receipt.schema.json"))
    except jsonschema.ValidationError as exc:
        raise CollaborationError("COLLAB_REVIEW_STALE", exc.message) from exc
    if receipt["work_package_id"] != package["package_id"] or receipt["work_package_digest"] != work_package_digest(package):
        raise CollaborationError("COLLAB_REVIEW_STALE", "package identity")
    snapshot = dict(receipt["authority_snapshot"])
    reviewed_revision = snapshot.pop("produced_revision", None)
    if snapshot != package["authority"]:
        raise CollaborationError("COLLAB_REVIEW_STALE", "authority snapshot")
    if receipt["reviewer"] != package["reviewer"] or receipt["reviewer"] == receipt["producer"]:
        raise CollaborationError("COLLAB_REVIEW_NOT_INDEPENDENT", receipt["reviewer"])
    results = {item["command"]: item["exit_code"] for item in receipt["validation_results"]}
    if any(results.get(command) != 0 for command in package["validation_commands"]):
        raise CollaborationError("COLLAB_REVIEW_STALE", "required validation")
    if produced_revision is not None and reviewed_revision != produced_revision:
        raise CollaborationError("COLLAB_REVIEW_STALE", "produced revision")
```

- [ ] **Step 5: Bind collaboration handoffs in `validate_handoffs.py`**

Add `--work-package-root` and extend the function signature to `validate_run_handoffs(run: Path, wave: str | None = None, require_complete: bool = False, work_package_root: Path | None = None)`. For tasks with projection fields, load `<root>/<work_package_id>/work-package.json`; verify the digest; require matching handoff package fields; verify validation commands and produced revision fields; retain existing inventory, artifact, write-scope, evidence-prefix, and conflict checks. Tasks without projection fields use the current legacy path unchanged.

- [ ] **Step 6: Run GREEN and commit**

```bash
python -m pytest plugins/ak/tests/test_collaboration_review.py plugins/ak/tests/test_package_smoke.py -q
git add plugins/ak/schemas/review-receipt.schema.json plugins/ak/contracts/review.py plugins/ak/schemas/handoff.schema.json plugins/ak/templates/agent-handoff.json plugins/ak/scripts/validate_handoffs.py plugins/ak/tests/collaboration_helpers.py plugins/ak/tests/test_collaboration_review.py plugins/ak/scripts/validate_structure.py
git commit -m "feat(collaboration): bind reviews and handoffs"
```

---

### Task 5: Contract-impact schema and changed-path gate

**Files:**
- Create: `plugins/ak/schemas/contract-impact.schema.json`
- Create: `plugins/ak/contracts/contract_impact.py`
- Create: `plugins/ak/tests/test_contract_impact.py`
- Modify: `plugins/ak/contracts/review.py`
- Modify: `plugins/ak/scripts/validate_structure.py`

- [ ] **Step 1: Write failing impact tests**

```python
# append to plugins/ak/tests/collaboration_helpers.py
def impact(package: dict) -> dict:
    return {
        "schema_version": "1.0", "impact_id": "CI-" + package["package_id"],
        "work_package_id": package["package_id"], "work_package_digest": work_package_digest(package),
        "changed_paths": ["plugins/ak/schemas/work-package.schema.json"],
        "affected_contracts": ["work-package.schema.json"], "compatibility": "compatible",
        "migration_behavior": {"required": False, "summary": "Additive schema."},
        "synthetic_fixtures": ["plugins/ak/fixtures/collaboration/two-contributor"],
        "compatibility_tests": ["plugins/ak/tests/test_collaboration.py"],
        "documentation_updates": ["docs/collaboration/contract-changes.md"],
        "validation_evidence": ["python -m pytest plugins/ak/tests/test_collaboration.py -q"],
        "untested_runtime_paths": [], "untested_runtime_reason": "All affected deterministic paths are covered.",
        "security_and_data_handling_impact": "No production bundle content enters Git.",
        "release_target": "2.7.2", "reviewer": package["reviewer"],
    }
```

```python
# plugins/ak/tests/test_contract_impact.py
import pytest
from collaboration import CollaborationError
from collaboration_helpers import impact, kit_package
from contract_impact import contract_impact_required, validate_contract_impact

@pytest.mark.parametrize("path", [
    "plugins/ak/schemas/task.schema.json", "plugins/ak/contracts/bundle.py",
    "plugins/ak/profiles/frontend.yaml", "plugins/ak/adapters/managed_access/adapter.py",
    "plugins/ak/orchestration/waves.json", "plugins/ak/scripts/ak.py",
])
def test_contract_paths_require_impact(path: str) -> None:
    assert contract_impact_required([path])

def test_ordinary_test_change_does_not_require_impact() -> None:
    assert not contract_impact_required(["plugins/ak/tests/test_collaboration.py"])

def test_valid_impact_matches_package_and_changed_paths() -> None:
    package = kit_package()
    validate_contract_impact(package, impact(package), ["plugins/ak/schemas/work-package.schema.json"])

def test_vague_impact_values_are_rejected() -> None:
    package = kit_package()
    record = impact(package)
    record["security_and_data_handling_impact"] = "N/A"
    with pytest.raises(CollaborationError, match="COLLAB_IMPACT_REQUIRED"):
        validate_contract_impact(package, record, record["changed_paths"])
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest plugins/ak/tests/test_contract_impact.py -q`

Expected: FAIL because `contract_impact.py` is missing.

- [ ] **Step 3: Add the closed impact schema**

Require every design field. `compatibility` is `compatible|migration_required|breaking`. Require non-empty summary/security strings and exact `release_target`. Arrays may be empty only when a companion reason string is non-empty. Reject additional properties.

- [ ] **Step 4: Implement path triggers and validation**

```python
# plugins/ak/contracts/contract_impact.py
from __future__ import annotations
from typing import Any
import jsonschema
from collaboration import CollaborationError, _schema, work_package_digest

SENSITIVE_PREFIXES = (
    "plugins/ak/contracts/", "plugins/ak/schemas/", "plugins/ak/profiles/",
    "plugins/ak/adapters/", "plugins/ak/orchestration/", "plugins/ak/templates/",
    "plugins/ak/specifications/", "plugins/ak/scripts/ak.py",
)
VAGUE = {"n/a", "na", "none", "later", "unknown", "tbd", "todo"}

def contract_impact_required(changed_paths: list[str]) -> bool:
    normalized = [path.replace("\\", "/") for path in changed_paths]
    return any(any(path == prefix or path.startswith(prefix) for prefix in SENSITIVE_PREFIXES) for path in normalized)

def validate_contract_impact(package: dict[str, Any], impact: dict[str, Any], changed_paths: list[str]) -> None:
    try:
        jsonschema.validate(impact, _schema("contract-impact.schema.json"))
    except jsonschema.ValidationError as exc:
        raise CollaborationError("COLLAB_IMPACT_REQUIRED", exc.message) from exc
    if impact["work_package_id"] != package["package_id"] or impact["work_package_digest"] != work_package_digest(package):
        raise CollaborationError("COLLAB_IMPACT_REQUIRED", "package identity")
    expected = sorted(path.replace("\\", "/") for path in changed_paths)
    if sorted(impact["changed_paths"]) != expected:
        raise CollaborationError("COLLAB_IMPACT_REQUIRED", "changed paths")
    strings = [impact["security_and_data_handling_impact"], impact["migration_behavior"]["summary"], impact["untested_runtime_reason"]]
    if any(value.strip().lower() in VAGUE for value in strings):
        raise CollaborationError("COLLAB_IMPACT_REQUIRED", "vague value")
```

- [ ] **Step 5: Gate implementation/publication reviews**

In `validate_review_receipt`, accept `changed_paths`; when `contract_impact_required(changed_paths)` is true, require `contract_impact` and call `validate_contract_impact`. Scope-acceptance receipts do not require impact because no produced change exists yet.

- [ ] **Step 6: Run GREEN and commit**

```bash
python -m pytest plugins/ak/tests/test_contract_impact.py plugins/ak/tests/test_collaboration_review.py -q
git add plugins/ak/schemas/contract-impact.schema.json plugins/ak/contracts/contract_impact.py plugins/ak/contracts/review.py plugins/ak/tests/test_contract_impact.py plugins/ak/scripts/validate_structure.py
git commit -m "feat(collaboration): require contract impact records"
```

---

### Task 6: Extended bundle-lock collaboration authority

**Files:**
- Modify: `plugins/ak/schemas/bundle-lock.schema.json`
- Modify: `plugins/ak/contracts/bundle.py`
- Modify: `plugins/ak/tests/test_bundle.py`
- Modify: `plugins/ak/tests/test_collaboration.py`

- [ ] **Step 1: Write failing legacy/enriched lock tests**

```python
# append to plugins/ak/tests/test_bundle.py
def test_legacy_lock_remains_valid() -> None:
    schema = json.loads((PACKAGE / "schemas/bundle-lock.schema.json").read_text(encoding="utf-8"))
    lock = make_lock("bundle-abc", "c" * 64, "1.0", {"topology": "split_file"}, "artifact_store://a05", "AP-1")
    jsonschema.validate(lock, schema)

def test_enriched_lock_records_portable_authority() -> None:
    lock = make_lock(
        "bundle-abc", "c" * 64, "1.0", {"topology": "split_file"}, "artifact_store://a05", "AP-1",
        lock_version="1.1", distribution_policy="artifact_store",
        artifact_reference="artifact_store://sms/A05/bundles/bundle-abc",
        bundle_approval_checksum="d" * 64,
        profile_rule_versions={"topology.split_file.backend_required": "1.0"},
        normalization_config_checksum="e" * 64,
    )
    assert lock["artifact_reference"].startswith("artifact_store://")
    assert lock["bundle_approval_checksum"] == "d" * 64

def test_enriched_lock_rejects_machine_absolute_location() -> None:
    schema = json.loads((PACKAGE / "schemas/bundle-lock.schema.json").read_text(encoding="utf-8"))
    lock = make_lock("bundle-abc", "c" * 64, "1.0", {"topology": "split_file"}, "D:/bundles/a05", "AP-1", lock_version="1.1", distribution_policy="artifact_store", artifact_reference="D:/bundles/a05")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(lock, schema)
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest plugins/ak/tests/test_bundle.py -q`

Expected: FAIL because `make_lock` does not accept enriched authority fields.

- [ ] **Step 3: Extend schema without invalidating legacy locks**

Keep the six current required fields. Add optional `lock_version`, `distribution_policy`, `artifact_reference`, `bundle_approval_checksum`, `profile_rule_versions`, `normalization_config_checksum`, and `supersedes_lock_checksum`. When `lock_version` is `1.1`, require distribution policy, artifact reference, approval checksum, rule versions, and normalization checksum. Artifact references use `^(artifact_store|shared_path|local_only|git_allowed)://` and never contain credentials.

- [ ] **Step 4: Extend `make_lock` with keyword-only options**

```python
def make_lock(bundle_id: str, checksum: str, schema_version: str, classification: dict[str, Any], approved_location: str, approval_record_id: str, *, lock_version: str | None = None, distribution_policy: str | None = None, artifact_reference: str | None = None, bundle_approval_checksum: str | None = None, profile_rule_versions: dict[str, str] | None = None, normalization_config_checksum: str | None = None, supersedes_lock_checksum: str | None = None) -> dict[str, Any]:
    value = {
        "bundle_id": bundle_id, "checksum": checksum, "schema_version": schema_version,
        "classification": classification, "approved_location": approved_location,
        "approval_record_id": approval_record_id,
    }
    optional = {
        "lock_version": lock_version, "distribution_policy": distribution_policy,
        "artifact_reference": artifact_reference, "bundle_approval_checksum": bundle_approval_checksum,
        "profile_rule_versions": profile_rule_versions,
        "normalization_config_checksum": normalization_config_checksum,
        "supersedes_lock_checksum": supersedes_lock_checksum,
    }
    value.update({key: item for key, item in optional.items() if item is not None})
    return value
```

- [ ] **Step 5: Run GREEN and commit**

```bash
python -m pytest plugins/ak/tests/test_bundle.py plugins/ak/tests/test_collaboration.py -q
git add plugins/ak/schemas/bundle-lock.schema.json plugins/ak/contracts/bundle.py plugins/ak/tests/test_bundle.py plugins/ak/tests/test_collaboration.py
git commit -m "feat(bundle): add collaboration authority to locks"
```

---

### Task 7: Collaboration CLI and English-canonical workflows

**Files:**
- Create: `plugins/ak/scripts/collaboration_cli.py`
- Create: `plugins/ak/tests/test_cli_collaboration.py`
- Modify: `plugins/ak/scripts/create_tasks.py`
- Modify: `plugins/ak/scripts/ak.py`
- Modify: `plugins/ak/scripts/validate_structure.py`
- Create: `docs/collaboration/contributor-workflow.md`
- Create: `docs/collaboration/application-team-workflow.md`
- Create: `docs/collaboration/contract-changes.md`
- Modify: `plugins/ak/skills/ak/SKILL.md`
- Modify: `.github/CODEOWNERS`

- [ ] **Step 1: Write failing CLI tests**

```python
# plugins/ak/tests/test_cli_collaboration.py
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
from collaboration_helpers import acceptance_receipt, application_package, candidate_task, impact, kit_package

PACKAGE = Path(__file__).resolve().parents[1]
AK = PACKAGE / "scripts" / "ak.py"

def run_cli(*args: str, expected: int = 0) -> dict:
    result = subprocess.run([sys.executable, str(AK), *args], cwd=PACKAGE, capture_output=True, text=True, encoding="utf-8")
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
    first, second = application_package("WP_ONE"), application_package("WP_TWO")
    second["write_paths"] = ["work/sql_data/module-orders/details"]
    write_json(tmp_path / "WP_ONE" / "work-package.json", first)
    write_json(tmp_path / "WP_TWO" / "work-package.json", second)
    data = run_cli("collaboration", "package", "conflicts", "--root", str(tmp_path), expected=2)
    assert data["conflicts"][0]["code"] == "COLLAB_WRITE_CONFLICT"

def test_review_validate_accepts_scope_receipt(tmp_path: Path) -> None:
    package = application_package()
    package_path = write_json(tmp_path / "work-package.json", package)
    receipt_path = write_json(tmp_path / "receipt.json", acceptance_receipt(package))
    data = run_cli("collaboration", "review", "validate", "--package", str(package_path), "--receipt", str(receipt_path))
    assert data["status"] == "APPROVED"

def test_package_project_binds_matching_candidate(tmp_path: Path) -> None:
    package = application_package()
    package_path = write_json(tmp_path / "work-package.json", package)
    receipt_path = write_json(tmp_path / "receipt.json", acceptance_receipt(package))
    run = tmp_path / "run"
    task_path = write_json(run / "tasks" / "candidate.json", candidate_task())
    data = run_cli("collaboration", "package", "project", "--package", str(package_path), "--receipt", str(receipt_path), "--run", str(run))
    assert data["projected_tasks"] == 1
    assert json.loads(task_path.read_text(encoding="utf-8"))["work_package_id"] == package["package_id"]

def test_impact_validate_checks_changed_path_file(tmp_path: Path) -> None:
    package = kit_package()
    changed = ["plugins/ak/schemas/work-package.schema.json"]
    package_path = write_json(tmp_path / "work-package.json", package)
    impact_path = write_json(tmp_path / "impact.json", impact(package))
    changed_path = write_json(tmp_path / "changed-paths.json", changed)
    data = run_cli("collaboration", "impact", "validate", "--package", str(package_path), "--impact", str(impact_path), "--changed-paths", str(changed_path))
    assert data["status"] == "VALID"
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest plugins/ak/tests/test_cli_collaboration.py -q`

Expected: FAIL because `ak.py` has no `collaboration` command.

- [ ] **Step 3: Implement the local deterministic CLI script**

`plugins/ak/scripts/collaboration_cli.py` exposes functions used by `ak.py`:

```python
def validate_package(path: Path) -> dict:
    package = load_work_package(path)
    return {"status": "VALID", "package_id": package["package_id"], "work_package_digest": work_package_digest(package)}

def scan_conflicts(root: Path) -> dict:
    packages = [load_work_package(path) for path in sorted(root.glob("*/work-package.json"))]
    conflicts = find_collaboration_conflicts(packages)
    return {"status": "CONFLICT" if conflicts else "VALID", "packages": len(packages), "conflicts": conflicts}

def validate_review(package_path: Path, receipt_path: Path) -> dict:
    package = load_work_package(package_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    validate_review_receipt(package, receipt)
    return {"status": receipt["decision"], "receipt_id": receipt["receipt_id"]}
```

Also implement `validate_impact`, `validate_handoff`, and `project_run_tasks`. Every function returns JSON-serializable data and raises `CollaborationError` with stable codes. No function shells out to Git, network tools, Access, SQL Server, or acquisition.

- [ ] **Step 4: Add bounded `ak.py collaboration` parsing and dispatch**

Implement the exact design commands:

```text
ak.py collaboration package validate --package <file>
ak.py collaboration package conflicts --root <dir>
ak.py collaboration package project --package <file> --receipt <file> --run <dir>
ak.py collaboration handoff validate --run <dir> --work-package-root <dir>
ak.py collaboration review validate --package <file> --receipt <file>
ak.py collaboration impact validate --package <file> --impact <file> --changed-paths <file>
```

Map `CollaborationError` to JSON such as `{"status":"ERROR","code":"COLLAB_PACKAGE_INVALID","message":"validation failed"}` and exit code 2. Success exits 0; detected conflicts exit 2.

- [ ] **Step 5: Bind accepted packages to generated run tasks**

Add `project_run_tasks(package, receipt, run)` to `scripts/collaboration_cli.py`. Validate a `scope_acceptance` receipt first. Read generated candidate tasks from `run/tasks/*.json`; match candidates by declared role, wave, phases, and modules; call `project_task`; overwrite only matched candidate files; fail if no task matches. Leave unmatched candidates unchanged for another package or legacy mode.

Add optional `--work-package`, `--acceptance-receipt`, and `--work-package-root` arguments to `create_tasks.py`. Without them, preserve current output exactly. With them, call the same projection function after normal deterministic task generation.

- [ ] **Step 6: Write English-canonical docs without pipeline duplication**

Each document starts with purpose, prerequisites, commands, failure handling, and links to `docs/architecture/investigation-pipeline.md`, `docs/architecture/extraction-bundle.md`, and `plugins/ak/references/orchestration-guide.md`.

- `contributor-workflow.md`: branch/worktree, package, TDD, impact, review, coordinator merge.
- `application-team-workflow.md`: approved bundle authority, disjoint scopes, handoffs, evidence merge, Phase checkpoint publication.
- `contract-changes.md`: changed-path triggers, compatibility categories, migration/fixture/test/docs/security requirements.

Do not copy the six-phase pipeline into these files. Update `SKILL.md` collaboration mode to require accepted work packages for new multi-developer flows. Add ownership for collaboration contracts/docs to `.github/CODEOWNERS`.

- [ ] **Step 7: Run GREEN and commit**

```bash
python -m pytest plugins/ak/tests/test_cli_collaboration.py plugins/ak/tests/test_cli_v27.py plugins/ak/tests/test_package_smoke.py -q
python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .
git add plugins/ak/scripts/collaboration_cli.py plugins/ak/scripts/create_tasks.py plugins/ak/scripts/ak.py plugins/ak/scripts/validate_structure.py plugins/ak/tests/test_cli_collaboration.py docs/collaboration plugins/ak/skills/ak/SKILL.md .github/CODEOWNERS
git commit -m "feat(collaboration): add CLI and team workflows"
```

---

### Task 8: Synthetic multi-contributor integration, release validation, and 2.7.2 metadata

**Files:**
- Create: `plugins/ak/fixtures/collaboration/two-contributor/`
- Create: `plugins/ak/tests/test_collaboration_integration.py`
- Modify: `plugins/ak/tests/test_package_smoke.py`
- Modify: `plugins/ak/scripts/validate_structure.py`
- Modify: `plugins/ak/specifications/package.json`
- Modify: `plugins/ak/.codex-plugin/plugin.json`
- Modify: `plugins/ak/.claude-plugin/plugin.json`
- Modify: `plugins/ak/skills/ak/SKILL.md`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Create the failing integration test before fixture files**

```python
# plugins/ak/tests/test_collaboration_integration.py
from __future__ import annotations
import json
from pathlib import Path
from collaboration import find_collaboration_conflicts, integration_order, load_work_package, project_task
from contract_impact import validate_contract_impact
from review import validate_review_receipt

PACKAGE = Path(__file__).resolve().parents[1]
FIXTURE = PACKAGE / "fixtures" / "collaboration" / "two-contributor"

def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def test_two_contributors_share_authority_and_keep_disjoint_scopes() -> None:
    packages = [load_work_package(path) for path in sorted((FIXTURE / "collaboration" / "work-packages").glob("*/work-package.json"))]
    assert len(packages) == 2
    assert find_collaboration_conflicts(packages) == []
    for package in packages:
        receipt = load(FIXTURE / "collaboration" / "reviews" / f"RR-{package['package_id']}.json")
        validate_review_receipt(package, receipt)
        task = load(FIXTURE / "run" / "candidate-tasks" / f"{package['package_id']}.json")
        projected = project_task(package, task)
        assert projected["work_package_id"] == package["package_id"]

def test_dependency_order_is_deterministic() -> None:
    packages = [load_work_package(path) for path in sorted((FIXTURE / "collaboration" / "work-packages").glob("*/work-package.json"))]
    expected = load(FIXTURE / "expected-integration-order.json")
    assert integration_order(packages) == expected == ["WP_SYN_SQL", "WP_SYN_UI"]

def test_contract_impact_fixture_is_bound_to_a_real_package() -> None:
    package = load_work_package(FIXTURE / "contract-fixture" / "work-package.json")
    impact = load(FIXTURE / "contract-fixture" / "contract-impact.json")
    validate_contract_impact(package, impact, impact["changed_paths"])

def test_fixture_contains_no_prohibited_binary_or_secret() -> None:
    prohibited = {".mdb", ".accdb", ".adp", ".mde", ".accde", ".bak", ".mdf", ".ldf", ".dsn"}
    assert not [path for path in FIXTURE.rglob("*") if path.is_file() and path.suffix.lower() in prohibited]
    text = "\n".join(path.read_text(encoding="utf-8") for path in FIXTURE.rglob("*") if path.is_file())
    assert "password=" not in text.lower()
    assert "D:\\" not in text
```

- [ ] **Step 2: Run RED**

Run: `python -m pytest plugins/ak/tests/test_collaboration_integration.py -q`

Expected: FAIL because the fixture directory does not exist.

- [ ] **Step 3: Add the exact synthetic fixture**

Create:

```text
two-contributor/
├─ bundle.lock.json
├─ expected-integration-order.json
├─ collaboration/
│  ├─ work-packages/WP_SYN_SQL/work-package.json
│  ├─ work-packages/WP_SYN_UI/work-package.json
│  ├─ reviews/RR-WP_SYN_SQL.json
│  ├─ reviews/RR-WP_SYN_UI.json
│  └─ conflicts/
├─ contract-fixture/
│  ├─ work-package.json
│  └─ contract-impact.json
└─ run/candidate-tasks/
   ├─ WP_SYN_SQL.json
   └─ WP_SYN_UI.json
```

Both packages use the same enriched synthetic `artifact_store://fixture/SYN/bundles/bundle-synthetic` authority, disjoint roles/write paths/evidence namespaces, and dependency `WP_SYN_UI` after `WP_SYN_SQL`. Receipts use exact package digests and successful validation commands. The contract-impact fixture is bound to the separate real package in `contract-fixture/work-package.json`; it does not participate in the two application-package merge.

- [ ] **Step 4: Add package-level integration assertions**

Extend `test_package_smoke.py` to run:

```python
result = run_script("ak.py", "collaboration", "package", "conflicts", "--root", str(fixture / "collaboration" / "work-packages"))
assert json.loads(result.stdout)["status"] == "VALID"
```

Register every new schema, contract, script, test, fixture root, and collaboration document in `validate_structure.py`. Keep the existing Windows/Linux GitHub Actions matrix; the normal pytest step now executes this synthetic integration test on both operating systems, so no duplicate workflow step is added.

- [ ] **Step 5: Bump lock-step metadata and changelog**

Set version `2.7.2` in:

- `plugins/ak/specifications/package.json`
- `plugins/ak/.codex-plugin/plugin.json`
- `plugins/ak/.claude-plugin/plugin.json`
- visible heading in `plugins/ak/skills/ak/SKILL.md`

Add `CHANGELOG.md` entry dated `2026-07-28`:

```markdown
## [2.7.2] - 2026-07-28

### Added
- Canonical human/agent work packages, review receipts, and contract-impact records.
- Deterministic collaboration conflict checks, runtime task projection, and English team workflows.

### Changed
- Bundle locks may carry portable multi-developer artifact authority while legacy locks remain valid.

### Security
- Production bundles remain outside Git by default; scoped paths, evidence namespaces, publication authority, and reviewer independence are validated before integration.
```

- [ ] **Step 6: Run focused, full, and structural verification**

```bash
python -m pytest plugins/ak/tests/test_collaboration_integration.py plugins/ak/tests/test_cli_collaboration.py -q
python -m pytest -q
python -m compileall -q plugins/ak/contracts plugins/ak/scripts plugins/ak/tests
python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .
git diff --check
```

Expected: all tests PASS; compile PASS; structure validation reports zero errors; diff check produces no output.

- [ ] **Step 7: Commit Task 8**

```bash
git add plugins/ak/fixtures/collaboration plugins/ak/tests/test_collaboration_integration.py plugins/ak/tests/test_package_smoke.py plugins/ak/scripts/validate_structure.py plugins/ak/specifications/package.json plugins/ak/.codex-plugin/plugin.json plugins/ak/.claude-plugin/plugin.json plugins/ak/skills/ak/SKILL.md CHANGELOG.md
git commit -m "chore(ak): validate collaboration release 2.7.2"
```

---

## Final Verification Gate

Before requesting merge:

```bash
python -m pytest -q
python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .
git diff --check main..HEAD
git status --short
```

Review the eight commits in dependency order. Confirm no Plan 3B analyzer, Graphify migration, live Access/SQL behavior, artifact upload, or GitHub-specific API was added. Use `superpowers:requesting-code-review`, then `superpowers:finishing-a-development-branch` only after all verification is fresh and green.
