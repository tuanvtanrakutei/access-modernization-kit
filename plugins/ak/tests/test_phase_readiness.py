from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
PROFILES = PACKAGE / "profiles"
sys.path.insert(0, str(PACKAGE / "contracts"))

from classification import Classification  # noqa: E402
from phase_readiness import compute_readiness  # noqa: E402

PHASES = tuple(f"phase{i}" for i in range(1, 7))


def test_adp_without_sql_schema_blocks_phase1_and_phase3() -> None:
    classification = Classification("client_server", "adp", "full", ("sql_server",))
    result = compute_readiness(classification, PROFILES, set())
    assert result["phase1"]["status"] == "BLOCKED"
    assert result["phase3"]["status"] == "BLOCKED"


def test_adp_with_sql_schema_is_ready_or_limited() -> None:
    classification = Classification("client_server", "adp", "full", ("sql_server",))
    caps = {"sql_server_schema_evidence", "server_object_inventory",
            "definitions_for_referenced_objects", "dependency_closure",
            "server_boundary_declared", "source_inventory", "field_inventory",
            "key_index_inventory", "boundary_inventory"}
    result = compute_readiness(classification, PROFILES, caps)
    assert result["phase1"]["status"] in {"READY", "LIMITED"}


def test_compiled_frontend_is_limited_for_phase3() -> None:
    classification = Classification("split_file", "mde", "compiled_only", ("access_file",))
    caps = {"access_object_inventory", "access_schema_inventory",
            "backend_authority_declared", "compiled_object_inventory"}
    result = compute_readiness(classification, PROFILES, caps)
    assert result["phase3"]["status"] == "LIMITED"


def test_not_applicable_requires_positive_proof() -> None:
    classification = Classification("split_file", "mdb", "full", ("access_file",))
    result = compute_readiness(classification, PROFILES, set())
    assert all(result[phase]["status"] != "NOT_APPLICABLE" for phase in PHASES)


def test_security_integrity_waiver_is_rejected() -> None:
    classification = Classification("split_file", "mdb", "full", ("unknown_boundary",))
    result = compute_readiness(classification, PROFILES, set(), waivers=[{
        "rule_id": "backend.unknown_boundary.blocks_ready", "approver": "reviewer",
        "reason": "continue anyway", "affected_scope": "phase1", "accepted_risk": "unknown backend",
    }])
    assert "backend.unknown_boundary.blocks_ready" in result["_meta"]["waivers_rejected"]
    assert result["phase1"]["status"] == "BLOCKED"


def test_phase1_baseline_requires_fields_keys_and_boundaries() -> None:
    classification = Classification("monolith", "mdb", "full", ("embedded_access",))
    incomplete = compute_readiness(
        classification, PROFILES, {"access_schema_inventory", "access_object_inventory", "source_inventory"}
    )
    assert incomplete["phase1"]["status"] == "BLOCKED"
    complete = compute_readiness(
        classification, PROFILES,
        {"access_schema_inventory", "access_object_inventory", "source_inventory",
         "field_inventory", "key_index_inventory", "boundary_inventory"},
    )
    assert complete["phase1"]["status"] == "READY"


def test_fixture_matrix_matches_expected_readiness() -> None:
    cases = sorted((PACKAGE / "fixtures").glob("*/*/expected-readiness.json"))
    assert len(cases) == 6
    for case in cases:
        spec = json.loads(case.read_text(encoding="utf-8"))
        raw = spec["classification"]
        classification = Classification(
            raw["topology"], raw["frontend_format"], raw["source_availability"],
            tuple(raw["backend_kinds"]),
        )
        actual = compute_readiness(classification, PROFILES, set(spec["present_capabilities"]))
        for phase, expected in spec["expected"].items():
            assert actual[phase]["status"] == expected, (case, phase)


# backend_authority_declared is required by the backend and split-topology profile
# rules, but no adapter can report it: adapters describe extracted evidence, while
# this is the project's statement about which store is authoritative. Nothing in the
# package produced it, so Phase 1 stayed BLOCKED on an unreachable capability.
def test_a_declared_required_backend_supplies_backend_authority(tmp_path) -> None:
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "contracts"))
    from acquisition_orchestrator import _declaration_capabilities
    from manifest_v22 import Artifact, SourceRef

    def artifact(role: str, required: bool, backend_kind: str | None) -> Artifact:
        return Artifact(
            id="DATA", kind="access_database", role=role, acquisition="managed",
            required=required, source_ref=SourceRef("local_path", "sources/access/data.mdb"),
            format="mdb", backend_kind=backend_kind,
        )

    declared = artifact("backend", True, "access_file")
    assert _declaration_capabilities((declared,)) == {"backend_authority_declared"}
    # An optional backend, or one whose kind is left unstated, is not a declaration.
    assert _declaration_capabilities((artifact("backend", False, "access_file"),)) == set()
    assert _declaration_capabilities((artifact("backend", True, None),)) == set()
    assert _declaration_capabilities((artifact("frontend", True, "access_file"),)) == set()
