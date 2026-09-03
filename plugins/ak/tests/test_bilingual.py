"""Composing an English name from Japanese terms, and never overclaiming one.

A composed name is a proposal. The tests that matter here are the ones that keep it
labelled as one, and the two defects the first coverage measurement exposed:

  - `配送コースマスタ20241231バックアップ` rendered as `..._2_0_2_4_1_2_3_1`, because
    Latin characters were taken one at a time instead of as runs. That is not a name
    anybody would accept, and it hid the real finding: a date inside a table name.
  - The term dictionary contained a column called `No`, which YAML 1.1 reads as the
    boolean false. Loading it raised from inside a normaliser three calls away.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

import bilingual as bl  # noqa: E402

TERMS = {
    "商品": {"en": "product", "provenance": "A01"},
    "店舗": {"en": "store", "provenance": "A01"},
    "コード": {"en": "cd", "provenance": "A01"},
    "ＤＰコード": {"en": "dp_cd", "provenance": "analysis"},
    "名": {"en": "name", "provenance": "A01"},
    "数量": {"en": "quantity", "provenance": "A01"},
    "マスタ": {"en": "master", "provenance": "A01"},
    "元": {"en": "source", "provenance": "analysis"},
    "移動元": {"en": "movement_source", "provenance": "A01"},
    "バックアップ": {"en": "backup", "provenance": "analysis"},
    "の": {"en": "", "provenance": "analysis"},
}


def compose(name: str, accepted: dict[str, str] | None = None):
    return bl.compose(name, TERMS, accepted)


def test_a_name_composes_from_its_terms_in_source_order() -> None:
    assert compose("商品コード").english == "product_cd"
    assert compose("店舗マスタ").english == "store_master"


def test_a_trailing_index_is_a_position_not_a_word() -> None:
    """`数量1` … `数量21` are one term twenty-one times."""
    assert compose("数量12").english == "quantity_12"
    assert compose("店舗コード21").english == "store_cd_21"


def test_a_full_width_index_is_read_as_an_index() -> None:
    assert compose("数量２").english == "quantity_2"


def test_the_longest_term_wins() -> None:
    """`移動元` must not be read as `移動` plus `元`, nor `ＤＰコード` as `コード`."""
    assert compose("移動元").english == "movement_source"
    assert compose("ＤＰコード").english == "dp_cd"


def test_width_is_normalised_before_matching() -> None:
    """A05's most-joined pair is `DPコード` against `ＤＰコード`. Both are the term."""
    assert compose("DPコード").english == "dp_cd"


def test_an_interior_digit_run_stays_one_token() -> None:
    rendered = compose("商品マスタ20241231バックアップ")
    assert rendered.english == "product_master_20241231_backup"
    assert "2_0_2_4" not in rendered.english


def test_a_partial_name_says_so_rather_than_looking_finished() -> None:
    rendered = compose("商品ワケワカラン")
    assert not rendered.is_complete
    assert rendered.covered < 1.0
    assert "partial" in rendered.bilingual()


def test_a_complete_proposal_is_still_marked_a_proposal() -> None:
    """Mechanical is not the same as correct."""
    rendered = compose("商品コード")
    assert rendered.is_complete
    assert not rendered.accepted
    assert rendered.bilingual() == "商品コード (product_cd?)"


def test_an_accepted_name_loses_the_question_mark() -> None:
    rendered = compose("商品コード", {"商品コード": "item_code"})
    assert rendered.accepted
    assert rendered.english == "item_code"
    assert rendered.bilingual() == "商品コード (item_code)"


def test_an_accepted_base_name_carries_its_index() -> None:
    rendered = compose("数量12", {"数量": "qty"})
    assert rendered.english == "qty_12"
    assert rendered.accepted


def test_a_name_with_no_term_renders_as_the_japanese_alone() -> None:
    rendered = compose("ワケワカラン")
    assert rendered.english == ""
    assert rendered.bilingual() == "ワケワカラン"


def test_a_particle_carrying_no_word_still_counts_as_covered() -> None:
    rendered = compose("商品コードの数量")
    assert rendered.is_complete
    assert rendered.english == "product_cd_quantity"


# --- provenance -------------------------------------------------------------


def test_provenance_is_A01_when_every_term_is_precedent() -> None:
    assert compose("商品コード").provenance == "A01"


def test_provenance_is_mixed_when_any_term_is_only_proposed() -> None:
    assert compose("ＤＰコード商品").provenance == "A01+analysis"


def test_provenance_is_none_when_nothing_matched() -> None:
    assert compose("ワケワカラン").provenance == "none"


# --- loading ----------------------------------------------------------------


def test_the_real_term_dictionary_loads_and_has_no_boolean_keys() -> None:
    """`No`, `Yes`, `On`, `Off` are booleans in YAML 1.1, and `No` is a real column."""
    terms = bl.load_terms(PACKAGE)
    assert terms, "the shipped dictionary must load"
    assert all(isinstance(key, str) for key in terms)
    assert "No" in terms, "a column called `No` must survive the YAML loader"


def test_every_shipped_term_has_an_english_name_and_a_provenance() -> None:
    for key, entry in bl.load_terms(PACKAGE).items():
        assert isinstance(entry, dict), key
        assert "en" in entry, key
        assert entry.get("provenance") in ("A01", "analysis"), key


def test_a_missing_glossary_means_nothing_accepted_rather_than_an_error(
    tmp_path: Path,
) -> None:
    assert bl.load_accepted(tmp_path / "absent.yaml") == {}


def test_only_accepted_entries_are_honoured(tmp_path: Path) -> None:
    path = tmp_path / "glossary.yaml"
    io.open(path, "w", encoding="utf-8").write(
        'columns:\n'
        '  "商品コード": {en: "item_code", status: "accepted"}\n'
        '  "店舗コード": {en: "shop_code", status: "proposed"}\n'
    )
    accepted = bl.load_accepted(path)
    assert accepted == {"商品コード": "item_code"}, (
        "a proposed name must not be treated as decided"
    )
