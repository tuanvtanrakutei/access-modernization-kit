from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
from typing import Any

import jsonschema

from collaboration import (
    CollaborationError,
    _schema,
    validate_work_package,
    work_package_digest,
    _task_logical_path,
)
from contract_impact import contract_impact_required, validate_contract_impact

REVIEW_FORMAT_CHECKER = jsonschema.FormatChecker()

def _parse_date_time(value: object) -> datetime:
    if not isinstance(value, str) or "T" not in value.upper():
        raise ValueError(value)
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        raise ValueError(value)
    return parsed


def artifact_set_digest(root: Path, artifacts: list[str]) -> str:
    entries: list[tuple[str, str]] = []
    identities: set[str] = set()
    for artifact in artifacts:
        logical = _task_logical_path(artifact, allow_parent_prefix=False)
        identity = logical.casefold()
        if identity in identities:
            raise CollaborationError("COLLAB_REVIEW_STALE", "duplicate artifact")
        identities.add(identity)
        path = root / logical
        if not path.is_file():
            raise CollaborationError("COLLAB_REVIEW_STALE", "produced artifact")
        entries.append((identity, hashlib.sha256(path.read_bytes()).hexdigest()))
    encoded = json.dumps(sorted(entries), separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@REVIEW_FORMAT_CHECKER.checks("date-time")
def _is_date_time(value: object) -> bool:
    try:
        _parse_date_time(value)
        return True
    except ValueError:
        return False

def _canonical_identity(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise CollaborationError("COLLAB_REVIEW_STALE", field)
    return value.strip()


def validate_review_receipt(
    package: dict[str, Any],
    receipt: dict[str, Any],
    *,
    expected_producer: str | None = None,
    produced_revision: str | None = None,
    produced_artifact_digest: str | None = None,
    expected_publication_phase: int | None = None,
    require_exact_output_binding: bool = True,
    review_not_before: str | None = None,
    changed_paths: list[str] | None = None,
    contract_impact: dict[str, Any] | None = None,
) -> None:
    validate_work_package(package)
    try:
        jsonschema.Draft202012Validator(
            _schema("review-receipt.schema.json"),
            format_checker=REVIEW_FORMAT_CHECKER,
        ).validate(receipt)
    except jsonschema.ValidationError as exc:
        raise CollaborationError("COLLAB_REVIEW_STALE", exc.message) from exc

    validation_commands: set[str] = set()
    for result in receipt["validation_results"]:
        command = result["command"]
        expected = "PASS" if result["exit_code"] == 0 else "FAIL"
        if result["result"] != expected:
            raise CollaborationError(
                "COLLAB_REVIEW_STALE", "inconsistent validation result"
            )
        if command in validation_commands:
            raise CollaborationError(
                "COLLAB_REVIEW_STALE", "duplicate validation result"
            )
        validation_commands.add(command)

    if (
        receipt["work_package_id"] != package["package_id"]
        or receipt["work_package_digest"] != work_package_digest(package)
    ):
        raise CollaborationError("COLLAB_REVIEW_STALE", "package identity")

    snapshot = dict(receipt["authority_snapshot"])
    reviewed_revision = snapshot.pop("produced_revision", None)
    reviewed_artifact_digest = snapshot.pop("produced_artifact_digest", None)
    if snapshot != package["authority"]:
        raise CollaborationError("COLLAB_REVIEW_STALE", "authority snapshot")
    stage = receipt["review_stage"]
    if (
        stage != "scope_acceptance"
        and changed_paths is not None
        and contract_impact_required(changed_paths)
    ):
        if contract_impact is None:
            raise CollaborationError("COLLAB_IMPACT_REQUIRED", "contract impact")
        validate_contract_impact(package, contract_impact, changed_paths)
    try:
        reviewed_at = _parse_date_time(receipt["reviewed_at"])
        not_before = _parse_date_time(
            package["created_at"]
            if stage == "scope_acceptance"
            else review_not_before
        ) if stage == "scope_acceptance" or review_not_before is not None else None
    except ValueError as exc:
        raise CollaborationError("COLLAB_REVIEW_STALE", "reviewed_at") from exc
    if not_before is not None and reviewed_at < not_before:
        raise CollaborationError("COLLAB_REVIEW_STALE", "reviewed_at")
    if stage == "publication":
        if receipt["publication_phase"] != expected_publication_phase:
            raise CollaborationError("COLLAB_REVIEW_STALE", "publication phase")
    elif expected_publication_phase is not None:
        raise CollaborationError("COLLAB_REVIEW_STALE", "publication phase")
    authority_kind = package["authority"]["kind"]
    if stage == "scope_acceptance":
        trusted_producer = _canonical_identity(package["created_by"], "producer")
    else:
        trusted_producer = _canonical_identity(
            expected_producer, "expected producer"
        )

    producer = _canonical_identity(receipt["producer"], "producer")
    reviewer = _canonical_identity(receipt["reviewer"], "reviewer")
    package_reviewer = _canonical_identity(package["reviewer"], "reviewer")

    if reviewer == trusted_producer:
        raise CollaborationError(
            "COLLAB_REVIEW_NOT_INDEPENDENT", reviewer
        )
    if producer != trusted_producer:
        raise CollaborationError("COLLAB_REVIEW_STALE", "producer")
    if reviewer != package_reviewer:
        raise CollaborationError("COLLAB_REVIEW_STALE", "reviewer")
    if receipt["decision"] != "APPROVED":
        raise CollaborationError("COLLAB_REVIEW_STALE", "decision")

    for command in package["validation_commands"]:
        matches = [
            result
            for result in receipt["validation_results"]
            if result["command"] == command
        ]
        if (
            len(matches) != 1
            or matches[0]["exit_code"] != 0
            or matches[0]["result"] != "PASS"
        ):
            raise CollaborationError("COLLAB_REVIEW_STALE", "required validation")

    if stage == "scope_acceptance":
        if (
            produced_revision is not None
            or reviewed_revision is not None
            or produced_artifact_digest is not None
            or reviewed_artifact_digest is not None
        ):
            raise CollaborationError("COLLAB_REVIEW_STALE", "produced artifact")
    elif not require_exact_output_binding:
        pass
    elif authority_kind in {"repository_revision", "mixed"}:
        if not isinstance(produced_revision, str) or not produced_revision.strip():
            raise CollaborationError("COLLAB_REVIEW_STALE", "produced revision")
        if reviewed_revision != produced_revision:
            raise CollaborationError("COLLAB_REVIEW_STALE", "produced revision")
        if (
            produced_artifact_digest is not None
            or reviewed_artifact_digest is not None
        ):
            raise CollaborationError("COLLAB_REVIEW_STALE", "produced artifact")
    elif produced_revision is not None or reviewed_revision is not None:
        raise CollaborationError("COLLAB_REVIEW_STALE", "produced revision")
    elif (
        not isinstance(produced_artifact_digest, str)
        or reviewed_artifact_digest != produced_artifact_digest
    ):
        raise CollaborationError("COLLAB_REVIEW_STALE", "produced artifact")
