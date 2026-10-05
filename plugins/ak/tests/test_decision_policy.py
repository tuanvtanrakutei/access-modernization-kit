"""Risks, standing policy and the decider's batch (A75, slice 3).

Every risk a phase writes carries a Mitigation, and for a legacy defect that is a recommended
answer: what the replacement should do about it. One project had 25, and nobody had been asked to
accept any of them; the register knew each one's severity and nothing else. The first run of
this slice on a copy of that project found the rest of what is tested here: a risk's row names no object
it would block, the Phase 1 table has no ID column, RA-02 names a question that was superseded
and another that was answered, and the marker that strips "Raised by E-11" from a question
also stripped "E-05: confirmed - do not carry it forward" from RA-10's Mitigation, which is the
part that says what to do.

Every test is a rule the maintainer approved with the design (a policy settles a class and the
item is still listed; behaviour defects are asked with the Mitigation as the default; an answer
is evidence, never queue text), or a defect that run showed.
"""
from __future__ import annotations

import io
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
import build_decisions  # noqa: E402
import decision_agenda as da  # noqa: E402
import decision_batch as batch  # noqa: E402
import decision_queue as dq  # noqa: E402
import decision_register as dr  # noqa: E402
import validate_phase_conformance as checker  # noqa: E402


# --- builders ----------------------------------------------------------------

def entry(eid: str, namespace: str, phase: int = 4, title: str | None = None, **extra: object) -> dict:
    return {"id": eid, "namespace": namespace, "phase": phase, "title": title or f"{eid} title",
            "evidence_ids": [], **extra}


def risk(eid: str, klass: str = "behaviour", severity: str = "HIGH", **over: object) -> dict:
    needs = {"kind": "DISPOSITION", "party": "decider", "blocks": [], "default": "mitigation",
             "class": klass}
    needs.update(over)
    namespace = eid[:3]
    return entry(eid, namespace, severity=severity, needs=needs)


def question(eid: str, **over: object) -> dict:
    needs = {"kind": "FACT", "party": "Operations", "blocks": ["WF-001"], "default": None}
    needs.update(over)
    return entry(eid, "Q", needs=needs)


def policy(*rules: dict) -> dq.Policy:
    return dq.Policy.from_mapping({"policy": list(rules)})


def rule(pid: str, klass: str, disposition: str, decided: bool = True) -> dict:
    return {"id": pid, "class": klass, "disposition": disposition,
            "decided_by": "Person One" if decided else None,
            "decided_on": "2026-10-02" if decided else None}


def base() -> list[dict]:
    return [entry("WF-001", "WF-", title="the morning import")]


def items(queue: dict) -> dict[str, dict]:
    return {i["id"]: i for i in queue["items"]}


# --- a risk is a disposition ---------------------------------------------------

def problems_of(e: dict, *others: dict) -> list[str]:
    ids = {x["id"] for x in [*base(), e, *others]}
    return dq.validate_needs(e, ids, dq.Parties.from_mapping({"parties": {}}))


def test_a_risk_is_a_disposition_and_names_its_class() -> None:
    assert problems_of(risk("RW-01")) == []
    as_fact = risk("RW-01", kind="FACT")
    assert any("its `kind` is DISPOSITION" in p for p in problems_of(as_fact))
    unclassed = risk("RW-01")
    unclassed["needs"].pop("class")
    assert any("names its `class`" in p for p in problems_of(unclassed))


def test_a_risk_on_its_own_mitigation_need_block_nothing_else_and_nothing_else_may() -> None:
    """That project's 25 risk rows name no object between them. What waits on a risk's disposition is
    the risk's own Mitigation, so `blocks` may be empty there and nowhere else."""
    assert problems_of(risk("RA-01")) == []
    no_default = risk("RA-01", default=None)
    assert any("`blocks` is empty" in p for p in problems_of(no_default))
    unknown = entry("UK-D05", "UK-", needs={"kind": "DISPOSITION", "party": "decider", "blocks": []})
    assert any("`blocks` is empty" in p for p in problems_of(unknown))


def test_a_disposition_chooses_among_the_four_and_nothing_else() -> None:
    assert problems_of(risk("RW-01", options=["fix", "preserve"])) == []
    assert any("chooses among" in p for p in problems_of(risk("RW-01", options=["fix", "keep"])))


def test_an_open_risk_with_no_needs_is_refused_and_a_closed_one_is_not() -> None:
    entries = [entry("RW-01", "RW-", severity="HIGH"),
               entry("RW-02", "RW-", severity="HIGH", resolved_by="A99-P4-TARGET-003")]
    found = dq.validate_register(entries, dq.Parties.from_mapping({}), 4)
    assert any(p.startswith("RW-01: an open risk with no `needs`") for p in found)
    assert not any(p.startswith("RW-02") for p in found)


