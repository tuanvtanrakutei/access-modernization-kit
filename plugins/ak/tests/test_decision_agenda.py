"""The queue a person works from, and the list that asks it (A75, slice 2).

Built on A06's register after the slice 1 backfill: 22 open items, 17 of them with no default,
11 closed - six of those by the bundle answering on its own, which nothing reported before.
Q&A 5 was open with the customer and in no item; Q&A 8 still is. Every test here is a rule the
maintainer approved with the design, or a defect the first run on A06 showed: an item ranked
first because of how many things it was guessed to block, a block list that read as a
paragraph, a citation left in the sentence a person is asked, a bundle-owned file called a
legacy object.
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

import build_decisions  # noqa: E402
import decision_agenda as da  # noqa: E402
import decision_queue as dq  # noqa: E402
import decision_register as dr  # noqa: E402
import workspace as workspace_contract  # noqa: E402

BOM = "﻿"


# --- builders ----------------------------------------------------------------

def entry(eid: str, namespace: str, phase: int = 4, title: str | None = None, **extra: object) -> dict:
    return {"id": eid, "namespace": namespace, "phase": phase, "title": title or f"{eid} title",
            "evidence_ids": [], **extra}


def needs(**over: object) -> dict:
    base: dict = {"kind": "FACT", "party": "常温庫", "blocks": ["WF-001"], "default": None}
    base.update(over)
    return base


def q(eid: str, **over: object) -> dict:
    return entry(eid, "Q", needs=needs(**over))


def base() -> list[dict]:
    return [
        entry("WF-001", "WF-", title="受注データ取込 - the morning order import"),
        entry("WF-002", "WF-", title="受注調整リスト印刷 - the morning picking list"),
        entry("F-006", "F-", 2, "入荷実績入力"),
        entry("RW-02", "RW-", severity="HIGH", title="The seed is not what was prepared"),
        entry("RW-07", "RW-", severity="MEDIUM", title="Eight actions have no owner"),
        entry("AS-31", "AS-"), entry("AS-32", "AS-"),
    ]


def build(entries: list[dict], **kw: object) -> dict:
    return da.build_queue(entries, kw.pop("parties", None), **kw)


def order(queue: dict) -> list[str]:
    return [i["id"] for i in queue["items"]]


def interviews(*rows: tuple[str, str], answered: tuple[str, ...] = ()) -> dict:
    return {
        "register": [{"id": i, "title": f"Q&A {i}", "status": s, "ask_date": "2026/08/19",
                      "respondent": "Respondent One", "answer_date": ""} for i, s in rows],
        "pages": [{"id": i, "answers": ([{"recorded_on": "2026-08-30", "person": "Respondent Two"}]
                                         if i in answered else [])} for i, _ in rows],
    }


# --- what is in the queue ----------------------------------------------------

def test_the_queue_is_the_open_entries_that_carry_a_needs_block() -> None:
    entries = base() + [q("Q1"), entry("Q2", "Q"), entry("Q3", "Q", resolved_by="A-1", needs=needs())]
    result = build(entries)
    assert order(result) == ["Q1"]
    # The two risks in base() carry no `needs` either, and since slice 3 a risk is routed too.
    assert result["unrouted"] == ["Q2", "RW-02", "RW-07"]


def test_an_unknown_a_question_asks_about_is_not_unrouted() -> None:
    entries = base() + [entry("UK-W01", "UK-"), q("Q1", gap="UK-W01"), entry("UK-W02", "UK-")]
    assert build(entries)["unrouted"] == ["RW-02", "RW-07", "UK-W02"]


def test_a_default_is_what_lets_an_item_proceed() -> None:
    entries = base() + [q("Q1"), q("Q2", default="AS-31"),
                        entry("RW-09", "RW-", needs=needs(kind="DISPOSITION", party="decider",
                                                          default="mitigation"))]
    postures = {i["id"]: i["posture"] for i in build(entries)["items"]}
    assert postures == {"Q1": "BLOCKING", "Q2": "PROCEEDS_ON_DEFAULT", "RW-09": "PROCEEDS_ON_DEFAULT"}


def test_blocks_carry_their_titles_and_an_object_stays_an_object() -> None:
    entries = base() + [q("Q1", blocks=["F-006", "RW-02", "object:商品情報aa"])]
    blocks = build(entries)["items"][0]["blocks"]
    assert blocks[0] == {"id": "F-006", "title": "入荷実績入力"}
    assert blocks[1]["severity"] == "HIGH"
    assert blocks[2] == {"object": "商品情報aa"}


# --- the order ---------------------------------------------------------------

def test_what_stops_work_is_asked_before_what_merely_risks_rework() -> None:
    entries = base() + [q("Q1", default="AS-31"), q("Q2")]
    assert order(build(entries)) == ["Q2", "Q1"]


def test_a_dependency_is_asked_before_what_waits_on_it() -> None:
    """Q1 ranks first on its own - blocking, two blocks - and waits behind Q2 anyway. Asking
    it first would be asking a question the next answer makes moot."""
    entries = base() + [q("Q1", blocks=["WF-001", "WF-002"], depends_on=["Q2"]),
                        q("Q2", default="AS-31")]
    assert order(build(entries)) == ["Q2", "Q1"]


def test_a_chain_is_ordered_end_to_end() -> None:
    entries = base() + [q("Q1", depends_on=["Q2"]), q("Q2", depends_on=["Q3"]), q("Q3")]
    assert order(build(entries)) == ["Q3", "Q2", "Q1"]


def test_a_dependency_that_is_closed_waits_for_nothing() -> None:
    entries = base() + [q("Q1", depends_on=["Q2"]), entry("Q2", "Q", resolved_by="A-1")]
    item = build(entries)["items"][0]
    assert item["waiting_on"] == [] and item["bucket"] == "blocking"


def test_a_loop_is_reported_and_every_item_is_still_listed() -> None:
    entries = base() + [q("Q1", depends_on=["Q2"]), q("Q2", depends_on=["Q1"])]
    result = build(entries)
    assert sorted(order(result)) == ["Q1", "Q2"]
    assert any("wait on each other" in p for p in result["problems"])


def test_what_the_analysis_called_high_outranks_a_longer_block_list() -> None:
    """The first run on A06 put the item that blocked six workflows first, because that is how
    its author had written it. The one that decides a HIGH risk should come before it."""
    entries = base() + [q("Q1", blocks=["WF-001", "WF-002"]), q("Q2", blocks=["RW-02"])]
    assert order(build(entries)) == ["Q2", "Q1"]


def test_among_equals_more_blocks_come_first_and_numbers_sort_naturally() -> None:
    entries = base() + [q("Q4"), q("Q3", blocks=["WF-001", "WF-002"]), q("Q101"), q("Q5")]
    assert order(build(entries)) == ["Q3", "Q4", "Q5", "Q101"]


def test_an_item_others_wait_on_comes_before_the_free_ones() -> None:
    entries = base() + [q("Q5"), q("Q6", depends_on=["Q5"]), q("Q7", blocks=["WF-001", "WF-002"])]
    assert order(build(entries)) == ["Q5", "Q7", "Q6"]


# --- what is already with the customer ----------------------------------------

def test_an_item_posted_and_still_open_is_with_the_customer_and_not_to_be_asked() -> None:
    entries = base() + [q("Q5", qa=[5]), q("Q6")]
    result = build(entries, interviews=interviews(("5", "In Progress")))
    by = {i["id"]: i for i in result["items"]}
    assert by["Q5"]["bucket"] == "with_customer" and by["Q5"]["customer"]["state"] == "with_customer"
    assert result["counts"]["with_customer"] == 1 and result["counts"]["to_ask_now"] == 1


def test_a_dated_answer_the_register_does_not_know_is_reported() -> None:
    entries = base() + [q("Q6", qa=[6])]
    result = build(entries, interviews=interviews(("6", "Answered"), answered=("6",)))
    item = result["items"][0]
    assert item["customer"]["state"] == "answered_unrecorded" and item["bucket"] == "to_record"
    assert item["customer"]["qa"][0]["answered_on"] == ["2026-08-30"]
    assert result["counts"]["answered_not_recorded"] == 1


def test_marked_answered_with_no_answer_in_its_page_is_not_called_answered() -> None:
    """A47: A06's Q&A 6 was `Answered` for two weeks with the answer visible to everyone but
    the kit. A status is not an answer."""
    entries = base() + [q("Q6", qa=[6])]
    item = build(entries, interviews=interviews(("6", "Answered")))["items"][0]
    assert item["customer"]["state"] == "answer_missing" and item["bucket"] == "to_record"


def test_a_link_to_a_qa_the_register_does_not_list_is_a_problem_not_a_guess() -> None:
    result = build(base() + [q("Q5", qa=[99])], interviews=interviews(("5", "In Progress")))
    assert any("Q&A 99" in p for p in result["problems"])
    assert result["items"][0]["customer"]["state"] == "unknown"
    assert result["items"][0]["bucket"] == "blocking"      # still asked: nothing says it was


def test_a_link_with_no_qa_register_at_all_is_a_problem() -> None:
    result = build(base() + [q("Q5", qa=[5])], interviews=None)
    assert any("no Q&A register" in p for p in result["problems"])


def test_a_qa_open_with_the_customer_that_no_item_names_is_reported() -> None:
    """A06: Q&A 8 is In Progress and in no item. The queue cannot see what it blocks."""
    entries = base() + [q("Q5", qa=[5])]
    result = build(entries, interviews=interviews(("5", "In Progress"), ("6", "Answered"),
                                                  ("8", "In Progress")))
    assert [u["id"] for u in result["untracked_qa"]] == ["8"]


# --- what the machine already did ----------------------------------------------

def test_closed_items_are_counted_by_who_closed_them() -> None:
    """Six of A06's eleven closures were the bundle answering on its own, after the question
    had been published as one to put to a person (Q109, Q120, Q106...)."""
    entries = base() + [
        entry("Q1", "Q", resolved_by="E1"), entry("Q2", "Q", resolved_by="E2"),
        entry("Q3", "Q", resolved_by="E3"), entry("Q4", "Q", resolved_by="E4"),
        entry("Q5", "Q", superseded_by="Q1"), entry("Q6", "Q", resolved_by="E-missing"),
    ]
    evidence = {"E1": {"evidence_class": "INTERVIEW"}, "E2": {"evidence_class": "CODE"},
                "E3": {"evidence_class": "TARGET_INTENT"}, "E4": {"evidence_class": "SCREENSHOT"}}
    closed = build(entries, evidence=evidence)["counts"]["closed"]
    assert closed == {"total": 6, "by_person": 1, "by_bundle": 2, "by_decision": 1,
                      "superseded": 1, "unknown": 1}


def test_without_an_evidence_register_closures_are_unknown_not_guessed() -> None:
    result = build(base() + [entry("Q1", "Q", resolved_by="E1")])
    assert result["closed"][0]["by_kind"] == "unknown"


def test_closure_kind_follows_the_evidence_class_and_a_person_declaration_is_a_person() -> None:
    assert da.closure_kind("OPERATOR_DECLARATION") == "person"
    assert da.closure_kind("DOCUMENT") == "person"
    assert da.closure_kind("DATA_STATE") == "bundle"
    assert da.closure_kind(None) == "unknown"


# --- agendas ------------------------------------------------------------------

def test_one_agenda_per_party_with_the_decider_last_however_long_it_is() -> None:
    entries = base() + [q("Q1"), q("Q2", party="システム課"),
                        q("Q3", kind="DISPOSITION", party="decider"),
                        q("Q4", kind="DISPOSITION", party="decider"),
                        q("Q5", kind="DISPOSITION", party="decider")]
    # Tied on one item each, the parties sort by name; the decider has three and is still last.
    assert build(entries)["party_order"] == ["システム課", "常温庫", "decider"]


def test_the_party_with_more_to_ask_comes_first() -> None:
    entries = base() + [q("Q1", party="システム課"), q("Q2"), q("Q3")]
    assert build(entries)["party_order"] == ["常温庫", "システム課"]


def test_an_item_also_answerable_by_another_party_is_cross_listed() -> None:
    result = build(base() + [q("Q1", also=["システム課"])])
    assert result["also_for"] == {"システム課": ["Q1"]}


# --- determinism and counts -----------------------------------------------------

def test_the_same_register_gives_the_same_bytes_and_carries_no_date() -> None:
    entries = base() + [q("Q1"), q("Q2", default="AS-31"), entry("Q3", "Q", resolved_by="E1")]
    first, second = da.render_json(build(entries)), da.render_json(build(copy_of(entries)))
    assert first == second and first.endswith("\n")
    markdown = da.render_markdown(build(entries))
    assert markdown == da.render_markdown(build(copy_of(entries)))
    import re

    assert "generated_at" not in first
    assert not re.search(r"\d{4}-\d{2}-\d{2}", first + markdown), "a date makes the file differ between runs"


def copy_of(entries: list[dict]) -> list[dict]:
    return json.loads(json.dumps(entries))


def test_the_counts_add_up() -> None:
    entries = base() + [
        q("Q1"), q("Q2", default="AS-31"), q("Q3", depends_on=["Q1"]),
        q("Q5", qa=[5]), q("Q6", qa=[6]),
    ]
    c = build(entries, interviews=interviews(("5", "In Progress"), ("6", "Answered"),
                                              answered=("6",)))["counts"]
    assert c["open"] == 5 and c["blocking"] == 4 and c["proceeding_on_default"] == 1
    assert c["waiting_on_another_item"] == 1 and c["with_customer"] == 1
    assert c["answered_not_recorded"] == 1 and c["to_ask_now"] == 3
    assert c["by_kind"] == {"FACT": 5}
    assert c["by_party"]["常温庫"]["open"] == 5


# --- the list --------------------------------------------------------------------

def parties() -> dq.Parties:
    return dq.Parties.from_mapping({"parties": {
        "常温庫": {"aliases": ["Warehouse operations", "Vận hành kho", "Third", "Fourth"]}}})


def test_the_list_opens_by_saying_it_was_generated_and_what_it_is_for() -> None:
    text = da.render_markdown(build(base() + [q("Q1")], app_id="A99"))
    assert text.startswith(da.GENERATED)
    assert "# A99 — Question list" in text and "edit the register, not this file" in text


def test_a_blocking_item_and_one_that_proceeds_sit_under_different_headings() -> None:
    text = da.render_markdown(build(base() + [q("Q1"), q("Q2", default="AS-31")]))
    blocking, proceeding = text.index("### Blocks work now"), text.index("### Work continues on an assumption")
    assert blocking < text.index("Q1") < proceeding < text.index("Q2")
    assert "**Proceeding on:** AS-31" in text


def test_an_f_identifier_is_never_a_bare_number() -> None:
    """ID-06, in a generated artefact: a reader cannot tell which screen F-006 is."""
    text = da.render_markdown(build(base() + [q("Q1", blocks=["F-006"])]))
    assert "F-006 入荷実績入力" in text


def test_a_long_workflow_title_is_cut_and_a_screen_name_is_not() -> None:
    long_title = "x" * 120
    entries = base() + [entry("WF-009", "WF-", title=long_title), entry("F-009", "F-", title="y" * 120),
                        q("Q1", blocks=["WF-009", "F-009"])]
    line = next(l for l in da.render_markdown(build(entries)).split("\n") if l.startswith("- **Blocks:**"))
    assert "x" * 120 not in line and "…" in line and "y" * 120 in line


def test_an_object_that_is_not_a_legacy_object_is_not_called_one() -> None:
    """Q105's block is the customer's scope drawing, which is not a legacy object."""
    text = da.render_markdown(build(base() + [q("Q1", blocks=["object:A06_Scope.drawio.pdf"])]))
    assert "`A06_Scope.drawio.pdf` (object)" in text and "legacy object" not in text


def test_the_sentence_a_person_is_asked_has_no_citation_and_no_origin_marker() -> None:
    """A06's Q121 reads '**Raised by E-11.** The monthly run ... [A06-P4-CODE-002] [A06-P4-CODE-003]'.
    The citations are listed under 'Evidence already read'; the marker is about the analysis."""
    texts = {"Q1": {"ask": "**Raised by E-11.** What is the screen for? [A06-P4-CODE-002] [A06-P4-CODE-003]"}}
    text = da.render_markdown(build(base() + [q("Q1")]), texts=texts)
    assert "> What is the screen for?" in text
    assert "Raised by" not in text and "A06-P4-CODE-002]" not in text


def test_a_sentence_that_repeats_the_title_is_not_printed_twice() -> None:
    entries = base() + [entry("Q1", "Q", title="Which date is entered", needs=needs())]
    text = da.render_markdown(build(entries), texts={"Q1": {"ask": "Which date is entered?"}})
    assert "> Which date is entered?" not in text


def test_why_and_what_would_settle_it_come_from_the_unknown_the_question_asks_about() -> None:
    entries = base() + [entry("UK-W01", "UK-"), q("Q1", gap="UK-W01")]
    texts = {"Q1": {"ask": "Which date?"},
             "UK-W01": {"ask": "which date", "why": "The two must agree", "settle": "An operator describing one evening"}}
    text = da.render_markdown(build(entries), texts=texts)
    assert "**Why it matters:** The two must agree" in text
    assert "**What would settle it:** An operator describing one evening" in text
    assert "**About the unknown:** UK-W01" in text


def test_a_party_heading_shows_two_aliases_and_not_a_paragraph() -> None:
    text = da.render_markdown(build(base() + [q("Q1")]), parties=parties())
    assert "## Agenda: 常温庫 (Warehouse operations, Vận hành kho, …)" in text


def test_dependencies_are_stated_on_both_sides() -> None:
    text = da.render_markdown(build(base() + [q("Q1", depends_on=["Q2"]), q("Q2")]))
    assert "**Waits behind:** Q2" in text and "**Settles first for:** Q1" in text


def test_the_deciders_section_is_last_and_says_decide() -> None:
    entries = base() + [q("Q1"), q("Q2", kind="DISPOSITION", party="decider", options=["preserve", "fix"])]
    text = da.render_markdown(build(entries))
    assert text.index("## Agenda: 常温庫") < text.index("## Decisions for the decider")
    assert "1 to decide." in text and "**Choices:** preserve / fix" in text


def test_only_one_party_prints_just_that_agenda() -> None:
    entries = base() + [q("Q1"), q("Q2", party="システム課")]
    text = da.render_markdown(build(entries), only="システム課")
    assert "## Agenda: システム課" in text and "Q2" in text
    assert "Where things stand" not in text and "Q1 " not in text
    assert "Nothing is open for this party." in da.render_markdown(build(entries), only="nobody")


def test_one_agenda_pasted_alone_still_says_what_is_already_with_the_customer() -> None:
    """Linking Q5 to Q&A 5 on A06 made the party's agenda read '0 to ask. 1 already with the
    customer.' and then nothing, because the detail lived in a table further down the full list."""
    entries = base() + [q("Q5", qa=[5]), q("Q6", qa=[6])]
    result = build(entries, interviews=interviews(("5", "In Progress"), ("6", "Answered"),
                                                  answered=("6",)))
    alone = da.render_markdown(result, only="常温庫")
    assert "### Already with the customer" in alone and "Q&A 5: In Progress, asked 2026/08/19" in alone
    assert "### Answered by the customer and not yet recorded" in alone
    assert "dated answer 2026-08-30" in alone
    full = da.render_markdown(result)
    assert full.count("### Already with the customer") == 0       # the full list has its own table


