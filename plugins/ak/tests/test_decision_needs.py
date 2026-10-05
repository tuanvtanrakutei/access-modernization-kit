"""The `needs` block, the parties it names, and the tables that must agree with it (A75).

Measured on A06 before any of this existed: 39 open Q and UK entries were about two dozen
distinct asks, twelve spellings stood for four parties, and the register knew none of it
because owner, blocks and default were prose in four tables. Q120 shows the cost. When it
was marked answered its row was rewritten in place: the Blocks column now holds the
original question, the Owner column an evidence id, the real owner is gone, and the
register still lists it as open. Q106 and UK-S03 are the same shape.

Every test here is one of those defects, or a guard that holds a contract stated in two
places together (the yaml, the schema and the module) - the drift A74 found when a class
existed in the yaml and the schema rejected the very item it was created for.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import backfill_needs  # noqa: E402
import decision_queue as dq  # noqa: E402
import validate_phase_conformance as checker  # noqa: E402

MARKERS = ("answered", "resolved", "superseded", "withdrawn")


# --- builders ----------------------------------------------------------------

def entry(eid: str, namespace: str, phase: int = 4, **extra: object) -> dict:
    return {"id": eid, "namespace": namespace, "phase": phase, "title": "t",
            "evidence_ids": [], **extra}


def needs(**over: object) -> dict:
    base: dict = {"kind": "FACT", "party": "常温庫", "blocks": ["WF-001"], "default": None}
    base.update(over)
    return base


RISK_NEEDS = {"kind": "DISPOSITION", "party": "decider", "blocks": [], "default": "mitigation",
              "class": "behaviour"}


def register(*extra: dict) -> list[dict]:
    return [
        entry("WF-001", "WF-"), entry("BR-ORD-10", "BR-", 3),
        entry("AS-32", "AS-", if_wrong="the overwrite lands elsewhere and RW-02 would not follow"),
        entry("UK-W01", "UK-"), entry("RW-02", "RW-", severity="HIGH", needs=dict(RISK_NEEDS)),
        *extra,
    ]


def parties() -> dq.Parties:
    return dq.Parties.from_mapping({"parties": {
        "常温庫": {"aliases": ["Warehouse operations"], "people": ["Person One"]},
        "システム課": {},
    }})


def problems(block: dict, namespace: str = "Q", eid: str = "Q117",
             with_parties: bool = False, **entry_extra: object) -> list[str]:
    e = entry(eid, namespace, needs=block, **entry_extra)
    ids = {x["id"] for x in register(e)}
    return dq.validate_needs(e, ids, parties() if with_parties else None)


# --- parties: twelve spellings, four parties --------------------------------

def test_one_department_under_two_spellings_is_one_party() -> None:
    """A06 writes the same department as `常温庫` (9 cells), 'Warehouse operations' (10)
    and `常温庫 / システム課` (3). An agenda keyed by the raw cell would be twelve agendas."""
    p = parties()
    assert p.resolve("Warehouse operations") == (["常温庫"], [])
    assert p.resolve("`常温庫`") == (["常温庫"], [])
    assert p.resolve("warehouse operations") == (["常温庫"], [])


def test_a_joint_owner_cell_resolves_to_each_party() -> None:
    assert parties().resolve("`常温庫` / `システム課`") == (["常温庫", "システム課"], [])


def test_a_spelling_that_is_no_party_is_reported_and_never_guessed() -> None:
    resolved, unresolved = parties().resolve("Master-data owner")
    assert resolved == [] and unresolved == ["Master-data owner"]


def test_a_dash_is_no_party_and_no_error() -> None:
    assert parties().resolve("—") == ([], [])
    assert parties().resolve("") == ([], [])


def test_the_decider_needs_no_declaration() -> None:
    assert dq.Parties.from_mapping({"parties": {}}).is_canonical(dq.DECIDER)
    assert dq.Parties.from_mapping(None).is_canonical(dq.DECIDER)


def test_one_spelling_cannot_name_two_parties() -> None:
    bad = dq.Parties.from_mapping({"parties": {"A": {"aliases": ["x"]}, "B": {"aliases": ["X"]}}})
    assert any("one spelling, one party" in p for p in bad.problems)


def test_a_misspelt_party_field_is_refused() -> None:
    """`alias:` for `aliases:` would be a field that does nothing and looks like one that works."""
    bad = dq.Parties.from_mapping({"parties": {"A": {"alias": ["x"]}}})
    assert any("unknown field" in p for p in bad.problems)


def test_a_person_is_listed_under_one_party_only() -> None:
    bad = dq.Parties.from_mapping({"parties": {"A": {"people": ["P"]}, "B": {"people": ["p"]}}})
    assert any("listed under both" in p for p in bad.problems)


def test_a_missing_parties_file_is_none_and_a_broken_one_says_so(tmp_path: Path) -> None:
    assert dq.load_parties(tmp_path / "parties.yaml") is None
    broken = tmp_path / "parties.yaml"
    broken.write_text("parties: [unclosed", encoding="utf-8")
    loaded = dq.load_parties(broken)
    assert loaded is not None and loaded.problems


# --- the block itself --------------------------------------------------------

def test_a_sound_block_has_no_problems() -> None:
    assert problems(needs(default="AS-32", gap="UK-W01", depends_on=["BR-ORD-10"])) == []


def test_a_misspelt_field_is_refused_rather_than_ignored() -> None:
    found = problems(needs(block=["WF-001"]))
    assert any("unknown `needs` field" in p and "block" in p for p in found)


def test_kind_party_and_blocks_are_required() -> None:
    found = problems({})
    text = " ".join(found)
    assert "`kind` must be one of" in text and "`party` is required" in text
    assert "`blocks` is empty" in text


def test_a_question_that_blocks_nothing_has_no_reason_to_be_asked() -> None:
    assert any("`blocks` is empty" in p for p in problems(needs(blocks=[])))


def test_a_policy_may_block_nothing_because_it_settles_a_class() -> None:
    assert problems(needs(kind="POLICY", party="decider", blocks=[]), with_parties=True) == []


def test_blocks_resolve_or_are_object_references() -> None:
    assert any("is not in the register" in p for p in problems(needs(blocks=["WF-099"])))
    assert any("neither an identifier" in p for p in problems(needs(blocks=["the whole thing"])))
    assert problems(needs(blocks=["object:商品情報", "WF-001"])) == []
    assert any("empty `object:`" in p for p in problems(needs(blocks=["object:  "])))


def test_a_question_cannot_block_itself() -> None:
    assert any("blocks itself" in p for p in problems(needs(blocks=["Q117"])))


def test_a_default_is_an_assumption_that_exists() -> None:
    assert any("must be an AS-" in p for p in problems(needs(default="Q117")))
    assert any("is not in the register" in p for p in problems(needs(default="AS-99")))


def test_mitigation_is_a_default_only_for_a_risk_disposition() -> None:
    risk = needs(kind="DISPOSITION", party="decider", default="mitigation", **{"class": "behaviour"})
    assert problems(risk, namespace="RW-", eid="RW-02", with_parties=True) == []
    assert any("belongs on a DISPOSITION anchored" in p
               for p in problems(needs(default="mitigation")))


def test_gap_is_a_unknown_and_belongs_to_a_question() -> None:
    assert any("must be a UK-" in p for p in problems(needs(gap="AS-32")))
    assert any("is not in the register" in p for p in problems(needs(gap="UK-W09")))
    assert any("belongs on a Q" in p
               for p in problems(needs(gap="UK-W01"), namespace="RW-", eid="RW-02"))


def test_class_belongs_to_risks_and_is_one_of_four() -> None:
    assert any("`class` is for risks" in p for p in problems(needs(**{"class": "data"})))
    assert any("must be one of" in p for p in problems(
        needs(**{"class": "typo"}), namespace="RW-", eid="RW-02"))
    assert problems(needs(kind="DISPOSITION", party="decider", **{"class": "technical"}),
                    namespace="RW-", eid="RW-02", with_parties=True) == []


def test_a_decision_about_the_new_system_belongs_to_the_decider() -> None:
    found = problems(needs(kind="DISPOSITION"), with_parties=True)
    assert any("decider's to settle" in p for p in found)
    assert problems(needs(kind="DISPOSITION", party="decider"), with_parties=True) == []


def test_the_register_keeps_the_canonical_name_not_an_alias() -> None:
    found = problems(needs(party="Warehouse operations"), with_parties=True)
    assert any("alias of '常温庫'" in p for p in found)


def test_an_unknown_party_is_refused() -> None:
    assert any("not in parties.yaml" in p
               for p in problems(needs(party="Master-data owner"), with_parties=True))


def test_also_names_parties_and_not_the_party_itself() -> None:
    assert problems(needs(also=["システム課"]), with_parties=True) == []
    assert any("not a party" in p for p in problems(needs(also=["nobody"]), with_parties=True))
    assert any("repeats the party" in p for p in problems(needs(also=["常温庫"]), with_parties=True))


def test_a_named_person_must_be_listed_under_a_party() -> None:
    assert problems(needs(named=["Person One"]), with_parties=True) == []
    assert any("listed under no party" in p
               for p in problems(needs(named=["Person Two"]), with_parties=True))


def test_depends_on_may_not_name_itself_or_a_stranger() -> None:
    assert any("depends on itself" in p for p in problems(needs(depends_on=["Q117"])))
    assert any("is not in the register" in p for p in problems(needs(depends_on=["Q999"])))


def test_options_are_two_or_more_choices_of_a_decision() -> None:
    ok = needs(kind="DISPOSITION", party="decider", options=["preserve", "fix"])
    assert problems(ok, with_parties=True) == []
    one = needs(kind="DISPOSITION", party="decider", options=["fix"])
    assert any("at least two" in p for p in problems(one, with_parties=True))
    assert any("choices of a DISPOSITION" in p for p in problems(needs(options=["a", "b"])))


# --- the register: ID-07 and ID-09 -------------------------------------------

def test_an_open_question_with_no_needs_is_refused() -> None:
    entries = register(entry("Q117", "Q"))
    found = dq.validate_register(entries, parties(), 4)
    assert any("Q117: an open question with no `needs`" in p for p in found)


def test_a_closed_question_needs_no_block() -> None:
    entries = [entry("Q6", "Q", resolved_by="A99-P1-INTERVIEW-001"),
               entry("Q108", "Q", superseded_by="Q103")]
    assert dq.validate_register(entries, parties(), 4) == []


def test_an_unknown_that_a_question_asks_about_needs_no_block_of_its_own() -> None:
    """Q and UK are one decision recorded twice on purpose: the gap and the action."""
    asked = register(entry("Q117", "Q", needs=needs(gap="UK-W01")))
    assert dq.validate_register(asked, parties(), 4) == []
    alone = register()
    found = dq.validate_register(alone, parties(), 4)
    assert any("UK-W01: an open unknown that no Q asks about" in p for p in found)


def test_an_unknown_nobody_asks_may_carry_its_own_block() -> None:
    own = [e if e["id"] != "UK-W01" else {**e, "needs": needs()} for e in register()]
    assert dq.validate_register(own, parties(), 4) == []


def test_only_the_phases_own_allocations_are_judged() -> None:
    entries = register(entry("Q5", "Q", 1))
    assert not any("Q5" in p for p in dq.validate_register(entries, parties(), 4))
    assert any("Q5" in p for p in dq.validate_register(entries, parties(), 1))


def test_a_dependency_loop_is_reported() -> None:
    entries = register(
        entry("Q117", "Q", needs=needs(depends_on=["Q118"])),
        entry("Q118", "Q", needs=needs(depends_on=["Q117"])))
    found = dq.validate_register(entries, parties(), 4)
    assert any("depends_on cycle" in p and "Q117" in p and "Q118" in p for p in found)


def test_a_chain_is_not_a_loop() -> None:
    entries = register(
        entry("Q117", "Q", needs=needs(depends_on=["Q118"])),
        entry("Q118", "Q", needs=needs(depends_on=["Q119"])),
        entry("Q119", "Q", needs=needs()))
    assert not any("cycle" in p for p in dq.validate_register(entries, parties(), 4))


# --- the document side -------------------------------------------------------

Q_HEAD = "| ID | Question | Blocks | Party | Default |\n|---|---|---|---|---|\n"
OLD_Q_HEAD = "| ID | Question | Blocks | Owner |\n|---|---|---|---|\n"
UK_HEAD = ("| ID | Unknown | Why it matters | What would settle it | Party | Asked as |\n"
           "|---|---|---|---|---|---|\n")


def compare(text: str, entries: list[dict], p: dq.Parties | None = None,
            phase: int = 4) -> dq.Comparison:
    return dq.compare_document(text, phase, entries, p if p is not None else parties(), MARKERS)


def test_an_escaped_pipe_is_text_and_an_unescaped_one_is_a_column() -> None:
    cells = dq.split_row(r"| Q1 | one \| two | WF-001 | 常温庫 |")
    assert cells == ["Q1", "one | two", "WF-001", "常温庫"]
    assert len(dq.split_row("| Q1 | one | two | WF-001 | 常温庫 |")) == 5


def test_a_row_of_the_wrong_width_is_reported_not_misread() -> None:
    """Positional parsing is only safe for a row the header's width. A pipe in prose makes
    the cells after it belong to the wrong columns, so the row is named, not compared."""
    text = "### Questions\n\n" + OLD_Q_HEAD + "| Q117 | which | date | is it | WF-001 | 常温庫 |\n"
    result = compare(text, register(entry("Q117", "Q", needs=needs())))
    assert any("6 cells under a 4-column header" in f and "`\\|`" in f for f in result.findings)


def test_a_risk_id_inside_the_first_cell_is_still_its_id() -> None:
    """A06's Phase 1 writes `| RD-01 — Missing primary keys | HIGH | ...`: no ID column,
    the identifier inside the first cell. Seven risks with no identifier to a parser."""
    assert dq.leading_identifier("RD-01 — Missing primary keys") == "RD-01"
    assert dq.leading_identifier("**Q116**") == "Q116"
    assert dq.leading_identifier("`BR-ORD-10` rule") == "BR-ORD-10"
    assert dq.leading_identifier("[A06-P4-CODE-003]") is None
    table = ("## 7. Risks\n\n| Risk | Severity | Consequence | Mitigation |\n|---|---|---|---|\n"
             "| RD-01 — Missing primary keys | HIGH | duplicates | Profile first |\n")
    rows = dq.tables(table)[0].rows
    assert rows[0].identifier == "RD-01" and rows[0].wellformed


def test_comments_and_fences_are_not_tables() -> None:
    """A template's guidance carries example tables; a checker that read them would report
    the template's rows as the document's."""
    text = ("<!-- example\n| ID | Question | Blocks | Party |\n|---|---|---|---|\n"
            "| Q1 | x | y | z |\n-->\n```\n| a | b |\n|---|---|\n| c | d |\n```\n")
    assert dq.tables(text) == []


def test_the_carried_forward_table_is_not_read_as_a_questions_table() -> None:
    """It opens with earlier phases' identifiers and has another shape. Reading it as a
    Questions table would report the carrying as a contradiction."""
    text = ("### Carried forward from earlier phases\n\n"
            "| ID | Raised in | Status | What this phase establishes |\n|---|---|---|---|\n"
            "| Q103 | Phase 1 | unchanged | nothing bears on it |\n")
    entries = register(entry("Q103", "Q", 1, needs=needs(party="システム課")))
    result = compare(text, entries)
    assert result.findings == [] and result.compared == 0


def test_the_same_department_under_another_spelling_agrees() -> None:
    text = "### Questions\n\n" + Q_HEAD + "| Q117 | which date | WF-001 | Warehouse operations | — |\n"
    result = compare(text, register(entry("Q117", "Q", needs=needs())))
    assert result.findings == [] and result.compared == 1


def test_a_party_that_differs_between_document_and_register_is_reported() -> None:
    text = "### Questions\n\n" + Q_HEAD + "| Q117 | which date | WF-001 | `システム課` | — |\n"
    result = compare(text, register(entry("Q117", "Q", needs=needs())))
    assert any("party: the document says ['システム課']" in f for f in result.findings)


def test_an_evidence_id_in_the_party_column_is_not_a_party() -> None:
    """Q120's Owner column. Its original cells were overwritten when it was answered."""
    text = ("### Questions\n\n" + OLD_Q_HEAD +
            "| Q120 | **Answered — E-11.** Original question: | Who uses it? | [A06-P4-CODE-003] |\n")
    entries = register(entry("Q120", "Q", resolved_by="A06-P4-CODE-003", needs=needs()))
    result = compare(text, entries)
    assert any("A06-P4-CODE-003" in f and "does not know" in f for f in result.findings)


