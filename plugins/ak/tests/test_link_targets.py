"""A39, A40, A41, A42 - link objects, duplicated inventories, connections, and `DSN=`.

Every case here is a row that existed in A06's sealed bundle. The figures in the names
are that bundle's: 188 table objects for 35 tables, 360 rows for 180 links, 4 rows for
2 specifications, `[]` for two SQL Server databases, and three ODBC links read as
delimited files.

The point of the file is the pair of tests that would have failed the *obvious* fix:
`test_an_odbc_link_is_not_an_autonumbered_duplicate` and
`test_a_source_table_that_carries_digits_is_not_a_duplicate`. A rule matching
`name != source_table_name`, or one matching a trailing-digit suffix, passes everything
else in this file and destroys those two.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

import bundle_assembly  # noqa: E402
import feed_samples  # noqa: E402
import link_targets  # noqa: E402

ODBC = ("ODBC;DSN=SMSIIS_TargetNeo;UID=<REDACTED>;APP=Microsoft (R) Access;"
        "WSID=SYSTEM01;DATABASE=TargetNeo;Trusted_Connection=Yes")
JET = r";DATABASE=L:\a06\常温品物流支援2003data2003.mdb"
DEAD = r";DATABASE=L:\新物流支援\常温\常温品物流支援data.mdb"


def flat(name, source, connect, read_error=""):
    return {"database_id": "FE", "name": name, "source_table_name": source,
            "connect": connect, "read_error": read_error, "attributes": 1073741824}


def component(name, source, connect, read_error=""):
    """The same link as the managed route describes it: everything under `metadata`."""
    return {"database_id": "FE", "name": name, "kind": "table", "container": "data",
            "id": f"FE:table:{name}", "logical_id": f"FE:table:{name}",
            "depends_on": [], "module_hint": "data", "source_paths": [],
            "metadata": {"linked": True, "connect": connect,
                         "source_table_name": source, "read_error": read_error}}


# ---------------------------------------------------------------- A39, the rule

def test_access_numbers_the_link_not_the_source():
    assert link_targets.is_autonumbered_duplicate("商品情報3", "商品情報")
    assert link_targets.is_autonumbered_duplicate("その他データ6", "その他データ")
    assert link_targets.is_autonumbered_duplicate("受注情報累積10", "受注情報累積")


def test_an_odbc_link_is_not_an_autonumbered_duplicate():
    """SQL Server answers `dbo.X` for a link named `X`, so `name != source` fires."""
    for name in ("仕入商品マスタ", "受注年月商品", "食材入荷予定データ"):
        assert name != f"dbo.{name}"
        assert not link_targets.is_autonumbered_duplicate(name, f"dbo.{name}")


def test_a_source_table_that_carries_digits_is_not_a_duplicate():
    """`商品情報20121115` is a real table named for a date, not `商品情報` linked again."""
    assert not link_targets.is_autonumbered_duplicate("商品情報20121115", "商品情報20121115")
    assert not link_targets.is_autonumbered_duplicate("受20130824", "受20130824")


def test_a_link_with_no_source_name_is_not_a_duplicate():
    assert not link_targets.is_autonumbered_duplicate("商品情報3", "")


def test_a_prefix_followed_by_anything_but_digits_is_not_a_duplicate():
    assert not link_targets.is_autonumbered_duplicate("商品情報aa", "商品情報")
    assert not link_targets.is_autonumbered_duplicate("商品情報old", "商品情報")


# ------------------------------------------------------- A39, objects to tables

def test_an_application_of_thirty_five_tables_is_not_reported_as_one_hundred_and_eighty_eight():
    rows = [flat(f"商品情報{n}" if n else "商品情報", "商品情報", DEAD if n else JET)
            for n in range(0, 8)]
    rows += [flat("商品マスタ", "商品マスタ", JET), flat("仕入商品マスタ", "dbo.仕入商品マスタ", ODBC)]
    rows += [flat("発注点設定", "", "")]
    summary, = link_targets.summarise(rows)
    assert summary["table_objects"] == 11
    assert summary["local_tables"] == 1
    assert summary["link_objects"] == 10
    assert summary["autonumbered_duplicate_links"] == 7
    # 商品情報, 商品マスタ, dbo.仕入商品マスタ - and the local table on top.
    assert summary["distinct_source_table_names"] == 3
    assert summary["tables_if_targets_are_copies"] == 4


def test_both_bounds_are_reported_because_one_table_at_two_paths_is_unresolved():
    rows = [flat("商品マスタ", "商品マスタ", JET), flat("商品マスタ1", "商品マスタ", DEAD)]
    summary, = link_targets.summarise(rows)
    assert summary["distinct_source_table_names"] == 1
    assert summary["distinct_target_and_source_pairs"] == 2
    assert summary["tables_if_targets_are_copies"] == 1
    assert summary["tables_if_targets_are_distinct"] == 2
    alias, = link_targets.unresolved_aliases(rows)
    assert alias["source_table_name"] == "商品マスタ"
    assert len(alias["targets"]) == 2


def test_a_summary_reads_a_link_described_as_a_component():
    """The shape A40's fold keeps is the one whose fields sit under `metadata`."""
    summary, = link_targets.summarise([component("商品情報3", "商品情報", DEAD)])
    assert summary["link_objects"] == 1
    assert summary["local_tables"] == 0
    assert summary["autonumbered_duplicate_links"] == 1


# ------------------------------------------------------------------------- A40

def test_two_routes_describing_one_link_are_folded_to_one():
    rows = [flat("商品マスタ", "商品マスタ", JET), component("商品マスタ", "商品マスタ", JET)]
    folded = link_targets.collapse(rows)
    assert len(folded) == 1
    assert link_targets.field(folded[0], "connect") == JET
    assert link_targets.field(folded[0], "source_table_name") == "商品マスタ"