def test_the_customers_side_the_unrecorded_answers_and_the_untracked_are_listed() -> None:
    entries = base() + [q("Q5", qa=[5]), q("Q6", qa=[6]), entry("Q9", "Q", resolved_by="E1")]
    text = da.render_markdown(build(
        entries, evidence={"E1": {"evidence_class": "CODE"}},
        interviews=interviews(("5", "In Progress"), ("6", "Answered"), ("8", "In Progress"),
                              answered=("6",))))
    assert "## Already with the customer" in text and "| Q5 Q5 title | 5 | In Progress |" in text
    assert "## Answered by the customer and not yet recorded" in text and "dated answer 2026-08-30" in text
    assert "## Open with the customer and in no item" in text and "Q&A 8" in text
    assert "| Q9 Q9 title | resolved by E1 | CODE |" in text
    assert "1 by the bundle, with nobody asked" in text


def test_a_register_nothing_can_route_says_so_in_its_own_list() -> None:
    text = da.render_markdown(build(base() + [entry("Q2", "Q")]))
    assert "## Problems" in text and "Q2 is open and carries no `needs`" in text


def test_an_empty_register_renders_an_empty_list() -> None:
    result = build([])
    text = da.render_markdown(result)
    assert result["counts"]["open"] == 0 and "| Open items | 0 |" in text
    assert "## Agenda" not in text and "## Problems" not in text


