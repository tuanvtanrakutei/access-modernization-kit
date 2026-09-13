"""A55 - what a screen opens, writes and hides, for all of them rather than a chosen few.

Enumeration belongs in the generated catalogue and claims belong in the phase document
(A14). This is the enumeration half: it was in A06's Phase 2, written out by hand for
twelve screens, with the other thirty-nine carrying none of it.

The control inventory that feeds the hidden column had a second defect. The exporter
writes `ui/controls.json` - 1,924 controls for A06 - and `_route_record` had no branch
for it, so it fell through to the `else` and landed in `databases/objects.json` as 423 KB
of JSON inside one record. Nothing was lost and nothing could read it, which meant every
control figure in Phase 2 was quoted from the unsealed export folder rather than from the
sealed bundle.
"""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

import screen_behaviour as behaviour  # noqa: E402

TABLES = {"受注情報", "商品マスタ", "在庫データ"}


def test_a_literal_open_is_an_edge() -> None:
    text = 'DoCmd.OpenForm "商品情報登録"\nDoCmd.OpenReport "在庫表", acViewPreview\n'
    assert behaviour.opens(text) == [("form", "商品情報登録"), ("report", "在庫表")]


def test_a_commented_out_call_is_not_an_edge() -> None:
    """A06 has two commented-out transfer calls; the same rule protects open calls."""
    assert behaviour.opens("'DoCmd.OpenForm \"死んだ画面\"\n") == []


def test_a_built_name_is_reported_as_the_expression() -> None:
    """The four reports A06 opens this way appear in `referenced by nothing` and are in
    daily use. The set of names the call can produce depends on a control's value, so the
    expression is the honest answer and enumerating it is a question for an operator."""
    text = 'DoCmd.OpenReport "受注数調整リスト" & Me.fraレポート, Me.印刷区分.value\n'
    assert behaviour.opens(text) == [], "no literal name to find"
    kind, expression = behaviour.built_opens(text)[0]
    assert kind == "report"
    assert expression.startswith('"受注数調整リスト" & Me.fra')


def test_only_targets_the_bundle_knows_are_counted() -> None:
    """`UPDATE cnt` and `UPDATE End` are VBA text a raw scan returns as SQL. Filtering on
    known table names discards them - and discards a statement built entirely from
    fragments too, which is why the column is published as a lower bound."""
    text = ("sql = \"INSERT INTO 受注情報 SELECT * FROM x\"\n"
            "cnt = 0\n"
            "UPDATE cnt\n"
            "sql = \"DELETE FROM \" & tableName\n")
    assert behaviour.writes(text, TABLES) == [("INSERT", "受注情報")]


def test_every_verb_is_recognised() -> None:
    text = ("INSERT INTO 受注情報 ...\nUPDATE 商品マスタ SET ...\n"
            "DELETE * FROM 在庫データ\n")
    assert behaviour.writes(text, TABLES) == [
        ("DELETE", "在庫データ"), ("INSERT", "受注情報"), ("UPDATE", "商品マスタ")]


def test_hidden_is_read_from_the_definition_not_guessed() -> None:
    controls = [{"name": "発注点更新ボタン", "visible": False},
                {"name": "終了ボタン", "visible": True},
                {"name": "no_flag"}]
    assert behaviour.hidden_controls(controls) == ["発注点更新ボタン"]


def test_the_control_inventory_reaches_the_bundle() -> None:
    """A55's other half: the section has to exist for the catalogue to read it."""
    sys.path.insert(0, str(PACKAGE / "adapters"))
    from base import empty_sections  # noqa: E402

    assert "controls" in empty_sections()["ui"], (
        "ui/controls.json fell through routing into databases/objects before A55")