def test_the_conformance_check_counts_the_risks_it_holds() -> None:
    registers = {"identifier_entries": [risk("RW-01"), entry("WF-001", "WF-")],
                 "parties": dq.Parties.from_mapping({})}
    results = checker.apparatus_checks(4, "# X", registers)
    found = next(r for r in results if r["check"] == "decision_fields_present")
    assert found["status"] == "PASS" and "1 risk(s)" in found["detail"]
    registers["identifier_entries"] = [entry("RW-01", "RW-", severity="HIGH")]
    found = next(r for r in checker.apparatus_checks(4, "# X", registers)
                 if r["check"] == "decision_fields_present")
    assert found["status"] == "FAIL" and "RW-01" in found["detail"]


# --- the document side --------------------------------------------------------

def test_a_risk_row_is_read_by_where_its_identifier_is() -> None:
    template = ["RW-01", "Overwrites hand entry", "HIGH", "No date predicate", "Restrict the update"]
    assert dq.risk_cells(template, "RW-01") == {
        "title": "Overwrites hand entry", "severity": "HIGH", "detail": "No date predicate",
        "mitigation": "Restrict the update"}
    with_evidence = ["**RA-01**", "Built names", "HIGH", "Nothing found", "Make it explicit", "[E]"]
    assert dq.risk_cells(with_evidence, "RA-01")["mitigation"] == "Make it explicit"
    # A real Phase 1, in English and in Vietnamese: no ID column, everything one to the left.
    phase1 = ["RD-05 — `準備数` lost during recovery (**E-02**)", "CAO", "Lost", "Give it a path"]
    assert dq.risk_cells(phase1, "RD-05") == {
        "title": "`準備数` lost during recovery (**E-02**)", "severity": "CAO",
        "detail": "Lost", "mitigation": "Give it a path"}
    assert dq.risk_cells(["RD-05 — short", "HIGH", "x"], "RD-05") is None


def test_none_proposed_is_no_mitigation_to_proceed_on() -> None:
    assert dq.has_mitigation("Restrict the update")
    assert not dq.has_mitigation("none proposed") and not dq.has_mitigation("—")


def test_a_mitigation_keeps_the_marker_that_says_what_to_do() -> None:
    """RA-10's Mitigation opens with the correction that decided it. The cleaner a question
    goes through removes that marker, and the default then read as a bare quotation."""
    cell = ("**E-05: confirmed — do not carry it forward.** The client answered *no floppies* "
            "[A99-P4-INTERVIEW-002]")
    assert da.clean_mitigation(cell) == ("E-05: confirmed — do not carry it forward. "
                                         "The client answered *no floppies*")
    assert "do not carry" not in da._clean(cell)          # what a question's text gets


# --- standing policy -----------------------------------------------------------

def test_a_rule_that_names_nobody_settles_nothing_and_says_what_it_would() -> None:
    queue = da.build_queue(base() + [risk("RD-01", "technical")],
                           policy=policy(rule("P-1", "technical", "fix", decided=False)))
    item = items(queue)["RD-01"]
    assert item["bucket"] == "proceeding" and item["settled_by"] is None
    assert item["would_settle"] == "P-1"
    assert queue["counts"]["settled_by_policy"] == 0
    assert queue["counts"]["settled_once_policy_decided"] == 1
    text = da.render_markdown(queue)
    assert "P-1 would settle it, once someone decides that policy" in text
    assert "proposed: settles nothing until" in text


def test_a_decided_rule_settles_its_class_and_the_item_is_still_listed() -> None:
    """Policy can hide decisions (design, section 11). It may not: a settled item leaves the
    agenda and is listed under the rule that settled it."""
    entries = base() + [risk("RD-01", "technical"), risk("RW-01", "behaviour")]
    queue = da.build_queue(entries, policy=policy(rule("P-1", "technical", "fix")))
    rd01 = items(queue)["RD-01"]
    assert (rd01["bucket"], rd01["settled_by"], rd01["disposition"]) == ("settled", "P-1", "fix")
    agenda = queue["agendas"]["decider"]
    assert agenda["settled"] == ["RD-01"] and "RD-01" not in agenda["proceeding"]
    counts = queue["counts"]
    assert counts["settled_by_policy"] == 1 and counts["open"] == 1 and counts["to_ask_now"] == 1
    text = da.render_markdown(queue)
    assert "### Settled by standing policy, not asked" in text
    assert "- RD-01 RD-01 title — P-1 (technical): fix" in text
    assert "| settled by standing policy, listed and not asked | 1 |" in text
    assert "| P-1 | technical | fix | decided by Person One on 2026-10-02 | RD-01 |" in text
    assert "#### 1. RW-01" in text


