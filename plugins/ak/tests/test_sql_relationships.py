"""Reading relationships out of SQL when the database declares none.

The A05 databases declare zero relationships, so this is the only thing that can fill
a catalogue's FK column. It has to be honest about three limits: an alias it cannot
bind, a table that does not exist, and the fact that a join proves use rather than
uniqueness.

One defect here was found by comparing a result against a plainer regex: the alias
pattern read `FROM 元商品マスタC LEFT JOIN` as alias `LEFT` for table `元商品マスタC`,
which put the real table name into the alias values and made the dangling-reference
check report 0 where 5 references were genuinely absent.
"""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

import sql_relationships as sql  # noqa: E402

TABLES = {"受注データ", "商品マスタ", "商品マスタ本", "店舗マスタ", "WK集計"}
QUERIES = {"q受注データ"}


def analyse(**sources: str):
    return sql.analyse(sources, TABLES, QUERIES)


def test_a_plain_join_is_read() -> None:
    result = analyse(one="SELECT * FROM 受注データ INNER JOIN 商品マスタ "
                         "ON 受注データ.商品コード = 商品マスタ.商品コード;")
    assert len(result.relationships) == 1
    relationship = result.relationships[0]
    assert {relationship.left_table, relationship.right_table} == {"受注データ", "商品マスタ"}
    assert relationship.left_column == relationship.right_column == "商品コード"
    assert relationship.occurrences == 1


def test_the_same_join_from_either_direction_is_one_relationship() -> None:
    result = analyse(
        a="SELECT * FROM 受注データ JOIN 商品マスタ ON 受注データ.商品コード = 商品マスタ.商品コード;",
        b="SELECT * FROM 商品マスタ JOIN 受注データ ON 商品マスタ.商品コード = 受注データ.商品コード;",
    )
    assert len(result.relationships) == 1
    assert result.relationships[0].occurrences == 2
    assert sorted(result.relationships[0].seen_in) == ["a", "b"]


def test_an_alias_is_resolved_to_its_table() -> None:
    result = analyse(one="SELECT * FROM 受注データ AS t1 INNER JOIN 商品マスタ AS m1 "
                         "ON t1.商品コード = m1.商品コード;")
    assert len(result.relationships) == 1
    assert {result.relationships[0].left_table,
            result.relationships[0].right_table} == {"受注データ", "商品マスタ"}


def test_a_join_keyword_is_not_mistaken_for_an_alias() -> None:
    """`FROM x LEFT JOIN y` used to bind `LEFT` as the alias of `x`."""
    result = sql.analyse(
        {"one": "SELECT * FROM 元商品マスタC LEFT JOIN 元商品マスタI "
                "ON 元商品マスタC.商品コード = 元商品マスタI.商品コード;"},
        TABLES, QUERIES)
    assert result.dangling == {"one": ["元商品マスタC", "元商品マスタI"]}, (
        "a table that exists nowhere must be reported, not absorbed as an alias"
    )


def test_a_column_joined_on_a_different_name_is_kept_as_written() -> None:
    """`DPマスタ.DPコード = コースマスタ.ＤＰコード` differs by width. Both are real."""
    tables = {"DPマスタ", "コースマスタ"}
    result = sql.analyse(
        {"one": "SELECT * FROM DPマスタ JOIN コースマスタ "
                "ON DPマスタ.DPコード = コースマスタ.ＤＰコード;"}, tables, set())
    relationship = result.relationships[0]
    assert not relationship.same_column_name
    assert {relationship.left_column, relationship.right_column} == {"DPコード", "ＤＰコード"}


def test_a_join_onto_a_saved_query_is_not_a_table_relationship() -> None:
    result = analyse(one="SELECT * FROM 受注データ JOIN q受注データ "
                         "ON 受注データ.商品コード = q受注データ.商品コード;")
    assert result.relationships == []
    assert result.joined_through_query == {"q受注データ": 1}
    assert result.unresolved_aliases == {}


def test_an_unbindable_alias_is_reported_not_guessed() -> None:
    result = analyse(one="SELECT * FROM (SELECT 1) AS t9 JOIN 商品マスタ "
                         "ON t9.商品コード = 商品マスタ.商品コード;")
    assert result.relationships == []
    assert "t9" in result.unresolved_aliases


# --- candidate keys ---------------------------------------------------------


def test_the_most_joined_column_is_the_candidate_key() -> None:
    result = analyse(
        a="SELECT * FROM 受注データ JOIN 商品マスタ ON 受注データ.商品コード = 商品マスタ.商品コード;",
        b="SELECT * FROM 受注データ JOIN 商品マスタ本 ON 受注データ.商品コード = 商品マスタ本.商品コード;",
        c="SELECT * FROM 受注データ JOIN 店舗マスタ ON 受注データ.店舗コード = 店舗マスタ.店舗コード;",
    )
    assert result.candidate_keys["受注データ"][0] == ("商品コード", 2)
    assert result.candidate_keys["商品マスタ"] == [("商品コード", 1)]


def test_a_work_table_is_named_as_one() -> None:
    """A work table with no key is normal; saying otherwise cries wolf 76 times."""
    assert sql.is_work_table("WK集計")
    assert sql.is_work_table("ＢＫ受注データ")
    assert not sql.is_work_table("受注データ")
    assert not sql.is_work_table("商品マスタ")


# --- dangling references ----------------------------------------------------


def test_a_table_created_by_the_statement_is_not_dangling() -> None:
    result = analyse(one="SELECT * INTO WK新規 FROM 受注データ;")
    assert result.dangling == {}


def test_a_missing_table_in_a_record_source_is_reported() -> None:
    """A screen whose record source names nothing cannot open."""
    result = analyse(**{"form 集計分類設定": "select * from 集計分類マスタ"})
    assert result.dangling == {"form 集計分類設定": ["集計分類マスタ"]}


def test_a_query_naming_only_real_objects_is_not_reported() -> None:
    result = analyse(one="SELECT * FROM 受注データ JOIN 店舗マスタ "
                         "ON 受注データ.店舗コード = 店舗マスタ.店舗コード;")
    assert result.dangling == {}


def test_bracketed_names_are_read() -> None:
    result = analyse(one="SELECT * FROM [受注データ] JOIN [店舗マスタ] "
                         "ON [受注データ].[店舗コード] = [店舗マスタ].[店舗コード];")
    assert len(result.relationships) == 1
    assert result.dangling == {}


def test_an_empty_source_is_skipped_rather_than_counted() -> None:
    result = analyse(one="", two="SELECT * FROM 受注データ;")
    assert result.sources_scanned == 1
