from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema

FORBIDDEN_SUFFIXES = {".mdb", ".accdb", ".adp", ".mde", ".accde", ".bak", ".mdf", ".ldf"}


class BundleError(ValueError):
    pass


def _canonical_identity(value: dict[str, Any]) -> dict[str, Any]:
    required = (
        "app_id", "classification", "classification_rule_versions", "artifacts", "adapters",
        "bundle_schema_version", "normalization_config",
    )
    missing = [key for key in required if key not in value]
    if missing:
        raise BundleError(f"Missing identity fields: {missing}")
    return {
        "app_id": value["app_id"],
        "classification": value["classification"],
        "classification_rule_versions": dict(sorted(value["classification_rule_versions"].items())),
        "artifacts": sorted(value["artifacts"], key=lambda item: (item["logical_id"], item["content_sha256"])),
        "adapters": sorted(value["adapters"], key=lambda item: (item["id"], item["version"])),
        "bundle_schema_version": value["bundle_schema_version"],
        "normalization_config": value["normalization_config"],
    }


def compute_bundle_id(value: dict[str, Any]) -> str:
    encoded = json.dumps(_canonical_identity(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "bundle-" + hashlib.sha256(encoded).hexdigest()


def verify_immutable(bundle_dir: Path, expected_hashes: dict[str, str]) -> None:
    root = Path(bundle_dir).resolve()
    for relative, expected in sorted(expected_hashes.items()):
        rel = PurePosixPath(relative)
        if rel.is_absolute() or ".." in rel.parts:
            raise BundleError(f"Invalid checksum path: {relative}")
        path = (root / Path(*rel.parts)).resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise BundleError(f"Checksum path escapes bundle: {relative}") from exc
        if not path.is_file():
            raise BundleError(f"Bundle file missing: {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise BundleError(f"Bundle file changed: {relative}")


def make_lock(
    bundle_id: str, checksum: str, schema_version: str,
    classification: dict[str, Any], approved_location: str, approval_record_id: str,
) -> dict[str, Any]:
    return {
        "bundle_id": bundle_id, "checksum": checksum, "schema_version": schema_version,
        "classification": classification, "approved_location": approved_location,
        "approval_record_id": approval_record_id,
    }


def make_approval(
    approval_id: str, bundle_id: str, checksum: str, schema_version: str,
    validator_version: str, approver: str, approved_at: str,
    distribution_policy: str = "artifact_store", superseded_bundle: str | None = None,
) -> dict[str, Any]:
    return {
        "approval_id": approval_id, "bundle_id": bundle_id, "checksum": checksum,
        "schema_version": schema_version, "validator_version": validator_version,
        "validation_result": "APPROVED", "approver": approver, "approved_at": approved_at,
        "distribution_policy": distribution_policy, "superseded_bundle": superseded_bundle,
    }


def read_checksums(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        checksum, relative = line.split(maxsplit=1)
        result[relative.lstrip(" *")] = checksum
    return result


def validate_bundle(bundle_dir: Path) -> dict[str, Any]:
    root = Path(bundle_dir).resolve()
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise BundleError(f"Forbidden raw binary in bundle: {path.relative_to(root)}")
    data = json.loads((root / "bundle.json").read_text(encoding="utf-8"))
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "bundle.schema.json"
    jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
    checksums_path = root / "checksums.sha256"
    if checksums_path.is_file():
        verify_immutable(root, read_checksums(checksums_path))
    return data