def test_ask_puts_each_item_of_its_class_to_the_decider() -> None:
    queue = da.build_queue(base() + [risk("RW-01", "behaviour")],
                           policy=policy(rule("P-4", "behaviour", "ask")))
    assert items(queue)["RW-01"]["bucket"] == "proceeding"
    assert items(queue)["RW-01"]["would_settle"] is None
    assert "each item is put to the decider" in da.render_markdown(queue)


def test_a_broken_policy_settles_nothing_and_says_so() -> None:
    broken = policy(rule("P-1", "technical", "fix"), rule("P-2", "technical", "drop"))
    assert any("two rules for one class contradict" in p for p in broken.problems)
    queue = da.build_queue(base() + [risk("RD-01", "technical")], policy=broken)
    assert items(queue)["RD-01"]["bucket"] == "proceeding"
    assert any("no policy settles anything" in p for p in queue["problems"])


@pytest.mark.parametrize("body, expected", [
    ({"id": "P-1", "class": "technical", "disposition": "fix", "decided": "x"}, "unknown field"),
    ({"id": "R-1", "class": "technical", "disposition": "fix"}, "a policy id is P-<n>"),
    ({"id": "P-1", "class": "typo", "disposition": "fix"}, "`class` must be one of"),
    ({"id": "P-1", "class": "data", "disposition": "migrate"}, "`disposition` must be one of"),
    ({"id": "P-1", "class": "data", "disposition": "fix", "decided_by": "Person One"}, "go together"),
    ({"id": "P-1", "class": "data", "disposition": "fix", "decided_by": "Person One",
      "decided_on": "yesterday"}, "is a date"),
])
def test_a_rule_is_refused_rather_than_half_read(body: dict, expected: str) -> None:
    assert any(expected in p for p in dq.Policy.from_mapping({"policy": [body]}).problems)


def test_an_unquoted_yaml_date_is_a_date() -> None:
    loaded = dq.Policy.from_mapping(yaml.safe_load(
        "policy:\n  - id: P-1\n    class: data\n    disposition: fix\n"
        "    decided_by: Person One\n    decided_on: 2026-10-02\n"))
    assert loaded.problems == [] and dq.Policy.in_force(loaded.entries[0])


def test_a_rule_outside_an_items_own_choices_does_not_settle_it() -> None:
    queue = da.build_queue(base() + [risk("RA-10", "retired", options=["fix", "preserve"])],
                           policy=policy(rule("P-2", "retired", "drop")))
    assert items(queue)["RA-10"]["bucket"] == "proceeding"


def test_fix_does_not_settle_a_risk_with_no_mitigation_to_do() -> None:
    """`fix` means doing what the Mitigation says. A row that proposed none leaves nothing to
    do, so the rule passes it by and the decider is asked."""
    bare = risk("RW-03", "technical", default=None, blocks=["WF-001"])
    queue = da.build_queue(base() + [bare], policy=policy(rule("P-1", "technical", "fix")))
    assert items(queue)["RW-03"]["bucket"] == "blocking"
    dropped = da.build_queue(base() + [risk("RA-10", "retired", default=None, blocks=["WF-001"])],
                             policy=policy(rule("P-2", "retired", "drop")))
    assert items(dropped)["RA-10"]["settled_by"] == "P-2"


def test_what_waits_on_a_settled_risk_waits_for_nothing() -> None:
    entries = base() + [risk("RA-07", "technical"),
                        risk("RW-02", "behaviour", depends_on=["RA-07"])]
    queue = da.build_queue(entries, policy=policy(rule("P-1", "technical", "fix")))
    assert items(queue)["RW-02"]["waiting_on"] == [] and items(queue)["RW-02"]["bucket"] == "proceeding"
    unsettled = da.build_queue(entries)
    assert items(unsettled)["RW-02"]["bucket"] == "waiting"
    # Settled, and what the fix contains still waits on the question its Mitigation names.
    behind = base() + [question("Q112"), risk("RA-07", "technical", depends_on=["Q112"])]
    text = da.render_markdown(da.build_queue(behind, policy=policy(rule("P-1", "technical", "fix"))))
    assert "— P-1 (technical): fix; what it does still waits on Q112" in text


def test_a_risks_own_severity_ranks_it() -> None:
    """A risk's disposition names nothing, so ranking by what it names put every risk level."""
    entries = base() + [risk("RA-01", severity="LOW"), risk("RA-02", severity="HIGH"),
                        risk("RA-03", severity="MEDIUM")]
    assert [i["id"] for i in da.build_queue(entries)["items"]] == ["RA-02", "RA-03", "RA-01"]