def test_a_pipe_in_a_title_does_not_shift_the_columns_of_a_table_row() -> None:
    """The defect the agreement check exists for, not committed by the generator that reads
    the same tables: one unescaped pipe and every cell after it belongs to the wrong column."""
    entries = base() + [entry("Q9", "Q", title="a | b", resolved_by="E1")]
    text = da.render_markdown(build(entries, evidence={"E1": {"evidence_class": "CODE"}}))
    row = next(line for line in text.split("\n") if line.startswith("| Q9"))
    assert dq.split_row(row) == ["Q9 a | b", "resolved by E1", "CODE"]


# --- the register helpers -----------------------------------------------------------

def test_the_register_round_trips_in_its_own_format(tmp_path: Path) -> None:
    register = {"app_id": "A99", "entries": [{"id": "Q1", "namespace": "Q", "phase": 1,
                                              "title": "常温庫", "evidence_ids": []}]}
    text = dr.format_register(register)
    assert text == json.dumps(register, indent=1, sort_keys=True, ensure_ascii=False) + "\n"
    assert "常温庫" in text and "\\u" not in text


def test_writing_the_register_keeps_every_previous_file(tmp_path: Path) -> None:
    space = workspace_contract.Workspace(tmp_path)
    (tmp_path / "input").mkdir()
    path = tmp_path / "A99_Identifiers.json"
    path.write_text(dr.format_register({"entries": []}), encoding="utf-8")
    first = dr.write_register(space, path, {"entries": [{"id": "Q1"}]})
    second = dr.write_register(space, path, {"entries": [{"id": "Q2"}]})
    assert first != second and first.is_file() and second.is_file()
    assert json.loads(first.read_text(encoding="utf-8")) == {"entries": []}
    assert json.loads(second.read_text(encoding="utf-8")) == {"entries": [{"id": "Q1"}]}


