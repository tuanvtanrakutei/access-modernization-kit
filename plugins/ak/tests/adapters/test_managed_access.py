from __future__ import annotations

import dataclasses
import json
import subprocess
from pathlib import Path

from adapters.base import AcquisitionRequest, AcquisitionResult
from adapters.managed_access.adapter import ManagedAccessAdapter

CLASSIFICATION = {
    "topology": "split_file", "frontend_format": "mdb",
    "source_availability": "full", "backend_kinds": ["access_file"],
}

def test_plan_requires_explicit_snapshot_authorization(tmp_path: Path) -> None:
    db = tmp_path / "frontend.mdb"
    db.write_bytes(b"synthetic-signature-only")
    request = AcquisitionRequest(
        "SYN", CLASSIFICATION,
        ({"id": "FRONTEND", "kind": "access_database", "role": "frontend", "acquisition": "managed", "required": True, "source_ref": {"type": "local_path", "value": "frontend.mdb"}, "format": "mdb"},),
        tmp_path,
    )
    plan = ManagedAccessAdapter().plan(request)
    assert plan.authorization_required == ("access_snapshot_extract",)
    assert "--execute" not in " ".join(plan.reads)

def test_normalize_maps_access_components() -> None:
    result = AcquisitionResult(
        app_id="SYN", adapter_id="managed_access", adapter_version="1.0.0", status="PARTIAL",
        records=({"database_id": "FRONTEND", "components": [
            {"type": "vba_module", "name": "Order", "text": "Option Explicit"},
            {"type": "query", "name": "qOrder", "sql": "SELECT 1"},
            {"type": "form", "name": "F_Order", "text": "Version =20"},
        ], "project_context": {}, "warnings": ["protected object"]},),
        failures=(), source_hashes={"FRONTEND": "a" * 64},
    )
    contribution = ManagedAccessAdapter().normalize(result)
    assert contribution["app_id"] == "SYN"
    assert len(contribution["code"]["vba"]) == 1
    assert len(contribution["code"]["access_sql"]) == 1
    assert len(contribution["ui"]["forms"]) == 1
    assert contribution["status"] == "PARTIAL"

def test_normalize_never_carries_snapshot_path() -> None:
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "acquisition" / "managed-access-export" / "complete" / "access-extraction.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    result = ManagedAccessAdapter().result_from_extraction("SYN", data)
    rendered = json.dumps(ManagedAccessAdapter().normalize(result))
    assert "snapshot" not in rendered.lower()
    assert ".mdb" not in rendered.lower()


def _managed_plan(tmp_path: Path, authorized: bool = True):
    db = tmp_path / "frontend.mdb"
    db.write_bytes(b"synthetic-signature-only")
    request = AcquisitionRequest("SYN", CLASSIFICATION, ({
        "id": "FRONTEND", "kind": "access_database", "role": "frontend",
        "acquisition": "managed", "required": True,
        "source_ref": {"type": "local_path", "value": "frontend.mdb"}, "format": "mdb",
    },), tmp_path)
    return dataclasses.replace(
        ManagedAccessAdapter().plan(request),
        acquisition_id="run-1", runtime_output_root=str(tmp_path / "staging"),
        granted_authorization=("access_snapshot_extract",) if authorized else (),
    )


def test_acquire_without_authorization_never_spawns(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("spawned")))
    result = ManagedAccessAdapter().acquire(_managed_plan(tmp_path, authorized=False))
    assert result.status == "BLOCKED"
    assert result.failures[0]["reason"] == "AUTHORIZATION_REQUIRED"


def test_acquire_rejects_preexisting_receipt(monkeypatch, tmp_path: Path) -> None:
    plan = _managed_plan(tmp_path)
    receipt = Path(plan.runtime_output_root) / "FRONTEND" / plan.acquisition_id / "access-extraction.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("spawned")))
    result = ManagedAccessAdapter().acquire(plan)
    assert result.status == "BLOCKED"
    assert result.failures[0]["reason"] == "STALE_EXTRACTION_RESULT"


def test_acquire_accepts_fresh_extractor_receipt(monkeypatch, tmp_path: Path) -> None:
    plan = _managed_plan(tmp_path)
    source_before = Path(plan.operations[0]["source"]).read_bytes()

    def fake_run(command, **kwargs):
        receipt = Path(plan.runtime_output_root) / "FRONTEND" / plan.acquisition_id / "access-extraction.json"
        receipt.parent.mkdir(parents=True)
        receipt.write_text(json.dumps({
            "database_id": "FRONTEND", "status": "EXTRACTED",
            "source": {"sha256": "a" * 64}, "components": [], "warnings": [],
        }), encoding="utf-8")
        assert "--execute" in command
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = ManagedAccessAdapter().acquire(plan)
    assert result.status == "VALID"
    assert Path(plan.operations[0]["source"]).read_bytes() == source_before