def test_the_list_shows_the_mitigation_it_proceeds_on() -> None:
    queue = da.build_queue(base() + [risk("RW-01")])
    texts = {"RW-01": {"why": "Hand entry is lost", "mitigation": "Restrict the update [A99-P4-CODE-001]"}}
    text = da.render_markdown(queue, texts=texts)
    assert "- **Proceeding on its Mitigation:** Restrict the update" in text
    assert "- **Why it matters:** Hand entry is lost" in text
    assert "- **Choices:** fix (the default) / preserve / drop / defer" in text
    assert "**Severity:** HIGH · **Class:** behaviour" in text


# --- the decider's batch -------------------------------------------------------

def batch_queue() -> dict:
    entries = base() + [
        entry("UK-D05", "UK-", needs={"kind": "DISPOSITION", "party": "decider", "blocks": ["WF-001"]}),
        risk("RW-01", severity="HIGH"), risk("RW-04", severity="MEDIUM"),
        risk("RD-01", "technical"),
        question("Q119"), risk("RW-02", depends_on=["Q119"]),
    ]
    return da.build_queue(entries, policy=policy(rule("P-1", "technical", "fix")))


def test_the_batch_is_what_the_decider_can_decide_now() -> None:
    queue = batch_queue()
    assert [i["id"] for i in batch.listed(queue)] == ["UK-D05", "RW-01", "RW-04"]
    # Settled by policy, or waiting behind Q119: not listed, still answerable by id.
    assert set(batch.decidable(queue)) == {"UK-D05", "RW-01", "RW-04", "RD-01", "RW-02"}


def test_ok_accepts_every_default_and_passes_over_an_item_with_none() -> None:
    queue = batch_queue()
    assert batch.parse("ok", batch.listed(queue), batch.decidable(queue)) == {
        "RW-01": "fix", "RW-04": "fix"}


def test_a_number_overrides_one_and_an_id_reaches_one_not_listed() -> None:
    queue = batch_queue()
    shown, known = batch.listed(queue), batch.decidable(queue)
    assert batch.parse("ok 3=preserve", shown, known) == {"RW-01": "fix", "RW-04": "preserve"}
    assert batch.parse("1=defer RD-01=preserve RW-02=ok", shown, known) == {
        "UK-D05": "defer", "RD-01": "preserve", "RW-02": "fix"}
    assert batch.parse("", shown, known) == {}


@pytest.mark.parametrize("line, expected", [
    ("4=fix", "there is no item 4"),
    ("2=keep", "chooses among"),
    ("1=ok", "has no default"),
    ("Q119=fix", "not an open disposition"),
    ("yes", "answer `ok`"),
    ("2=fix 2=drop", "answered twice"),
])
def test_an_answer_that_cannot_be_recorded_is_refused(line: str, expected: str) -> None:
    queue = batch_queue()
    with pytest.raises(batch.AnswerProblem, match=expected):
        batch.parse(line, batch.listed(queue), batch.decidable(queue))


def test_the_class_serial_continues_across_phases() -> None:
    """One register numbers per class: TARGET-001 is Phase 1's and TARGET-002 Phase 4's."""
    existing = [{"id": "A99-P1-TARGET-001"}, {"id": "A99-P4-TARGET-002"}, {"id": "A99-P4-CODE-009"}]
    assert batch.next_serial(existing, "A99") == 3
    assert batch.next_serial([], "A99") == 1


def made_items(decisions: dict[str, str], existing: list[dict] | None = None) -> list[dict]:
    queue = batch_queue()
    texts = {"RW-01": {"mitigation": "Restrict the update"}}
    record = batch.record_markdown("A99", decisions, items(queue), texts, decided_by="Person One",
                                   decided_on="2026-10-02", answers="ok")
    return batch.evidence_items(
        "A99", decisions, items(queue), texts, existing or [{"id": "A99-P4-TARGET-002"}],
        decided_by="Person One", decided_on="2026-10-02", created_at="2026-10-02T10:00:00+07:00",
        phase=4, run_id="2026-09-14-0000", record_path="input/target-intent/A99_Decisions_2026-10-02.md",
        record_text=record)


def test_each_answer_is_an_evidence_item_the_schema_accepts() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((PACKAGE / "schemas" / "evidence.schema.json").read_text(encoding="utf-8"))
    made = made_items({"RW-01": "fix", "RW-04": "preserve"})
    jsonschema.validate({"app_id": "A99", "generated_at": "2026-10-02T00:00:00+07:00", "items": made},
                        schema)
    assert [m["id"] for m in made] == ["A99-P4-TARGET-003", "A99-P4-TARGET-004"]
    first = made[0]
    assert first["evidence_class"] == "TARGET_INTENT" and first["claim_kind"] == "SCOPE"
    assert first["attribution"] == {"person": "Person One", "recorded_on": "2026-10-02",
                                    "role": "decider", "question_id": "RW-01"}
    assert first["statement"] == ("Disposition of RW-01: fix. "
                                  "Do what its Mitigation says: Restrict the update.")
    assert made[1]["statement"].startswith("Disposition of RW-04: preserve. Keep the legacy")