def test_a_language_the_phase_was_never_written_in_falls_back_to_english(tmp_path: Path) -> None:
    for name in ("A99_Phase3_Logic_EN.md", "A99_Phase4_Flow_EN.md", "A99_Phase4_Flow_VI.md"):
        (tmp_path / name).write_text("x", encoding="utf-8")
    chosen = {p: path.name for p, path in dr.phase_documents(tmp_path, "VI").items()}
    assert chosen == {3: "A99_Phase3_Logic_EN.md", 4: "A99_Phase4_Flow_VI.md"}
    assert {p: path.name for p, path in dr.phase_documents(tmp_path).items()}[4] == "A99_Phase4_Flow_EN.md"


PHASE_DOC = """### Unknowns

| ID | Unknown | Why it matters | What would settle it | Party |
|---|---|---|---|---|
| UK-W01 | Which date is entered? | The two must agree | An operator describing one evening | 常温庫 |

### Questions

| ID | Question | Blocks | Party |
|---|---|---|---|
| Q117 | Which date is entered on the evening build? | Reproducing the day boundary | 常温庫 |
| Q118 | Which action makes the PDFs? | WF-001 | 常温庫 |
| Q120 | **Answered — E-11.** Rewritten in place | Who uses it? | [A99-P4-CODE-003] |
"""