def test_acquire_rejects_nonzero_extractor_without_receipt(monkeypatch, tmp_path: Path) -> None:
    plan = _managed_plan(tmp_path)
    monkeypatch.setattr(
        subprocess, "run",
        lambda command, **kwargs: subprocess.CompletedProcess(command, 2, "", "failed"),
    )
    result = ManagedAccessAdapter().acquire(plan)
    assert result.status == "BLOCKED"
    assert result.failures[0]["reason"] == "EXTRACTOR_FAILED"


def _extraction(**overrides: object) -> dict:
    data = {
        "schema_version": "2.1", "database_id": "DATA", "session_id": "s1",
        "source": {"path": "<ORIGINAL_REDACTED_BY_ADAPTER>", "format": "mdb", "sha256": "a" * 64},
        "snapshot": {"path": "s", "sha256": "a" * 64},
        "status": "EXTRACTED",
        "runtime": {}, "project_context": {}, "components": [], "warnings": [],
    }
    data.update(overrides)
    return data


# extract_access.ps1 labels every object with "kind"; the router used to read only
# "type"/"object_type", so a real extraction landed entirely in databases.objects
# and the ui/code sections stayed empty no matter how complete it was.
def test_normalize_routes_the_kind_key_the_extractor_actually_emits() -> None:
    data = _extraction(components=[
        {"kind": "table", "name": "T", "metadata": {"linked": False}},
        {"kind": "query", "name": "q", "metadata": {}},
        {"kind": "form", "name": "F", "metadata": {}},
        {"kind": "report", "name": "R", "metadata": {}},
        {"kind": "macro", "name": "M", "metadata": {}},
        {"kind": "module", "name": "Mod", "metadata": {}},
    ])
    adapter = ManagedAccessAdapter()
    contribution = adapter.normalize(adapter.result_from_extraction("SYN", data))
    assert contribution["databases"]["objects"] == []
    assert len(contribution["databases"]["tables"]) == 1
    assert len(contribution["code"]["access_sql"]) == 1
    assert len(contribution["code"]["vba"]) == 1
    assert len(contribution["ui"]["forms"]) == 1
    assert len(contribution["ui"]["reports"]) == 1
    assert len(contribution["ui"]["macros"]) == 1


# A linked table is declared as a table carrying metadata.linked, never as its own
# kind, so routing on kind alone lost every boundary the application depends on.
def test_normalize_records_a_linked_table_as_both_schema_and_boundary() -> None:
    data = _extraction(components=[
        {"kind": "table", "name": "Orders", "metadata": {"linked": True, "source_table_name": "order.txt"}},
    ])
    adapter = ManagedAccessAdapter()
    contribution = adapter.normalize(adapter.result_from_extraction("SYN", data))
    assert len(contribution["databases"]["tables"]) == 1
    assert len(contribution["interfaces"]["linked_tables"]) == 1
    assert "boundary_inventory" in contribution["provenance"]["capabilities"]


# Field and index detail used to stop at schema/tables.json, which normalize never
# reads, so field_inventory and key_index_inventory could not be reported at all.
def test_normalize_flattens_table_detail_into_field_and_index_inventories() -> None:
    data = _extraction(
        components=[{"kind": "table", "name": "Orders", "metadata": {"linked": False}}],
        tables=[{
            "name": "Orders",
            "fields": [{"name": "id", "type": 4, "size": 4, "required": True},
                       {"name": "code", "type": 10, "size": 20, "required": False}],
            "indexes": [{"name": "PrimaryKey", "primary": True, "unique": True, "fields": ["id"]}],
        }],
    )
    adapter = ManagedAccessAdapter()
    contribution = adapter.normalize(adapter.result_from_extraction("SYN", data))
    assert len(contribution["databases"]["fields"]) == 2
    assert len(contribution["databases"]["indexes"]) == 1
    assert contribution["databases"]["fields"][0]["table"] == "Orders"
    capabilities = contribution["provenance"]["capabilities"]
    assert "field_inventory" in capabilities
    assert "key_index_inventory" in capabilities


