"""The catalogues, and the two defects that got past reading the code.

Both were found by comparing generated output against numbers already established,
not by review, and both were silent:

  - Node ids are slugs, so a lookup built from `{database}:{kind}:{name}` missed every
    time. Every object read "referenced by 0" and the unreferenced list claimed all
    118 against 26. A dict miss returns a default; nothing raises.
  - `metadata.returns_records` is True for an UPDATE, so trusting it reported "0 of 79
    queries write" about a database with four writers, one of which multiplies a
    quantity by 1.5 with no guard.

Each has a test here that fails if the shortcut comes back.
"""
from __future__ import annotations

import io
import json
import re
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
sys.path.insert(0, str(PACKAGE / "contracts"))

import generate_catalogues as catalogues  # noqa: E402

FE, BE = "FRONT_1111", "BACK_2222"


def write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(payload, ensure_ascii=False, indent=1))


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "T01"
    bundle = root / ".ak" / "bundles" / "bundle-abc"
    write(bundle / "bundle.json", {"id": "bundle-abc"})
    write(bundle / "databases" / "tables.json", [
        {"database_id": BE, "name": "受注データ", "kind": "table",
         "metadata": {"linked": False, "connect": "", "source_table_name": ""}},
        {"database_id": BE, "name": "元受注データ", "kind": "table",
         "metadata": {"linked": True, "connect": "Text;FMT=Delimited;HDR=NO",
                      "source_table_name": "order#txt"}},
        {"database_id": FE, "name": "商品情報", "kind": "table", "metadata": {}},
    ])
    write(bundle / "databases" / "fields.json", [
        {"database_id": BE, "name": "伝票番号", "table": "受注データ", "type": 4,
         "size": 4, "required": True},
        {"database_id": BE, "name": "出荷日付", "table": "受注データ", "type": 10,
         "size": 8, "required": False},
        {"database_id": BE, "name": "出荷数量", "table": "受注データ", "type": 7,
         "size": 8, "required": False},
        {"database_id": FE, "name": "商品コード", "table": "商品情報", "type": 4,
         "size": 4, "required": True},
    ])
    write(bundle / "databases" / "indexes.json", [
        {"database_id": BE, "name": "key_1", "table": "受注データ",
         "fields": ["伝票番号"], "primary": True, "unique": True},
    ])
    write(bundle / "databases" / "declared-relationships.json", [])
    # The link declares a DSN, which is what makes the specification tables worth
    # reading: with HDR=NO the columns are positional and the spec is the only
    # declaration of what those positions mean.
    write(bundle / "interfaces" / "linked-tables.json", [
        {"database_id": BE, "name": "元受注データ", "connect": "Text;FMT=Delimited;HDR=NO;IMEX=2;DSN=order_spec;DATABASE=L:\\x"},
    ])
    # Every field of every row, the way the extractor emits them.
    write(bundle / "interfaces" / "imex-specs.json", [
        {"database_id": BE, "table": "MSysIMEXSpecs", "status": "read", "reason": "",
         "rows": [{"SpecID": "1", "SpecName": "order_spec", "FileType": "932"}]},
        {"database_id": BE, "table": "MSysIMEXColumns", "status": "read", "reason": "",
         "rows": [
             {"SpecID": "1", "FieldName": "商品コード", "Start": "1", "Width": "7"},
             {"SpecID": "1", "FieldName": "数量", "Start": "8", "Width": "5"},
         ]},
    ])
    # Two boundary files, one each way. The outbound one declares no format, which is
    # the normal state: a declaration says where a file goes, not what is in it.
    write(bundle / "interfaces" / "file-interfaces.json", [
        {"database_id": FE, "name": "order.txt", "path": "L:/in/order.txt",
         "direction": "inbound", "format": "Delimited;HDR=NO"},
        {"database_id": FE, "name": "shipping.dat", "path": "L:/out/shipping.dat",
         "direction": "outbound"},
    ])
    write(bundle / "ui" / "forms" / "inventory.json", [
        {"database_id": FE, "name": "メインメニュー", "kind": "form"},
        {"database_id": FE, "name": "商品検索", "kind": "form"},
    ])
    write(bundle / "ui" / "reports" / "inventory.json", [
        {"database_id": FE, "name": "ピッキングリスト", "kind": "report"},
        {"database_id": BE, "name": "ピッキングリスト", "kind": "report"},
    ])
    write(bundle / "ui" / "macros" / "inventory.json", [
        {"database_id": FE, "name": "AutoExec", "kind": "macro"},
    ])
    write(bundle / "code" / "access-sql" / "inventory.json", [
        {"database_id": BE, "name": "q受注データ", "kind": "query", "path": "aaa.txt",
         "metadata": {"returns_records": True}},
        {"database_id": BE, "name": "カクテキ倍数", "kind": "query", "path": "bbb.txt",
         # True even though the SQL is an UPDATE. This is what the real bundle records.
         "metadata": {"returns_records": True}},
        {"database_id": BE, "name": "配送コースマスタ追加", "kind": "query",
         "path": "ccc.txt", "metadata": {"returns_records": True}},
    ])
    sql = bundle / "code" / "access-sql"
    io.open(sql / "aaa.txt", "w", encoding="utf-8").write("SELECT * FROM 受注データ;")
    io.open(sql / "bbb.txt", "w", encoding="utf-8").write(
        'UPDATE 受注データ SET 出荷数量 = Format(([出荷数量]*1.5),"0");')
    io.open(sql / "ccc.txt", "w", encoding="utf-8").write(
        "INSERT INTO 配送コースマスタ SELECT * FROM 店舗マスタ;")
    write(bundle / "code" / "vba" / "inventory.json", [
        {"database_id": FE, "name": "AutoExec", "kind": "module"},
        {"database_id": FE, "name": "印刷設定", "kind": "module"},
    ])

    # A derived graph in the deriver's real shape: slug ids, DATABASE_ID:path source.
    extracted = root / ".ak" / "extracted"
    write(extracted / "derived-extraction.json", {
        "nodes": [
            {"id": "form_front_1111_a_1111", "label": "メインメニュー",
             "source_file": f"{FE}:.ak/staging/{FE}/fresh-01/forms/メインメニュー.txt"},
            {"id": "form_front_1111_b_2222", "label": "商品検索",
             "source_file": f"{FE}:.ak/staging/{FE}/fresh-01/forms/商品検索.txt"},
            {"id": "report_front_1111_c_3333", "label": "ピッキングリスト",
             "source_file": f"{FE}:.ak/staging/{FE}/fresh-01/reports/ピッキングリスト.txt"},
            {"id": "report_back_2222_d_4444", "label": "ピッキングリスト",
             "source_file": f"{BE}:.ak/staging/{BE}/fresh-01/reports/ピッキングリスト.txt"},
            {"id": "query_back_2222_e_5555", "label": "q受注データ",
             "source_file": f"{BE}:.ak/staging/{BE}/fresh-01/queries/q受注データ.sql"},
            {"id": "module_front_1111_f_6666", "label": "印刷設定",
             "source_file": f"{FE}:.ak/staging/{FE}/fresh-01/vba/印刷設定.txt"},
            {"id": "table_back_2222_g_7777", "label": "受注データ",
             "source_file": f"{BE}:schema/tables.json"},
        ],
        "edges": [
            # メインメニュー opens 商品検索, and both copies of the shared report name.
            {"source": "form_front_1111_a_1111", "target": "form_front_1111_b_2222",
             "relation": "references"},
            {"source": "form_front_1111_b_2222", "target": "report_front_1111_c_3333",
             "relation": "references"},
            {"source": "form_front_1111_b_2222", "target": "report_back_2222_d_4444",
             "relation": "references"},
            {"source": "query_back_2222_e_5555", "target": "table_back_2222_g_7777",
             "relation": "references"},
        ],
    })
    facts = extracted / "ui-facts"
    facts.mkdir(parents=True, exist_ok=True)
    io.open(facts / "a.md", "w", encoding="utf-8", newline="\n").write(
        "# メインメニュー\n\n- database: FRONT_1111\n- kind: form\n"
        "- record source: select * from 集計商品マスタ\n"
        "- bound fields:\n  - 商品コード\n  - 商品名\n"
        "- event procedures:\n  - 終了_Click\n"
        "- embedded controls:\n  - BARCODE.BarCodeCtrl.1\n")
    io.open(root / "manifest.yaml", "w", encoding="utf-8").write(
        "version: '2.2'\napp:\n  id: T01\n")
    # `input/` is what makes Workspace read this as the current layout. Without it
    # every accessor answers with the pre-2.10.0 paths and the bundle is not found.
    (root / "input" / "access").mkdir(parents=True, exist_ok=True)
    return root