def test_blocks_that_differ_are_reported_when_the_cell_names_identifiers() -> None:
    text = "### Questions\n\n" + Q_HEAD + "| Q117 | which date | WF-001, BR-ORD-10 | 常温庫 | — |\n"
    result = compare(text, register(entry("Q117", "Q", needs=needs())))
    assert any("only in the document ['BR-ORD-10']" in f for f in result.findings)


def test_a_prose_blocks_cell_is_counted_not_compared() -> None:
    """A06's Q117 reads 'Reproducing the day boundary - the `参考日` half of this is Q115'.
    Q115 is mentioned, not blocked, and a register that is right must not be contradicted
    by a sentence."""
    text = ("### Questions\n\n" + OLD_Q_HEAD +
            "| Q117 | which date | Reproducing the day boundary — the `参考日` half of this is Q115 | `常温庫` |\n")
    result = compare(text, register(entry("Q117", "Q", needs=needs())))
    assert result.findings == [] and result.unstructured == 1


def test_a_dash_in_blocks_is_a_statement_and_not_prose() -> None:
    assert dq.cell_blocks("—") == set()
    text = "### Questions\n\n" + Q_HEAD + "| Q117 | which date | — | 常温庫 | — |\n"
    result = compare(text, register(entry("Q117", "Q", needs=needs())))
    assert any("only in the register ['WF-001']" in f for f in result.findings)


