from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from collaboration import (
    CollaborationError,
    load_work_package,
    validate_work_package,
    work_package_digest,
)
from collaboration_helpers import application_package, kit_package, mixed_package


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


@pytest.mark.parametrize(
    "package_factory", [kit_package, application_package, mixed_package]
)
def test_synthetic_authority_variants_validate(package_factory) -> None:
    validate_work_package(package_factory())


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
        "D:/secret/file",
        "D:\\secret\\file",
        "../escape",
        "safe/../../escape",
        "/etc/passwd",
        "//server/share/file",
    ],
)
def test_paths_must_be_relative_and_confined(bad_path: str) -> None:
    package = kit_package()
    package["write_paths"] = [bad_path]

    with pytest.raises(CollaborationError, match="COLLAB_PATH_ESCAPE"):
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

    with pytest.raises(CollaborationError, match="COLLAB_PUBLICATION_FORBIDDEN"):
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