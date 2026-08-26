from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(PACKAGE / "contracts"))
sys.path.insert(0, str(PACKAGE / "scripts"))

import evidence_requirements  # noqa: E402
import phase_evidence  # noqa: E402
from classification import Classification  # noqa: E402

PROFILES = PACKAGE / "profiles"
SPLIT = Classification("split_file", "mdb", "full", ("access_file",))


# Readiness said which capability was missing and never what to do about it, so
# "missing:any:trigger_effect_output_trace" was a true statement nobody could act on.
def test_every_capability_a_phase_can_require_names_a_way_to_supply_it() -> None:
    required: set[str] = set()
    for baseline in evidence_requirements.phase_readiness_contract.BASELINE.values():
        required |= set(baseline.get("all", set()))
        required |= set(baseline.get("any", set()))
    for profile in ("topology.yaml", "backend.yaml", "frontend.yaml", "source-availability.yaml"):
        data = yaml.safe_load((PROFILES / profile).read_text(encoding="utf-8")) or {}
        for rule in data.get("rules", []) or []:
            require = rule.get("require", {}) or {}
            required |= set(require.get("all", []) or [])
            required |= set(require.get("any", []) or [])
    undocumented = sorted(required - set(evidence_requirements.SUPPLY))
    assert undocumented == [], f"no supply route documented for: {undocumented}"


def test_requirements_separates_what_is_present_from_what_is_missing() -> None:
    present = {"field_inventory", "key_index_inventory", "boundary_inventory",
               "access_schema_inventory", "backend_authority_declared"}
    report = evidence_requirements.requirements(1, SPLIT, PROFILES, present)
    assert report["status"] == "READY"
    assert {item["capability"] for item in report["satisfied"]} >= {"field_inventory", "boundary_inventory"}
    assert report["missing"] == []

    blocked = evidence_requirements.requirements(4, SPLIT, PROFILES, present)
    assert blocked["status"] == "BLOCKED"
    gap = blocked["missing"][0]
    assert "trigger_effect_output_trace" in gap.get("alternatives", [gap["capability"]])
    assert {item["route"] for item in gap["supply"]} == {"files", "runtime"}


def _workspace(tmp_path: Path, capabilities: dict[str, list[str]] | None = None) -> Path:
    app = tmp_path / "A99"
    (app / "acquired" / "bundle-abc").mkdir(parents=True)
    (app / "manifest.yaml").write_text(yaml.safe_dump({
        "version": "2.2",
        "app": {"id": "A99", "name_en": "Evidence Test"},
        "project": {"classification": {
            "topology": "split_file", "frontend_format": "mdb",
            "source_availability": "full", "backend_kinds": ["access_file"],
        }},
        "artifacts": [],
    }, sort_keys=False), encoding="utf-8")
    bundle = app / "acquired" / "bundle-abc"
    (bundle / "bundle.json").write_text(json.dumps({"bundle_id": "bundle-abc"}), encoding="utf-8")
    provenance: dict = {"schema_version": "2.7.3", "bundle_id": "bundle-abc", "sources": []}
    if capabilities is not None:
        provenance["capabilities"] = capabilities
    (bundle / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    return app


# The point of persisting capabilities: a later phase must not ask again for evidence
# an earlier one already supplied, and must be able to say where it came from.
def test_evidence_already_supplied_is_not_requested_again(tmp_path: Path) -> None:
    app = _workspace(tmp_path, {
        "field_inventory": ["managed_access"],
        "key_index_inventory": ["managed_access"],
        "boundary_inventory": ["managed_access"],
        "access_schema_inventory": ["imported_sources"],
        "backend_authority_declared": ["manifest"],
    })
    report = phase_evidence.phase_report(app, 1)
    assert report["status"] == "READY"
    assert report["missing"] == []
    by_name = {item["capability"]: item["supplied_by"] for item in report["satisfied"]}
    assert by_name["field_inventory"] == "managed_access"
    assert by_name["access_schema_inventory"] == "imported_sources"


def test_a_missing_capability_comes_with_a_runnable_command(tmp_path: Path) -> None:
    app = _workspace(tmp_path, {})
    report = phase_evidence.phase_report(app, 1)
    assert report["status"] == "BLOCKED"
    routes = {item["route"]: item for gap in report["missing"] for item in gap["supply"]}
    assert "acquire run" in " ".join(routes["runtime"]["commands"])
    files = " ".join(routes["files"]["commands"])
    assert "ExportAccessObjects.bas" in files
    assert "import-sources" in files
    # The command has to name this workspace, not a placeholder path.
    assert str(app) in files


# A bundle written before capabilities were recorded still says which phases it
# reached, so its evidence is treated as supplied rather than demanded again.
def test_an_older_bundle_falls_back_to_its_readiness_verdict(tmp_path: Path) -> None:
    app = _workspace(tmp_path, None)
    bundle = app / "acquired" / "bundle-abc"
    (bundle / "phase-readiness.json").write_text(json.dumps({
        "phase1": {"status": "READY", "reasons": [], "rule_ids": []},
    }), encoding="utf-8")
    report = phase_evidence.phase_report(app, 1)
    supplied = {item["capability"]: item["supplied_by"] for item in report["satisfied"]}
    assert "field_inventory" in supplied
    assert "capabilities not recorded" in supplied["field_inventory"]


def test_a_waiver_is_reported_alongside_the_phase_it_unblocked(tmp_path: Path) -> None:
    app = _workspace(tmp_path, {})
    report = phase_evidence.phase_report(app, 4, ("trigger_effect_output_trace",), "no sample files exist")
    assert report["status"] != "BLOCKED"
    assert report["waived"] == [
        {"capability": "trigger_effect_output_trace", "reason": "no sample files exist"}
    ]
