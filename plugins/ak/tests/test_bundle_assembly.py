from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(PACKAGE / "contracts"))

from adapters.base import empty_sections  # noqa: E402
from bundle_assembly import assemble_bundle  # noqa: E402
import bundle as bundle_contract  # noqa: E402

def _contribution(adapter_id: str) -> dict:
    sections = empty_sections()
    sections["code"]["access_sql"].append({"logical_id": "q1", "text": "SELECT 1", "sha256": "a" * 64})
    return {
        "adapter_id": adapter_id, "adapter_version": "1.0.0", "app_id": "SYN", "status": "PARTIAL",
        **sections, "failures": [], "provenance": {"producer": adapter_id, "source_hashes": {"q1": "a" * 64}},
    }

def _classification() -> dict:
    return {"topology": "monolith", "frontend_format": "mdb", "source_availability": "exported_only", "backend_kinds": ["embedded_access"]}

def test_assemble_writes_layout_and_lock(tmp_path: Path) -> None:
    out = assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=[_contribution("imported_sources")], normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path,
    )
    bundle_dir = Path(out["bundle_dir"])
    assert (bundle_dir / "bundle.json").is_file()
    assert (bundle_dir / "checksums.sha256").is_file()
    assert (bundle_dir / "provenance.json").is_file()
    assert (bundle_dir / "profile-validation.json").is_file()
    assert (bundle_dir / "phase-readiness.json").is_file()
    assert (bundle_dir / "coverage.json").is_file()
    assert (bundle_dir / "code" / "access-sql" / "inventory.json").is_file()
    assert (bundle_dir / "databases" / "tables.json").is_file()
    assert (bundle_dir / "evidence-sources" / "documents" / "inventory.json").is_file()
    assert (bundle_dir / "failures" / "extraction-failures.json").is_file()
    data = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    assert data["bundle_id"] == out["bundle_id"]
    assert data["bundle_id"].startswith("bundle-")
    # Reuses canonical identity from contracts/bundle.py
    assert data["bundle_id"] == bundle_contract.compute_bundle_id({
        "app_id": "SYN", "classification": _classification(),
        "classification_rule_versions": {"topology": "1.0.0"},
        "artifacts": [{"logical_id": "q1", "content_sha256": "a" * 64}],
        "adapters": [{"id": "imported_sources", "version": "1.0.0"}],
        "bundle_schema_version": data["schema_version"], "normalization_config": {"text": "utf-8-lf"},
    })
    for output_name, schema_name in (
        ("provenance.json", "bundle-provenance.schema.json"),
        ("coverage.json", "bundle-coverage.schema.json"),
    ):
        output = json.loads((bundle_dir / output_name).read_text(encoding="utf-8"))
        schema = json.loads((PACKAGE / "schemas" / schema_name).read_text(encoding="utf-8"))
        jsonschema.validate(output, schema)
    assert bundle_contract.validate_bundle(bundle_dir)["bundle_id"] == out["bundle_id"]

def test_assemble_is_deterministic_across_paths(tmp_path: Path) -> None:
    first = assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=[_contribution("imported_sources")], normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path / "a",
    )
    second = assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=[_contribution("imported_sources")], normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path / "b",
    )
    assert first["bundle_id"] == second["bundle_id"]

def test_assemble_rejects_forbidden_binary(tmp_path: Path) -> None:
    bad = _contribution("managed_access")
    bad["databases"]["objects"].append({"logical_id": "db", "raw_path": "legacy.mdb", "raw_binary": True})
    try:
        assemble_bundle(
            app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
            contributions=[bad], normalization_config={"text": "utf-8-lf"},
            profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "BLOCKED"}},
            output_root=tmp_path,
        )
    except ValueError:
        return
    raise AssertionError("assembly must reject raw binary contributions")
