from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import jsonschema
import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

from bundle import BundleError, compute_bundle_id, make_lock, verify_immutable  # noqa: E402

BASE = {
    "app_id": "A05",
    "classification": {"topology": "split_file", "frontend_format": "mdb", "source_availability": "full", "backend_kinds": ["access_file"]},
    "classification_rule_versions": {"frontend.mdb.dao": "1.0"},
    "artifacts": [{"logical_id": "A05_FRONTEND", "content_sha256": "a" * 64}],
    "adapters": [{"id": "managed_access", "version": "2.7.0"}],
    "bundle_schema_version": "1.0",
    "normalization_config": {"encoding": "utf-8", "line_endings": "LF"},
    "assembly_version": "0123456789ab",
    "supplied_evidence": "9d81b7b71189e9e6",
}


def test_id_ignores_paths_and_timestamps() -> None:
    noisy = dict(BASE, _absolute_path="D:/machine", _generated_at="2026-07-27T00:00:00Z")
    assert compute_bundle_id(noisy) == compute_bundle_id(BASE)


def test_id_changes_when_the_supplied_evidence_changes() -> None:
    """The commonest action in the workflow, and it did not move the id.

    A person adds a document, a screenshot or a recorded answer to a class directory -
    which is how evidence arrives - and every other identity term stays put: same
    manifest, same adapters, same assembling code. The bundle then said something new
    under the name of the old one, and re-acquiring ended in BUNDLE_PATH_CONFLICT.
    """
    changed = dict(BASE, supplied_evidence="aa43c68f53f844b4")
    assert compute_bundle_id(changed) != compute_bundle_id(BASE)


def test_an_undeclared_identity_term_is_refused_rather_than_dropped() -> None:
    """The guard exists because this exact mistake was made writing A33.

    `_canonical_identity` returns an explicit mapping, so a term added to the identity
    dict and not to that mapping was silently discarded - the id did not move, nothing
    failed, and the only symptom arrived two runs later as a path conflict. An
    underscore still means "machine noise, keep it out of the address"; anything else
    is now an error at the point of the mistake.
    """
    with pytest.raises(BundleError) as caught:
        compute_bundle_id(dict(BASE, evidence_digest="whatever"))
    assert "Undeclared identity fields" in str(caught.value)
    assert "evidence_digest" in str(caught.value)


def test_id_changes_when_content_changes() -> None:
    changed = dict(BASE, artifacts=[{"logical_id": "A05_FRONTEND", "content_sha256": "b" * 64}])
    assert compute_bundle_id(changed) != compute_bundle_id(BASE)


def test_id_changes_when_classification_changes() -> None:
    changed = dict(BASE, classification={"topology": "hybrid", "frontend_format": "mdb", "source_availability": "full", "backend_kinds": ["access_file"]})
    assert compute_bundle_id(changed) != compute_bundle_id(BASE)


def test_immutable_hash_verification(tmp_path: Path) -> None:
    file = tmp_path / "bundle.json"
    file.write_text("{}", encoding="utf-8")
    expected = {"bundle.json": hashlib.sha256(b"{}").hexdigest()}
    verify_immutable(tmp_path, expected)
    file.write_text("{ }", encoding="utf-8")
    with pytest.raises(BundleError):
        verify_immutable(tmp_path, expected)


def test_lock_has_external_approval_reference() -> None:
    lock = make_lock("bundle-abc", "c" * 64, "1.0", {"topology": "split_file"}, "artifact_store://a05", "AP-1")
    assert lock["bundle_id"] == "bundle-abc"
    assert lock["approval_record_id"] == "AP-1"


def lock_schema() -> dict:
    return json.loads(
        (PACKAGE / "schemas/bundle-lock.schema.json").read_text(encoding="utf-8")
    )


def enriched_lock(**overrides) -> dict:
    values = {
        "lock_version": "1.1",
        "distribution_policy": "artifact_store",
        "artifact_reference": "artifact_store://sms/A05/bundles/bundle-abc",
        "bundle_approval_checksum": "d" * 64,
        "profile_rule_versions": {"topology.split_file.backend_required": "1.0"},
        "normalization_config_checksum": "e" * 64,
    }
    values.update(overrides)
    return make_lock(
        "bundle-abc",
        "c" * 64,
        "1.0",
        {"topology": "split_file"},
        values.pop("approved_location", "artifact_store://a05"),
        "AP-1",
        **values,
    )


def test_legacy_lock_remains_valid() -> None:
    lock = make_lock(
        "bundle-abc",
        "c" * 64,
        "1.0",
        {"topology": "split_file"},
        "D:/legacy/bundles/a05",
        "AP-1",
    )

    jsonschema.validate(lock, lock_schema())


def test_enriched_lock_records_portable_authority() -> None:
    lock = enriched_lock()

    jsonschema.validate(lock, lock_schema())
    assert lock["artifact_reference"].startswith("artifact_store://")
    assert lock["bundle_approval_checksum"] == "d" * 64


@pytest.mark.parametrize(
    "field",
    [
        "distribution_policy",
        "artifact_reference",
        "bundle_approval_checksum",
        "profile_rule_versions",
        "normalization_config_checksum",
    ],
)
def test_enriched_lock_requires_complete_authority(field: str) -> None:
    lock = enriched_lock()
    del lock[field]

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(lock, lock_schema())


@pytest.mark.parametrize(
    "overrides",
    [
        {"artifact_reference": "D:/bundles/a05"},
        {"approved_location": "D:/bundles/a05"},
        {"artifact_reference": "artifact_store://user:secret@store/a05"},
        {"artifact_reference": "artifact_store://store/a05?token=secret"},
        {
            "distribution_policy": "shared_path",
            "artifact_reference": "artifact_store://sms/A05/bundle-abc",
        },
    ],
)
def test_enriched_lock_rejects_nonportable_authority(overrides: dict) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(enriched_lock(**overrides), lock_schema())


def test_bundle_schema_requires_normalized_evidence_sources() -> None:
    schema = json.loads((PACKAGE / "schemas/bundle.schema.json").read_text(encoding="utf-8"))
    bundle = {
        "schema_version": "1.0", "bundle_id": "bundle-abc", "app_id": "A05",
        "classification": {"topology": "split_file", "frontend_format": "mdb",
                           "source_availability": "full", "backend_kinds": ["access_file"]},
        "rule_versions": {"frontend.mdb.dao": "1.0"},
        "evidence_sources": {
            "documents": {"inventory": "evidence-sources/documents/inventory.json"},
            "screenshots": {"inventory": "evidence-sources/screenshots/inventory.json"},
            "reports": {"inventory": "evidence-sources/reports/inventory.json"},
            "samples": {"inventory": "evidence-sources/samples/inventory.json"},
        },
    }
    jsonschema.validate(bundle, schema)