def build(workspace: Path) -> dict[str, str]:
    import subprocess

    result = subprocess.run(
        [sys.executable, str(PACKAGE / "scripts" / "generate_catalogues.py"),
         "--app-root", str(workspace)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    assert result.returncode == 0, result.stderr
    output = workspace / "output"
    return {p.name: p.read_text(encoding="utf-8") for p in output.glob("*.md")}


# --- the two silent defects -------------------------------------------------


def test_reference_counts_resolve_against_slug_node_ids(workspace: Path) -> None:
    """The ids are slugs. A count built from a guessed id format reads zero for all."""
    derived = json.loads(
        (workspace / ".ak" / "extracted" / "derived-extraction.json").read_text(
            encoding="utf-8"))
    counts = catalogues.reference_counts(derived)
    assert counts[("FRONT_1111", "form", "商品検索")] == 1
    assert counts[("FRONT_1111", "report", "ピッキングリスト")] == 1
    assert counts[("BACK_2222", "report", "ピッキングリスト")] == 1
    assert counts[("BACK_2222", "table", "受注データ")] == 1
    assert ("FRONT_1111", "form", "メインメニュー") not in counts


def test_a_shared_name_is_counted_per_object_not_per_name(workspace: Path) -> None:
    """E-06: a form and a report may share a name, and so may two reports."""
    screens = build(workspace)["T01_ScreenCatalogue.md"]
    assert screens.count("| `ピッキングリスト` |") == 2, (
        "both objects carrying the shared name must appear as their own row"
    )


def test_the_statement_comes_from_the_sql_not_the_metadata(workspace: Path) -> None:
    """Every fixture query says returns_records: true; two of the three write."""
    logic = build(workspace)["T01_LogicCatalogue.md"]
    assert "**UPDATE**" in logic
    assert "**INSERT**" in logic
    assert "2 of 3 queries write" in logic


def test_a_query_with_no_sql_in_the_bundle_says_so(workspace: Path) -> None:
    bundle = workspace / ".ak" / "bundles" / "bundle-abc"
    inventory = bundle / "code" / "access-sql" / "inventory.json"
    rows = json.loads(inventory.read_text(encoding="utf-8"))
    rows.append({"database_id": BE, "name": "missing", "kind": "query",
                 "metadata": {"returns_records": True}})
    write(inventory, rows)
    logic = build(workspace)["T01_LogicCatalogue.md"]
    assert "_no SQL in bundle_" in logic


# --- completeness, which is the whole point ---------------------------------


def test_every_table_and_every_column_appears(workspace: Path) -> None:
    data = build(workspace)["T01_DataCatalogue.md"]
    for name in ("受注データ", "元受注データ", "商品情報"):
        assert f"`{name}`" in data
    for column in ("伝票番号", "出荷日付", "出荷数量", "商品コード"):
        assert f"`{column}`" in data


def test_every_form_report_query_and_module_appears(workspace: Path) -> None:
    built = build(workspace)
    screens, logic = built["T01_ScreenCatalogue.md"], built["T01_LogicCatalogue.md"]
    for name in ("メインメニュー", "商品検索", "ピッキングリスト"):
        assert f"`{name}`" in screens
    for name in ("q受注データ", "カクテキ倍数", "配送コースマスタ追加", "印刷設定"):
        assert f"`{name}`" in logic


# --- what the evidence cannot fill -----------------------------------------


def test_a_dao_type_code_is_translated(workspace: Path) -> None:
    """Publishing `10` for 421 of 1055 columns told a migration team nothing."""
    data = build(workspace)["T01_DataCatalogue.md"]
    assert "Short Text(8)" in data, "dbText must carry its declared size"
    assert "Number (Long Integer)" in data
    assert "Number (Double)" in data
    assert "| 10 |" not in data


def test_unfillable_columns_are_present_and_marked(workspace: Path) -> None:
    data = build(workspace)["T01_DataCatalogue.md"]
    assert catalogues.NEEDS_DOC in data, "an English name needs a document; EC-01"
    assert catalogues.NEEDS_DECISION in data, "a target type is a person's decision"


def test_zero_declared_relationships_is_stated_as_a_finding(workspace: Path) -> None:
    data = build(workspace)["T01_DataCatalogue.md"]
    assert "Zero relationships are declared" in data
    assert "finding about the application, not a gap in the extraction" in data


def test_tables_without_a_primary_key_are_counted(workspace: Path) -> None:
    data = build(workspace)["T01_DataCatalogue.md"]
    assert "2 of 3 table objects have no primary key" in data


def test_the_unreferenced_list_says_it_is_not_a_list_of_dead_objects(
    workspace: Path,
) -> None:
    """メインメニュー is unreferenced and is the startup form. Both are true."""
    screens = build(workspace)["T01_ScreenCatalogue.md"]
    assert "referenced by nothing (1)" in screens
    assert "startup form belongs in this list and is not dead" in screens


def test_a_production_name_containing_a_pipe_cannot_break_its_table(
    workspace: Path,
) -> None:
    bundle = workspace / ".ak" / "bundles" / "bundle-abc"
    tables = bundle / "databases" / "tables.json"
    rows = json.loads(tables.read_text(encoding="utf-8"))
    rows.append({"database_id": BE, "name": "a|b", "kind": "table", "metadata": {}})
    write(tables, rows)
    data = build(workspace)["T01_DataCatalogue.md"]
    assert "`a\\|b`" in data


def test_regenerating_is_byte_identical(workspace: Path) -> None:
    """A catalogue is generated, so two runs on one bundle must not differ."""
    first = build(workspace)
    second = build(workspace)
    assert first == second


# --- what the SQL fills in when the schema declares nothing ------------------


def test_inferred_relationships_appear_when_none_are_declared(workspace: Path) -> None:
    bundle = workspace / ".ak" / "bundles" / "bundle-abc"
    io.open(bundle / "code" / "access-sql" / "aaa.txt", "w", encoding="utf-8").write(
        "SELECT * FROM 受注データ INNER JOIN 商品情報 "
        "ON 受注データ.伝票番号 = 商品情報.商品コード;")
    data = build(workspace)["T01_DataCatalogue.md"]
    assert "Relationships inferred from real joins" in data
    assert "| 1 | INFERRED |" in data
    assert "The SQL still knows" in data


def test_a_candidate_key_is_offered_only_where_none_is_declared(
    workspace: Path,
) -> None:
    bundle = workspace / ".ak" / "bundles" / "bundle-abc"
    io.open(bundle / "code" / "access-sql" / "aaa.txt", "w", encoding="utf-8").write(
        "SELECT * FROM 受注データ INNER JOIN 商品情報 "
        "ON 受注データ.伝票番号 = 商品情報.商品コード;")
    data = build(workspace)["T01_DataCatalogue.md"]
    section = data.split("### 2.2")[1].split("## 3.")[0]
    # 受注データ declares a primary key in the fixture, so it must not be suggested one.
    assert "`商品情報`" in section
    assert "`受注データ`" not in section


def test_a_candidate_key_says_it_cannot_be_confirmed(workspace: Path) -> None:
    """A join proves the column identifies a row, not that it does so uniquely."""
    bundle = workspace / ".ak" / "bundles" / "bundle-abc"
    io.open(bundle / "code" / "access-sql" / "aaa.txt", "w", encoding="utf-8").write(
        "SELECT * FROM 受注データ JOIN 商品情報 ON 受注データ.伝票番号 = 商品情報.商品コード;")
    data = build(workspace)["T01_DataCatalogue.md"]
    assert "requires rows, which means SAMPLE_DATA" in data


def test_sql_naming_a_nonexistent_object_is_reported(workspace: Path) -> None:
    bundle = workspace / ".ak" / "bundles" / "bundle-abc"
    io.open(bundle / "code" / "access-sql" / "aaa.txt", "w", encoding="utf-8").write(
        "SELECT * FROM 元受注データC LEFT JOIN 元受注データI "
        "ON 元受注データC.伝票番号 = 元受注データI.伝票番号;")
    logic = build(workspace)["T01_LogicCatalogue.md"]
    assert "SQL naming an object that does not exist" in logic
    assert "`元受注データC`" in logic and "`元受注データI`" in logic
    assert "cannot run" in logic


def test_a_screen_record_source_is_checked_too(workspace: Path) -> None:
    """The fixture's main menu binds to a table that is not in the inventory.

    Which is the real A05 case: two screens bind to `集計分類マスタ`, and it
    exists nowhere - so neither screen can open, and nothing said so.
    """
    logic = build(workspace)["T01_LogicCatalogue.md"]
    assert "form メインメニュー" in logic
    assert "`集計商品マスタ`" in logic
    assert "cannot open" in logic


def test_a_clean_application_says_so_rather_than_showing_an_empty_table(
    workspace: Path,
) -> None:
    bundle = workspace / ".ak" / "bundles" / "bundle-abc"
    tables = bundle / "databases" / "tables.json"
    rows = json.loads(tables.read_text(encoding="utf-8"))
    rows.append({"database_id": FE, "name": "集計商品マスタ",
                 "kind": "table", "metadata": {}})
    write(tables, rows)
    io.open(bundle / "code" / "access-sql" / "ccc.txt", "w", encoding="utf-8").write(
        "INSERT INTO 商品情報 SELECT * FROM 受注データ;")
    logic = build(workspace)["T01_LogicCatalogue.md"]
    assert "SQL naming an object that does not exist (0)" in logic
    assert "Every table and query named in a saved query or a screen record "            "source exists" in logic


def test_a_recorded_screen_meaning_reaches_the_catalogue(workspace: Path) -> None:  # noqa: F811
    """`Business purpose` was hard-coded to the marker, so the column could not change.

    Tables and columns have been fillable from `meanings.yaml` since that file existed;
    screens could not, so every row of this catalogue asserted a gap rather than
    reporting one - and `$ak meanings` had nothing to write a screen entry into. A
    column that cannot change is worse than a missing column, because it looks answered
    when somebody answers it and it is not.
    """
    screens = build(workspace)["T01_ScreenCatalogue.md"]
    assert catalogues.NEEDS_DOC in screens

    target = workspace / "input" / "decisions" / "meanings.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("""
screens:
  "form メインメニュー":
    meaning: The startup form; every day's work begins by choosing a task here.
    evidence_class: INTERVIEW
    source: 業務課 (堀内), 2026-09-07, asked by Vo Ta Tuan
""", encoding="utf-8")

    screens = build(workspace)["T01_ScreenCatalogue.md"]
    assert "every day's work begins by choosing a task here" in screens
    # The citation travels with it - a meaning without its source is the claim this
    # kit exists to refuse.
    assert "INTERVIEW: 業務課 (堀内), 2026-09-07" in screens
    # A form and a report share a name in this fixture; only the form was answered.
    row = next(line for line in screens.splitlines()
               if "ピッキングリスト" in line and line.startswith("|"))
    assert catalogues.NEEDS_DOC in row


def test_a_recorded_boundary_meaning_reaches_the_catalogue(workspace: Path) -> None:  # noqa: F811
    """The boundary table had no column for what a file is for at all.

    It carried the path, the direction and the declared format - everything a
    declaration states. Who sends the file, how often, and what happens when it does
    not arrive are USAGE and INTENT, and there was nowhere for an answer to them to go.
    """
    logic = build(workspace)["T01_LogicCatalogue.md"]
    assert "| What it is for |" in logic
    row = next(line for line in logic.splitlines() if "`order.txt`" in line)
    assert catalogues.NEEDS_DOC in row

    target = workspace / "input" / "decisions" / "meanings.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("""
boundaries:
  "order.txt":
    meaning: Yesterday's orders from the warehouse system; absent means the night job failed.
    evidence_class: INTERVIEW
    source: 業務課 (堀内), 2026-09-08, asked by Vo Ta Tuan
""", encoding="utf-8")

    logic = build(workspace)["T01_LogicCatalogue.md"]
    row = next(line for line in logic.splitlines() if "`order.txt`" in line)
    assert "absent means the night job failed" in row
    assert "INTERVIEW: 業務課 (堀内), 2026-09-08" in row
    # The other file was not answered, and says so.
    other = next(line for line in logic.splitlines() if "`shipping.dat`" in line)
    assert catalogues.NEEDS_DOC in other


def test_a_linked_table_shows_the_meaning_it_already_has(workspace: Path) -> None:  # noqa: F811
    """One subject, one question. A linked table's row reads the `tables:` answer.

    Giving the boundary table its own question for a linked table would have been the
    obvious symmetry and the wrong one: the same file would appear twice in
    `meanings.yaml` with no way for a reader to know which answer wins.
    """
    target = workspace / "input" / "decisions" / "meanings.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("""
tables:
  "元受注データ":
    meaning: The previous day's orders, linked from the share rather than stored here.
    evidence_class: DOCUMENT
    source: operations manual, page 4
""", encoding="utf-8")
    logic = build(workspace)["T01_LogicCatalogue.md"]
    row = next(line for line in logic.splitlines()
               if "元受注データ" in line and "inbound link" in line)
    assert "linked from the share rather than stored here" in row


# --- the table has to be a table --------------------------------------------


CELL_SPLIT = re.compile(r"(?<!\\)\|")


def table_widths(text: str) -> list[tuple[int, list[int]]]:
    """Every markdown table in the document, as (line number, cell counts per row)."""
    tables: list[tuple[int, list[int]]] = []
    current: list[int] = []
    start = 0
    for number, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if not current:
                start = number
            current.append(len(CELL_SPLIT.split(stripped.strip("|"))))
            continue
        if current:
            tables.append((start, current))
            current = []
    if current:
        tables.append((start, current))
    return tables


def test_every_generated_row_has_as_many_cells_as_its_header(workspace: Path) -> None:
    """A row wider than its header does not render as a wider row - it renders wrong.

    The screen catalogue emitted ten cells per row under a nine-column header: the
    English name was written per row and never declared, so every column from
    `Database` rightwards was reading under its neighbour's title and `Business
    meaning` fell off the end. The generator is the one part of this kit that cannot
    be wrong about enumeration - it exists because the narratives were (A14) - and
    nothing checked the shape of what it wrote.
    """
    for name, text in build(workspace).items():
        for line, widths in table_widths(text):
            assert len(set(widths)) == 1, (
                f"{name}: table at line {line} has rows of {sorted(set(widths))} "
                f"cells; a header and its rows must agree"
            )
