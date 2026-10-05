"""A question is not put to a person when the kit already holds the answer (A58, slice 4).

Q109 asked warehouse operations for the option-group values behind two lists. The form
declares exactly two, `バラのみ` at 1 and `ケースとバラ` at 2, and the bundle had held them from
the start; the question was withdrawn by hand after it was published. The pre-check looks in
the two places that already hold facts - the screen catalogue's `Offers` column and
`meanings.yaml` - and flags, never answers.

A flag a person learns to skip is worse than none, so half of these tests are the ways a
matcher goes noisy. The first run on one register's 47 open items flagged one, and it was wrong: a
question about whether two screens were reachable matched an object whose short name sat
inside a longer one the question quoted.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import decision_agenda as da  # noqa: E402
import decision_precheck as dp  # noqa: E402
import decision_queue as dq  # noqa: E402
from test_decision_agenda import entry, needs, parties, q, run  # noqa: E402
from test_decision_agenda import make_workspace  # noqa: E402

CATALOGUE = """# A99 - Screen Catalogue

## Interactive controls (4 of 20 controls)

| Object | Control | Type | Caption | Offers | On click | Visible |
|---|---|---|---|---|---|---|
| `出荷数確認リスト印刷画面` | `fraレポート` | option group | — | `1` = バラのみ, `2` = ケースとバラ (default `2`) | — | visible |
| `出荷数確認リスト印刷画面` | `cmd印刷` | button | `印刷` | — | `[Event Procedure]` | visible |
| `在庫数記入リスト印刷画面` | `fra分類` | option group | — | `1` = 保冷品, `2` = 常温品 | — | visible |
| `印刷画面` | `fra向き` | option group | — | `1` = 縦, `2` = 横 | — | visible |
"""


def offers() -> list[dp.Offer]:
    return dp.catalogue_offers(CATALOGUE)


def flags(text: str, meanings: list[dp.Meaning] | None = None, *, kind: str = "FACT",
          closed: bool = False) -> list[dict]:
    e = entry("Q109", "Q", 2, title="t", needs=needs(kind=kind) if kind != "DISPOSITION" else
              {"kind": "DISPOSITION", "party": "decider", "blocks": []})
    if closed:
        e["resolved_by"] = "A99-P2-INTERVIEW-001"
    return dp.precheck({"Q109": {"ask": text}}, [e], offers(), meanings or []).get("Q109", [])


# --- the catalogue -----------------------------------------------------------------

def test_the_catalogue_is_read_by_header_name_and_rows_with_no_offers_are_skipped() -> None:
    rows = offers()
    assert [(o.object, o.control) for o in rows] == [
        ("出荷数確認リスト印刷画面", "fraレポート"), ("在庫数記入リスト印刷画面", "fra分類"), ("印刷画面", "fra向き")]
    assert "ケースとバラ" in rows[0].offers


def test_a_catalogue_with_the_columns_in_another_order_reads_the_same() -> None:
    swapped = ("| Offers | Control | Object |\n|---|---|---|\n"
               "| `1` = a, `2` = b | `fraX` | `画面Y` |\n| — | `cmd` | `画面Y` |\n")
    assert [(o.object, o.control, o.offers) for o in dp.catalogue_offers(swapped)] == [
        ("画面Y", "fraX", "`1` = a, `2` = b")]


def test_text_with_no_such_table_gives_nothing() -> None:
    assert dp.catalogue_offers("# nothing\n\n| a | b |\n|---|---|\n| 1 | 2 |\n") == []


# --- what is flagged -----------------------------------------------------------------

def test_q109_as_it_was_asked_is_flagged_before_it_is_put_to_anyone() -> None:
    found = flags("What are the option-group values behind `出荷数確認リスト` and `在庫数記入リスト`?")
    assert {f["name"] for f in found} == {"出荷数確認リスト", "在庫数記入リスト"}
    assert all(f["kind"] == "offers" and f["source"] == "ScreenCatalogue" for f in found)
    assert "ケースとバラ" in found[0]["text"] and "fraレポート" in found[0]["text"]


def test_a_control_named_exactly_is_flagged_without_asking_about_choices() -> None:
    """The control is the subject when it is named whole; no wording is needed to know it."""
    found = flags("Who chooses `fra分類` each evening?")
    assert len(found) == 1 and "常温品" in found[0]["text"]


def test_naming_an_object_is_not_asking_what_it_offers() -> None:
    assert flags("Is `出荷数確認リスト印刷画面` reachable at all?") == []


def test_an_object_inside_a_longer_quoted_name_is_a_different_object() -> None:
    """The one flag that first run produced, and it was wrong: `印刷画面` is a real object, and
    it sits inside the name of a screen the question was asking about for another reason."""
    assert flags("What values does `新規事業部受注合計表印刷画面` take?") == []


def test_a_name_too_short_to_mean_anything_is_not_matched_inside_other_names() -> None:
    assert flags("Which value is `画面`?") == []


def test_a_question_that_quotes_nothing_is_not_checked() -> None:
    """A stated limit, not a hidden one: the names read are the ones a document quotes."""
    assert flags("What are the option values behind the adjustment lists?") == []


def test_only_an_open_fact_is_checked() -> None:
    text = "Which `fra分類` is chosen?"
    assert flags(text) and not flags(text, kind="DISPOSITION") and not flags(text, closed=True)


# --- meanings.yaml ---------------------------------------------------------------------

MEANINGS = [dp.Meaning("table", "商品情報", "Product-specific logistics attributes.", "input/interviews/QA-06, 2026-08-30"),
            dp.Meaning("column", "準備数", "Preparation quantity entered by staff.", "")]


def test_a_table_the_meanings_file_already_explains_is_flagged_with_its_source() -> None:
    found = flags("What does the table `商品情報` hold?", MEANINGS)
    assert found == [{"kind": "meaning", "name": "商品情報", "source": "input/interviews/QA-06, 2026-08-30",
                      "text": "meanings.yaml already says the table `商品情報` means: Product-specific logistics attributes."}]


def test_a_meaning_with_no_source_names_the_file_instead() -> None:
    assert flags("What is `準備数`?", MEANINGS)[0]["source"] == "meanings.yaml"


def test_read_meanings_ignores_blank_entries_and_a_missing_file(tmp_path: Path) -> None:
    assert dp.read_meanings(tmp_path / "meanings.yaml") == []
    path = tmp_path / "meanings.yaml"
    path.write_text("tables:\n  商品情報:\n    meaning: ''\n  受注:\n    meaning: Orders.\n    source: s\ncolumns: {}\n",
                    encoding="utf-8")
    assert [(m.name, m.source) for m in dp.read_meanings(path)] == [("受注", "s")]
    path.write_text("tables: [this is not a mapping\n", encoding="utf-8")
    assert dp.read_meanings(path) == []


# --- the list and the queue ------------------------------------------------------------

def queue_with(prechecks: dict | None) -> dict:
    entries = [entry("WF-001", "WF-"), q("Q117", blocks=["WF-001"])]
    return da.build_queue(entries, parties(), app_id="A99", prechecks=prechecks)


def test_a_queue_with_nothing_found_is_the_same_as_before() -> None:
    plain = queue_with(None)
    assert queue_with({}) == plain
    assert "precheck" not in plain["items"][0] and "prechecked" not in plain["counts"]


def test_a_flag_reaches_the_item_the_count_and_the_written_list() -> None:
    found = {"Q117": [{"kind": "offers", "name": "x", "source": "ScreenCatalogue",
                       "text": "`fra分類` on `画面` offers `1` = 保冷品"}]}
    built = queue_with(found)
    assert built["items"][0]["precheck"] == found["Q117"]
    assert built["counts"]["prechecked"] == 1
    markdown = da.render_markdown(built, parties=parties(), texts={}, source="x")
    assert "- **Check before asking:** `fra分類` on `画面` offers `1` = 保冷品 (ScreenCatalogue)" in markdown


def test_the_command_flags_a_question_from_the_catalogue_beside_the_documents(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    doc = root / "output" / "A99_Phase4_Flow_EN.md"
    doc.write_text(doc.read_text(encoding="utf-8").replace(
        "Which action makes the PDFs?", "Which `fra分類` value applies to the PDFs?"), encoding="utf-8")
    (root / "output" / "A99_ScreenCatalogue.md").write_text(CATALOGUE, encoding="utf-8")
    assert run(monkeypatch, root) == 0
    assert "1 open item(s) name something the kit already holds" in capsys.readouterr().out
    queue = json.loads((root / "output" / "A99_DecisionQueue.json").read_text(encoding="utf-8"))
    flagged = {i["id"]: i for i in queue["items"] if i.get("precheck")}
    assert list(flagged) == ["Q118"] and "常温品" in flagged["Q118"]["precheck"][0]["text"]
    assert "Check before asking" in (root / "output" / "A99_QuestionList.md").read_text(encoding="utf-8")


def test_a_workspace_with_no_catalogue_is_checked_against_what_it_has(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    assert run(monkeypatch, root) == 0
    assert "already holds" not in capsys.readouterr().out


def test_the_first_catalogue_beside_the_documents_is_the_one_read(tmp_path: Path) -> None:
    (tmp_path / "A99_ScreenCatalogue.md").write_text(CATALOGUE, encoding="utf-8")
    (tmp_path / "B77_ScreenCatalogue.md").write_text("nothing", encoding="utf-8")
    loaded, _ = dp.load(tmp_path, tmp_path, "A99")
    assert len(loaded) == 3
    assert dp.load(tmp_path, tmp_path, "C00")[0] == []
