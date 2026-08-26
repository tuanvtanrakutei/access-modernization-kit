from __future__ import annotations

import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(PACKAGE / "contracts"))
sys.path.insert(0, str(PACKAGE / "scripts"))

import acquisition_preview  # noqa: E402
from classification import Classification  # noqa: E402

PROFILES = PACKAGE / "profiles"
SPLIT = Classification("split_file", "mdb", "full", ("access_file",))


def mdb(artifact_id: str, role: str = "unknown", **extra) -> dict:
    artifact = {
        "id": artifact_id, "kind": "access_database", "role": role,
        "acquisition": "managed", "required": True, "format": "mdb",
        "source_ref": {"type": "local_path", "value": f"sources/access/{artifact_id}.mdb"},
    }
    artifact.update(extra)
    return artifact


def export(artifact_id: str, fmt: str = "directory") -> dict:
    return {
        "id": artifact_id, "kind": "source_export", "role": "frontend",
        "acquisition": "imported", "required": True, "format": fmt,
        "source_ref": {"type": "local_path", "value": f"sources/{artifact_id}"},
    }


def document(artifact_id: str) -> dict:
    return {
        "id": artifact_id, "kind": "document", "role": "documentation",
        "acquisition": "imported", "required": False, "format": "xlsx",
        "source_ref": {"type": "local_path", "value": f"sources/documents/{artifact_id}.xlsx"},
    }


def test_mode_comes_from_what_the_artifacts_are_not_from_evidence_alongside_them() -> None:
    assert acquisition_preview.observed_mode([mdb("FE")]) == "extract"
    assert acquisition_preview.observed_mode([export("PKG")]) == "export"
    assert acquisition_preview.observed_mode([mdb("FE"), export("PKG")]) == "mixed"
    assert acquisition_preview.observed_mode([]) == "none"
    # Documents and screenshots ride along with either mode and must not decide it.
    assert acquisition_preview.observed_mode([mdb("FE"), document("LIST")]) == "extract"


# kind wins over acquisition inside the router, so "imported" on an Access database
# reads as a choice the operator made and the run silently ignores.
def test_imported_on_an_access_database_is_reported_as_a_contradiction() -> None:
    conflicts = acquisition_preview.contradictions([mdb("FE", acquisition="imported")])
    assert [item["reason"] for item in conflicts] == ["ACQUISITION_IGNORED"]
    assert acquisition_preview.contradictions([mdb("FE")]) == []


def test_only_extract_reaches_the_phase1_capabilities() -> None:
    extract = acquisition_preview.expected_capabilities([mdb("FE")])
    reachable = set(extract["expected"]) | set(extract["content_dependent"])
    assert {"field_inventory", "key_index_inventory", "access_schema_inventory"} <= reachable

    exported = acquisition_preview.expected_capabilities([export("PKG"), document("LIST")])
    reachable = set(exported["expected"]) | set(exported["content_dependent"])
    assert "field_inventory" not in reachable
    assert "key_index_inventory" not in reachable
    # ...and only export declares documents, which is what Phase 5 asks for.
    assert "document_inventory" in exported["expected"]


# backend_authority_declared is a statement the manifest makes, not evidence an
# adapter extracts, so leaving role: unknown is visible before anything is acquired.
def test_backend_authority_follows_the_declared_role() -> None:
    unresolved = acquisition_preview.expected_capabilities([mdb("FE"), mdb("DATA")])
    assert "backend_authority_declared" not in unresolved["expected"]

    resolved = acquisition_preview.expected_capabilities([
        mdb("FE", role="frontend"),
        mdb("DATA", role="backend", backend_kind="access_file"),
    ])
    assert "backend_authority_declared" in resolved["expected"]