def test_the_documents_row_supplies_the_sentence_why_and_what_would_settle_it(tmp_path: Path) -> None:
    (tmp_path / "A99_Phase4_Flow_EN.md").write_text(PHASE_DOC, encoding="utf-8")
    entries = [entry("UK-W01", "UK-"), entry("Q117", "Q"), entry("Q118", "Q"), entry("Q120", "Q")]
    texts = dr.item_texts(tmp_path, entries, None, ("answered",))
    assert texts["Q117"] == {"ask": "Which date is entered on the evening build?",
                             "blocks_prose": "Reproducing the day boundary"}
    assert texts["Q118"]["blocks_prose"] == ""                 # a structured cell is not prose
    assert texts["UK-W01"] == {"ask": "Which date is entered?", "why": "The two must agree",
                               "settle": "An operator describing one evening"}
    assert "Q120" not in texts                                   # rewritten when it closed


# --- the command ------------------------------------------------------------------

REGISTER_CSV = (
    BOM + "ID,詳細(Detail）,Status,Asker,Ask date,Respondent,Answer date,機能・画面(Funct/Scr)\n"
    "5,Initial data and placement,In Progress,Asker One,2026/08/19,Respondent One,2026/08/20,\n"
    "6,Delete and new registration,Answered,Asker Two,2026/08/26,Respondent Two,2026/08/30,\n"
)


