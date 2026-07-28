from __future__ import annotations

import json
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
