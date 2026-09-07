"""Annotating a written document with English names, without damaging it.

Three ways this could do harm, one test each: annotating inside a fenced block would
break a mermaid diagram and change what a SQL snippet means; annotating every mention
would turn a table row into a wall; and annotating twice would produce
`商品コード (product_cd?) (product_cd?)`.
"""
from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
sys.path.insert(0, str(PACKAGE / "contracts"))

import annotate_bilingual as annotator  # noqa: E402
import bilingual as bilingual_contract  # noqa: E402


class Naming:
    def __init__(self, accepted: dict[str, str] | None = None) -> None:
        self.terms = bilingual_contract.load_terms(PACKAGE)
        self.accepted = accepted or {}
        self.cache: dict[str, object] = {}

    def of(self, name: str) -> object:
        if name not in self.cache:
            self.cache[name] = bilingual_contract.compose(
                name, self.terms, self.accepted)
        return self.cache[name]


def test_the_first_mention_is_annotated() -> None:
    text, added = annotator.annotate("The `受注データ` table.", Naming())
    # No `?`: every term in `受注データ` was decided in the A01 conversion table.
    assert text == "The `受注データ` (order_data) table."
    assert added == 1


def test_only_the_first_mention_is_annotated() -> None:
    body = "`受注データ` is read by `商品マスタ`, and `受注データ` again."
    text, added = annotator.annotate(body, Naming())
    assert text.count("(order_data)") == 1
    assert added == 2


def test_nothing_inside_a_fenced_block_is_touched() -> None:
    body = (
        "Before `受注データ`.\n\n"
        "```mermaid\nflowchart TD\n  A[`商品マスタ`] --> B\n```\n\n"
        "```sql\nSELECT * FROM `店舗マスタ`;\n```\n"
    )
    text, _ = annotator.annotate(body, Naming())
    assert "(order_data)" in text
    assert "product_master" not in text, "a diagram must not be rewritten"
    assert "store_master" not in text, "a SQL snippet must not be rewritten"


def test_an_unclosed_fence_protects_the_rest_of_the_document() -> None:
    body = "Fine `受注データ`.\n\n```\nnot closed `商品マスタ`\n"
    text, _ = annotator.annotate(body, Naming())
    assert "(order_data)" in text
    assert "product_master" not in text


def test_running_twice_does_not_annotate_twice() -> None:
    naming = Naming()
    once, _ = annotator.annotate("The `受注データ` table.", naming)
    twice, added = annotator.annotate(once, Naming())
    assert twice == once
    assert added == 0


def test_a_partial_proposal_is_not_printed_inline() -> None:
    """A half-finished name in front of a reader reads like a name."""
    naming = Naming()
    body = "The `ワケワカラン商品` table."
    text, added = annotator.annotate(body, naming)
    assert text == body
    assert added == 0


def test_an_accepted_name_has_no_question_mark() -> None:
    naming = Naming({"受注データ": "order_line"})
    text, _ = annotator.annotate("The `受注データ` table.", naming)
    assert text == "The `受注データ` (order_line) table."


def test_a_latin_only_name_is_left_alone() -> None:
    text, added = annotator.annotate("Run `AutoExec` and `modExportAccess`.", Naming())
    assert added == 0


def test_the_appendix_lists_every_name_including_the_partial_ones() -> None:
    body = "`受注データ` and `ワケワカラン商品` and `AutoExec`."
    text = annotator.appendix(body, Naming())
    assert "`受注データ`" in text and "`order_data`" in text
    assert "`ワケワカラン商品`" in text and "partial" in text
    assert "AutoExec" not in text, "a Latin name needs no entry"


def test_the_appendix_says_the_japanese_name_stays_authoritative() -> None:
    text = annotator.appendix("`受注データ`", Naming())
    assert "authoritative" in text


@pytest.fixture()
def published(tmp_path: Path) -> Path:
    root = tmp_path / "T01"
    (root / "input" / "decisions").mkdir(parents=True)
    output = root / "output"
    output.mkdir()
    io.open(output / "T01_Phase1_DataUnderstanding_EN.md", "w", encoding="utf-8").write(
        "# Phase 1\n\nThe `受注データ` table feeds `商品マスタ`.\n")
    io.open(output / "T01_DataCatalogue.md", "w", encoding="utf-8").write(
        "# Catalogue\n\n| `受注データ` | `order_data?` |\n")
    return root


