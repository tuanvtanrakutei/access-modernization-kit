from __future__ import annotations

from copy import deepcopy
from itertools import permutations
import json
from pathlib import Path

import jsonschema
import pytest

from collaboration import (
    CollaborationError,
    find_collaboration_conflicts,
    integration_order,
    load_work_package,
    project_task,
    validate_work_package,
    work_package_digest,
)
from collaboration_helpers import (
    application_package,
    candidate_task,
    kit_package,
    mixed_package,
)


TOP_LEVEL_FIELDS = {
    "schema_version",
    "package_id",
    "title",
    "objective",
    "work_kind",
    "authority",
    "scope",
    "dependencies",
    "input_paths",
    "write_paths",
    "expected_artifacts",
    "evidence_namespace",
    "validation_commands",
    "coordinator",
    "reviewer",
    "publication_policy",
    "security_constraints",
    "created_by",
    "created_at",
}
SCOPE_FIELDS = {
    "roles",
    "wave_ids",
    "phase_targets",
    "module_targets",
    "profile_targets",
    "adapter_targets",
    "document_targets",
}


def schema() -> dict:
    path = Path(__file__).resolve().parents[1] / "schemas" / "work-package.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))

def conflict_schema() -> dict:
    path = Path(__file__).resolve().parents[1] / "schemas" / "conflict.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))

def conflict_record() -> dict:
    return {
        "conflict_id": "SYN-CONFLICT-001",
        "run_id": "SYN-RUN-001",
        "app_id": "SYN",
        "topic": "COLLAB_WRITE_CONFLICT",
        "severity": "HIGH",
        "status": "OPEN",
        "observations": [
            {"evidence_id": "SYN-EVIDENCE-001", "statement": "First claim"},
            {"evidence_id": "SYN-EVIDENCE-002", "statement": "Second claim"},
        ],
        "created_at": "2026-07-28T00:00:00Z",
    }

def codes(packages: list[dict]) -> set[str]:
    return {item["code"] for item in find_collaboration_conflicts(packages)}


@pytest.mark.parametrize(
    "package_factory", [kit_package, application_package, mixed_package]
)
def test_synthetic_authority_variants_validate(package_factory) -> None:
    validate_work_package(package_factory())


def test_expected_artifact_must_be_inside_package_write_scope() -> None:
    package = application_package()
    package["expected_artifacts"][0]["path"] = "work/other/result.json"

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        validate_work_package(package)


def test_expected_artifact_identities_are_casefold_unique() -> None:
    package = application_package()
    duplicate = deepcopy(package["expected_artifacts"][0])
    duplicate["path"] = duplicate["path"].replace("result.json", "RESULT.JSON")
    package["expected_artifacts"].append(duplicate)

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        validate_work_package(package)


def test_invalid_artifact_contract_fails_before_scope_review() -> None:
    package = application_package()
    package["expected_artifacts"][0]["path"] = "work/other/result.json"
    task = candidate_task()
    task["role"] = "workflow"

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        project_task(package, task)


def test_digest_ignores_created_at_and_dict_order_only() -> None:
    first = kit_package()
    second = dict(reversed(list(first.items())))
    second["authority"] = dict(reversed(list(second["authority"].items())))
    second["created_at"] = "2030-01-01T00:00:00Z"

    assert work_package_digest(first) == work_package_digest(second)

    second["title"] = "Different semantic scope"
    assert work_package_digest(first) != work_package_digest(second)


@pytest.mark.parametrize(
    "bad_path",
    [
        "safe\\file.txt",
        "/absolute/file.txt",
        "C:/drive/file.txt",
        "C:relative/file.txt",
        "C:",
        "//server/share/file.txt",
        "safe/../escape.txt",
        "safe/./file.txt",
        "safe//file.txt",
        "safe/file.txt/",
        "safe/" + chr(1) + "file.txt",
        "safe/" + chr(127) + "file.txt",
        "safe/file.txt:stream",
        "safe/file<.txt",
        "safe/file>.txt",
        'safe/file".txt',
        "safe/file|.txt",
        "safe/file?.txt",
        "safe/file*.txt",
        "safe/CON/file.txt",
        "safe/prn.txt",
        "safe/file.txt ",
        "safe/file.txt.",
    ],
)
@pytest.mark.parametrize(
    "collection", ["input_paths", "write_paths", "expected_artifacts"]
)
def test_package_paths_use_canonical_cross_platform_rules(
    collection: str, bad_path: str
) -> None:
    package = kit_package()
    if collection == "expected_artifacts":
        package[collection][0]["path"] = bad_path
    else:
        package[collection] = [bad_path]

    with pytest.raises(CollaborationError, match="COLLAB_PATH_ESCAPE"):
        validate_work_package(package)

