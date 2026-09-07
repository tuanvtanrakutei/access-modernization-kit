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
    evidence_class: INTERVIEW
    source: Vo Ta Tuan, 2026-09-07
""")
    text = run(workspace)
    assert "One row per ordered line." in text
    assert "role: \"transaction\"" in text
    entry = meanings_contract.load(target).table("受注データ")
    assert entry is not None and entry.role == "transaction"
    # And the subjects it did not have are added alongside, still blank.
    assert '"商品情報":' in text


def test_a_meaning_declared_by_the_operator_is_refused(workspace: Path) -> None:  # noqa: F811
    """A18, settled 2026-09-07: OPERATOR_DECLARATION cannot carry a MEANING.

    The class is a statement about the inputs - which file is the backend, which copy
    is current. An operator who knows what a table is for is still a source, and the
    class for a source who is a person is INTERVIEW, so the identical sentence is
    accepted the moment it names who said it and when. That is the whole of what
    changed, and it is why this refusal costs an operator nothing.
    """
    target = workspace / "input" / "decisions" / "meanings.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    declared = """
tables:
  受注データ:
    meaning: One row per ordered line.
    evidence_class: OPERATOR_DECLARATION
    source: Vo Ta Tuan, 2026-09-07
"""
    target.write_text(declared, encoding="utf-8")
    refused = meanings_contract.load(target)
    assert refused.table("受注データ") is None
    assert any("受注データ" in row and "DOCUMENT, INTERVIEW" in row
               for row in refused.incomplete), refused.incomplete

    target.write_text(declared.replace("OPERATOR_DECLARATION", "INTERVIEW"),
                      encoding="utf-8")
    assert meanings_contract.load(target).table("受注データ") is not None


def test_a_form_and_a_report_sharing_a_name_are_two_questions(
    workspace: Path,  # noqa: F811
) -> None:
    """Keyed `"{kind} {name}"`, because A05 has a form and a report called the same.

    Keying by name alone would put one duplicate key in the YAML, where the last one
    silently wins - the defect the tables section already had to be fixed for. The
    fixture's two reports share a name across databases and are deliberately *one*
    entry; a form and a report sharing one would be two.
    """
    text = run(workspace)
    screens = text.split("screens:", 1)[1]
    assert '"form メインメニュー":' in screens
    assert '"form 商品検索":' in screens
    # Same name in two databases is one question, the same rule tables follow.
    assert screens.count('"report ピッキングリスト":') == 1
    assert "in 2 databases (BACK_2222, FRONT_1111)" in screens


def test_a_screen_note_carries_what_the_definition_already_says(
    workspace: Path,  # noqa: F811
) -> None:
    """The note is USAGE and STRUCTURE informing the question, never answering it.

    A person filling in a screen that 3 objects open and that carries 14 event
    procedures knows it is worth getting right. One that nothing opens needs a
    different question, and EC-05 is why: no code path opening it is unreachability,
    not disuse.
    """
    screens = run(workspace).split("screens:", 1)[1]
    assert "record source `select * from 集計商品マスタ`" in screens
    assert "2 bound field(s); 1 event procedure(s); opened by 0 object(s)" in screens
    assert "unreachability and not disuse" in screens
    # And nothing is proposed: every added entry is blank, screens included.
    body = screens.split('"form メインメニュー":', 1)[1]
    assert body.lstrip().startswith('meaning: ""')


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


def test_a_section_this_tool_does_not_manage_survives(workspace: Path) -> None:  # noqa: F811
    """Found by running the first version against the real A05 workspace.

    Its `meanings.yaml` carried a third section, `system:`, holding a sourced
    DOCUMENT-class statement of what the whole application is for, plus a note saying
    why the per-table meanings below it were still empty. Rewriting the file from its
    parsed `tables` and `columns` would have deleted both without a word - a tool that
    destroys sourced evidence while helping you record more of it.
    """
    target = workspace / "input" / "decisions" / "meanings.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    io.open(target, "w", encoding="utf-8", newline="\n").write("""
tables:

# --- recorded 2026-09-03 from the supplied system inventory ---
# The document is a system inventory, not a data dictionary, which is why the
# per-table meanings are still empty.

system:
  A05:
    meaning: Printing the lists used by 入出庫課 and 運送課.
    evidence_class: DOCUMENT
    source: SMSシステム一覧 20241015.xlsx, row 11
""")
    text = run(workspace)
    assert "system:" in text
    assert "Printing the lists used by 入出庫課" in text
    # The comment explaining it travels with it: it is often the only record of why
    # the entry reads the way it does.
    assert "not a data dictionary" in text
    # And the managed sections were still filled in alongside.
    assert '"受注データ":' in text


def test_an_unmanaged_section_still_parses_after_a_rewrite(workspace: Path) -> None:  # noqa: F811
    import yaml

    target = workspace / "input" / "decisions" / "meanings.yaml"
    target.parent.mkdir(parents=True, exist_ok=True)
    io.open(target, "w", encoding="utf-8", newline="\n").write(
        "system:\n  A05:\n    meaning: x\n    evidence_class: DOCUMENT\n"
        "    source: y\n")
    data = yaml.safe_load(run(workspace))
    assert data["system"]["A05"]["source"] == "y"
    assert "tables" in data and "columns" in data


def test_one_name_in_two_databases_is_one_entry(workspace: Path) -> None:  # noqa: F811
    """`contracts/meanings.py` resolves a table meaning by name alone.

    Emitting one key per database put a duplicate key in the YAML, where the last
    silently wins. On the real A05 workspace that turned 121 subjects into 118 entries
    and lost three tables' notes - `商品情報` among them, which the evidence request has
    an open question about precisely because it exists in both databases.
    """
    import yaml

    tables = workspace / ".ak" / "bundles" / "bundle-abc" / "databases" / "tables.json"
    io.open(tables, "w", encoding="utf-8", newline="\n").write(
        '[{"database_id": "%s", "name": "商品情報", "kind": "table", "metadata": {}},'
        ' {"database_id": "%s", "name": "商品情報", "kind": "table", "metadata": {}}]'
        % (BE, FE))
    text = run(workspace)
    assert text.count('  "商品情報":') == 1
    data = yaml.safe_load(text)
    assert len(data["tables"]) == 1
    # And the note says it is in both, which is the fact that makes it worth asking.
    assert any("in 2 databases" in line and BE in line and FE in line
               for line in text.splitlines() if line.strip().startswith("#"))