# The whole point of the three capabilities above: without them Phase 1 is blocked
# by its own baseline, however clean the database is. Phase 1 can still be held by
# a profile rule (backend authority) - that is a separate, manifest-level gap, so
# this asserts the baseline is satisfied rather than that the phase turns READY.
def test_a_complete_access_extraction_satisfies_the_phase1_baseline() -> None:
    from classification import Classification
    from phase_readiness import compute_readiness

    data = _extraction(
        components=[
            {"kind": "table", "name": "Orders", "metadata": {"linked": False}},
            {"kind": "table", "name": "Feed", "metadata": {"linked": True}},
            {"kind": "query", "name": "q", "metadata": {}},
            {"kind": "form", "name": "F", "metadata": {}},
        ],
        tables=[{
            "name": "Orders",
            "fields": [{"name": "id", "type": 4, "size": 4, "required": True}],
            "indexes": [{"name": "PrimaryKey", "primary": True, "unique": True, "fields": ["id"]}],
        }],
    )
    adapter = ManagedAccessAdapter()
    contribution = adapter.normalize(adapter.result_from_extraction("SYN", data))
    profiles = Path(__file__).resolve().parents[2] / "profiles"
    readiness = compute_readiness(
        Classification("split_file", "mdb", "full", ("access_file",)),
        profiles,
        set(contribution["provenance"]["capabilities"]),
    )
    assert "baseline.phase1" not in readiness["phase1"]["rule_ids"]
    assert readiness["phase2"]["status"] == "READY"
    assert readiness["phase3"]["status"] == "READY"


# PowerShell writes diagnostics in the console codepage. A strict utf-8 decode blew
# up subprocess's reader threads, so the extractor's own explanation never reached
# the caller and every failure looked like a bare returncode.
def test_extractor_failure_keeps_its_diagnostic_and_tolerates_console_codepage(monkeypatch, tmp_path: Path) -> None:
    plan = _managed_plan(tmp_path)
    seen: dict[str, object] = {}

    def fake_run(command, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(command, 3, "", "Access is registered but COM activation failed.")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = ManagedAccessAdapter().acquire(plan)
    assert seen["errors"] == "replace"
    assert result.failures[0]["reason"] == "EXTRACTOR_FAILED"
    assert "COM activation failed" in result.failures[0]["detail"]


# The manifest schema allows extra artifact keys, and a declared runtime block is the
# only way to reach the extractor's own remedies - pinning an install, skipping a
# host a broken VBA project would stall, raising the timeout.
def test_declared_runtime_reaches_the_extractor_command(monkeypatch, tmp_path: Path) -> None:
    plan = _managed_plan(tmp_path)
    plan.operations[0]["artifact"]["runtime"] = {
        "access_progid": "Access.Application.11",
        "skip_object_export": True,
        "timeout": 900,
        "unknown_key": "ignored",
    }
    seen: list[str] = []

    def fake_run(command, **kwargs):
        seen.extend(command)
        return subprocess.CompletedProcess(command, 1, "", "no")

    monkeypatch.setattr(subprocess, "run", fake_run)
    ManagedAccessAdapter().acquire(plan)
    assert "--access-progid" in seen and "Access.Application.11" in seen
    assert "--skip-object-export" in seen
    assert seen[seen.index("--timeout") + 1] == "900"
    # An unrecognized key must never become a command-line argument.
    assert "ignored" not in seen and "--unknown-key" not in seen


# The extractor writes its receipt with a BOM. Reading it as plain utf-8 raised on
# every real extraction while a Python-written test fixture passed.
def test_receipt_is_read_even_with_a_byte_order_mark(monkeypatch, tmp_path: Path) -> None:
    plan = _managed_plan(tmp_path)
    receipt = Path(plan.runtime_output_root) / "FRONTEND" / plan.acquisition_id / "access-extraction.json"

    def fake_run(command, **kwargs):
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_text(
            json.dumps(_extraction(database_id="FRONTEND", status="EXTRACTED")),
            encoding="utf-8-sig",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = ManagedAccessAdapter().acquire(plan)
    assert result.status == "VALID"
    assert result.source_hashes["FRONTEND"] == "a" * 64


# A22 gave the shape exclusion an evidence trail, and the trail arrives through the
# warning channel: an `EXCLUDED:` summary, one `EXCLUDED table <name>: <fields>` line
# per table dropped, and one `KEPT table ...` per table the second condition saved.
# Only the summary carried the marker this router matched, so 210 of those lines on one
# A05 frontend would have been filed as objects that could not be read - which is the
# defect the router was written to fix, in the code that fixed it.
def test_an_exclusion_with_its_evidence_is_still_an_exclusion() -> None:
    adapter = ManagedAccessAdapter()
    data = _extraction(warnings=[
        "EXCLUDED: 3 non-model tables: Access temporary (~*) and auto-generated "
        "ImportErrors tables.",
        "EXCLUDED table Sheet1$_x: A(Text) / B(Text) / C(Long) - Access ImportErrors "
        "shape and field names",
        "KEPT table M: X(Text) / Y(Text) / Z(Long) - the ImportErrors shape, but not "
        "its field names",
        "Could not read table T: no read definitions permission",
    ])
    failures = adapter.normalize(adapter.result_from_extraction("SYN", data))["failures"]
    kinds = [entry.get("kind") for entry in failures]
    assert kinds == ["exclusion", "exclusion", "observation", None]
    # And every reason survives in full: the field names are the whole point of the line.
    assert "A(Text) / B(Text) / C(Long)" in failures[1]["reason"]