@pytest.mark.parametrize(
    ("collection", "path"),
    [
        ("input_paths", "inputs/\u6ce8\u6587\u7167\u4f1a.sql"),
        ("write_paths", "work/\u7d50\u679c"),
        ("expected_artifacts", "work/\u7d50\u679c.json"),
    ],
)
def test_package_paths_preserve_japanese_unicode(
    collection: str, path: str
) -> None:
    package = kit_package()
    if collection == "expected_artifacts":
        package[collection][0]["path"] = path
        package["write_paths"] = ["work"]
    elif collection == "write_paths":
        package[collection] = [path]
        package["expected_artifacts"][0]["path"] = f"{path}/result.json"
    else:
        package[collection] = [path]

    validate_work_package(package)


@pytest.mark.parametrize("command", [" ", "\t"])
def test_validation_commands_must_be_nonblank(command: str) -> None:
    package = kit_package()
    package["validation_commands"] = [command]

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        validate_work_package(package)


def test_validation_commands_preserve_unicode() -> None:
    package = kit_package()
    package["validation_commands"] = ["python -m pytest \u30c6\u30b9\u30c8/\u6ce8\u6587.py -q"]

    validate_work_package(package)


@pytest.mark.parametrize("phase", range(1, 7))
def test_scoped_worker_cannot_claim_canonical_phase_output(phase: int) -> None:
    package = application_package()
    package["write_paths"].append(f"outputs/SYN_Phase{phase}_Canonical_EN.md")

    with pytest.raises(CollaborationError, match="COLLAB_PUBLICATION_FORBIDDEN"):
        validate_work_package(package)


def test_scoped_worker_cannot_bypass_publication_with_backslashes() -> None:
    package = application_package()
    package["write_paths"].append("outputs\\SYN_Phase1_Canonical_EN.md")

    with pytest.raises(CollaborationError, match="COLLAB_PATH_ESCAPE"):
        validate_work_package(package)


def test_missing_authority_has_stable_code() -> None:
    package = kit_package()
    del package["authority"]

    with pytest.raises(CollaborationError, match="COLLAB_AUTHORITY_MISSING"):
        validate_work_package(package)


@pytest.mark.parametrize(
    "path",
    [
        "sources/live.mdb",
        "sources/live.accdb",
        "sources/live.adp",
        "sources/live.mde",
        "sources/live.accde",
        "sources/backup.bak",
        "sources/database.mdf",
        "sources/database.ldf",
        "sources/connection.dsn",
        "sources/password.env",
        "secrets/token.txt",
    ],
)
def test_prohibited_binary_or_secret_reference_is_blocked(path: str) -> None:
    package = kit_package()
    package["input_paths"] = [path]

    with pytest.raises(
        CollaborationError, match="COLLAB_SECRET_OR_BINARY_PROHIBITED"
    ):
        validate_work_package(package)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("package_id", "lowercase"),
        ("work_kind", "future_kind"),
        ("publication_policy", "worker_can_publish"),
    ],
)
def test_other_schema_failures_have_stable_code(field: str, value: str) -> None:
    package = kit_package()
    package[field] = value

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        validate_work_package(package)


def test_duplicate_validation_commands_are_invalid() -> None:
    package = kit_package()
    package["validation_commands"].append(package["validation_commands"][0])

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        validate_work_package(package)


@pytest.mark.parametrize("field", ["coordinator", "reviewer", "created_by"])
@pytest.mark.parametrize("value", [" ", "	", " identity", "identity "])
def test_work_package_identities_must_be_nonblank(
    field: str, value: str
) -> None:
    package = kit_package()
    package[field] = value

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        validate_work_package(package)