def test_the_default_column_must_agree() -> None:
    text = "### Questions\n\n" + Q_HEAD + "| Q117 | which date | WF-001 | 常温庫 | AS-32 |\n"
    ok = compare(text, register(entry("Q117", "Q", needs=needs(default="AS-32"))))
    assert ok.findings == []
    bad = compare(text, register(entry("Q117", "Q", needs=needs())))
    assert any("default: the document says AS-32" in f for f in bad.findings)


def test_a_row_marked_answered_while_the_register_is_open_is_reported() -> None:
    """Q120, Q106 and UK-S03 on A06: the document knew, the register did not."""
    text = ("### Questions\n\n" + OLD_Q_HEAD +
            "| Q120 | **Answered — E-11, and it should never have been asked.** | x | y |\n")
    result = compare(text, register(entry("Q120", "Q")))
    assert any("marked closed in the document and is open in the register" in f
               for f in result.findings)


def test_the_same_row_passes_once_the_register_agrees() -> None:
    text = ("### Questions\n\n" + OLD_Q_HEAD +
            "| Q120 | **Answered — E-11.** | x | y |\n")
    assert compare(text, register(entry("Q120", "Q", resolved_by="A99-P4-CODE-003"))).findings == []
    assert compare(text, register(entry("Q120", "Q", superseded_by="Q103"))).findings == []


