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
    assert text == "The `受注データ` (order_data?) table."
    assert added == 1


def test_only_the_first_mention_is_annotated() -> None:
    body = "`受注データ` is read by `商品マスタ`, and `受注データ` again."
    text, added = annotator.annotate(body, Naming())
    assert text.count("(order_data?)") == 1
    assert added == 2


def test_nothing_inside_a_fenced_block_is_touched() -> None:
    body = (
        "Before `受注データ`.\n\n"
        "```mermaid\nflowchart TD\n  A[`商品マスタ`] --> B\n```\n\n"
        "```sql\nSELECT * FROM `店舗マスタ`;\n```\n"
    )
    text, _ = annotator.annotate(body, Naming())
    assert "(order_data?)" in text
    assert "product_master" not in text, "a diagram must not be rewritten"
    assert "store_master" not in text, "a SQL snippet must not be rewritten"


def test_an_unclosed_fence_protects_the_rest_of_the_document() -> None:
    body = "Fine `受注データ`.\n\n```\nnot closed `商品マスタ`\n"
    text, _ = annotator.annotate(body, Naming())
    assert "(order_data?)" in text
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
    assert "(order_data?)" in narrative
    assert "(product_master?)" in narrative
    assert annotator.APPENDIX_HEADING in narrative


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
