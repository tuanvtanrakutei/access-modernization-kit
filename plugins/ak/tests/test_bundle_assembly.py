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


def _assemble(tmp_path: Path, contributions: list[dict]) -> dict:
    return assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=contributions, normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path,
    )


def test_cross_adapter_hash_conflict_is_rejected(tmp_path: Path) -> None:
    first = _contribution("imported_sources")
    second = _contribution("msaccess_vcs")
    second["provenance"]["source_hashes"]["q1"] = "b" * 64
    second["code"]["access_sql"][0]["sha256"] = "b" * 64
    try:
        _assemble(tmp_path, [first, second])
    except ValueError as exc:
        assert str(exc) == "DUPLICATE_MISMATCH:q1"
        return
    raise AssertionError("cross-adapter digest conflicts must be rejected")


def test_identical_cross_adapter_record_is_deduplicated(tmp_path: Path) -> None:
    result = _assemble(tmp_path, [_contribution("imported_sources"), _contribution("msaccess_vcs")])
    inventory = json.loads(
        (Path(result["bundle_dir"]) / "code" / "access-sql" / "inventory.json").read_text(encoding="utf-8")
    )
    assert len(inventory) == 1


def test_reassembly_reuses_identical_existing_bundle(tmp_path: Path) -> None:
    first = _assemble(tmp_path, [_contribution("imported_sources")])
    second = _assemble(tmp_path, [_contribution("imported_sources")])
    assert second == first


def test_reassembly_rejects_stale_extra_file_without_deleting_it(tmp_path: Path) -> None:
    first = _assemble(tmp_path, [_contribution("imported_sources")])
    stale = Path(first["bundle_dir"]) / "stale.txt"
    stale.write_text("stale", encoding="utf-8")
    try:
        _assemble(tmp_path, [_contribution("imported_sources")])
    except ValueError as exc:
        assert str(exc) == "BUNDLE_PATH_CONFLICT"
        assert stale.read_text(encoding="utf-8") == "stale"
        return
    raise AssertionError("stale target content must not be overwritten")


def _assemble_one(tmp_path: Path, contribution: dict):
    return assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=[contribution], normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path,
    )


# A linked Access table records its target as two facts: Connect says where the data
# lives, SourceTableName says what inside it. For a split Access application that target
# is very often another .mdb, and naming it is the investigation's purpose. The suffix
# rule rejected the structured field while letting the identical path through inside a
# read_error sentence, so the guard blocked the machine-readable form of a fact the
# bundle already carried as prose.
def test_linked_table_boundary_target_may_name_an_external_database(tmp_path: Path) -> None:
    contribution = _contribution("managed_access")
    contribution["interfaces"]["linked_tables"].append({
        "logical_id": "SYN:table:操作履歴", "name": "操作履歴", "database_id": "SYN",
        "metadata": {
            "linked": True,
            "connect": r";DATABASE=L:\新品揃支援\XP\品揃支援data.mdb",
            "source_table_name": "操作履歴",
        },
    })
    result = _assemble_one(tmp_path, contribution)
    assert result["bundle_id"]


# The allowance is scoped to those two keys and nothing wider.
def test_raw_binary_elsewhere_is_still_rejected(tmp_path: Path) -> None:
    contribution = _contribution("managed_access")
    contribution["databases"]["objects"].append({
        "logical_id": "SYN:table:x", "source_paths": ["snapshot/legacy.mdb"],
    })
    try:
        _assemble_one(tmp_path, contribution)
    except ValueError as exc:
        assert "forbidden raw binary" in str(exc)
        return
    raise AssertionError("a source path pointing at a raw database must still be rejected")


def test_raw_binary_flag_is_still_rejected_inside_metadata(tmp_path: Path) -> None:
    contribution = _contribution("managed_access")
    contribution["interfaces"]["linked_tables"].append({
        "logical_id": "SYN:table:y", "metadata": {"raw_path": "legacy.mdb", "raw_binary": True},
    })
    try:
        _assemble_one(tmp_path, contribution)
    except ValueError as exc:
        assert "carries a raw database binary" in str(exc)
        return
    raise AssertionError("a raw_binary marker must still be rejected")