def test_withdrawn_is_closed_and_raised_by_is_not() -> None:
    """Q106 was 'Withdrawn ... without being asked'; Q121 was 'Raised by E-11', which says
    where it came from, not where it ended."""
    withdrawn = ("### Questions\n\n" + OLD_Q_HEAD +
                 "| Q106 | **Withdrawn 2026-09-15 without being asked — E-10.** | — | — |\n")
    assert compare(withdrawn, register(entry("Q106", "Q"))).findings
    raised = "### Questions\n\n" + OLD_Q_HEAD + "| Q121 | **Raised by E-11.** The monthly run | x | y |\n"
    assert compare(raised, register(entry("Q121", "Q"))).findings == []


def test_closure_phrases_exist_for_every_output_language() -> None:
    """A49: a gate that reads one language reports a conformant document in another as
    non-conformant. The Vietnamese A06 documents say 'Đã trả lời' and 'Rút lại'."""
    for language in ("EN", "JA", "VI"):
        assert checker.signals_for("closed_item", Path(f"A99_Phase4_{language}.md")), language
    vi = checker.signals_for("closed_item", Path("A99_Phase4_WorkflowReconstruction_VI.md"))
    assert any("Rút lại".casefold().startswith(m) or m in "rút lại" for m in vi)
    assert dq.starts_closed("**Đã trả lời — E-11.**", vi)
    assert dq.starts_closed("**Rút lại 2026-09-15 mà không hỏi — E-10.**", vi)


