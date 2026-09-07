"""The meanings worklist: what it writes, and the one thing it must never write.

`$ak glossary` proposes a name and marks it `proposed`. The temptation is to do the
same for meanings, and the whole kit is an argument against it: a composed name is
checkable against the terms it came from, a composed meaning is indistinguishable from
an answer. So the test that matters most here is that every entry comes out blank.
"""
from __future__ import annotations

import io
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
sys.path.insert(0, str(PACKAGE / "contracts"))

import meanings as meanings_contract  # noqa: E402
import build_meanings as builder  # noqa: E402

from test_generate_catalogues import BE, FE, workspace  # noqa: E402,F401


def run(root: Path, *extra: str) -> str:
    sys.argv = ["build_meanings.py", "--app-root", str(root), *extra]
    assert builder.main() == 0
    return (root / "input" / "decisions" / "meanings.yaml").read_text(encoding="utf-8")


def test_every_entry_is_written_blank(workspace: Path) -> None:  # noqa: F811
    """No proposal, ever. Rules EC-01 and EC-03 are the reason.

    A generated meaning would read exactly like a sourced one in the catalogue, and
    nobody downstream could tell which they were looking at.
    """
    text = run(workspace)
    loaded = meanings_contract.load(
        workspace / "input" / "decisions" / "meanings.yaml")
    assert loaded.tables == {} and loaded.columns == {}
    assert loaded.incomplete == [], "a blank worklist entry is not a defect"
    assert loaded.unfilled, "every subject should be waiting"
    # Not one entry carries a value, in any field. Read from the body rather than the
    # whole file, because the header explains EC-03 using the words a proposal would.
    body = text.split("\ntables:", 1)[1]
    values = [line.split(":", 1)[1].strip() for line in body.splitlines()
              if line.startswith("    ")]
    assert values and set(values) == {'""'}


def test_the_note_carries_what_the_kit_knows(workspace: Path) -> None:  # noqa: F811
    """USAGE and STRUCTURE evidence beside the blank, to inform the sentence.

    受注データ is written by a query and named by one object; 商品情報 by nothing. That
    difference is what tells a person which question to ask about which table.
    """
    text = run(workspace)
    for line in text.splitlines():
        if "受注データ" in line and line.strip().startswith("#"):
            break
    notes = {line.strip("# ").strip() for line in text.splitlines()
             if line.strip().startswith("#")}
    assert any("writer(s)" in note and "column(s)" in note for note in notes)
    assert any("no writer attributable" in note for note in notes)


def test_a_shared_column_name_is_asked_once(workspace: Path) -> None:  # noqa: F811
    """A name in several tables is one question, and the bare key answers all of them.

    `contracts/meanings.py` resolves a bare name for every table, so scoping each
    occurrence separately would be more work for a worse answer.
    """
    fields = workspace / ".ak" / "bundles" / "bundle-abc" / "databases" / "fields.json"
    io.open(fields, "w", encoding="utf-8", newline="\n").write(
        '[{"database_id": "%s", "name": "出荷数量", "table": "受注データ", "type": 7},'
        ' {"database_id": "%s", "name": "出荷数量", "table": "WK集計", "type": 7},'
        ' {"database_id": "%s", "name": "商品コード", "table": "商品情報", "type": 4}]'
        % (BE, BE, FE))
    text = run(workspace)
    assert '"出荷数量":' in text, "shared, so keyed bare"
    assert '"受注データ.出荷数量":' not in text
    assert '"商品情報.商品コード":' in text, "in one table only, so scoped to it"


def test_a_filled_entry_survives_a_rerun(workspace: Path) -> None:  # noqa: F811
    """The file is person-owned. A re-run adds; it never edits."""
    run(workspace)
    target = workspace / "input" / "decisions" / "meanings.yaml"
    io.open(target, "w", encoding="utf-8", newline="\n").write("""
tables:
  受注データ:
    role: transaction
    meaning: One row per ordered line.
    evidence_class: OPERATOR_DECLARATION
    source: Vo Ta Tuan, 2026-09-07
""")
    text = run(workspace)
    assert "One row per ordered line." in text
    assert "role: \"transaction\"" in text
    entry = meanings_contract.load(target).table("受注データ")
    assert entry is not None and entry.role == "transaction"
    # And the subjects it did not have are added alongside, still blank.
    assert '"商品情報":' in text


def test_a_sourced_meaning_outlives_its_table(workspace: Path) -> None:  # noqa: F811
    """A meaning somebody obtained is not dropped because a bundle stopped listing it.

    This is what separates the file from a generated artefact: re-deriving it would
    lose the only thing in it that cost a person something.
    """
    target = workspace / "input" / "decisions" / "meanings.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    io.open(target, "w", encoding="utf-8", newline="\n").write("""
tables:
  廃止テーブル:
    meaning: Superseded by 受注データ in 2019; kept for the archive.
    evidence_class: INTERVIEW
    source: 業務課, 2026-09-07
  空欄テーブル:
    meaning: ""
    evidence_class: ""
    source: ""
""")
    text = run(workspace)
    assert "Superseded by 受注データ" in text
    assert "no longer in the bundle; kept because it is sourced" in text
    # A blank entry for a subject that is gone is just stale worklist, and is dropped.
    assert '"空欄テーブル":' not in text


def test_top_limits_what_is_added_without_dropping_anything(
    workspace: Path,  # noqa: F811
) -> None:
    """1,176 blank entries is a worklist nobody starts. `--top` is where to start."""
    text = run(workspace, "--top", "1")
    tables = [line for line in text.splitlines()
              if line.startswith('  "') and line.endswith('":')]
    assert len(tables) < 5, "only the highest-priority subject per section"
    # And the rest arrive on a later run, with the first still there.
    again = run(workspace)
    assert len(again) > len(text)
    for name in ("受注データ", "商品情報", "元受注データ"):
        assert f'"{name}":' in again


def test_the_file_it_writes_parses_as_yaml(workspace: Path) -> None:  # noqa: F811
    """A production name may contain anything, including a `#` or a leading `No`."""
    import yaml

    tables = workspace / ".ak" / "bundles" / "bundle-abc" / "databases" / "tables.json"
    io.open(tables, "w", encoding="utf-8", newline="\n").write(
        '[{"database_id": "%s", "name": "No", "kind": "table", "metadata": {}},'
        ' {"database_id": "%s", "name": "\\u53d7\\u6ce8 # \\u4eee", "kind": "table",'
        ' "metadata": {}}]' % (BE, BE))
    data = yaml.safe_load(run(workspace))
    assert "No" in data["tables"], "an unquoted No is the boolean False in YAML 1.1"
    assert "受注 # 仮" in data["tables"], "a # would otherwise start a comment"