def make_workspace(tmp_path: Path, *, registers_dir: bool = False, unrouted: bool = False) -> Path:
    root = tmp_path / "A99"
    (root / "input" / "decisions").mkdir(parents=True)
    interviews_dir = root / "input" / "interviews"
    interviews_dir.mkdir(parents=True)
    (interviews_dir / "QA-register.csv").write_text(REGISTER_CSV, encoding="utf-8")
    (interviews_dir / "q6.md").write_text(
        "# Q6\n\nID: 6\nAsk date: 2026/08/26\nAsker: Asker Two\nStatus: Answered\n\n"
        "【2026/08/30: Respondent Two】Add and delete exist and have never been used.\n", encoding="utf-8")
    (root / "input" / "decisions" / "parties.yaml").write_text(
        "parties:\n  常温庫:\n    aliases: [Warehouse operations]\n", encoding="utf-8")
    out = root / "output"
    where = out / "registers" if registers_dir else out
    where.mkdir(parents=True)
    entries = [
        entry("WF-001", "WF-", title="受注データ取込"), entry("AS-32", "AS-"),
        entry("UK-W01", "UK-"),
        q("Q117", default="AS-32", gap="UK-W01"),
        q("Q118", depends_on=["Q117"]),
        entry("Q5", "Q", 1, needs=needs()),
        entry("Q6", "Q", 1, resolved_by="A99-P1-INTERVIEW-001"),
    ]
    if unrouted:
        entries.append(entry("Q120", "Q"))
    (where / "A99_Identifiers.json").write_text(
        json.dumps({"app_id": "A99", "entries": entries}, indent=1, sort_keys=True,
                   ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    (where / "A99_Evidence.json").write_text(json.dumps({"app_id": "A99", "items": [
        {"id": "A99-P1-INTERVIEW-001", "evidence_class": "INTERVIEW"}]}), encoding="utf-8")
    (out / "A99_Phase4_Flow_EN.md").write_text(PHASE_DOC, encoding="utf-8")
    return root


def run(monkeypatch: pytest.MonkeyPatch, root: Path, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["build_decisions.py", "--app-root", str(root), *args])
    return build_decisions.main()


def test_it_writes_the_list_beside_the_documents_and_the_queue_beside_the_registers(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path, registers_dir=True)
    assert run(monkeypatch, root) == 0
    assert (root / "output" / "A99_QuestionList.md").is_file()
    assert (root / "output" / "registers" / "A99_DecisionQueue.json").is_file()
    assert not (root / "output" / "A99_DecisionQueue.json").exists()


def test_a_second_run_changes_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    run(monkeypatch, root)
    before = {p.name: p.read_bytes() for p in (root / "output").glob("A99_[QD]*")}
    capsys.readouterr()
    assert run(monkeypatch, root) == 0
    assert "unchanged" in capsys.readouterr().out
    assert {p.name: p.read_bytes() for p in (root / "output").glob("A99_[QD]*")} == before
    assert all(b"\r" not in blob for blob in before.values())


def test_it_will_not_overwrite_a_list_it_did_not_write(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """A05's was written by hand and numbered its questions itself, which is how A12 happened."""
    root = make_workspace(tmp_path)
    handwritten = root / "output" / "A99_QuestionList.md"
    handwritten.write_text("# My own list\n\nQ3: something else entirely\n", encoding="utf-8")
    assert run(monkeypatch, root) == 2
    assert "did not write" in capsys.readouterr().err
    assert handwritten.read_text(encoding="utf-8").startswith("# My own list")
    assert not (root / "output" / "A99_DecisionQueue.json").exists()
    assert run(monkeypatch, root, "--replace-handwritten") == 0
    assert handwritten.read_text(encoding="utf-8").startswith(da.GENERATED)


def test_a_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    assert run(monkeypatch, root, "--dry-run") == 0
    assert not list((root / "output").glob("A99_Q*")) and not list((root / "output").glob("A99_D*"))


def test_one_partys_agenda_prints_to_the_terminal_and_nothing_is_written(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    assert run(monkeypatch, root, "--party", "Warehouse operations") == 0     # an alias is enough
    out = capsys.readouterr().out
    assert "## Agenda: 常温庫" in out and "Q118" in out and "Where things stand" not in out
    assert not (root / "output" / "A99_QuestionList.md").exists()


def test_the_question_text_comes_from_the_document_not_only_the_title(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    run(monkeypatch, root)
    text = (root / "output" / "A99_QuestionList.md").read_text(encoding="utf-8")
    assert "> Which action makes the PDFs?" in text
    assert "**What would settle it:** An operator describing one evening" in text


def test_linking_a_question_to_its_qa_moves_it_to_the_customers_side(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    register = root / "output" / "A99_Identifiers.json"
    assert run(monkeypatch, root, "--link", "Q5=5") == 0
    entries = {e["id"]: e for e in json.loads(register.read_text(encoding="utf-8"))["entries"]}
    assert entries["Q5"]["needs"]["qa"] == [5]
    assert list((root / ".ak" / "backups").glob("A99_Identifiers.*.json"))
    text = (root / "output" / "A99_QuestionList.md").read_text(encoding="utf-8")
    assert "## Already with the customer" in text and "In Progress" in text
    queue = json.loads((root / "output" / "A99_DecisionQueue.json").read_text(encoding="utf-8"))
    assert queue["counts"]["with_customer"] == 1


def test_linking_is_idempotent_and_adds_rather_than_replaces(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    run(monkeypatch, root, "--link", "Q5=5")
    capsys.readouterr()
    run(monkeypatch, root, "--link", "Q5=5")
    assert "already recorded" in capsys.readouterr().out
    run(monkeypatch, root, "--link", "Q5=6")
    entries = {e["id"]: e for e in json.loads(
        (root / "output" / "A99_Identifiers.json").read_text(encoding="utf-8"))["entries"]}
    assert entries["Q5"]["needs"]["qa"] == [5, 6]


def test_a_link_to_a_qa_that_is_not_in_the_register_is_refused_and_writes_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    register = root / "output" / "A99_Identifiers.json"
    before = register.read_bytes()
    assert run(monkeypatch, root, "--link", "Q5=99") == 2
    assert "not in the Q&A register" in capsys.readouterr().err
    assert register.read_bytes() == before


def test_a_link_on_an_item_with_no_needs_is_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path, unrouted=True)
    assert run(monkeypatch, root, "--link", "Q120=5") == 2
    assert "no `needs`" in capsys.readouterr().err


def test_a_malformed_link_is_refused(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    assert run(monkeypatch, root, "--link", "Q5") == 2
    assert run(monkeypatch, root, "--link", "Q5=five") == 2


def test_an_answer_the_register_does_not_know_is_reported_not_applied(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    run(monkeypatch, root, "--link", "Q118=6")
    text = (root / "output" / "A99_QuestionList.md").read_text(encoding="utf-8")
    assert "## Answered by the customer and not yet recorded" in text
    entries = {e["id"]: e for e in json.loads(
        (root / "output" / "A99_Identifiers.json").read_text(encoding="utf-8"))["entries"]}
    assert "resolved_by" not in entries["Q118"]            # recording an answer is a person's act


def test_the_qa_register_is_read_fresh_every_time(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A06's stored record had five rows when the CSV beside it had six."""
    root = make_workspace(tmp_path)
    run(monkeypatch, root)
    assert "Q&A 8" not in (root / "output" / "A99_QuestionList.md").read_text(encoding="utf-8")
    csv_path = root / "input" / "interviews" / "QA-register.csv"
    csv_path.write_text(REGISTER_CSV + "8,Order import format,In Progress,Asker One,,Respondent One,2026/09/17,\n",
                        encoding="utf-8")
    run(monkeypatch, root)
    assert "Q&A 8" in (root / "output" / "A99_QuestionList.md").read_text(encoding="utf-8")


def test_a_register_with_an_unrouted_question_still_writes_and_exits_one(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path, unrouted=True)
    assert run(monkeypatch, root) == 1
    assert "PROBLEM" in capsys.readouterr().out
    assert "Q120 is open and carries no `needs`" in (
        root / "output" / "A99_QuestionList.md").read_text(encoding="utf-8")


def test_a_block_that_resolves_to_nothing_is_a_problem_in_the_run(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """The slice's acceptance line: every `blocks` id resolves, or the run says which does not."""
    root = make_workspace(tmp_path)
    register = root / "output" / "A99_Identifiers.json"
    data = json.loads(register.read_text(encoding="utf-8"))
    for e in data["entries"]:
        if e["id"] == "Q118":
            e["needs"]["blocks"] = ["WF-999"]
    register.write_text(dr.format_register(data), encoding="utf-8", newline="\n")
    assert run(monkeypatch, root) == 1
    out = capsys.readouterr().out
    assert "PROBLEM" in out and "WF-999" in out and "not in the register" in out


def test_the_language_chooses_the_document_the_question_text_is_read_from(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    (root / "output" / "A99_Phase4_Flow_VI.md").write_text(
        PHASE_DOC.replace("Which action makes the PDFs?", "Hành động nào tạo ra các PDF?"),
        encoding="utf-8")
    assert run(monkeypatch, root, "--language", "VI") == 0
    vi = (root / "output" / "A99_QuestionList_VI.md").read_text(encoding="utf-8")
    assert "> Hành động nào tạo ra các PDF?" in vi
    assert not (root / "output" / "A99_QuestionList.md").exists()


# --- the qa field, in the contract ---------------------------------------------------

@pytest.mark.parametrize("qa,ok", [([5], True), ([5, 6], True), (None, True), ([], True),
                                   ([0], False), (["5"], False), ([True], False),
                                   ([5, 5], False), (5, False)])
def test_qa_is_a_list_of_distinct_positive_register_ids(qa: object, ok: bool) -> None:
    e = entry("Q1", "Q", needs=needs(qa=qa))
    found = dq.validate_needs(e, {"Q1", "WF-001"}, None)
    assert (not any("`qa`" in p for p in found)) is ok, found


def test_the_schema_and_the_validator_agree_about_qa() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((PACKAGE / "schemas" / "decision-needs.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    for qa, expected in (([5], True), ([0], False), (["5"], False), ([5, 5], False), (None, True)):
        block = needs(qa=qa)
        by_schema = not list(validator.iter_errors(block))
        by_module = not dq.validate_needs(entry("Q1", "Q", needs=block), {"Q1", "WF-001"}, None)
        assert by_schema == by_module == expected, (qa, by_schema, by_module)


# --- the contract files ------------------------------------------------------------

def test_the_output_contract_lists_the_queue_and_the_template_states_its_reader() -> None:
    import yaml

    contract = yaml.safe_load((PACKAGE / "specifications" / "output-contract.yaml")
                              .read_text(encoding="utf-8"))
    assert "{APP_ID}_DecisionQueue.json" in contract["required_control_outputs"]
    template = (PACKAGE / "templates" / "question-list.md").read_text(encoding="utf-8")
    assert "Who reads it" in template and "$ak decisions" in template
    readme = (PACKAGE / "templates" / "readme.md").read_text(encoding="utf-8")
    assert "_QuestionList.md" in readme and "_DecisionQueue.json" in readme
