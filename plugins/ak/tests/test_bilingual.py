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


def test_a_partial_name_is_flagged_on_the_object_even_though_nothing_is_printed() -> None:
    """A partial name is never printed inline; the appendix is where it is marked."""
    rendered = compose("商品ワケワカラン")
    assert not rendered.is_complete
    assert rendered.covered < 1.0


def test_a_name_from_a01_precedent_alone_carries_no_question_mark() -> None:
    """`?` must mean "this analysis made this up", or it means nothing.

    `商品コード` composes from `商品` and `コード`, both decided in the A01 conversion
    table. That is precedent applied, not a proposal, and 149 of 649 A05 names are in
    that position.
    """
    rendered = compose("商品コード")
    assert rendered.provenance == "A01"
    assert rendered.is_settled and not rendered.accepted
    assert rendered.bilingual() == "商品コード (product_cd)"


def test_no_rendered_name_carries_a_marker() -> None:
    """Removed on request: the reader corrects names in the glossary, not inline."""
    for name in ("商品コード", "ＤＰコード商品", "商品ワケワカラン", "数量12"):
        assert "?" not in compose(name).bilingual(), name


def test_a_name_using_any_analysis_term_records_that_in_its_provenance() -> None:
    """The standing is on the object and in the appendix, not in the printed name.

    A `?` inline went on 500 of 649 names, which is wallpaper rather than a warning.
    `provenance` and `is_settled` still carry the distinction for anything that needs
    to act on it.
    """
    rendered = compose("ＤＰコード商品")
    assert rendered.is_complete
    assert rendered.provenance == "A01+analysis"
    assert not rendered.is_settled
    assert rendered.bilingual() == "ＤＰコード商品 (dp_cd_product)"


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


def test_a_roman_numeral_term_does_not_capture_the_plain_letter() -> None:
    """NFKC makes `Ⅰ` and `I` the same character.

    A term mapping `Ⅰ` to "1" therefore also matched the plain letter, and
    `元受注データI` - the test-side staging table - rendered as `source_order_data_1`.
    The shipped dictionary leaves both Roman numerals out for that reason.
    """
    terms = bl.load_terms(PACKAGE)
    assert "Ⅰ" not in terms and "Ⅱ" not in terms
    assert bl.compose("元受注データI", terms).english == "source_order_data_i"
    assert bl.compose("元受注データC", terms).english == "source_order_data_c"
    assert bl.compose("雑貨Ⅱ分類コード", terms).english == "sundries_ii_category_cd"


def test_no_shipped_term_collides_with_another_under_nfkc() -> None:
    """Two keys that normalise to the same text must agree on the English name.

    `ＦＬＧ` and `FLG` are the same term written two ways and both map to `flg`, which
    is fine. Two keys normalising alike with different values would make the result
    depend on dictionary order.
    """
    import unicodedata
    from collections import defaultdict

    by_normal = defaultdict(set)
    for key, entry in bl.load_terms(PACKAGE).items():
        by_normal[unicodedata.normalize("NFKC", key)].add(str(entry.get("en")))
    clashes = {k: v for k, v in by_normal.items() if len(v) > 1}
    assert not clashes, clashes