def test_columns_are_read_by_position_so_a_vietnamese_table_is_the_same_table() -> None:
    text = ("### Câu hỏi\n\n| ID | Câu hỏi | Chặn cái gì | Chủ sở hữu |\n|---|---|---|---|\n"
            "| Q117 | Ngày nào? | WF-001, BR-ORD-10 | `常温庫` |\n")
    result = compare(text, register(entry("Q117", "Q", needs=needs())))
    assert any("only in the document ['BR-ORD-10']" in f for f in result.findings)


def test_asked_as_must_agree_with_the_gap_links() -> None:
    asked = register(entry("Q117", "Q", needs=needs(gap="UK-W01")))
    text = "### Unknowns\n\n" + UK_HEAD + "| UK-W01 | which date | why | settle | 常温庫 | Q117 |\n"
    assert compare(text, asked).findings == []
    unasked = compare(text, register())
    assert any("asked as: the document says ['Q117']" in f for f in unasked.findings)


def test_an_unknown_with_its_own_block_is_compared_on_party() -> None:
    own = [e if e["id"] != "UK-W01" else {**e, "needs": needs(party="システム課")} for e in register()]
    text = "### Unknowns\n\n" + UK_HEAD + "| UK-W01 | which date | why | settle | 常温庫 | — |\n"
    assert any("party: the document says" in f for f in compare(text, own).findings)


# --- the conformance checks ---------------------------------------------------

def names(results: list[dict]) -> set[str]:
    return {r["check"] for r in results}


def test_neither_check_runs_without_a_register() -> None:
    assert not {"decision_fields_present", "decision_tables_agree"} & names(
        checker.apparatus_checks(1, "# X", {}))


def test_an_open_question_with_no_needs_fails_the_apparatus_check() -> None:
    registers = {"identifier_entries": register(entry("Q117", "Q")), "parties": parties()}
    result = next(r for r in checker.apparatus_checks(4, "# X", registers)
                  if r["check"] == "decision_fields_present")
    assert result["status"] == "FAIL" and "Q117" in result["detail"]


def test_a_routable_question_passes_both_checks() -> None:
    entries = register(entry("Q117", "Q", needs=needs(gap="UK-W01", default="AS-32")))
    text = "### Questions\n\n" + Q_HEAD + "| Q117 | which date | WF-001 | 常温庫 | AS-32 |\n"
    results = checker.apparatus_checks(4, text, {"identifier_entries": entries, "parties": parties()})
    by_name = {r["check"]: r for r in results}
    assert by_name["decision_fields_present"]["status"] == "PASS", by_name["decision_fields_present"]
    assert by_name["decision_tables_agree"]["status"] == "PASS", by_name["decision_tables_agree"]


def test_no_parties_file_is_reported_not_skipped() -> None:
    """A project that predates the file is not one that wrote it wrong, but the check must
    say it could not check, rather than pass for want of anything to compare against."""
    entries = register(entry("Q117", "Q", needs=needs()))
    result = next(r for r in checker.apparatus_checks(4, "# X", {"identifier_entries": entries})
                  if r["check"] == "decision_fields_present")
    assert result["status"] == "FAIL" and "parties.yaml" in result["detail"]


def test_a_phase_with_no_questions_is_not_accused() -> None:
    result = next(r for r in checker.apparatus_checks(
        2, "# X", {"identifier_entries": [entry("F-001", "F-", 2)], "parties": parties()})
        if r["check"] == "decision_fields_present")
    assert result["status"] == "PASS" and "no question, unknown, risk or assumption" in result["detail"]


def test_prose_cells_are_visible_in_the_result() -> None:
    entries = register(entry("Q117", "Q", needs=needs()))
    text = ("### Questions\n\n" + OLD_Q_HEAD +
            "| Q117 | which date | Reproducing the day boundary | `常温庫` |\n")
    result = next(r for r in checker.apparatus_checks(
        4, text, {"identifier_entries": entries, "parties": parties()})
        if r["check"] == "decision_tables_agree")
    assert result["status"] == "PASS" and "1 cell(s) are prose" in result["detail"]


def test_load_registers_reads_parties_beside_the_outputs(tmp_path: Path) -> None:
    outputs = tmp_path / "A99" / "output"
    outputs.mkdir(parents=True)
    assert checker.load_registers(outputs)["parties"] is None
    decisions = tmp_path / "A99" / "input" / "decisions"
    decisions.mkdir(parents=True)
    (decisions / "parties.yaml").write_text(
        "parties:\n  常温庫:\n    aliases: [Warehouse operations]\n", encoding="utf-8")
    loaded = checker.load_registers(outputs)["parties"]
    assert loaded is not None and loaded.resolve("Warehouse operations")[0] == ["常温庫"]


# --- the contract stated in three places -------------------------------------

def scheme() -> dict:
    return yaml.safe_load((PACKAGE / "specifications" / "identifier-scheme.yaml")
                          .read_text(encoding="utf-8"))


