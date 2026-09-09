"""The Q&A register read against the pages it indexes.

INTERVIEW is the one class nothing in this kit produces, and a project keeping a
register of its questions holds the most valuable evidence it has. What the kit could
see before this was only that some files existed in `input/interviews/`.

The finding that matters is a disagreement, and it was real on the first register this
ran against: A06's ID 6 carries `Status: Answered`, a respondent and an answer date, and
its page holds no answer at all. Nothing else in the workspace can say so.
"""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
sys.path.insert(0, str(PACKAGE / "contracts"))

import check_interview_register as checker  # noqa: E402
import workspace as workspace_contract  # noqa: E402

BOM = "﻿"
REGISTER = (
    BOM + "ID,詳細(Detail）,Status,Asker,Ask date,Respondent,Answer date,機能・画面(Funct/Scr)\n"
    "1,Related to classification,Answered,Dung,2026/08/17,HideroTanaka,2026/08/19,商品情報登録\n"
    "5,初期データや配置位置,In Progress,Dung,2026/08/19,\"HideroTanaka, 堀内\",2026/08/20,\n"
    "6,商品情報画面の削除,Answered,hiepnq,2026/08/26,榎本 稔,2026/08/30,\n"
)


def _page(identifier: str, body: str) -> str:
    return (
        "# Question " + identifier + "\n\n"
        "ID: " + identifier + "\n"
        "Ask date: 2026/08/17\n"
        "Asker: Dung\n"
        "Status: Answered\n"
        "\n" + body + "\n"
    )


def _workspace(tmp_path: Path, pages: dict, register: str | None = REGISTER):
    interviews = tmp_path / "input" / "interviews"
    interviews.mkdir(parents=True)
    if register is not None:
        (interviews / "QA-register.csv").write_text(register, encoding="utf-8")
    for name, text in pages.items():
        (interviews / name).write_text(text, encoding="utf-8")
    return workspace_contract.Workspace(tmp_path)


def test_a_question_recorded_as_answered_whose_page_holds_no_answer(tmp_path: Path) -> None:
    """The finding this exists for, and it was real on the first register read.

    A06's ID 6: `Answered`, `Respondent: 榎本 稔`, `Answer date: 2026/08/30`, and a page
    carrying only the question and a screenshot. A closed question with no answer in it
    cannot be cited, and the register is the only thing claiming it is closed.
    """
    space = _workspace(tmp_path, {
        "q1.md": _page("1", "【2026/08/19: 田中】All 担当者 become 商品区分."),
        "q5.md": _page("5", "No dated answer yet."),
        "q6.md": _page("6", "上記の画面では、削除および新規登録は可能でしょうか。"),
    })
    result = checker.observe(space)
    codes = {(f["id"], f["code"]) for f in result["findings"]}
    assert ("6", "ANSWERED_WITHOUT_AN_ANSWER") in codes
    assert ("5", "NOT_ANSWERED") in codes
    # ID 1 is answered and its page proves it, so it raises nothing of its own.
    assert not [f for f in result["findings"]
                if f["id"] == "1" and f["code"] != "NO_SCREEN_NAMED"]


def test_an_emphasis_bracket_is_not_an_answer(tmp_path: Path) -> None:
    """Japanese prose uses full-width brackets for headings, and a real register does.

    A06's Q&A 5 opens its body with `【質問1：インポートファイルの文字コードについて】`.
    Counting that as an answer would report the one genuinely open question as closed -
    the exact error this check exists to catch, made by the check.
    """
    space = _workspace(
        tmp_path,
        {"q6.md": _page("6", "【質問1：インポートファイルの文字コードについて】\n本文です。")},
        register=BOM + "ID,Status,Respondent\n6,Answered,榎本 稔\n",
    )
    result = checker.observe(space)
    assert result["pages"][0]["answers"] == []
    assert [f for f in result["findings"] if f["code"] == "ANSWERED_WITHOUT_AN_ANSWER"]