def run(root: Path, *extra: str) -> str:
    result = subprocess.run(
        [sys.executable, str(PACKAGE / "scripts" / "annotate_bilingual.py"),
         "--outputs", str(root / "output"), *extra],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout


def test_a_catalogue_is_skipped_because_it_already_carries_both(published: Path) -> None:
    run(published)
    catalogue = (published / "output" / "T01_DataCatalogue.md").read_text(
        encoding="utf-8")
    assert catalogue.count("order_data") == 1, "the catalogue must not be re-annotated"


def test_the_narrative_gains_names_and_an_appendix(published: Path) -> None:
    run(published)
    narrative = (published / "output" / "T01_Phase1_DataUnderstanding_EN.md").read_text(
        encoding="utf-8")
    assert "(order_data)" in narrative
    assert "(product_master)" in narrative
    assert annotator.APPENDIX_HEADING in narrative
    assert "A01 precedent" in narrative, (
        "the appendix must distinguish precedent from a proposal"
    )


def test_a_second_run_is_a_no_op(published: Path) -> None:
    run(published)
    first = (published / "output" / "T01_Phase1_DataUnderstanding_EN.md").read_text(
        encoding="utf-8")
    run(published)
    assert (published / "output" / "T01_Phase1_DataUnderstanding_EN.md").read_text(
        encoding="utf-8") == first


def test_dry_run_changes_nothing(published: Path) -> None:
    before = (published / "output" / "T01_Phase1_DataUnderstanding_EN.md").read_bytes()
    run(published, "--dry-run")
    assert (published / "output"
            / "T01_Phase1_DataUnderstanding_EN.md").read_bytes() == before


# --- the two cases the idempotency test missed -------------------------------
#
# `test_running_twice_does_not_annotate_twice` used `受注データ` -> `order_data`, which
# is short and has no dot, so it passed while 14 duplicates went into the published
# set. Both failing shapes are pinned here.


def test_a_name_containing_a_dot_is_not_annotated_twice() -> None:
    """`品揃支援DATA.MDB` -> `assortment_support_data.mdb`. The dot broke the check."""
    naming = Naming()
    once, _ = annotator.annotate("Reads `品揃支援DATA.MDB` at startup.", naming)
    assert "(assortment_support_data.mdb)" in once
    twice, added = annotator.annotate(once, Naming())
    assert twice == once
    assert added == 0


def test_a_long_english_name_is_not_annotated_twice() -> None:
    """The check peeked at 40 characters; this annotation is longer than that."""
    naming = Naming()
    once, _ = annotator.annotate("See `青果集計商品マスタフッタ`.", naming)
    english = Naming().of("青果集計商品マスタフッタ").english
    # What overflowed the old window was the whole annotation, not the name: a space,
    # a bracket, the name, the `?` and the closing bracket.
    assert len(f" ({english}?)") > 40, "the fixture must exceed the old peek window"
    twice, added = annotator.annotate(once, Naming())
    assert twice == once
    assert added == 0


def test_no_annotation_is_ever_repeated_across_the_whole_term_dictionary() -> None:
    """Every shipped term composed and re-annotated, so no length or character can hide."""
    import re

    naming = Naming()
    names = ["受注データ", "品揃支援DATA.MDB", "青果集計商品マスタフッタ",
             "雑貨Ⅱアイテム別確認表フッタ2", "配送コースマスタ20241231バックアップ",
             "店舗ピッキングライン表示情報"]
    body = " ".join(f"`{n}`" for n in names)
    once, _ = annotator.annotate(body, naming)
    twice, added = annotator.annotate(once, Naming())
    assert added == 0
    duplicate = re.compile(r"\(([a-z0-9_.\-]+\??)\)\s*\(\1\)")
    assert not duplicate.search(twice), duplicate.findall(twice)


def test_the_appendix_distinguishes_the_three_states() -> None:
    """accepted / A01 precedent / proposed. A `?` on all three signals nothing."""
    naming = Naming({"店舗マスタ": "shop_master"})
    body = "`店舗マスタ` and `受注データ` and `ＤＰコード`."
    text = annotator.appendix(body, naming)
    assert "| `店舗マスタ` | `shop_master` | accepted |" in text
    assert "| `受注データ` | `order_data` | A01 precedent |" in text
    assert "| `ＤＰコード` | `dp_cd` | proposed |" in text


def test_an_annotation_from_the_older_marked_form_is_still_recognised() -> None:
    """A document annotated before the marker was removed must not gain a second one."""
    body = "The `受注データ` (order_data?) table."
    text, added = annotator.annotate(body, Naming())
    assert text == body
    assert added == 0