def test_the_scheme_and_the_module_state_one_contract() -> None:
    declared = scheme()["register"]["needs"]
    assert tuple(declared["fields"]) == dq.NEEDS_KEYS
    assert tuple(declared["kinds"]) == dq.KINDS
    assert tuple(declared["risk_classes"]) == dq.RISK_CLASSES
    assert "needs" in scheme()["register"]["fields"]
    assert {"ID-07", "ID-08", "ID-09", "ID-10"} <= {r["id"] for r in scheme()["rules"]}


def test_the_finder_accepts_every_example_the_scheme_gives() -> None:
    """A13: a finder stated apart from the scheme drifts from it. Every namespace example,
    including the workflow-scoped BR form, must be found whole and judged well formed."""
    for name, body in scheme()["namespaces"].items():
        for key in ("example", "example_workflow_scoped"):
            example = (body or {}).get(key)
            if example:
                assert dq.find_identifiers(example) == [example], (name, example)
                assert dq.is_identifier(example), (name, example)


def test_a_column_named_like_an_identifier_is_not_one() -> None:
    """A52: `d31` is a real column and exactly the shape of the `d-` namespace."""
    assert dq.find_identifiers("sums `d1+d2+...+d31` for WF-001") == ["WF-001"]


def test_the_schema_file_and_the_validator_agree_on_structure() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((PACKAGE / "schemas" / "decision-needs.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    cases = [
        (True, "Q", needs()),
        (True, "Q", needs(default="AS-32", gap="UK-W01", depends_on=["BR-ORD-10"])),
        (True, "Q", needs(kind="POLICY", party="decider", blocks=[])),
        (True, "RW-", needs(kind="DISPOSITION", party="decider", default="mitigation",
                            options=["preserve", "fix"], **{"class": "behaviour"})),
        (False, "Q", needs(block=["WF-001"])),
        (False, "Q", {"kind": "FACT", "blocks": ["WF-001"]}),
        (False, "Q", needs(kind="ASK")),
        (False, "Q", needs(blocks=[])),
        (False, "Q", needs(default="Q117")),
        (False, "Q", needs(gap="UK-1")),
        (False, "RW-", needs(**{"class": "typo"})),
        (False, "RW-", needs(kind="DISPOSITION", party="decider", options=["fix"])),
        (False, "Q", needs(blocks="WF-001")),
    ]
    for expected, namespace, block in cases:
        eid = "RW-02" if namespace == "RW-" else "Q117"
        by_schema = not list(validator.iter_errors(block))
        by_module = not dq.validate_needs(
            entry(eid, namespace, needs=block), {x["id"] for x in register()} | {eid}, None)
        assert by_schema == by_module == expected, (block, by_schema, by_module)


# --- the templates -----------------------------------------------------------

@pytest.mark.parametrize("name", [
    "phase1-data-understanding.md", "phase2-screen-analysis.md", "phase3-logic-processing.md",
    "phase4-workflow-reconstruction.md", "phase5-document-integration.md"])
def test_every_phase_template_carries_the_decision_columns(name: str) -> None:
    text = (PACKAGE / "templates" / name).read_text(encoding="utf-8")
    assert "| ID | Question | Blocks | Party | Default |" in text
    assert "| ID | Unknown | Why it matters | What would settle it | Party | Asked as |" in text
    assert "| ID | Question | Blocks | Owner |" not in text
    assert "Who can settle it" not in text
    # The instructions name the failure that made them necessary, not a general principle.
    assert "resolved_by" in text and "**Answered - <evidence id>**" in text
    assert "Write \\| for a pipe" in text


def test_the_template_tables_parse_as_the_tables_the_checker_reads() -> None:
    for path in sorted((PACKAGE / "templates").glob("phase[1-5]-*.md")):
        found = {tuple(t.header) for t in dq.tables(path.read_text(encoding="utf-8"))}
        assert ("ID", "Question", "Blocks", "Party", "Default") in found, path.name
        assert ("ID", "Unknown", "Why it matters", "What would settle it", "Party", "Asked as") in found, path.name


# --- the backfill ------------------------------------------------------------

PHASE_DOC = """# A99 - Phase 4

### Assumptions

| ID | Assumption | If wrong |
|---|---|---|
| AS-32 | The imported day is in the table | the overwrite lands elsewhere |

### Unknowns

| ID | Unknown | Why it matters | What would settle it | Who can settle it |
|---|---|---|---|---|
| UK-W01 | Which date is entered? | the two must agree | an operator | Warehouse operations |

### Questions

| ID | Question | Blocks | Owner |
|---|---|---|---|
| Q117 | Which date is entered on the evening build? | WF-001, BR-ORD-10 | `常温庫` |
| Q118 | Which action produces the two PDFs? | The trace | Warehouse operations |
| Q120 | **Answered — E-11, and it should never have been asked.** Original question: | Who uses it? | [A99-P4-CODE-003] |
"""


def make_workspace(tmp_path: Path) -> Path:
    root = tmp_path / "A99"
    (root / "input" / "decisions").mkdir(parents=True)
    out = root / "output"
    out.mkdir()
    entries = [
        entry("WF-001", "WF-"), entry("BR-ORD-10", "BR-", 3), entry("AS-32", "AS-"),
        entry("UK-W01", "UK-"), entry("Q117", "Q"), entry("Q118", "Q"), entry("Q120", "Q"),
    ]
    text = json.dumps({"app_id": "A99", "entries": entries}, indent=1, sort_keys=True,
                      ensure_ascii=False) + "\n"
    (out / "A99_Identifiers.json").write_text(text, encoding="utf-8", newline="\n")
    (out / "A99_Evidence.json").write_text(
        json.dumps({"app_id": "A99", "items": [{"id": "A99-P4-CODE-003"}]}), encoding="utf-8")
    (out / "A99_Phase4_WorkflowReconstruction_EN.md").write_text(PHASE_DOC, encoding="utf-8")
    return root


def run_backfill(monkeypatch: pytest.MonkeyPatch, root: Path, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["backfill_needs.py", "--app-root", str(root), *args])
    return backfill_needs.main()


def write_parties(root: Path) -> None:
    (root / "input" / "decisions" / "parties.yaml").write_text(
        "parties:\n  常温庫:\n    aliases: [Warehouse operations]\n", encoding="utf-8")


def test_the_first_run_drafts_parties_and_stops(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    assert run_backfill(monkeypatch, root) == 0
    draft = (root / "input" / "decisions" / "parties.yaml").read_text(encoding="utf-8")
    assert "Warehouse operations" in draft and "常温庫" in draft
    # Merging spellings is a decision, so the draft lists each one separately...
    assert draft.count("aliases: []") == 2
    # ...and a row the document calls closed does not contribute its overwritten Owner cell.
    assert "A99-P4-CODE-003" not in draft
    assert not (root / "input" / "decisions" / "needs-proposal.yaml").exists()
    assert "Merge the spellings" in capsys.readouterr().out


def test_the_proposal_derives_what_it_can_and_marks_the_rest_undecided(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    write_parties(root)
    assert run_backfill(monkeypatch, root) == 0
    text = (root / "input" / "decisions" / "needs-proposal.yaml").read_text(encoding="utf-8")
    proposal = yaml.safe_load(text)
    q117 = proposal["needs"]["Q117"]
    assert q117["party"] == "常温庫" and q117["blocks"] == ["BR-ORD-10", "WF-001"]
    assert q117["default"] == "UNDECIDED"
    assert proposal["needs"]["Q118"]["blocks"] == "UNDECIDED"      # 'The trace' is prose
    assert proposal["needs"]["UK-W01"]["party"] == "常温庫"          # via the alias
    assert "Q120" not in proposal["needs"] and proposal["close"]["Q120"] == "UNDECIDED"
    assert "A99-P4-CODE-003" in text                                  # offered as a hint


def test_a_proposal_that_may_hold_edits_is_not_overwritten(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    write_parties(root)
    assert run_backfill(monkeypatch, root) == 0
    assert run_backfill(monkeypatch, root) == 2
    assert "may hold edits" in capsys.readouterr().err
    assert run_backfill(monkeypatch, root, "--force") == 0


def test_apply_refuses_a_proposal_that_still_says_undecided(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    write_parties(root)
    before = (root / "output" / "A99_Identifiers.json").read_bytes()
    run_backfill(monkeypatch, root)
    assert run_backfill(monkeypatch, root, "--apply") == 1
    assert "UNDECIDED" in capsys.readouterr().out
    assert (root / "output" / "A99_Identifiers.json").read_bytes() == before


def reviewed(root: Path) -> None:
    path = root / "input" / "decisions" / "needs-proposal.yaml"
    proposal = yaml.safe_load(path.read_text(encoding="utf-8"))
    proposal["needs"]["Q117"].update(default="AS-32", gap="UK-W01")
    proposal["needs"]["Q118"].update(blocks=["object:商品情報入力表"], default=None)
    del proposal["needs"]["UK-W01"]            # asked by Q117, so it needs no block of its own
    proposal["close"]["Q120"] = "A99-P4-CODE-003"
    path.write_text(yaml.safe_dump(proposal, allow_unicode=True, sort_keys=False), encoding="utf-8")


def test_a_reviewed_proposal_is_written_in_the_registers_own_format(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    write_parties(root)
    register_file = root / "output" / "A99_Identifiers.json"
    before = json.loads(register_file.read_text(encoding="utf-8"))
    run_backfill(monkeypatch, root)
    reviewed(root)
    assert run_backfill(monkeypatch, root, "--apply") == 0

    raw = register_file.read_bytes()
    after = json.loads(raw.decode("utf-8"))
    assert raw.endswith(b"\n") and b"\r" not in raw
    assert json.dumps(after, indent=1, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n" == raw

    old = {e["id"]: e for e in before["entries"]}
    new = {e["id"]: e for e in after["entries"]}
    assert set(old) == set(new)
    assert new["Q117"]["needs"]["gap"] == "UK-W01" and new["Q120"]["resolved_by"] == "A99-P4-CODE-003"
    # Nothing but the needs blocks, the closure and the assumption's `if_wrong` changed.
    changed = ("needs", "resolved_by", "if_wrong")
    for eid in old:
        stripped = {k: v for k, v in new[eid].items() if k not in changed}
        assert stripped == {k: v for k, v in old[eid].items() if k not in changed}
    assert new["AS-32"]["if_wrong"] == "the overwrite lands elsewhere"
    assert list((root / ".ak" / "backups").glob("A99_Identifiers.*.json"))
    assert (root / "input" / "decisions" / "needs-proposal.applied.yaml").is_file()
    assert not (root / "input" / "decisions" / "needs-proposal.yaml").exists()
    assert dq.validate_register(after["entries"], dq.load_parties(
        root / "input" / "decisions" / "parties.yaml")) == []


def test_apply_will_not_close_an_item_with_evidence_that_does_not_exist(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    write_parties(root)
    run_backfill(monkeypatch, root)
    reviewed(root)
    path = root / "input" / "decisions" / "needs-proposal.yaml"
    proposal = yaml.safe_load(path.read_text(encoding="utf-8"))
    proposal["close"]["Q120"] = "A99-P4-CODE-404"
    path.write_text(yaml.safe_dump(proposal, allow_unicode=True, sort_keys=False), encoding="utf-8")
    assert run_backfill(monkeypatch, root, "--apply") == 1
    assert "not in the evidence register" in capsys.readouterr().out


def test_apply_will_not_leave_an_open_question_without_a_block(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """All or nothing: a backfill that left Q118 uncovered would leave the register in the
    state ID-07 forbids."""
    root = make_workspace(tmp_path)
    write_parties(root)
    run_backfill(monkeypatch, root)
    reviewed(root)
    path = root / "input" / "decisions" / "needs-proposal.yaml"
    proposal = yaml.safe_load(path.read_text(encoding="utf-8"))
    del proposal["needs"]["Q118"]
    path.write_text(yaml.safe_dump(proposal, allow_unicode=True, sort_keys=False), encoding="utf-8")
    before = (root / "output" / "A99_Identifiers.json").read_bytes()
    assert run_backfill(monkeypatch, root, "--apply") == 1
    assert "Q118: an open question with no `needs`" in capsys.readouterr().out
    assert (root / "output" / "A99_Identifiers.json").read_bytes() == before


def test_apply_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    write_parties(root)
    run_backfill(monkeypatch, root)
    reviewed(root)
    before = (root / "output" / "A99_Identifiers.json").read_bytes()
    assert run_backfill(monkeypatch, root, "--apply", "--dry-run") == 0
    assert (root / "output" / "A99_Identifiers.json").read_bytes() == before
    assert (root / "input" / "decisions" / "needs-proposal.yaml").is_file()


def test_the_backfilled_register_passes_the_conformance_checks(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The point of the whole slice: an old workspace, backfilled, is routable."""
    root = make_workspace(tmp_path)
    write_parties(root)
    outputs = root / "output"
    document = (outputs / "A99_Phase4_WorkflowReconstruction_EN.md").read_text(encoding="utf-8")

    before = checker.apparatus_checks(4, document, checker.load_registers(outputs))
    assert {r["check"]: r["status"] for r in before}["decision_fields_present"] == "FAIL"

    run_backfill(monkeypatch, root)
    reviewed(root)
    assert run_backfill(monkeypatch, root, "--apply") == 0
    after = {r["check"]: r for r in checker.apparatus_checks(
        4, document, checker.load_registers(outputs), outputs / "A99_Phase4_WorkflowReconstruction_EN.md")}
    assert after["decision_fields_present"]["status"] == "PASS", after["decision_fields_present"]
    assert after["decision_tables_agree"]["status"] == "PASS", after["decision_tables_agree"]
    # Q117 and Q118 carry a block and are compared. Q120 is closed and needs none. Q118's
    # Blocks cell is the prose "The trace", which is counted rather than compared.
    detail = after["decision_tables_agree"]["detail"]
    assert detail.startswith("2 row(s) compared") and "1 cell(s) are prose" in detail


# --- the register's own key ----------------------------------------------------

def test_a_register_that_keeps_its_rows_under_items_is_read_as_entries(tmp_path: Path) -> None:
    """A05's register predates the rename. `backfill-needs` stopped on it with KeyError."""
    import decision_register as dr

    path = tmp_path / "A05_Identifiers.json"
    path.write_text(json.dumps({"app_id": "A05", "items": [{"id": "Q1", "namespace": "Q"}]}),
                    encoding="utf-8")
    register = dr.read_identifiers(path)
    assert register["entries"] == [{"id": "Q1", "namespace": "Q"}]
    assert "items" not in register


def test_a_register_under_entries_is_read_unchanged(tmp_path: Path) -> None:
    import decision_register as dr

    path = tmp_path / "A06_Identifiers.json"
    body = {"app_id": "A06", "entries": [{"id": "Q1", "namespace": "Q"}]}
    path.write_text(json.dumps(body), encoding="utf-8")
    assert dr.read_identifiers(path) == body


def test_a_namespace_written_without_its_dash_is_read_with_it(tmp_path: Path) -> None:
    """A05 writes `UK` for `UK-L01`. Every unknown and risk fell out of the proposal."""
    import decision_register as dr

    path = tmp_path / "A05_Identifiers.json"
    rows = [{"id": "UK-L01", "namespace": "UK"}, {"id": "RA-02", "namespace": "RA"},
            {"id": "Q1", "namespace": "Q"}, {"id": "A05-P3-FORMAT-015", "namespace": "A05-P3-FORMAT"}]
    path.write_text(json.dumps({"app_id": "A05", "items": rows}), encoding="utf-8")
    spaces = [e["namespace"] for e in dr.read_identifiers(path)["entries"]]
    assert spaces == ["UK-", "RA-", "Q", "A05-P3-FORMAT"]
