"""Business meaning, and the rule that a meaning without a source is not stored.

This is the kit's own central finding turned into a mechanism: no volume of schema or
code establishes what a table is for, so the column stays empty until a document, an
interview or an operator says so. Before this file existed there was nowhere to put
such an answer, which meant the column would have stayed empty however many documents
arrived.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

import meanings as m  # noqa: E402


def write(path: Path, body: str) -> Path:
    io.open(path, "w", encoding="utf-8", newline="\n").write(body)
    return path


def test_a_missing_file_means_nothing_recorded(tmp_path: Path) -> None:
    loaded = m.load(tmp_path / "absent.yaml")
    assert loaded.tables == {} and loaded.columns == {}
    assert loaded.incomplete == []


def test_a_complete_entry_is_stored_and_cites_its_source(tmp_path: Path) -> None:
    path = write(tmp_path / "meanings.yaml", """
tables:
  受注データ:
    role: Transaction
    meaning: One row per ordered line, per store, per shipping date.
    evidence_class: INTERVIEW
    source: 受注課, 2026-09-10
""")
    loaded = m.load(path)
    entry = loaded.table("受注データ")
    assert entry is not None
    assert entry.role == "Transaction"
    assert "INTERVIEW: 受注課, 2026-09-10" in entry.cite()


def test_a_meaning_with_no_source_is_refused(tmp_path: Path) -> None:
    """The rule this kit exists to enforce, applied to its own decisions file."""
    path = write(tmp_path / "meanings.yaml", """
tables:
  受注データ:
    meaning: Orders, probably.
    evidence_class: INTERVIEW
""")
    loaded = m.load(path)
    assert loaded.table("受注データ") is None
    assert any("no source" in problem for problem in loaded.incomplete)


def test_an_invented_evidence_class_is_refused(tmp_path: Path) -> None:
    """CODE and SCHEMA cannot establish a meaning. Rule EC-01."""
    for bad in ("CODE", "SCHEMA", "INFERENCE", ""):
        path = write(tmp_path / "meanings.yaml", f"""
tables:
  受注データ:
    meaning: Orders.
    evidence_class: "{bad}"
    source: somewhere
""")
        loaded = m.load(path)
        assert loaded.table("受注データ") is None, bad
        assert loaded.incomplete, bad


def test_every_valid_class_is_accepted(tmp_path: Path) -> None:
    for good in m.VALID_CLASSES:
        path = write(tmp_path / "meanings.yaml", f"""
tables:
  受注データ:
    meaning: Orders.
    evidence_class: {good}
    source: a named source
""")
        assert m.load(path).table("受注データ") is not None, good


def test_a_column_meaning_can_be_scoped_to_one_table_or_to_the_name(
    tmp_path: Path,
) -> None:
    """53 A05 column names appear in several tables, so both forms are needed."""
    path = write(tmp_path / "meanings.yaml", """
columns:
  出荷数量:
    meaning: Quantity to ship.
    evidence_class: DOCUMENT
    source: function list v3 p.12
  受注データ.伝票番号:
    meaning: Slip number allocated at import, unique per shipping date only.
    evidence_class: INTERVIEW
    source: 受注課
""")
    loaded = m.load(path)
    # The bare name applies wherever the column appears.
    assert loaded.column("受注データ", "出荷数量") is not None
    assert loaded.column("WK集計", "出荷数量") is not None
    # The scoped one applies only to its table.
    assert loaded.column("受注データ", "伝票番号") is not None
    assert loaded.column("商品マスタ", "伝票番号") is None


def test_a_scoped_entry_wins_over_the_bare_name(tmp_path: Path) -> None:
    path = write(tmp_path / "meanings.yaml", """
columns:
  数量:
    meaning: A quantity, generally.
    evidence_class: DOCUMENT
    source: general glossary
  受注データ.数量:
    meaning: Ordered quantity before any weight adjustment.
    evidence_class: INTERVIEW
    source: 受注課
""")
    entry = m.load(path).column("受注データ", "数量")
    assert entry is not None
    assert "before any weight adjustment" in entry.text


def test_a_malformed_entry_is_reported_rather_than_crashing(tmp_path: Path) -> None:
    path = write(tmp_path / "meanings.yaml", """
tables:
  受注データ: "just a string"
""")
    loaded = m.load(path)
    assert loaded.tables == {}
    assert any("not a mapping" in problem for problem in loaded.incomplete)
