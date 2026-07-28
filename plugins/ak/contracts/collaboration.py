from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import jsonschema

PACKAGE = Path(__file__).resolve().parents[1]
CANONICAL_OUTPUT_MARKERS = tuple(f"_Phase{number}_" for number in range(1, 7))
FORBIDDEN_SUFFIXES = {
    ".mdb",
    ".accdb",
    ".adp",
    ".mde",
    ".accde",
    ".bak",
    ".mdf",
    ".ldf",
    ".dsn",
    ".env",
}
WINDOWS_RESERVED_TASK_NAMES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{prefix}{number}"
    for prefix in ("COM", "LPT")
    for number in range(1, 10)
}


class CollaborationError(ValueError):
    def __init__(self, code: str, message: str, *, detail: Any = None) -> None:
        self.code = code
        self.detail = message if detail is None else detail
        super().__init__(f"{code}: {message}")


def _schema(name: str) -> dict[str, Any]:
    return json.loads((PACKAGE / "schemas" / name).read_text(encoding="utf-8"))


def _validate_task(value: dict[str, Any]) -> None:
    try:
        jsonschema.validate(value, _schema('task.schema.json'))
    except jsonschema.ValidationError as exc:
        raise CollaborationError('COLLAB_PROJECTION_EXPANDED', exc.message) from exc

