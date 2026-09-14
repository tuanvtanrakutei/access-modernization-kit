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


CAPTION_FORM = (
    'Version =20\n'
    'Begin Form\n'
    '    RecordSelectors = NotDefault\n'
    '    Caption ="商品情報登録"\n'
    '    Begin Section\n'
    '        Begin CommandButton\n'
    '            Name ="商品情報設定ボタン"\n'
    '            Caption ="押さないで"\n'
    '        End\n'
    '    End\n'
    'End\n')


def test_caption_is_the_forms_own_not_a_controls() -> None:
    """The defect this exists for: A06 published a screen called `商品情報登録`, which is
    the caption on `商品情報設定画面` and the label on the switchboard button that opens
    it. Reading the first `Caption =` at any depth would have found a button's."""
    assert behaviour.caption(CAPTION_FORM) == "商品情報登録"


def test_an_object_declaring_no_caption_returns_empty() -> None:
    """Access falls back to the object name at run time. Returning the name here would
    publish a guess about a runtime nobody observed as though it were read from the
    definition - `入荷実績入力` declares none."""
    assert behaviour.caption('Begin Form\n    RecordSelectors = NotDefault\nEnd\n') == ""
    assert behaviour.caption("") == ""
    assert behaviour.caption(None) == ""


# --- option groups: the enumeration that closed a question ------------------
#
# Phase 2 asked warehouse operations `What are the option-group values behind
# 受注数調整リスト?` and routed it to a person, while `fraレポート` sat in the bundle
# declaring both of them. A question spends the one kind of evidence this kit cannot
# generate, so the enumeration has to come first.

OPTION_FORM = (
    'Begin Form\n'
    '    Begin Section\n'
    '        Begin OptionGroup\n'
    '            Name =\"fraReport\"\n'
    '            DefaultValue =\"2\"\n'
    '            Begin\n'
    '                Begin OptionButton\n'
    '                    OptionValue =2\n'
    '                    Name =\"opt34\"\n'
    '                End\n'
    '                Begin OptionButton\n'
    '                    OptionValue =1\n'
    '                    Name =\"opt32\"\n'
    '                End\n'
    '            End\n'
    '        End\n'
    '        Begin TextBox\n'
    '            Name =\"plainBox\"\n'
    '        End\n'
    '    End\n'
    'End\n')

OPTION_CONTROLS = [
    {"name": "fraReport", "type": behaviour.TYPE_OPTION_GROUP, "parent": "F"},
    {"name": "opt34", "type": behaviour.TYPE_OPTION_BUTTON, "parent": "fraReport",
      "attached_label": "cases and loose"},
    {"name": "opt32", "type": behaviour.TYPE_OPTION_BUTTON, "parent": "fraReport",
      "attached_label": "loose only"},
    {"name": "plainBox", "type": behaviour.TYPE_TEXTBOX, "parent": "F"},
]


def test_an_option_group_is_enumerated_with_values_and_labels() -> None:
    groups = behaviour.option_choices(OPTION_FORM, OPTION_CONTROLS)
    assert len(groups) == 1
    group = groups[0]
    assert group["group"] == "fraReport"
    assert group["default"] == "2"
    assert [(c["value"], c["label"]) for c in group["choices"]] == [
        ("1", "loose only"), ("2", "cases and loose")]


def test_option_value_and_default_value_sit_on_opposite_sides_of_the_name() -> None:
    """A single pending-value scan gets one and silently loses the other: `OptionValue`
    is written above the `Name` it belongs to and `DefaultValue` below it."""
    group = behaviour.option_choices(OPTION_FORM, OPTION_CONTROLS)[0]
    assert group["default"] == "2", "DefaultValue is written below the group's Name"
    assert group["choices"][0]["value"] == "1", "OptionValue is written above it"


def test_a_control_without_an_option_value_does_not_inherit_the_one_above_it() -> None:
    """Carrying a pending value forwards has to stop at the next block boundary, or the
    following control steals it - here the text box would come out holding value 1."""
    groups = behaviour.option_choices(OPTION_FORM, OPTION_CONTROLS)
    assert "plainBox" not in {c["name"] for g in groups for c in g["choices"]}


def test_a_definition_with_no_option_group_yields_nothing() -> None:
    assert behaviour.option_choices(CAPTION_FORM, []) == []
    assert behaviour.option_choices("", []) == []
