from __future__ import annotations

from adapters.base import empty_sections
from acquisition_orchestrator import _capabilities, _flag_export_drift


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


def _drift_contribution(adapter_id: str, provenance: dict) -> dict:
    return {"adapter_id": adapter_id, "adapter_version": "1.0.0", "failures": [], "provenance": provenance}


# A hybrid run takes schema from the live database and definition text from an earlier
# export. That is legitimate; doing it silently is not. If the database has changed since
# the export, the bundle mixes current schema with stale definitions and says nothing.
def test_export_from_a_different_database_is_reported() -> None:
    managed = _drift_contribution("managed_access", {"producer": "ak-managed-access", "source_hashes": {"A05_FRONTEND": "a" * 64}})
    imported = _drift_contribution("imported_sources", {
        "producer": "declared_import", "source_hashes": {"PKG:form:forms/F.txt": "c" * 64},
        "exported_from": {"PKG:form:forms/F.txt": {"sha256": "b" * 64, "path": "old.mdb"}},
    })
    _flag_export_drift([managed, imported])
    assert [failure["reason"] for failure in imported["failures"]] == ["EXPORT_SOURCE_DRIFT"]
    assert "A05_FRONTEND" in imported["failures"][0]["detail"]


def test_export_from_the_acquired_database_is_not_reported() -> None:
    managed = _drift_contribution("managed_access", {"producer": "ak-managed-access", "source_hashes": {"A05_FRONTEND": "a" * 64}})
    imported = _drift_contribution("imported_sources", {
        "producer": "declared_import", "source_hashes": {"PKG:form:forms/F.txt": "c" * 64},
        "exported_from": {"PKG:form:forms/F.txt": {"sha256": "a" * 64}},
    })
    _flag_export_drift([managed, imported])
    assert imported["failures"] == []


# Silence is not evidence of a match. An export that never declared its source database
# must not be reported as drifted, and must not be reported as current either.
def test_export_without_a_declared_source_is_not_reported() -> None:
    managed = _drift_contribution("managed_access", {"producer": "ak-managed-access", "source_hashes": {"A05_FRONTEND": "a" * 64}})
    imported = _drift_contribution("imported_sources", {
        "producer": "declared_import", "source_hashes": {"PKG:form:forms/F.txt": "c" * 64},
    })
    _flag_export_drift([managed, imported])
    assert imported["failures"] == []


# An import-only run has no database to compare against, so there is nothing to claim.
def test_import_only_run_reports_no_drift() -> None:
    imported = _drift_contribution("imported_sources", {
        "producer": "declared_import", "source_hashes": {"PKG:form:forms/F.txt": "c" * 64},
        "exported_from": {"PKG:form:forms/F.txt": {"sha256": "b" * 64}},
    })
    _flag_export_drift([imported])
    assert imported["failures"] == []


# One entry per drifted database, not one per file: a 200-file export would otherwise
# bury every other failure in the bundle under 200 copies of the same finding.
def test_drift_is_reported_once_per_database_not_once_per_file() -> None:
    managed = _drift_contribution("managed_access", {"producer": "ak-managed-access", "source_hashes": {"A05": "a" * 64}})
    stale = {"sha256": "b" * 64}
    imported = _drift_contribution("imported_sources", {
        "producer": "declared_import",
        "source_hashes": {f"PKG:form:forms/F{index}.txt": "c" * 64 for index in range(50)},
        "exported_from": {f"PKG:form:forms/F{index}.txt": stale for index in range(50)},
    })
    _flag_export_drift([managed, imported])
    assert len(imported["failures"]) == 1


# --- A34: a required database that yielded nothing --------------------------

import types

import pytest

from acquisition_orchestrator import (
    _database_ids_with_rows,
    _declaration_capabilities,
    _refuse_a_required_database_that_yielded_nothing,
)


def _artifact(identifier: str, role: str = "backend", required: bool = True) -> types.SimpleNamespace:
    return types.SimpleNamespace(
        id=identifier, role=role, required=required,
        kind="access_database", backend_kind="access_file",
    )


def _with_tables(*database_ids: str) -> list[dict]:
    contribution = _contribution("managed_access", [])
    contribution["databases"]["tables"] = [
        {"database_id": identifier, "name": f"t_{identifier}"} for identifier in database_ids
    ]
    contribution["failures"] = []
    return [contribution]


def test_a_required_database_that_yielded_no_rows_stops_the_run() -> None:
    """Measured on A06: the run that lost the whole backend published anyway.

    188 tables and 730 fields where the complete bundle has 209 and 1,215 - and
    `bundle validate` said VALID, `phase1` said READY, and `coverage.json` reported
    730 as the figure. A Phase 1 against it would have described 60% of the schema as
    all of it.
    """
    contributions = _with_tables("FE")
    contributions[0]["failures"] = [{
        "logical_id": "BE",
        "reason": "DAO tier failed (DAO.DBEngine.36): Not a valid password.",
    }]
    with pytest.raises(ValueError) as caught:
        _refuse_a_required_database_that_yielded_nothing(
            (_artifact("FE", role="frontend"), _artifact("BE")),
            _database_ids_with_rows(contributions),
            contributions,
        )
    message = str(caught.value)
    assert message.startswith("REQUIRED_DATABASE_YIELDED_NOTHING:")
    # The failure is quoted, so the operator does not have to open a file with 159
    # entries to learn which one mattered.
    assert "BE (backend)" in message
    assert "Not a valid password" in message


def test_a_run_that_read_everything_it_was_told_to_is_not_refused() -> None:
    contributions = _with_tables("FE", "BE")
    _refuse_a_required_database_that_yielded_nothing(
        (_artifact("FE", role="frontend"), _artifact("BE")),
        _database_ids_with_rows(contributions),
        contributions,
    )


def test_an_optional_database_may_yield_nothing() -> None:
    """The contract the refusal creates, and the way out of it.

    Zero rows cannot distinguish an empty database from an unread one, so the rule
    errs toward refusing - and a project that genuinely has an empty one says so in
    the manifest rather than being blocked forever.
    """
    contributions = _with_tables("FE")
    _refuse_a_required_database_that_yielded_nothing(
        (_artifact("FE", role="frontend"), _artifact("BE", required=False)),
        _database_ids_with_rows(contributions),
        contributions,
    )


def test_a_backend_nobody_could_read_is_not_a_declared_authority() -> None:
    """A26's shape again: a gate answering from the wrong source.

    All three conditions read the manifest, and none asked whether the declared
    backend had been read - so the run that lost it still reported the capability
    satisfied, and the profile rule that requires it stayed happy.
    """
    artifacts = (_artifact("FE", role="frontend"), _artifact("BE"))
    # What the manifest declares, asked before any acquisition exists to check
    # against. Unchanged, because that is a different question.
    assert _declaration_capabilities(artifacts) == {"backend_authority_declared"}
    # And once there is a run to check against.
    assert _declaration_capabilities(artifacts, {"FE", "BE"}) == {"backend_authority_declared"}
    assert _declaration_capabilities(artifacts, {"FE"}) == set()