def work_package_digest(value: dict[str, Any]) -> str:
    scoped = {key: item for key, item in value.items() if key != "created_at"}
    encoded = json.dumps(
        scoped, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_relative(path: str) -> None:
    normalized = path.replace("\\", "/")
    parsed = PurePosixPath(normalized)
    if (
        parsed.is_absolute()
        or PureWindowsPath(path).drive
        or ".." in parsed.parts
        or not parsed.parts
    ):
        raise CollaborationError("COLLAB_PATH_ESCAPE", path)


def validate_work_package(value: dict[str, Any]) -> None:
    if "authority" not in value:
        raise CollaborationError("COLLAB_AUTHORITY_MISSING", "authority")
    try:
        jsonschema.validate(value, _schema("work-package.schema.json"))
    except jsonschema.ValidationError as exc:
        raise CollaborationError("COLLAB_PACKAGE_INVALID", exc.message) from exc

    required_authority_kind = {
        "kit_code": "repository_revision",
        "kit_contract": "repository_revision",
        "kit_docs": "repository_revision",
        "application_evidence": "approved_bundle",
        "application_docs": "approved_bundle",
        "application_qa": "approved_bundle",
        "mixed_pilot": "mixed",
    }[value["work_kind"]]
    if value["authority"]["kind"] != required_authority_kind:
        raise CollaborationError("COLLAB_PACKAGE_INVALID", "authority")

    paths = (
        value["input_paths"]
        + value["write_paths"]
        + [item["path"] for item in value["expected_artifacts"]]
    )
    for path in paths:
        _validate_relative(path)
        normalized = path.replace("\\", "/").lower()
        if (
            PurePosixPath(normalized).suffix in FORBIDDEN_SUFFIXES
            or normalized.startswith("secrets/")
            or "/secrets/" in normalized
        ):
            raise CollaborationError("COLLAB_SECRET_OR_BINARY_PROHIBITED", path)

    if value["publication_policy"] == "scoped_only":
        for path in value["write_paths"]:
            normalized = path.replace("\\", "/")
            if normalized.startswith("outputs/") and any(
                marker in normalized for marker in CANONICAL_OUTPUT_MARKERS
            ):
                raise CollaborationError("COLLAB_PUBLICATION_FORBIDDEN", path)


def load_work_package(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_work_package(value)
    return value

def _contains(parent: str, child: str) -> bool:
    left = PurePosixPath(parent.replace("\\", "/"))
    right = PurePosixPath(child.replace("\\", "/"))
    return left == right or left in right.parents

def _task_logical_path(path: str, *, allow_parent_prefix: bool) -> str:
    raw_parts = tuple(path.split('/'))
    if (
        '\\' in path
        or path.startswith('./')
        or '//' in path
        or path.endswith('/')
        or ':' in path
        or '.' in raw_parts
    ):
        raise CollaborationError('COLLAB_PROJECTION_EXPANDED', 'task path')
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or PureWindowsPath(path).drive or not path:
        raise CollaborationError('COLLAB_PROJECTION_EXPANDED', 'task path')
    if (
        allow_parent_prefix
        and raw_parts[:2] == ('..', '..')
        and raw_parts[2:]
        and '..' not in raw_parts[2:]
    ):
        logical_parts = raw_parts[2:]
    elif '..' in raw_parts:
        raise CollaborationError('COLLAB_PROJECTION_EXPANDED', 'task path')
    else:
        logical_parts = raw_parts
    if any(
        not part.rstrip(' .') or part.endswith((' ', '.'))
        for part in logical_parts
    ):
        raise CollaborationError('COLLAB_PROJECTION_EXPANDED', 'task path')
    if any(
        part.rstrip(' .').split('.', 1)[0].rstrip(' .').upper()
        in WINDOWS_RESERVED_TASK_NAMES
        for part in logical_parts
    ):
        raise CollaborationError('COLLAB_PROJECTION_EXPANDED', 'task path')
    return PurePosixPath(*logical_parts).as_posix()

def _inside_any(
    path: str, allowed: list[str], *, allow_parent_prefix: bool
) -> bool:
    logical = _task_logical_path(path, allow_parent_prefix=allow_parent_prefix)
    return any(_contains(parent, logical) for parent in allowed)

def project_task(package: dict[str, Any], task: dict[str, Any]) -> dict[str, Any]:
    validate_work_package(package)
    scope = package['scope']
    authority = package['authority']
    package_namespace = package['evidence_namespace']
    bindings = {
        'work_package_id': package['package_id'],
        'work_package_digest': work_package_digest(package),
        'projection_version': '1.0',
    }
    projection_fields = tuple(bindings)
    has_projection = any(field in task for field in projection_fields)
    validation_task = task
    if (
        package_namespace is None
        and task.get('evidence_namespace') is None
        and not has_projection
    ):
        validation_task = dict(task)
        validation_task.update(bindings)
    _validate_task(validation_task)
    if has_projection and (
        not all(field in task for field in projection_fields)
        or any(task[field] != bindings[field] for field in projection_fields)
    ):
        raise CollaborationError('COLLAB_PROJECTION_EXPANDED', 'work package binding')
    task_namespace = task['evidence_namespace']
    namespace_valid = (
        task_namespace is None
        if package_namespace is None
        else isinstance(task_namespace, str)
        and (
            task_namespace == package_namespace
            or task_namespace.startswith(package_namespace + '-')
        )
    )
    checks = (
        (
            authority['kind'] not in {'approved_bundle', 'mixed'}
            or task['app_id'] == authority['app_id'],
            'app_id',
        ),
        (task['role'] in scope['roles'], 'role'),
        (task['wave_id'] in scope['wave_ids'], 'wave_id'),
        (set(task.get('phase_targets', [])).issubset(scope['phase_targets']), 'phase_targets'),
        (set(task.get('module_targets', [])).issubset(scope['module_targets']), 'module_targets'),
        (
            all(
                _inside_any(
                    path, package['input_paths'], allow_parent_prefix=True
                )
                for path in task['input_paths']
            ),
            'input_paths',
        ),
        (
            all(
                _inside_any(
                    path, package['write_paths'], allow_parent_prefix=False
                )
                for path in task['write_paths']
            ),
            'write_paths',
        ),
        (namespace_valid, 'evidence_namespace'),
    )
    for valid, field in checks:
        if not valid:
            raise CollaborationError('COLLAB_PROJECTION_EXPANDED', field)
    projected = deepcopy(task)
    projected.update(bindings)
    _validate_task(projected)
    return projected

def _authority_key(package: dict[str, Any]) -> str:
    return json.dumps(
        package["authority"],
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )

def integration_order(
    packages: list[dict[str, Any]],
    *,
    integrated_package_ids: set[str] | None = None,
) -> list[str]:
    integrated = integrated_package_ids or set()
    grouped: dict[str, list[dict[str, Any]]] = {}
    for item in packages:
        grouped.setdefault(item["package_id"], []).append(item)
    invalid_ids = [
        package_id
        for package_id in sorted(grouped)
        if len({work_package_digest(item) for item in grouped[package_id]}) > 1
    ]
    if invalid_ids:
        raise CollaborationError(
            "COLLAB_PACKAGE_INVALID",
            f"duplicate package ids with different digests: {', '.join(invalid_ids)}",
            detail=invalid_ids,
        )
    by_id = {
        package_id: grouped[package_id][0]
        for package_id in sorted(grouped)
    }
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
            elif dependency not in integrated:
                raise CollaborationError(
                    "COLLAB_PACKAGE_INVALID",
                    f"{package_id} depends on unresolved dependency {dependency}",
                    detail=[package_id, dependency],
                )
        visiting.remove(package_id)
        visited.add(package_id)
        ordered.append(package_id)

    for package_id in sorted(by_id):
        visit(package_id)
    return ordered

def find_collaboration_conflicts(
    packages: list[dict[str, Any]],
    *,
    integrated_package_ids: set[str] | None = None,
) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    integrated = integrated_package_ids or set()
    try:
        integration_order(packages, integrated_package_ids=integrated)
    except CollaborationError as exc:
        detail = exc.detail
        conflict_packages = list(detail) if isinstance(detail, list) else [str(detail)]
        dependency_issue = {"code": exc.code, "packages": conflict_packages}
        if exc.code != "COLLAB_DEPENDENCY_CYCLE":
            return [dependency_issue]
        issues.append(dependency_issue)
    ordered = sorted(
        {item["package_id"]: item for item in packages}.values(),
        key=lambda item: item["package_id"],
    )
    for index, left in enumerate(ordered):
        for right in ordered[index + 1:]:
            sequential = (
                left["package_id"] in right.get("dependencies", [])
                and left["package_id"] in integrated
            ) or (
                right["package_id"] in left.get("dependencies", [])
                and right["package_id"] in integrated
            )
            if not sequential and any(
                _contains(left_path, right_path)
                or _contains(right_path, left_path)
                for left_path in left["write_paths"]
                for right_path in right["write_paths"]
            ):
                issues.append(
                    {
                        "code": "COLLAB_WRITE_CONFLICT",
                        "packages": [left["package_id"], right["package_id"]],
                    }
                )
            left_namespace = left.get("evidence_namespace")
            right_namespace = right.get("evidence_namespace")
            if left_namespace and right_namespace and (
                left_namespace == right_namespace
                or left_namespace.startswith(right_namespace + "-")
                or right_namespace.startswith(left_namespace + "-")
            ):
                issues.append(
                    {
                        "code": "COLLAB_EVIDENCE_CONFLICT",
                        "packages": [left["package_id"], right["package_id"]],
                    }
                )
            if _authority_key(left) != _authority_key(right):
                issues.append(
                    {
                        "code": "COLLAB_AUTHORITY_MISMATCH",
                        "packages": [left["package_id"], right["package_id"]],
                    }
                )
    return sorted(issues, key=lambda item: (item["code"], item["packages"]))
