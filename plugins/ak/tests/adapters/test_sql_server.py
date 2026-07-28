from pathlib import Path

from adapters.base import AcquisitionRequest
from adapters.sql_server.adapter import SqlServerAdapter

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "acquisition" / "sql-server-scripts"
CLASSIFICATION = {"topology": "client_server", "frontend_format": "adp", "source_availability": "full", "backend_kinds": ["sql_server"]}

def _request(root: Path, artifacts: tuple[dict, ...]) -> AcquisitionRequest:
    return AcquisitionRequest("SYN", CLASSIFICATION, artifacts, root)

def test_scripts_and_catalog_produce_server_capability() -> None:
    artifacts = (
        {"id": "DDL", "kind": "sql_server_schema", "role": "backend", "acquisition": "imported", "required": True, "source_ref": {"type": "local_path", "value": "schema.sql"}, "format": "sql"},
        {"id": "CATALOG", "kind": "sql_server_catalog", "role": "backend", "acquisition": "imported", "required": True, "source_ref": {"type": "local_path", "value": "catalog.json"}, "format": "json"},
    )
    adapter = SqlServerAdapter()
    result = adapter.acquire(adapter.plan(_request(FIXTURE / "complete", artifacts)))
    contribution = adapter.normalize(result)
    assert result.status == "VALID"
    assert contribution["code"]["sql_server"]
    assert contribution["databases"]["tables"]
    assert contribution["provenance"]["capabilities"] == ["server_object_inventory"]

def test_mdf_and_ldf_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "db.mdf").write_bytes(b"synthetic")
    artifact = {"id": "MDF", "kind": "sql_server_data_file", "role": "backend", "acquisition": "imported", "required": True, "source_ref": {"type": "external_path", "value": str(tmp_path / "db.mdf")}, "format": "mdf"}
    adapter = SqlServerAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, (artifact,))))
    assert result.status == "INVALID"
    assert result.failures[0]["reason"] == "UNSUPPORTED_DIRECT_ATTACH"

def test_bak_is_reference_only() -> None:
    artifact = {"id": "BAK", "kind": "sql_server_backup", "role": "backend", "acquisition": "imported", "required": False, "source_ref": {"type": "external_path", "value": "X:/external/app.bak"}, "format": "bak"}
    adapter = SqlServerAdapter()
    result = adapter.acquire(adapter.plan(_request(FIXTURE / "incomplete", (artifact,))))
    contribution = adapter.normalize(result)
    assert ".bak" not in str(contribution).lower()
    assert result.status == "PARTIAL"