def test_the_queue_reads_back_only_what_the_writer_wrote() -> None:
    made = made_items({"RW-04": "drop"})
    assert dq.recorded_disposition(made[0]) == "drop"
    assert dq.recorded_disposition({"statement": "The scope transcription names ..."}) is None


# --- the command --------------------------------------------------------------

PHASE4 = """# A99 - Phase 4

### Risks

| ID | Risk | Severity | Detail | Mitigation |
|---|---|---|---|---|
| RW-01 | A second build overwrites hand entry | HIGH | No date predicate | Restrict the update to the date being built [A99-P4-CODE-001] |
| RW-02 | The history records the seed | HIGH | Overwritten first | Do not migrate that column as history until Q119 says who reads it |
| RW-03 | The only recovery is manual | HIGH | Three thousand rows | none proposed |
| RW-04 | 参考日 is not validated | MEDIUM | Defaults to nothing | Validate it |

### Questions

| ID | Question | Blocks | Party | Default |
|---|---|---|---|---|
| Q118 | Which action makes the PDFs? | WF-001 | Operations | — |
| Q119 | Does anything read the history? | RW-02 | Operations | — |
"""

PHASE1 = """# A99 - Phase 1

### Risks

| Risk | Severity | Consequence at migration | Mitigation |
|---|---|---|---|
| RD-01 — Missing primary keys | HIGH | Duplicates surface | Profile before loading |
"""


def make_workspace(tmp_path: Path, *, with_needs: bool = True) -> Path:
    root = tmp_path / "A99"
    (root / "input" / "decisions").mkdir(parents=True)
    (root / "input" / "decisions" / "parties.yaml").write_text(
        "parties:\n  Operations:\n    aliases: [Warehouse operations]\n", encoding="utf-8")
    out = root / "output"
    out.mkdir()
    risks = [risk("RW-01"), risk("RW-02", depends_on=["Q119"]), risk("RW-04", severity="MEDIUM"),
             risk("RW-03", default=None, blocks=["WF-001"]),
             {**risk("RD-01", "technical"), "phase": 1}]
    if not with_needs:
        risks = [{k: v for k, v in r.items() if k != "needs"} for r in risks]
    entries = [entry("WF-001", "WF-", title="the morning import"), *risks,
               question("Q118"), question("Q119", blocks=["RW-02"]),
               entry("Q108", "Q", superseded_by="Q119"), entry("UK-S04", "UK-", resolved_by="A99-P4-CODE-001")]
    (out / "A99_Identifiers.json").write_text(dr.format_register({"app_id": "A99", "entries": entries}),
                                              encoding="utf-8", newline="\n")
    (out / "A99_Evidence.json").write_text(dr.format_register({
        "app_id": "A99", "generated_at": "2026-09-15T00:00:00+07:00", "items": [
            {"id": "A99-P4-CODE-001", "evidence_class": "CODE", "run_id": "2026-09-14-0000"},
            {"id": "A99-P1-TARGET-001", "evidence_class": "TARGET_INTENT", "run_id": "2026-09-14-0000"}]}),
        encoding="utf-8", newline="\n")
    (out / "A99_Phase4_Flow_EN.md").write_text(PHASE4, encoding="utf-8")
    (out / "A99_Phase1_Data_EN.md").write_text(PHASE1, encoding="utf-8")
    return root


def run(monkeypatch: pytest.MonkeyPatch, root: Path, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["build_decisions.py", "--app-root", str(root), *args])
    return build_decisions.main()


DECIDE = ("--decide", "--by", "Person One", "--on", "2026-10-02")


def registers(root: Path) -> tuple[dict, dict]:
    out = root / "output"
    return ({e["id"]: e for e in json.loads((out / "A99_Identifiers.json").read_text(encoding="utf-8"))["entries"]},
            json.loads((out / "A99_Evidence.json").read_text(encoding="utf-8")))


