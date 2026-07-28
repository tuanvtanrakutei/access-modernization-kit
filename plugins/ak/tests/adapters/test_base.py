from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from adapters.base import (
    AcquisitionResult,
    BundleContribution,
    contribution_content_id,
    validate_contribution,
)

PACKAGE = Path(__file__).resolve().parents[2]

def _contribution() -> BundleContribution:
    return {
        "adapter_id": "imported_sources",
        "adapter_version": "1.0.0",
        "app_id": "SYN",
        "status": "PARTIAL",
        "databases": {"objects": [], "tables": [], "fields": [], "indexes": [], "declared_relationships": []},
        "code": {"vba": [], "access_sql": [], "sql_server": []},
        "ui": {"forms": [], "reports": [], "macros": []},
        "interfaces": {"linked_tables": [], "file_interfaces": [], "connections_redacted": []},
        "evidence_sources": {
            "documents": {"inventory": []}, "screenshots": {"inventory": []},
            "reports": {"inventory": []}, "samples": {"inventory": []},
        },
        "failures": [],
        "provenance": {"producer": "manual", "source_hashes": {}},
    }

def test_contribution_matches_schema() -> None:
    schema = json.loads((PACKAGE / "schemas" / "bundle-contribution.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(_contribution(), schema)

def test_content_id_is_path_and_order_stable() -> None:
    first = _contribution()
    second = _contribution()
    second["provenance"]["source_hashes"] = {"b": "2" * 64, "a": "1" * 64}
    first["provenance"]["source_hashes"] = {"a": "1" * 64, "b": "2" * 64}
    assert contribution_content_id(first) == contribution_content_id(second)

def test_content_id_changes_with_status() -> None:
    baseline = _contribution()
    changed = _contribution()
    changed["status"] = "VALID"
    assert contribution_content_id(baseline) != contribution_content_id(changed)

def test_result_rejects_unknown_status() -> None:
    try:
        AcquisitionResult(app_id="SYN", adapter_id="x", adapter_version="1", status="DONE", records=(), failures=(), source_hashes={})
    except ValueError:
        return
    raise AssertionError("AcquisitionResult must reject unknown status")