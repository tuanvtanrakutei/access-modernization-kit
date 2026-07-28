from __future__ import annotations

import hashlib
import json
import re
import zipfile
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

from adapters.base import (
    AcquisitionPlan, AcquisitionRequest, AcquisitionResult, BundleContribution,
    CapabilityReport, empty_sections, validate_contribution,
)
from adapters.imported_sources.adapter import safe_zip_members

PACKAGE = Path(__file__).resolve().parents[2]
ADAPTER_ID = "sql_server"
ADAPTER_VERSION = "1.0.0"

UNSUPPORTED = {"mdf", "ldf"}
SCRIPT_FORMATS = {"sql"}
CATALOG_FORMATS = {"json"}
PACKAGE_FORMATS = {"dacpac"}
BACKUP_FORMATS = {"bak"}
DACPAC_TYPES = {
    "SqlTable": "table", "SqlView": "view", "SqlProcedure": "procedure",
    "SqlScalarFunction": "function", "SqlTableValuedFunction": "function",
    "SqlDmlTrigger": "trigger", "SqlUserDefinedType": "type", "SqlSequence": "sequence",
}


class SqlServerAdapter:
    adapter_id = ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    supported_profiles = ("client_server", "hybrid")
    supported_artifact_kinds = (
        "sql_server_schema", "sql_server_catalog", "sql_server_package",
        "sql_server_backup", "sql_server_data_file",
    )

    def probe(self, request: AcquisitionRequest) -> CapabilityReport:
        missing = tuple(
            artifact["id"] for artifact in request.artifacts
            if str(artifact.get("format", "")).lower() in UNSUPPORTED
        )
        return CapabilityReport(self.adapter_id, self.adapter_version, not missing, missing)

    def plan(self, request: AcquisitionRequest) -> AcquisitionPlan:
        operations = tuple({"artifact": artifact, "source_root": str(request.source_root.resolve())} for artifact in request.artifacts)
        return AcquisitionPlan(
            self.adapter_id, self.adapter_version,
            tuple(artifact["id"] for artifact in request.artifacts),
            operations=operations, app_id=request.app_id,
        )

    def acquire(self, plan: AcquisitionPlan) -> AcquisitionResult:
        records: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        hashes: dict[str, str] = {}
        for operation in plan.operations:
            artifact = operation["artifact"]
            try:
                produced, produced_failures, produced_hashes = _handle_artifact(
                    artifact, Path(operation["source_root"])
                )
            except (OSError, UnicodeError, ValueError, zipfile.BadZipFile, ElementTree.ParseError) as exc:
                reason = str(exc) if str(exc).isupper() else "INVALID_SQL_ARTIFACT"
                failures.append({"logical_id": artifact["id"], "reason": reason})
                continue
            records.extend(produced)
            failures.extend(produced_failures)
            hashes.update(produced_hashes)
        if failures and not records:
            status = "INVALID"
        elif failures or any(record["kind"] == "backup_reference" for record in records) and not _has_inventory(records):
            status = "PARTIAL" if records else "INVALID"
        elif _has_inventory(records):
            status = "VALID"
        else:
            status = "PARTIAL"
        return AcquisitionResult(plan.app_id, self.adapter_id, self.adapter_version, status, tuple(records), tuple(failures), hashes)

    def normalize(self, result: AcquisitionResult) -> BundleContribution:
        sections = empty_sections()
        has_inventory = False
        for record in result.records:
            kind = record["kind"]
            if kind == "sql_server":
                sections["code"]["sql_server"].append({key: value for key, value in record.items() if key != "catalog"})
            elif kind == "catalog":
                has_inventory = True
                for obj in record["catalog"]["objects"]:
                    target = "tables" if obj["type"] == "table" else "objects"
                    sections["databases"][target].append(obj)
            elif kind == "backup_reference":
                sections["interfaces"]["file_interfaces"].append({"logical_id": record["logical_id"], "external_only": True, "role": "sql_server_backup"})
        provenance: dict[str, Any] = {
            "producer": "sql-server-evidence", "source_hashes": dict(sorted(result.source_hashes.items())),
            "capabilities": ["server_object_inventory"] if has_inventory else [],
        }
        return validate_contribution({
            "adapter_id": self.adapter_id, "adapter_version": self.adapter_version, "app_id": result.app_id,
            "status": result.status, **sections, "failures": list(result.failures), "provenance": provenance,
        })


def _has_inventory(records: list[dict[str, Any]]) -> bool:
    return any(record["kind"] == "catalog" for record in records)


def _resolve_source(artifact: dict[str, Any], source_root: Path) -> Path:
    ref = artifact["source_ref"]
    value = ref["value"]
    if ref.get("type") == "external_path":
        return Path(value)
    return (source_root / value)


def _handle_artifact(artifact: dict[str, Any], source_root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, str]]:
    fmt = str(artifact.get("format", "")).lower()
    if fmt in UNSUPPORTED:
        return [], [{"logical_id": artifact["id"], "reason": "UNSUPPORTED_DIRECT_ATTACH"}], {}
    if fmt in BACKUP_FORMATS:
        return [{"logical_id": artifact["id"], "kind": "backup_reference", "external_only": True}], [], {}
    path = _resolve_source(artifact, source_root)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if fmt in SCRIPT_FORMATS:
        text = raw.decode("utf-8", errors="strict").replace("\r\n", "\n")
        return [{"logical_id": artifact["id"], "kind": "sql_server", "text": text, "sha256": digest}], [], {artifact["id"]: digest}
    if fmt in CATALOG_FORMATS:
        catalog = _validate_catalog(json.loads(raw.decode("utf-8")))
        return [{"logical_id": artifact["id"], "kind": "catalog", "catalog": catalog, "sha256": digest}], [], {artifact["id"]: digest}
    if fmt in PACKAGE_FORMATS:
        objects = _read_dacpac_model(path)
        catalog = _validate_catalog({"version": "1.0", "database": artifact["id"], "objects": objects})
        return [{"logical_id": artifact["id"], "kind": "catalog", "catalog": catalog, "sha256": digest}], [], {artifact["id"]: digest}
    return [], [{"logical_id": artifact["id"], "reason": "UNSUPPORTED_SQL_ARTIFACT"}], {}


def _validate_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    import jsonschema

    schema_path = PACKAGE / "schemas" / "sql-server-catalog.schema.json"
    jsonschema.validate(catalog, json.loads(schema_path.read_text(encoding="utf-8")))
    return catalog


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _qualified_name(value: str) -> tuple[str, str]:
    parts = re.findall(r"\[([^]]+)\]", value)
    if len(parts) >= 2:
        return parts[-2], parts[-1]
    plain = [part for part in value.split(".") if part]
    return (plain[-2], plain[-1]) if len(plain) >= 2 else ("dbo", plain[-1])


def _read_dacpac_model(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as archive:
        members = safe_zip_members(archive)
        models = [info for info in members if Path(info.filename).name == "model.xml"]
        if len(models) != 1:
            raise ValueError("DACPAC_MODEL_REQUIRED")
        root = ElementTree.fromstring(archive.read(models[0]))
    objects: list[dict[str, Any]] = []
    for element in root.iter():
        if _local_name(element.tag) != "Element":
            continue
        mapped = DACPAC_TYPES.get(str(element.get("Type", "")))
        if mapped is None:
            continue
        schema, name = _qualified_name(str(element.get("Name", "")))
        objects.append({
            "schema": schema, "name": name, "type": mapped,
            "columns": [], "definition": None,
        })
    return sorted(objects, key=lambda item: (item["schema"], item["name"], item["type"]))
