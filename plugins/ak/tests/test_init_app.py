from __future__ import annotations

from pathlib import Path

import init_app


def _sources(root: Path) -> Path:
    """A source tree in the shape this kit's own extractor produces."""
    (root / "access").mkdir(parents=True)
    (root / "forms").mkdir()
    (root / "queries").mkdir()
    (root / "schema").mkdir()
    return root


# Two Access databases are a split application, not a monolith with two frontends.
# The wrong role is the costly part: nothing then declares an authoritative backend,
# so Phase 1 can never leave BLOCKED however complete the extraction is.
def test_two_access_databases_are_classified_as_a_split_application(tmp_path: Path) -> None:
    app_root = tmp_path / "A05"
    sources = _sources(app_root / "sources")
    (sources / "access" / "frontend.mdb").write_bytes(b"x")
    (sources / "access" / "data.mdb").write_bytes(b"x")

    classification, artifacts = init_app.discover_sources(app_root)

    assert classification["topology"] == "split_file"
    assert classification["backend_kinds"] == ["access_file"]
    databases = [item for item in artifacts if item["kind"] == "access_database"]
    assert len(databases) == 2
    # Which file is authoritative cannot be read off the filesystem, so the role is
    # left explicitly unknown for a human rather than guessed from a filename.
    assert {item["role"] for item in databases} == {"unknown"}


def test_a_single_access_database_stays_a_monolith(tmp_path: Path) -> None:
    app_root = tmp_path / "A05"
    sources = _sources(app_root / "sources")
    (sources / "access" / "only.mdb").write_bytes(b"x")

    classification, artifacts = init_app.discover_sources(app_root)

    assert classification["topology"] == "monolith"
    assert classification["backend_kinds"] == ["embedded_access"]
    assert [item["role"] for item in artifacts if item["kind"] == "access_database"] == ["frontend"]


# A Japanese name - the norm in this kit's target systems - lost every character to
# the id sanitize, so distinct objects collapsed onto one base and were separated by
# an arrival-order counter that changed whenever the file order did.
def test_non_ascii_names_get_stable_distinct_ids(tmp_path: Path) -> None:
    app_root = tmp_path / "A05"
    sources = _sources(app_root / "sources")
    (sources / "forms" / "共通ルーチン.txt").write_text("Version =20", encoding="utf-8")
    (sources / "forms" / "印刷設定.txt").write_text("Version =20", encoding="utf-8")

    _, first = init_app.discover_sources(app_root)
    _, second = init_app.discover_sources(app_root)

    ids = [item["id"] for item in first]
    assert len(set(ids)) == 2, ids
    assert not any(item["id"] == "ART" for item in first)
    # Derived from the name, so a second pass produces the same ids.
    assert ids == [item["id"] for item in second]


# extract_access.ps1 writes object definitions as .txt under forms/, reports/,
# macros/ and vba/. Classifying by extension alone dropped all of it into the
# catch-all sample bucket, so the package did not recognize its own output.
def test_the_kits_own_export_layout_is_recognized(tmp_path: Path) -> None:
    app_root = tmp_path / "A05"
    sources = _sources(app_root / "sources")
    (sources / "forms" / "OrderEntry.txt").write_text("Version =20", encoding="utf-8")
    (sources / "schema" / "tables.txt").write_text("{}", encoding="utf-8")
    (sources / "queries" / "qOrders.sql").write_text("SELECT 1;", encoding="utf-8")

    classification, artifacts = init_app.discover_sources(app_root)

    by_id = {item["id"]: item for item in artifacts}
    assert by_id["ORDERENTRY"]["format"] == "form"
    assert by_id["ORDERENTRY"]["kind"] == "source_export"
    assert by_id["TABLES"]["format"] == "table_schema"
    # Query SQL exported out of an Access database is not evidence of a SQL Server
    # backend; only .sql outside a queries/ folder implies a server.
    assert classification["backend_kinds"] == ["embedded_access"]


def test_sql_outside_a_queries_folder_still_implies_a_server(tmp_path: Path) -> None:
    app_root = tmp_path / "A05"
    sources = _sources(app_root / "sources")
    (sources / "sql").mkdir()
    (sources / "sql" / "schema.sql").write_text("CREATE TABLE t (id int);", encoding="utf-8")

    classification, _ = init_app.discover_sources(app_root)

    assert classification["backend_kinds"] == ["sql_server"]


# A generated manifest declared a graph runtime, its version and its refresh policy.
# None of it survives: derivation needs no runtime, no version pin and no policy, so a
# manifest that still carried the block would be describing machinery that is gone.
def test_generated_v22_manifest_declares_no_graph_runtime() -> None:
    import yaml

    text = init_app.manifest_v22_text(
        "A05", "Product Assortment Support",
        {"topology": "monolith", "frontend_format": "mdb", "source_availability": "full", "backend_kinds": ["embedded_access"]},
        [],
    )
    data = yaml.safe_load(text)
    assert "graphify" not in data
    assert set(data) == {"version", "app", "project", "artifacts"}
