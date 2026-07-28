from __future__ import annotations

from adapters.base import empty_sections
from acquisition_orchestrator import _capabilities


def _contribution(adapter_id: str, capabilities: list[str]) -> dict:
    return {
        "adapter_id": adapter_id, "adapter_version": "1.0.0", "app_id": "SYN",
        "status": "VALID", **empty_sections(), "failures": [],
        "provenance": {
            "producer": adapter_id, "source_hashes": {}, "capabilities": capabilities,
        },
    }


def test_sql_tables_do_not_imply_access_schema_capability() -> None:
    contribution = _contribution("sql_server", ["server_object_inventory"])
    contribution["databases"]["tables"].append({
        "schema": "dbo", "name": "Order", "type": "table"
    })
    assert _capabilities([contribution]) == {"server_object_inventory"}


def test_only_declared_capabilities_are_aggregated() -> None:
    first = _contribution("imported_sources", ["vba_query_inventory"])
    second = _contribution("managed_access", ["access_object_inventory", "ui_object_inventory"])
    assert _capabilities([first, second]) == {
        "vba_query_inventory", "access_object_inventory", "ui_object_inventory"
    }
