"""An answer either holds an assumption or breaks it, and the register says which (A75, errata slice).

A question that has a default proceeds on an assumption (design 4.3). When it is answered the
answer confirms that assumption or contradicts it, and a contradiction is an errata entry whose
`affected` list is what the assumption said would stop holding. Before this slice "If wrong"
was a prose column in four tables: the register recorded the answer and left the assumption
standing as though nothing had been asked, and nothing could produce the list of what to
refresh. A real register's E-01 and E-02 are the case: a published claim stayed in force after the evidence
that ended it, and the refresh list was assembled by a person reading three documents.

Each test is one way that goes wrong.
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

import decision_agenda as da  # noqa: E402
import decision_queue as dq  # noqa: E402
import validate_phase_conformance as checker  # noqa: E402
from test_decision_needs import (  # noqa: E402
    RISK_NEEDS, entry, make_workspace, needs, parties, reviewed, run_backfill, scheme, write_parties)

WRONG = "§6.2 overstates the reach of the `UPDATE`, and RW-02 and WF-001 would not follow; see E-01"


def base(*extra: dict, assumption: dict | None = None) -> list[dict]:
    return [
        entry("WF-001", "WF-"), entry("RW-02", "RW-", severity="HIGH", needs=dict(RISK_NEEDS)),
        {**entry("AS-32", "AS-", 4, if_wrong=WRONG), **(assumption or {})},
        entry("E-01", "E-", 4), *extra,
    ]


def errata(affected: object, eid: str = "E-03") -> list[dict]:
    return [{"id": eid, "affected": affected}]


def problems(entries: list[dict], errata_entries: list[dict] | None = None, phase: int | None = None) -> list[str]:
    return dq.validate_assumptions(entries, errata_entries, phase)


# --- ID-12: an assumption says what breaks if it is wrong ----------------------

def test_an_open_assumption_with_no_if_wrong_is_refused() -> None:
    entries = [entry("AS-32", "AS-", 4)]
    found = problems(entries)
    assert len(found) == 1 and "AS-32" in found[0] and "if_wrong" in found[0]


@pytest.mark.parametrize("blank", ["", "   ", None])
def test_if_wrong_that_says_nothing_is_not_an_answer(blank: object) -> None:
    entries = [entry("AS-32", "AS-", 4, if_wrong=blank)]
    # None is "absent" (reported as such) and the others are present but empty.
    assert problems(entries) and "AS-32" in problems(entries)[0]


def test_a_non_text_if_wrong_is_refused() -> None:
    assert "must be text" in problems([entry("AS-32", "AS-", 4, if_wrong=["RW-02"])])[0]


def test_a_settled_assumption_is_not_asked_for_its_if_wrong() -> None:
    """The closing fields mean the same on every identifier (register.closing): an assumption
    already confirmed or corrected has nothing left to refresh."""
    for closing in ({"resolved_by": "A99-P4-INTERVIEW-001"}, {"superseded_by": "AS-31"}):
        assert problems([entry("AS-32", "AS-", 4, **closing)]) == []


def test_only_the_phase_being_checked_is_held_to_it() -> None:
    entries = [entry("AS-01", "AS-", 2), entry("AS-32", "AS-", 4, if_wrong=WRONG)]
    assert problems(entries, phase=4) == []
    assert "AS-01" in problems(entries, phase=2)[0]


# --- the refresh set ------------------------------------------------------------

def test_the_refresh_set_is_the_identifiers_the_sentence_names() -> None:
    assert dq.refresh_set({"id": "AS-32", "if_wrong": WRONG}) == ["RW-02", "WF-001"]


def test_the_refresh_set_leaves_out_the_assumption_errata_and_columns() -> None:
    """`d31` is a column in a real table and exactly the shape of the `d-` namespace (A52);
    the assumption cannot be what is refreshed because of itself; and an E- is the correction."""
    text = "AS-32 itself, a column `d31`, E-04, and RW-01"
    assert dq.refresh_set({"id": "AS-32", "if_wrong": text}) == ["RW-01"]


def test_an_assumption_with_no_if_wrong_refreshes_nothing() -> None:
    assert dq.refresh_set({"id": "AS-32"}) == []


# --- ID-13: an answer settles the assumption it proceeded on ---------------------

def asked(**over: object) -> dict:
    return entry("Q117", "Q", 4, needs=needs(default="AS-32"), **over)


def test_an_answered_question_leaves_its_assumption_unsettled() -> None:
    entries = base(asked(resolved_by="A99-P4-INTERVIEW-001"))
    found = problems(entries)
    assert len(found) == 1
    assert "AS-32" in found[0] and "Q117" in found[0] and "resolved_by" in found[0]


def test_confirming_the_assumption_settles_it() -> None:
    entries = base(asked(resolved_by="A99-P4-INTERVIEW-001"),
                   assumption={"resolved_by": "A99-P4-INTERVIEW-001"})
    assert problems(entries) == []


def test_a_question_still_open_leaves_the_assumption_standing() -> None:
    assert problems(base(asked())) == []


def test_an_assumption_two_questions_proceed_on_waits_for_both() -> None:
    """Q118 has not been answered, so nothing yet says the assumption held or broke."""
    second = entry("Q118", "Q", 4, needs=needs(default="AS-32"))
    entries = base(asked(resolved_by="A99-P4-INTERVIEW-001"), second)
    assert problems(entries) == []
    second["resolved_by"] = "A99-P4-INTERVIEW-002"
    assert problems(entries)


def test_a_duplicate_question_that_was_only_superseded_does_not_settle_anything() -> None:
    """`superseded_by` says another item asks the same thing. No answer was given."""
    assert problems(base(asked(superseded_by="Q118"))) == []


# --- a contradiction is an errata entry that names the refresh set -----------------

def contradicted(**over: object) -> list[dict]:
    return base(asked(resolved_by="A99-P4-INTERVIEW-001"),
                assumption={"superseded_by": "E-03", **over})


def test_a_contradiction_that_names_everything_it_refreshes_passes() -> None:
    covering = errata(["A99_Phase4_WorkflowReconstruction_{EN,VI}.md RW-02", "WF-001 section 3.2"])
    assert problems(contradicted(), covering) == []


def test_a_correction_that_leaves_out_what_the_assumption_named_is_refused() -> None:
    """The refresh list is the point of recording the contradiction: a correction that names
    one of the two sections leaves the other published, still reading as it did."""
    found = problems(contradicted(), errata(["RW-02 only"]))
    assert len(found) == 1 and "WF-001" in found[0] and "E-03" in found[0]
    assert "RW-02" not in found[0].split("leaves out")[1]


def test_a_correction_may_carry_affected_as_one_string() -> None:
    assert problems(contradicted(), errata("RW-02, WF-001")) == []


def test_a_contradiction_pointing_at_no_errata_entry_is_refused() -> None:
    found = problems(contradicted(), errata(["RW-02 WF-001"], eid="E-09"))
    assert len(found) == 1 and "E-03" in found[0] and "not in the errata register" in found[0]


def test_a_project_without_an_errata_register_is_not_accused_of_an_entry_it_could_not_have() -> None:
    assert problems(contradicted(), None) == []


def test_a_phase_is_not_held_to_a_correction_that_concerns_only_other_phases() -> None:
    early = [{**e, "phase": 2} for e in contradicted()]
    assert problems(early, errata(["RW-02"]), phase=2)       # the phase that owns it is
    assert problems(early, errata(["RW-02"]), phase=4) == []


# --- the register as a whole ------------------------------------------------------

def test_validate_register_carries_the_assumption_rules() -> None:
    entries = base(asked(resolved_by="A99-P4-INTERVIEW-001"))
    found = dq.validate_register(entries, parties(), 4)
    assert any("AS-32" in p and "resolved_by" in p for p in found)
    clean = dq.validate_register(
        base(asked(resolved_by="A99-P4-INTERVIEW-001"), assumption={"resolved_by": "A99-P4-INTERVIEW-001"}),
        parties(), 4)
    assert not any("AS-32" in p for p in clean)


def test_the_conformance_check_reads_the_errata_register(tmp_path: Path) -> None:
    entries = contradicted()
    result = {r["check"]: r for r in checker.apparatus_checks(
        4, "# X", {"identifier_entries": entries, "parties": parties(), "errata_entries": errata(["RW-02"])})}
    assert result["decision_fields_present"]["status"] == "FAIL"
    assert "WF-001" in result["decision_fields_present"]["detail"]
    good = {r["check"]: r for r in checker.apparatus_checks(
        4, "# X", {"identifier_entries": entries, "parties": parties(),
                   "errata_entries": errata(["RW-02", "WF-001"])})}
    assert good["decision_fields_present"]["status"] == "PASS"
    assert "assumption(s)" in good["decision_fields_present"]["detail"]


def test_load_registers_reads_the_errata_entries_beside_the_identifiers(tmp_path: Path) -> None:
    outputs = tmp_path / "A99" / "output"
    outputs.mkdir(parents=True)
    assert "errata_entries" not in checker.load_registers(outputs)
    (outputs / "A99_Errata.json").write_text(
        json.dumps({"app_id": "A99", "entries": [{"id": "E-01", "affected": ["WF-001"]}]}), encoding="utf-8")
    assert checker.load_registers(outputs)["errata_entries"][0]["id"] == "E-01"


# --- the list shows what an answer would refresh ------------------------------------

def queue(extra: list[dict]) -> dict:
    built = da.build_queue(base(*extra), parties(), app_id="A99")
    built["items"] = {item["id"]: item for item in built["items"]}
    return built


def test_an_item_with_a_default_says_what_is_refreshed_if_the_default_is_wrong() -> None:
    item = queue([asked()])["items"]["Q117"]
    default = item["default"]
    assert default["id"] == "AS-32"
    assert default["if_wrong"] == WRONG
    assert default["refresh"] == ["RW-02", "WF-001"]


def test_the_written_list_carries_that_sentence_and_the_refresh_set() -> None:
    markdown = da.render_markdown(da.build_queue(base(asked()), parties(), app_id="A99"),
                                  parties=parties(), texts={}, source="A99_Identifiers.json")
    assert "**If that is wrong:**" in markdown
    assert "(refresh: RW-02, WF-001)" in markdown
    assert "§6.2 overstates the reach of the `UPDATE`" in markdown


def test_an_assumption_without_if_wrong_adds_no_line_and_no_crash() -> None:
    lone = [entry("WF-001", "WF-"), entry("AS-32", "AS-", 4),
            entry("Q117", "Q", 4, needs=needs(default="AS-32"))]
    markdown = da.render_markdown(da.build_queue(lone, parties(), app_id="A99"), parties=parties(),
                                  texts={}, source="x")
    assert "If that is wrong" not in markdown and "Proceeding on" in markdown


# --- the backfill copies the sentence the document already holds ---------------------

def test_the_proposal_copies_if_wrong_from_the_assumptions_table(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    write_parties(root)
    assert run_backfill(monkeypatch, root) == 0
    proposal = yaml.safe_load((root / "input" / "decisions" / "needs-proposal.yaml").read_text(encoding="utf-8"))
    assert proposal["if_wrong"] == {"AS-32": "the overwrite lands elsewhere"}


def test_a_missing_row_is_left_for_a_person_rather_than_invented(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    write_parties(root)
    doc = root / "output" / "A99_Phase4_WorkflowReconstruction_EN.md"
    doc.write_text(doc.read_text(encoding="utf-8").replace(
        "| AS-32 | The imported day is in the table | the overwrite lands elsewhere |\n", ""), encoding="utf-8")
    assert run_backfill(monkeypatch, root) == 0
    proposal = yaml.safe_load((root / "input" / "decisions" / "needs-proposal.yaml").read_text(encoding="utf-8"))
    assert proposal["if_wrong"] == {"AS-32": "UNDECIDED"}
    reviewed(root)
    assert run_backfill(monkeypatch, root, "--apply") == 1       # UNDECIDED holds the apply


def test_apply_writes_if_wrong_and_the_register_then_passes(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    write_parties(root)
    run_backfill(monkeypatch, root)
    reviewed(root)
    assert run_backfill(monkeypatch, root, "--apply") == 0
    after = json.loads((root / "output" / "A99_Identifiers.json").read_text(encoding="utf-8"))
    assert {e["id"]: e for e in after["entries"]}["AS-32"]["if_wrong"] == "the overwrite lands elsewhere"
    assert dq.validate_register(after["entries"], dq.load_parties(
        root / "input" / "decisions" / "parties.yaml")) == []


def test_apply_keeps_an_if_wrong_a_person_already_wrote(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    write_parties(root)
    register_file = root / "output" / "A99_Identifiers.json"
    data = json.loads(register_file.read_text(encoding="utf-8"))
    for e in data["entries"]:
        if e["id"] == "AS-32":
            e["if_wrong"] = "written by hand"
    register_file.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    run_backfill(monkeypatch, root)
    proposal = yaml.safe_load((root / "input" / "decisions" / "needs-proposal.yaml").read_text(encoding="utf-8"))
    assert proposal["if_wrong"] is None or "AS-32" not in proposal["if_wrong"]
    reviewed(root)
    assert run_backfill(monkeypatch, root, "--apply") == 0
    after = json.loads(register_file.read_text(encoding="utf-8"))
    assert {e["id"]: e for e in after["entries"]}["AS-32"]["if_wrong"] == "written by hand"


def test_apply_refuses_an_if_wrong_on_something_that_is_not_an_assumption(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    write_parties(root)
    run_backfill(monkeypatch, root)
    reviewed(root)
    path = root / "input" / "decisions" / "needs-proposal.yaml"
    proposal = yaml.safe_load(path.read_text(encoding="utf-8"))
    proposal["if_wrong"]["WF-001"] = "nothing"
    path.write_text(yaml.safe_dump(proposal, allow_unicode=True, sort_keys=False), encoding="utf-8")
    before = (root / "output" / "A99_Identifiers.json").read_bytes()
    assert run_backfill(monkeypatch, root, "--apply") == 1
    assert "assumption" in capsys.readouterr().out
    assert (root / "output" / "A99_Identifiers.json").read_bytes() == before


# --- the contract stated in three places ----------------------------------------------

def test_the_scheme_states_the_rules_and_the_field() -> None:
    declared = scheme()
    assert dq.IF_WRONG in declared["register"]["fields"]
    assert {"ID-12", "ID-13"} <= {r["id"] for r in declared["rules"]}
    assert "if_wrong" in " ".join(declared["namespaces"]["AS"].get("requires", [])) or \
        "wrong" in " ".join(declared["namespaces"]["AS"].get("requires", []))