def test_work_package_identities_preserve_unicode() -> None:
    package = kit_package()
    package["coordinator"] = "調整担当"
    package["reviewer"] = "査読担当"
    package["created_by"] = "計画担当"

    validate_work_package(package)


def test_unknown_top_level_field_is_invalid() -> None:
    package = kit_package()
    package["future_field"] = True

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        validate_work_package(package)


def test_invalid_sha256_authority_field_is_invalid() -> None:
    package = application_package()
    package["authority"]["checksum"] = "A" * 64

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
        validate_work_package(package)


def test_schema_is_closed_draft_2020_12_contract() -> None:
    value = schema()
    jsonschema.Draft202012Validator.check_schema(value)

    assert value["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert value["additionalProperties"] is False
    assert set(value["required"]) == TOP_LEVEL_FIELDS
    assert set(value["properties"]["scope"]["required"]) == SCOPE_FIELDS
    assert value["properties"]["package_id"]["pattern"] == "^[A-Z0-9_-]+$"
    assert value["properties"]["work_kind"]["enum"] == [
        "kit_code",
        "kit_contract",
        "kit_docs",
        "application_evidence",
        "application_docs",
        "application_qa",
        "mixed_pilot",
    ]
    assert value["properties"]["publication_policy"]["enum"] == [
        "scoped_only",
        "document_owner",
        "coordinator_only",
    ]
    assert value["properties"]["validation_commands"]["uniqueItems"] is True
    assert {
        item["properties"]["kind"]["const"]
        for item in value["properties"]["authority"]["oneOf"]
    } == {"repository_revision", "approved_bundle", "mixed"}


def test_load_work_package_reads_utf8_validates_and_returns_dict(tmp_path: Path) -> None:
    package = kit_package()
    package["title"] = "Synthetic 日本語 package"
    path = tmp_path / "work-package.json"
    path.write_text(json.dumps(package, ensure_ascii=False), encoding="utf-8")

    assert load_work_package(path) == package

def test_overlapping_write_paths_are_blocked() -> None:
    first, second = application_package("WP_ONE"), application_package("WP_TWO")
    second["write_paths"] = ["work/sql_data/module-orders/details"]
    assert "COLLAB_WRITE_CONFLICT" in codes([first, second])


def test_write_conflict_containment_is_case_insensitive() -> None:
    first, second = application_package("WP_ONE"), application_package("WP_TWO")
    first["write_paths"] = ["work/Orders"]
    second["write_paths"] = ["work/orders/details"]

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
    first = application_package("WP_ONE")
    second = application_package("WP_TWO")
    first["dependencies"], second["dependencies"] = ["WP_TWO"], ["WP_ONE"]
    second["authority"]["app_id"] = "OTHER"

    with pytest.raises(CollaborationError, match="COLLAB_DEPENDENCY_CYCLE") as error:
        integration_order([first, second])

    assert error.value.detail == "WP_ONE"
    assert find_collaboration_conflicts([first, second]) == [
        {
            "code": "COLLAB_AUTHORITY_MISMATCH",
            "packages": ["WP_ONE", "WP_TWO"],
        },
        {"code": "COLLAB_DEPENDENCY_CYCLE", "packages": ["WP_ONE"]},
        {
            "code": "COLLAB_EVIDENCE_CONFLICT",
            "packages": ["WP_ONE", "WP_TWO"],
        },
        {
            "code": "COLLAB_WRITE_CONFLICT",
            "packages": ["WP_ONE", "WP_TWO"],
        },
    ]

def test_integration_order_is_dependency_stable() -> None:
    first, second = kit_package("WP_ONE"), kit_package("WP_TWO")
    second["dependencies"] = ["WP_ONE"]
    assert integration_order([second, first]) == ["WP_ONE", "WP_TWO"]

def test_integrated_predecessor_allows_sequential_overlap() -> None:
    first, second = kit_package("WP_ONE"), kit_package("WP_TWO")
    first["write_paths"] = ["docs/collaboration"]
    second["write_paths"] = ["docs/collaboration/contributor-workflow.md"]
    second["dependencies"] = ["WP_ONE"]
    conflicts = find_collaboration_conflicts(
        [first, second], integrated_package_ids={"WP_ONE"}
    )
    assert "COLLAB_WRITE_CONFLICT" not in {item["code"] for item in conflicts}

def test_reverse_lexical_integrated_predecessor_allows_sequential_overlap() -> None:
    predecessor, dependent = kit_package("WP_Z"), kit_package("WP_A")
    predecessor["write_paths"] = ["docs/collaboration"]
    dependent["write_paths"] = ["docs/collaboration/contributor-workflow.md"]
    dependent["dependencies"] = ["WP_Z"]

    assert find_collaboration_conflicts(
        [dependent, predecessor], integrated_package_ids={"WP_Z"}
    ) == []

def test_sequential_packages_still_require_identical_authority() -> None:
    predecessor = application_package("WP_A")
    dependent = application_package("WP_Z")
    dependent["dependencies"] = ["WP_A"]
    dependent["write_paths"] = ["work/isolated/WP_Z"]
    dependent["evidence_namespace"] = "SYN-P1-ISOLATED-Z"
    dependent["authority"]["app_id"] = "OTHER"

    assert find_collaboration_conflicts(
        [dependent, predecessor], integrated_package_ids={"WP_A"}
    ) == [
        {
            "code": "COLLAB_AUTHORITY_MISMATCH",
            "packages": ["WP_A", "WP_Z"],
        }
    ]

@pytest.mark.parametrize(
    ("package_factory", "field", "value"),
    [
        (application_package, "app_id", "OTHER"),
        (application_package, "bundle_lock_digest", "d" * 64),
        (application_package, "approval_record_id", "AP-SYN-2"),
        (application_package, "distribution_policy", "shared_path"),
        (
            application_package,
            "artifact_reference",
            "artifact_store://fixture/SYN/bundle-b",
        ),
        (mixed_package, "repository", "other-repository"),
        (mixed_package, "base_revision", "deadbeef"),
        (mixed_package, "app_id", "OTHER"),
        (mixed_package, "bundle_id", "bundle-" + "d" * 64),
        (mixed_package, "checksum", "d" * 64),
        (mixed_package, "bundle_lock_digest", "d" * 64),
        (mixed_package, "approval_record_id", "AP-SYN-2"),
        (mixed_package, "distribution_policy", "shared_path"),
        (
            mixed_package,
            "artifact_reference",
            "artifact_store://fixture/SYN/bundle-b",
        ),
    ],
)
def test_authority_comparison_uses_complete_validated_object(
    package_factory, field: str, value: str
) -> None:
    first = package_factory("WP_ONE")
    second = package_factory("WP_TWO")
    second["write_paths"] = ["work/isolated/WP_TWO"]
    second["evidence_namespace"] = "SYN-P1-ISOLATED-TWO"
    second["authority"][field] = value

    assert find_collaboration_conflicts([second, first]) == [
        {
            "code": "COLLAB_AUTHORITY_MISMATCH",
            "packages": ["WP_ONE", "WP_TWO"],
        }
    ]

@pytest.mark.parametrize("reverse", [False, True])
def test_differing_duplicate_package_ids_are_rejected_deterministically(
    reverse: bool,
) -> None:
    first = kit_package("WP_DUP")
    second = deepcopy(first)
    second["title"] = "Different semantic package"
    packages = [second, first] if reverse else [first, second]

    assert find_collaboration_conflicts(packages) == [
        {"code": "COLLAB_PACKAGE_INVALID", "packages": ["WP_DUP"]}
    ]

def test_exact_duplicate_packages_are_deduplicated() -> None:
    package = kit_package("WP_DUP")

    assert integration_order([deepcopy(package), package]) == ["WP_DUP"]
    assert find_collaboration_conflicts([package, deepcopy(package)]) == []

def test_multiple_differing_duplicate_ids_are_permutation_stable() -> None:
    alpha_first = kit_package("WP_ALPHA")
    alpha_second = deepcopy(alpha_first)
    alpha_second["title"] = "Different alpha package"
    zeta_first = kit_package("WP_ZETA")
    zeta_second = deepcopy(zeta_first)
    zeta_second["title"] = "Different zeta package"
    expected = [
        {
            "code": "COLLAB_PACKAGE_INVALID",
            "packages": ["WP_ALPHA", "WP_ZETA"],
        }
    ]

    for ordered in permutations(
        [alpha_first, alpha_second, zeta_first, zeta_second]
    ):
        packages = list(ordered)
        with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID") as error:
            integration_order(packages)
        assert error.value.detail == ["WP_ALPHA", "WP_ZETA"]
        assert find_collaboration_conflicts(packages) == expected

def test_unresolved_dependency_is_rejected_by_integration_order() -> None:
    package = kit_package("WP_ONE")
    package["dependencies"] = ["WP_MISSING"]

    with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID") as error:
        integration_order([package])

    assert error.value.detail == ["WP_ONE", "WP_MISSING"]

def test_unresolved_dependency_is_reported_by_conflict_detection() -> None:
    package = kit_package("WP_ONE")
    package["dependencies"] = ["WP_MISSING"]

    assert find_collaboration_conflicts([package]) == [
        {
            "code": "COLLAB_PACKAGE_INVALID",
            "packages": ["WP_ONE", "WP_MISSING"],
        }
    ]

def test_integrated_dependency_satisfies_order_and_conflict_detection() -> None:
    package = kit_package("WP_ONE")
    package["dependencies"] = ["WP_INTEGRATED"]

    assert integration_order(
        [package], integrated_package_ids={"WP_INTEGRATED"}
    ) == ["WP_ONE"]
    assert find_collaboration_conflicts(
        [package], integrated_package_ids={"WP_INTEGRATED"}
    ) == []

def test_evidence_namespace_schema_rejects_empty_string() -> None:
    package = application_package()
    package["evidence_namespace"] = ""

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(package, schema())

def test_empty_evidence_namespaces_cannot_bypass_validation() -> None:
    packages = [application_package("WP_ONE"), application_package("WP_TWO")]
    for package in packages:
        package["evidence_namespace"] = ""

    for package in packages:
        with pytest.raises(CollaborationError, match="COLLAB_PACKAGE_INVALID"):
            validate_work_package(package)

@pytest.mark.parametrize("reverse", [False, True])
def test_conflict_payloads_are_exact_and_permutation_stable(reverse: bool) -> None:
    first = application_package("WP_ONE")
    second = application_package("WP_TWO")
    second["authority"]["app_id"] = "OTHER"
    packages = [second, first] if reverse else [first, second]

    assert find_collaboration_conflicts(packages) == [
        {
            "code": "COLLAB_AUTHORITY_MISMATCH",
            "packages": ["WP_ONE", "WP_TWO"],
        },
        {
            "code": "COLLAB_EVIDENCE_CONFLICT",
            "packages": ["WP_ONE", "WP_TWO"],
        },
        {
            "code": "COLLAB_WRITE_CONFLICT",
            "packages": ["WP_ONE", "WP_TWO"],
        },
    ]

def test_legacy_task_reported_conflict_is_valid() -> None:
    record = conflict_record()
    record["reported_by_task"] = "SYN-TASK-001"

    jsonschema.validate(record, conflict_schema())


def test_legacy_open_conflict_allows_null_closure_fields() -> None:
    record = conflict_record()
    record["reported_by_task"] = "SYN-TASK-001"
    record.update(
        {
            "resolution": None,
            "decision_source": None,
            "resolved_by_task": None,
            "resolved_by_work_package": None,
            "resolved_at": None,
        }
    )

    jsonschema.validate(record, conflict_schema())

def test_work_package_reported_conflict_is_valid() -> None:
    record = conflict_record()
    record["reported_by_work_package"] = "WP_ONE"

    jsonschema.validate(record, conflict_schema())

def test_conflict_with_both_reporters_is_invalid() -> None:
    record = conflict_record()
    record["reported_by_task"] = "SYN-TASK-001"
    record["reported_by_work_package"] = "WP_ONE"

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(record, conflict_schema())

def test_conflict_without_reporter_is_invalid() -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(conflict_record(), conflict_schema())

def test_resolved_by_work_package_is_valid() -> None:
    record = conflict_record()
    record["reported_by_work_package"] = "WP_ONE"
    record["status"] = "RESOLVED"
    record["resolution"] = "Use the coordinator decision."
    record["decision_source"] = "review-record-001"
    record["resolved_by_work_package"] = "WP_COORDINATOR"
    record["resolved_at"] = "2026-07-28T00:10:00Z"

    jsonschema.validate(record, conflict_schema())