def test_the_fold_keeps_two_rows_that_disagree():
    """A real discrepancy about a link is not a duplicate, and is not resolved here."""
    rows = [flat("商品マスタ", "商品マスタ", JET), flat("商品マスタ", "商品マスタ", DEAD)]
    assert len(link_targets.collapse(rows)) == 2


def test_the_interface_inventories_that_two_adapters_write_are_deduped():
    assert set(bundle_assembly.INTERFACE_IDENTITY) == {"linked_tables", "imex_specs"}
    assert bundle_assembly.INTERFACE_IDENTITY["linked_tables"] == ("database_id", "name")
    assert bundle_assembly.INTERFACE_IDENTITY["imex_specs"] == ("database_id", "table")


def test_a_specification_reported_by_both_routes_is_one_specification():
    rows = [{"database_id": "FE", "table": "MSysIMEXSpecs", "status": "read", "rows": []},
            {"database_id": "FE", "table": "MSysIMEXSpecs", "status": "read", "rows": []}]
    bundle_assembly._dedupe_schema(rows, ("database_id", "table"))
    assert len(rows) == 1


# ------------------------------------------------------------------------- A41

def test_connections_are_derived_where_nothing_ever_wrote_them():
    rows = [flat("仕入商品マスタ", "dbo.仕入商品マスタ", ODBC),
            flat("食材入荷予定データ", "dbo.食材入荷予定データ", ODBC),
            flat("商品マスタ", "商品マスタ", JET),
            flat("商品マスタ1", "商品マスタ", DEAD, read_error="For loop not initialized")]
    connections = link_targets.connections(rows)
    assert len(connections) == 3
    odbc, = [c for c in connections if c["kind"] == "odbc"]
    assert odbc["dsn"] == "SMSIIS_TargetNeo"
    assert odbc["database"] == "TargetNeo"
    assert odbc["link_count"] == 2
    assert sorted(odbc["source_tables"]) == ["dbo.仕入商品マスタ", "dbo.食材入荷予定データ"]
    dead, = [c for c in connections if c["unreadable_link_count"]]
    assert dead["link_count"] == dead["unreadable_link_count"] == 1
    assert dead["autonumbered_duplicate_link_count"] == 1


def test_a_local_table_names_no_connection():
    assert link_targets.connections([flat("発注点設定", "", "")]) == []


def test_connections_are_ordered_so_an_unchanged_source_gives_an_unchanged_bundle():
    rows = [flat("b", "b", DEAD), flat("a", "a", JET), flat("c", "c", ODBC)]
    once = link_targets.connections(rows)
    assert once == link_targets.connections(list(reversed(rows)))
    assert json.dumps(once, ensure_ascii=False)  # no sets survive into the bundle


def test_a_connection_carries_no_credential_even_if_a_route_forgets():
    """The macro redacts PWD/PASSWORD/UID; the section is named for the property."""
    leaked = "ODBC;DSN=X;UID=sa;PWD=hunter2;TOKEN=abc;DATABASE=T"
    connection, = link_targets.connections([flat("t", "dbo.t", leaked)])
    assert "hunter2" not in connection["connect"]
    assert "sa" not in connection["connect"].replace("<REDACTED>", "")
    assert "abc" not in connection["connect"]
    assert connection["connect"].count("<REDACTED>") == 3


def test_the_assembly_identity_covers_the_module_that_derives_them():
    """A16: a bundle's identity must move when the code writing its content moves."""
    assert "contracts/link_targets.py" in bundle_assembly._IDENTITY_SOURCES


# ------------------------------------------------------------------------- A42

def test_an_odbc_data_source_is_not_an_import_specification():
    assert feed_samples.specification_name(ODBC) == ""
    assert feed_samples.feeds([flat("仕入商品マスタ", "dbo.仕入商品マスタ", ODBC)]) == []


def test_a_text_link_still_names_its_specification():
    connect = (r"Text;DSN=DPSHOHIN ﾘﾝｸの定義;FMT=Delimited;HDR=NO;IMEX=2;"
               r"CharacterSet=932;DATABASE=C:\feeds")
    assert feed_samples.specification_name(connect) == "DPSHOHIN ﾘﾝｸの定義"
    feed, = feed_samples.feeds([flat("元商品マスタ", "Dpshohin.csv", connect)])
    assert feed.spec_name == "DPSHOHIN ﾘﾝｸの定義"


# --------------------------------------------------------------------- parsing

@pytest.mark.parametrize("connect,kind,database", [
    (JET, "file", r"L:\a06\常温品物流支援2003data2003.mdb"),
    (ODBC, "odbc", "TargetNeo"),
    (r"Text;DSN=spec;DATABASE=C:\feeds", "file", r"C:\feeds"),
    ("", "local", ""),
    ("something unparseable", "other", ""),
])
def test_a_connect_string_is_read_by_its_driver(connect, kind, database):
    parsed = link_targets.parse_connect(connect)
    assert parsed["kind"] == kind
    assert parsed["database"] == database


def test_the_same_file_by_two_letter_cases_is_one_target():
    lower = link_targets.parse_connect(r";DATABASE=L:\a06\X.mdb")["target"]
    upper = link_targets.parse_connect(r";DATABASE=l:\A06\x.MDB")["target"]
    assert lower == upper


def test_a_unc_path_and_a_mapped_drive_stay_two_targets():
    """The kit reports them separately; resolving them is a question about the estate."""
    unc = link_targets.parse_connect(r";DATABASE=\\10.10.10.101\sms\常温\x.mdb")["target"]
    drive = link_targets.parse_connect(r";DATABASE=L:\常温\x.mdb")["target"]
    assert unc != drive