def test_an_answer_is_read_with_its_person_and_date(tmp_path: Path) -> None:
    """Both forms the real register uses, including a single-digit month."""
    space = _workspace(
        tmp_path,
        {"q1.md": _page("1", "【2026/08/19: 田中】one\n【2026/8/20: 堀内】two")},
        register=BOM + "ID,Status\n1,Answered\n",
    )
    assert checker.observe(space)["pages"][0]["answers"] == [
        {"recorded_on": "2026-08-19", "person": "田中"},
        {"recorded_on": "2026-08-20", "person": "堀内"},
    ]


def test_the_columns_are_matched_by_name_not_position(tmp_path: Path) -> None:
    """The same Notion database exports twice with the columns in two orders.

    A06's `X.csv` and `X_all.csv` differ, so a position-mapped reader would be right
    about one file and silently wrong about the other.
    """
    reordered = (
        BOM + "詳細(Detail）,Answer date,Ask date,Asker,ID,Respondent,Status,機能・画面(Funct/Scr)\n"
        "a title,2026/08/19,2026/08/17,Dung,1,HideroTanaka,Answered,商品情報登録\n"
    )
    space = _workspace(tmp_path, {"q1.md": _page("1", "【2026/08/19: 田中】yes")}, reordered)
    assert checker.observe(space)["register"] == [{
        "id": "1", "title": "a title", "status": "Answered", "asker": "Dung",
        "respondent": "HideroTanaka", "ask_date": "2026/08/17",
        "answer_date": "2026/08/19", "screen": "商品情報登録",
    }]


def test_the_guide_init_writes_is_not_read_as_a_question(tmp_path: Path) -> None:
    """`input/interviews/README.md` is the kit's own guide (A29), not a Q&A page.

    Decided by shape rather than by filename, so the rule does not break the moment
    somebody names a real answer `README.md` - a page is a page when it carries a
    property block with an ID.
    """
    space = _workspace(
        tmp_path,
        {
            "README.md": "# The interviews guide\n\nSome guidance: with a colon in it.\n",
            "q1.md": _page("1", "【2026/08/19: 田中】yes"),
        },
        register=BOM + "ID,Status\n1,Answered\n",
    )
    assert [page["id"] for page in checker.observe(space)["pages"]] == ["1"]


def test_a_page_the_register_does_not_list_is_reported_and_so_is_the_reverse(
    tmp_path: Path,
) -> None:
    space = _workspace(
        tmp_path,
        {"q9.md": _page("9", "【2026/08/19: 田中】yes")},
        register=BOM + "ID,Status\n1,Answered\n",
    )
    codes = {(f["id"], f["code"]) for f in checker.observe(space)["findings"]}
    assert ("9", "NOT_IN_REGISTER") in codes
    assert ("1", "NO_PAGE") in codes


def test_the_screen_column_is_reported_once_not_per_question(tmp_path: Path) -> None:
    """Five identical lines drowned the two findings about a specific question.

    Which is the failure a report has instead of a crash: it is read to the end, or it
    is not read.
    """
    space = _workspace(
        tmp_path,
        {"q1.md": _page("1", "x"), "q2.md": _page("2", "y")},
        register=BOM + "ID,Status\n1,Answered\n2,Answered\n",
    )
    screen = [f for f in checker.observe(space)["findings"]
              if f["code"] == "NO_SCREEN_NAMED"]
    assert len(screen) == 1
    assert "1, 2" in screen[0]["detail"]


def test_no_register_at_all_reports_nothing_to_read(tmp_path: Path) -> None:
    (tmp_path / "input" / "interviews").mkdir(parents=True)
    result = checker.observe(workspace_contract.Workspace(tmp_path))
    assert result["registers"] == [] and result["pages"] == []


def test_a_cp932_register_is_read(tmp_path: Path) -> None:
    """A register hand-edited in Excel on a Japanese host arrives that way."""
    interviews = tmp_path / "input" / "interviews"
    interviews.mkdir(parents=True)
    (interviews / "reg.csv").write_bytes(
        "ID,Status,詳細(Detail）\n1,Answered,商品情報登録について\n".encode("cp932")
    )
    (interviews / "q1.md").write_text(_page("1", "【2026/08/19: 田中】yes"), encoding="utf-8")
    result = checker.observe(workspace_contract.Workspace(tmp_path))
    assert result["register"][0]["title"] == "商品情報登録について"
