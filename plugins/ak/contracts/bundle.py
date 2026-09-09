from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema

FORBIDDEN_SUFFIXES = {".mdb", ".accdb", ".adp", ".mde", ".accde", ".bak", ".mdf", ".ldf"}


class BundleError(ValueError):
    pass


_IDENTITY_TERMS = (
    "app_id", "classification", "classification_rule_versions", "artifacts", "adapters",
    "bundle_schema_version", "normalization_config", "assembly_version",
    "supplied_evidence",
)


def _canonical_identity(value: dict[str, Any]) -> dict[str, Any]:
    missing = [key for key in _IDENTITY_TERMS if key not in value]
    if missing:
        raise BundleError(f"Missing identity fields: {missing}")
    # A term nobody declared here is a term that silently does not affect the id, and
    # that is not a theoretical risk - it happened. A33 added `supplied_evidence` to
    # the identity dict, the id did not move, and the only symptom was a
    # BUNDLE_PATH_CONFLICT two runs later. This function returns an explicit mapping,
    # so an undeclared key was dropped without a word.
    #
    # A leading underscore stays the way to say "deliberate noise, keep it out of the
    # id" - `_absolute_path` and `_generated_at` are machine facts that must never
    # change an address, and a test asserts they do not. Everything else is a mistake
    # and now says so.
    undeclared = sorted(
        key for key in value if not key.startswith("_") and key not in _IDENTITY_TERMS
    )
    if undeclared:
        raise BundleError(
            f"Undeclared identity fields: {undeclared}. Add them to _IDENTITY_TERMS "
            "and to the mapping below, or prefix with '_' if they must not affect the "
            "bundle id."
        )
    return {
        "app_id": value["app_id"],
        "classification": value["classification"],
        "classification_rule_versions": dict(sorted(value["classification_rule_versions"].items())),
        "artifacts": sorted(value["artifacts"], key=lambda item: (item["logical_id"], item["content_sha256"])),
        "adapters": sorted(value["adapters"], key=lambda item: (item["id"], item["version"])),
        "bundle_schema_version": value["bundle_schema_version"],
        "normalization_config": value["normalization_config"],
        # The code that did the assembling. Without it, two bundles built from one set
        # of sources by two versions of the kit are the same bundle by name and
        # different on disk, and the second one cannot be published at all.
        "assembly_version": value["assembly_version"],
        # And the evidence a person supplied, which no adapter produces and the
        # manifest does not declare. Without it the same thing happened for the
        # commonest action in the whole workflow: add a document, re-acquire, and the
        # bundle says something new under the name of the old one.
        "supplied_evidence": value["supplied_evidence"],
    }


def compute_bundle_id(value: dict[str, Any]) -> str:
    encoded = json.dumps(_canonical_identity(value), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "bundle-" + hashlib.sha256(encoded).hexdigest()


def bundle_dir_name(bundle_id: str, when: date | None = None) -> str:
    """A directory a person can read, for an id that is a content address.

    The id has to be the full digest - that is what makes it an address. Using it
    as the directory name too gave every workspace a 71-character path nobody can
    type, read aloud, or sort by recency; with two bundles present you could not
    tell which was current without opening both. The date leads so the newest
    sorts last, and eight digest characters keep it unique in practice while the
    full id stays in bundle.json where it is actually consumed.
    """
    digest = bundle_id[len("bundle-"):] if bundle_id.startswith("bundle-") else bundle_id
    return f"{(when or date.today()).isoformat()}-{digest[:8]}"


def find_bundles(acquired_root: Path) -> list[Path]:
    """Every bundle under a workspace, old layout and new.

    `acquired/bundles/<date>-<digest>/` is what is written now;
    `acquired/bundle-<64 hex>/` is what workspaces written before 2.9.0 carry. Both
    are read, so upgrading the kit does not strand a workspace mid-investigation.
    """
    root = Path(acquired_root)
    found = list((root / "bundles").glob("*")) + list(root.glob("bundle-*"))
    return [path for path in found if (path / "bundle.json").is_file()]


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
    *,
    lock_version: str | None = None,
    distribution_policy: str | None = None,
    artifact_reference: str | None = None,
    bundle_approval_checksum: str | None = None,
    profile_rule_versions: dict[str, str] | None = None,
    normalization_config_checksum: str | None = None,
    supersedes_lock_checksum: str | None = None,
) -> dict[str, Any]:
    value = {
        "bundle_id": bundle_id, "checksum": checksum, "schema_version": schema_version,
        "classification": classification, "approved_location": approved_location,
        "approval_record_id": approval_record_id,
    }
    optional = {
        "lock_version": lock_version,
        "distribution_policy": distribution_policy,
        "artifact_reference": artifact_reference,
        "bundle_approval_checksum": bundle_approval_checksum,
        "profile_rule_versions": profile_rule_versions,
        "normalization_config_checksum": normalization_config_checksum,
        "supersedes_lock_checksum": supersedes_lock_checksum,
    }
    value.update({key: item for key, item in optional.items() if item is not None})
    return value


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