def test_a_batch_records_who_decided_and_closes_each_item_against_its_evidence(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    assert run(monkeypatch, root, *DECIDE, "--answers", "ok 2=preserve") == 0
    out = capsys.readouterr().out
    # Listed: RD-01 (HIGH, phase 1), RW-01 (HIGH), RW-04. RW-03 has no default and blocks;
    # RW-02 waits behind Q119.
    assert "1. RW-03 [HIGH]" in out and "(no default: answer it by number)" in out
    record = root / "input" / "target-intent" / "A99_Decisions_2026-10-02.md"
    text = record.read_text(encoding="utf-8")
    assert "| Decided by | Person One (decider) |" in text and "| Decided on | 2026-10-02 |" in text
    assert "`ok 2=preserve`" in text
    entries, evidence = registers(root)
    made = [i for i in evidence["items"] if i["evidence_class"] == "TARGET_INTENT" and i["id"] != "A99-P1-TARGET-001"]
    decided = {i["attribution"]["question_id"]: dq.recorded_disposition(i) for i in made}
    # Listed 1 RW-03, 2 RD-01, 3 RW-01, 4 RW-04: blocking first, then HIGH before MEDIUM.
    assert decided == {"RD-01": "preserve", "RW-01": "fix", "RW-04": "fix"}
    assert all(i["source_path"] == "input/target-intent/A99_Decisions_2026-10-02.md" for i in made)
    assert [i["id"] for i in made] == ["A99-P4-TARGET-002", "A99-P4-TARGET-003", "A99-P4-TARGET-004"]
    for item in made:
        assert entries[item["attribution"]["question_id"]]["resolved_by"] == item["id"]
    assert entries["RW-03"].get("resolved_by") is None and entries["RW-02"].get("resolved_by") is None
    backups = root / ".ak" / "backups"
    assert list(backups.glob("A99_Evidence.*.json")) and list(backups.glob("A99_Identifiers.*.json"))
    listing = (root / "output" / "A99_QuestionList.md").read_text(encoding="utf-8")
    assert "3 by a decision" in listing
    assert ": preserve | TARGET_INTENT |" in listing


def test_the_evidence_register_still_validates_after_a_batch(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("jsonschema")
    root = make_workspace(tmp_path)
    run(monkeypatch, root, *DECIDE, "--answers", "ok")
    _entries, evidence = registers(root)
    made = [i for i in evidence["items"] if i.get("task_id") == "decisions"]
    assert len(made) == 3 and build_decisions._schema_problems(made) == []


def test_a_wrong_answer_writes_nothing(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    before = {p.name: p.read_bytes() for p in (root / "output").glob("A99_*.json")}
    assert run(monkeypatch, root, *DECIDE, "--answers", "ok 2=keep") == 2
    assert "nothing recorded" in capsys.readouterr().err
    assert {p.name: p.read_bytes() for p in (root / "output").glob("A99_*.json")} == before
    assert not (root / "input" / "target-intent").exists()


def test_an_evidence_item_the_schema_refuses_is_never_appended(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    """The evidence register is append-only, so a malformed item is refused before anything
    is written - the record, the evidence and the register together."""
    pytest.importorskip("jsonschema")
    root = make_workspace(tmp_path)
    before = {p.name: p.read_bytes() for p in (root / "output").glob("A99_*.json")}
    made = batch.evidence_items

    def malformed(*args: object, **kwargs: object) -> list[dict]:
        return [{**item, "status": "GUESSED"} for item in made(*args, **kwargs)]

    monkeypatch.setattr(batch, "evidence_items", malformed)
    assert run(monkeypatch, root, *DECIDE, "--answers", "ok") == 2
    assert "would not validate" in capsys.readouterr().err
    assert {p.name: p.read_bytes() for p in (root / "output").glob("A99_*.json")} == before
    assert not (root / "input" / "target-intent").exists()


def test_a_decision_names_who_made_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    assert run(monkeypatch, root, "--decide", "--answers", "ok") == 2
    assert "--by NAME" in capsys.readouterr().err
    (root / "input" / "decisions" / "parties.yaml").write_text(
        "parties:\n  Operations: {}\n  decider:\n    people: [Person Two]\n", encoding="utf-8")
    assert run(monkeypatch, root, *DECIDE, "--answers", "ok") == 2
    assert "not one of the decider's people" in capsys.readouterr().err
    assert run(monkeypatch, root, "--decide", "--by", "Person Two", "--on", "2 Oct", "--answers", "ok") == 2
    assert "--on wants a date" in capsys.readouterr().err


def test_a_dry_run_decides_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                   capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    before = {p.name: p.read_bytes() for p in (root / "output").glob("A99_*.json")}
    assert run(monkeypatch, root, *DECIDE, "--answers", "ok", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "would close: RD-01 -> A99-P4-TARGET-002" in out
    assert {p.name: p.read_bytes() for p in (root / "output").glob("A99_*.json")} == before
    assert not (root / "input" / "target-intent").exists()


def test_the_answers_are_read_from_the_terminal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                                capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    monkeypatch.setattr(sys, "stdin", io.StringIO("RW-04=drop\n"))
    assert run(monkeypatch, root, *DECIDE) == 0
    entries, _evidence = registers(root)
    assert entries["RW-04"]["resolved_by"] == "A99-P4-TARGET-002"
    assert entries["RW-01"].get("resolved_by") is None
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    capsys.readouterr()
    assert run(monkeypatch, root, *DECIDE) == 0
    assert "nothing decided" in capsys.readouterr().out


def test_a_second_batch_the_same_day_is_its_own_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    run(monkeypatch, root, *DECIDE, "--answers", "RW-04=drop")
    run(monkeypatch, root, *DECIDE, "--answers", "RW-01=fix")
    names = sorted(p.name for p in (root / "input" / "target-intent").iterdir())
    assert names == ["A99_Decisions_2026-10-02-2.md", "A99_Decisions_2026-10-02.md"]
    _entries, evidence = registers(root)
    assert [i["id"] for i in evidence["items"]][-2:] == ["A99-P4-TARGET-002", "A99-P4-TARGET-003"]


def test_a_decided_policy_takes_its_class_off_the_batch(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = make_workspace(tmp_path)
    (root / "input" / "decisions" / "policy.yaml").write_text(yaml.safe_dump({"policy": [
        rule("P-1", "technical", "fix")]}), encoding="utf-8")
    assert run(monkeypatch, root, *DECIDE, "--answers", "ok") == 0
    entries, _evidence = registers(root)
    assert entries["RD-01"].get("resolved_by") is None          # settled, not decided one by one
    listing = (root / "output" / "A99_QuestionList.md").read_text(encoding="utf-8")
    assert "- RD-01 RD-01 title — P-1 (technical): fix" in listing
    queue = json.loads((root / "output" / "A99_DecisionQueue.json").read_text(encoding="utf-8"))
    assert queue["counts"]["settled_by_policy"] == 1
    assert "settled by standing policy" in capsys.readouterr().out


def test_decide_and_party_do_not_go_together(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path)
    with pytest.raises(SystemExit):
        run(monkeypatch, root, *DECIDE, "--party", "Operations")


# --- the backfill -------------------------------------------------------------

def run_backfill(monkeypatch: pytest.MonkeyPatch, root: Path, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["backfill_needs.py", "--app-root", str(root), *args])
    return backfill_needs.main()


def test_each_open_risk_is_proposed_as_a_disposition_with_its_class_left_to_decide(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path, with_needs=False)
    assert run_backfill(monkeypatch, root) == 0
    text = (root / "input" / "decisions" / "needs-proposal.yaml").read_text(encoding="utf-8")
    proposal = yaml.safe_load(text)["needs"]
    assert set(proposal) == {"RW-01", "RW-02", "RW-03", "RW-04", "RD-01"}
    rw01 = proposal["RW-01"]
    assert rw01 == {"kind": "DISPOSITION", "party": "decider", "blocks": [], "default": "mitigation",
                    "class": "UNDECIDED", "depends_on": []}
    assert proposal["RW-02"]["depends_on"] == ["Q119"]
    assert proposal["RW-03"]["default"] is None                 # "none proposed": it blocks,
    assert proposal["RW-03"]["blocks"] == "UNDECIDED"           # so it has to name what
    assert proposal["RD-01"]["default"] == "mitigation"         # read from Phase 1's shape
    assert '"Profile before loading"' in text                   # the reviewer sees what was read


def test_what_a_mitigation_waits_on_follows_supersession_and_skips_what_is_closed() -> None:
    """A real RA-02 names Q108, superseded by Q103, and UK-S04, answered."""
    entries = [entry("Q108", "Q", superseded_by="Q103"), question("Q103"),
               entry("UK-S04", "UK-", resolved_by="A99-P4-CODE-001"),
               entry("UK-S06", "UK-"), question("Q110", gap="UK-S06")]
    found, notes = backfill_needs.waits_on("Ask first — Q108, UK-S04", "RA-02", entries)
    assert found == ["Q103"]
    assert "Q108 is superseded by Q103" in notes and "UK-S04 is closed by A99-P4-CODE-001" in notes
    # RW-06 names the unknown and the question that asks about it: one item to wait on.
    assert backfill_needs.waits_on("Analyse it — UK-S06, Q110", "RW-06", entries)[0] == ["Q110"]


def test_the_first_run_drafts_a_policy_with_nothing_in_force(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path, with_needs=False)
    run_backfill(monkeypatch, root)
    drafted = dq.load_policy(root / "input" / "decisions" / "policy.yaml")
    assert drafted is not None and drafted.problems == []
    assert [(r["class"], r["disposition"]) for r in drafted.entries] == [
        ("technical", "fix"), ("retired", "drop"), ("data", "fix"), ("behaviour", "ask")]
    assert not any(dq.Policy.in_force(r) for r in drafted.entries)
    edited = "edited by the decider\n"
    (root / "input" / "decisions" / "policy.yaml").write_text(edited, encoding="utf-8")
    run_backfill(monkeypatch, root, "--force")
    assert (root / "input" / "decisions" / "policy.yaml").read_text(encoding="utf-8") == edited


def test_a_reviewed_risk_proposal_applies_and_the_register_passes_its_checks(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = make_workspace(tmp_path, with_needs=False)
    run_backfill(monkeypatch, root)
    path = root / "input" / "decisions" / "needs-proposal.yaml"
    assert run_backfill(monkeypatch, root, "--apply") == 1        # the classes are UNDECIDED
    path.write_text(path.read_text(encoding="utf-8").replace("class: UNDECIDED", "class: behaviour")
                    .replace("blocks: UNDECIDED", 'blocks: ["WF-001"]'), encoding="utf-8")
    assert run_backfill(monkeypatch, root, "--apply") == 0
    entries, _evidence = registers(root)
    assert entries["RW-02"]["needs"]["depends_on"] == ["Q119"]
    assert dq.validate_register(list(entries.values()),
                                dq.load_parties(root / "input" / "decisions" / "parties.yaml")) == []


def test_a_second_applied_proposal_does_not_replace_the_first(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A register is backfilled twice, the questions in slice 1 and the risks in slice 3. The second
    apply renamed its proposal over the first reviewed one, the only record of that review."""
    root = make_workspace(tmp_path, with_needs=False)
    decisions = root / "input" / "decisions"
    earlier = "needs:\n  Q1: reviewed in slice 1\n"
    (decisions / "needs-proposal.applied.yaml").write_text(earlier, encoding="utf-8")
    run_backfill(monkeypatch, root)
    path = decisions / "needs-proposal.yaml"
    path.write_text(path.read_text(encoding="utf-8").replace("class: UNDECIDED", "class: behaviour")
                    .replace("blocks: UNDECIDED", 'blocks: ["WF-001"]'), encoding="utf-8")
    assert run_backfill(monkeypatch, root, "--apply") == 0
    assert (decisions / "needs-proposal.applied.yaml").read_text(encoding="utf-8") == earlier
    assert "class: behaviour" in (decisions / "needs-proposal.applied.2.yaml").read_text(encoding="utf-8")
    assert not path.exists()


def test_an_unknown_a_question_already_asks_about_is_not_proposed_again() -> None:
    """Re-running the backfill on a real register after slice 1 proposed 14 unknowns again, every one of
    them already asked by a question's `gap`, for a reviewer to delete a second time."""
    entries = [entry("UK-W01", "UK-"), question("Q117", gap="UK-W01"), entry("UK-W02", "UK-")]
    assert [e["id"] for e in backfill_needs.open_asks(entries)] == ["UK-W02"]


# --- the contract in three places -----------------------------------------------

def scheme() -> dict:
    return yaml.safe_load((PACKAGE / "specifications" / "identifier-scheme.yaml").read_text(encoding="utf-8"))


def test_the_scheme_and_the_module_state_one_policy_contract() -> None:
    register = scheme()["register"]
    assert tuple(register["needs"]["dispositions"]) == dq.DISPOSITIONS
    assert tuple(register["policy"]["fields"]) == dq.POLICY_KEYS
    assert tuple(register["policy"]["dispositions"]) == dq.POLICY_DISPOSITIONS
    assert "ID-11" in {r["id"] for r in scheme()["rules"]}
    schema = json.loads((PACKAGE / "schemas" / "decision-needs.schema.json").read_text(encoding="utf-8"))
    enums = [part["then"]["properties"]["options"]["items"]["enum"] for part in schema["allOf"]
             if "options" in part["then"]["properties"]]
    assert enums == [list(dq.DISPOSITIONS)]


def test_the_schema_and_the_validator_agree_on_a_risks_block() -> None:
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads((PACKAGE / "schemas" / "decision-needs.schema.json").read_text(encoding="utf-8"))
    validator = jsonschema.Draft202012Validator(schema)
    cases = [
        (True, risk("RW-01")),
        (True, risk("RW-01", options=["fix", "drop"])),
        (False, risk("RW-01", options=["fix", "keep"])),
        (False, risk("RW-01", default=None)),
    ]
    for expected, e in cases:
        by_schema = not list(validator.iter_errors(e["needs"]))
        by_module = not problems_of(e)
        assert by_schema == by_module == expected, (e["needs"], by_schema, by_module)


@pytest.mark.parametrize("name", [
    "phase1-data-understanding.md", "phase2-screen-analysis.md", "phase3-logic-processing.md",
    "phase4-workflow-reconstruction.md", "phase5-document-integration.md"])
def test_every_phase_template_says_what_a_risk_carries_in_the_register(name: str) -> None:
    text = (PACKAGE / "templates" / name).read_text(encoding="utf-8")
    risks = text[text.index("| ID | Risk | Severity"):]
    guidance = risks[:risks.index("-->")]
    assert "ID-11" in guidance and "DISPOSITION" in guidance and "`class`" in guidance
    assert "none proposed" in guidance and "depends_on" in guidance