def test_phase_outlook_separates_the_floor_from_the_ceiling() -> None:
    artifacts = [mdb("FE", role="frontend"), mdb("DATA", role="backend", backend_kind="access_file")]
    outlook = acquisition_preview.phase_outlook(
        SPLIT, PROFILES, acquisition_preview.expected_capabilities(artifacts),
    )
    # Phase 1 needs an index and a boundary, neither of which can be promised from a
    # manifest, so it is reachable but not guaranteed.
    assert outlook["guaranteed"]["phase1"] == "BLOCKED"
    assert outlook["if_content_present"]["phase1"] == "READY"
    # Phase 2 only needs an object inventory, which any Access extraction yields.
    assert outlook["guaranteed"]["phase2"] == "READY"


# Only the Access Application tier can require elevation; the DAO tier activates
# in-process. Saying otherwise trains operators to elevate runs that never needed it.
def test_access_host_requirement_follows_skip_object_export() -> None:
    with_host = acquisition_preview.needs_access_host([mdb("FE")])
    assert with_host["required"] is True
    assert with_host["artifacts"] == ["FE"]

    dao_only = acquisition_preview.needs_access_host([mdb("FE", runtime={"skip_object_export": True})])
    assert dao_only["required"] is False
    assert dao_only["artifacts"] == []

    assert acquisition_preview.needs_access_host([export("PKG")])["required"] is False


def test_preview_flags_a_declaration_that_disagrees_with_the_artifacts() -> None:
    artifacts = [mdb("FE", role="frontend")]
    assert acquisition_preview.preview("extract", artifacts, SPLIT, PROFILES)["mode_agrees"] is True
    assert acquisition_preview.preview("export", artifacts, SPLIT, PROFILES)["mode_agrees"] is False
    # An undeclared mode is not a disagreement - it is simply unstated.
    assert acquisition_preview.preview(None, artifacts, SPLIT, PROFILES)["mode_agrees"] is True


# init writes the declaration that acquisition later verifies. If the two rules ever
# drift, every generated manifest would be refused by the run that reads it.
def test_init_and_acquisition_agree_on_how_mode_is_derived() -> None:
    import init_app

    for artifacts in (
        [mdb("FE")],
        [export("PKG")],
        [mdb("FE"), export("PKG")],
        [document("LIST")],
        [],
    ):
        assert init_app.acquisition_mode(artifacts) == acquisition_preview.observed_mode(artifacts)


def _manifest(tmp_path: Path, artifacts: list[dict], mode: str | None = None) -> Path:
    import yaml

    project: dict = {
        "classification": {
            "topology": "split_file", "frontend_format": "mdb",
            "source_availability": "full", "backend_kinds": ["access_file"],
        },
    }
    if mode:
        project["acquisition_mode"] = mode
    path = tmp_path / "manifest.yaml"
    path.write_text(yaml.safe_dump({
        "version": "2.2",
        "app": {"id": "A99", "name_en": "Contract Test"},
        "project": project,
        "artifacts": artifacts,
    }, sort_keys=False), encoding="utf-8")
    return path


# A contradiction cannot be honoured either way, so it stops the run.
def test_acquisition_refuses_a_contradictory_artifact(tmp_path: Path) -> None:
    from acquisition_orchestrator import run_acquisition

    path = _manifest(tmp_path, [mdb("FE", role="frontend", acquisition="imported")])
    with pytest.raises(ValueError, match="ACQUISITION_IGNORED"):
        run_acquisition(path, tmp_path / "out", ("access_snapshot_extract",), "run-1")


# A stale mode label describes the artifacts wrongly, but the artifacts are the truth
# and the run they describe was going to be correct, so it is corrected, not refused.
def test_a_stale_mode_label_does_not_stop_the_run(tmp_path: Path) -> None:
    from acquisition_orchestrator import run_acquisition

    path = _manifest(tmp_path, [mdb("FE", role="frontend")], mode="export")
    # Without authorization the managed adapter reports BLOCKED, which is enough to see
    # that the mode label was not what stopped it, and that it was reported.
    result = run_acquisition(path, tmp_path / "out", (), "run-1")
    assert result["status"] == "BLOCKED"
    assert result["mode"]["declared"] == "export"
    assert result["mode"]["observed"] == "extract"
