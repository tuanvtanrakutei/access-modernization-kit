import zipfile
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


MODEL_XML = b'''<?xml version="1.0" encoding="utf-8"?>
<DataSchemaModel xmlns="http://schemas.microsoft.com/sqlserver/dac/Serialization/2012/02">
  <Model>
    <Element Type="SqlTable" Name="[sales].[Order]" />
    <Element Type="SqlProcedure" Name="[sales].[usp_Order]" />
    <Element Type="SqlScalarFunction" Name="[sales].[fn_Order]" />
    <Element Type="SqlColumn" Name="[sales].[Order].[OrderId]" />
  </Model>
</DataSchemaModel>'''


def _write_dacpac(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)


def test_dacpac_model_maps_supported_objects_without_extracting(tmp_path: Path) -> None:
    _write_dacpac(tmp_path / "schema.dacpac", {"model.xml": MODEL_XML})
    artifact = {
        "id": "DACPAC", "kind": "sql_server_package", "role": "backend",
        "acquisition": "imported", "required": True,
        "source_ref": {"type": "local_path", "value": "schema.dacpac"}, "format": "dacpac",
    }
    adapter = SqlServerAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, (artifact,))))
    contribution = adapter.normalize(result)
    assert result.status == "VALID"
    assert [(item["schema"], item["name"], item["type"]) for item in contribution["databases"]["tables"]] == [
        ("sales", "Order", "table")
    ]
    assert {(item["name"], item["type"]) for item in contribution["databases"]["objects"]} == {
        ("fn_Order", "function"), ("usp_Order", "procedure")
    }
    assert not (tmp_path / "model.xml").exists()


def test_dacpac_requires_exactly_one_model(tmp_path: Path) -> None:
    _write_dacpac(tmp_path / "schema.dacpac", {"a/model.xml": MODEL_XML, "b/model.xml": MODEL_XML})
    artifact = {
        "id": "DACPAC", "kind": "sql_server_package", "role": "backend",
        "acquisition": "imported", "required": True,
        "source_ref": {"type": "local_path", "value": "schema.dacpac"}, "format": "dacpac",
    }
    adapter = SqlServerAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, (artifact,))))
    assert result.status == "INVALID"
    assert result.failures == ({"logical_id": "DACPAC", "reason": "DACPAC_MODEL_REQUIRED"},)
