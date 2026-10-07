"""A question with no default can be given one, and the register stays honest about it (A80).

A question that blocks what it names and has no default stops the modernize pre-flight on
every screen it names directly. Some of those questions wait on a customer for weeks. The
register already models the way out - `needs.default` naming an `AS-` whose `if_wrong`
says what to correct - and `$ak decisions --assume` writes it without hand-editing the
register. Each test is one way that would go wrong.
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
import decision_assume as da_assume  # noqa: E402
import decision_queue as dq  # noqa: E402
import decision_register as dr  # noqa: E402
from test_decision_needs import RISK_NEEDS, entry, needs  # noqa: E402

THAT = "Initial data is loaded once before go-live"
IF_WRONG = "F-001 needs an initial-load path, and WF-001 would change"


def parties() -> dq.Parties:
    return dq.Parties.from_mapping({"parties": {
        "Operations": {"aliases": ["Warehouse operations"]},
        "decider": {"people": ["Person One"]},
    }})


def register() -> list[dict]:
    return [
        entry("WF-001", "WF-"), entry("F-001", "F-", 2, title="Import screen"),
        entry("AS-07", "AS-", if_wrong="WF-001 changes"),
        entry("Q5", "Q", 1, needs=needs(party="Operations", blocks=["F-001"])),
        entry("Q6", "Q", 1, needs=needs(party="Operations", default="AS-07")),
        entry("Q7", "Q", 1, resolved_by="A99-P1-CODE-001", needs=needs(party="Operations")),
        entry("Q8", "Q", 1),
        entry("RW-02", "RW-", severity="HIGH", needs=dict(RISK_NEEDS)),
    ]


def assume(entries: list[dict], item: str = "Q5", **over: str) -> da_assume.Assumption:
    args = {"statement": THAT, "if_wrong": IF_WRONG, "by": "Person One", "on": "2026-10-07"} | over
    return da_assume.assume(entries, item, args["statement"], args["if_wrong"], args["by"],
                            args["on"], parties())


def test_the_question_proceeds_on_a_new_assumption_and_stays_open() -> None:
    entries = register()
    made = assume(entries)
    by_id = {e["id"]: e for e in entries}
    assert made.entry["id"] == "AS-08"
    assert by_id["Q5"]["needs"]["default"] == "AS-08"
    assert dq.is_open(by_id["Q5"]), "an assumption is not an answer"
    new = by_id["AS-08"]
    assert new["title"] == THAT and new[dq.IF_WRONG] == IF_WRONG
    assert (new["assumed_for"], new["assumed_by"], new["assumed_on"]) == ("Q5", "Person One", "2026-10-07")
    # Allocated where the question was, because that phase's document has to change.
    assert new["phase"] == 1
    # Q8 has no `needs` on purpose, for the refusal below; nothing else may be reported.
    assert [p for p in dq.validate_register(entries, parties()) if not p.startswith("Q8:")] == []


def test_the_queue_moves_it_from_blocking_to_proceeding() -> None:
    import decision_agenda as da

    entries = register()
    before = {i["id"]: i for i in da.build_queue(entries, parties())["items"]}
    assume(entries)
    after = {i["id"]: i for i in da.build_queue(entries, parties())["items"]}
    assert before["Q5"]["posture"] == "BLOCKING"
    assert after["Q5"]["posture"] != "BLOCKING"
    assert after["Q5"]["default"]["if_wrong"] == IF_WRONG


@pytest.mark.parametrize(("item", "message"), [
    ("Q99", "not in the register"),
    ("Q8", "has no `needs`"),
    ("Q7", "is closed"),
    ("Q6", "already proceeds on AS-07"),
    ("RW-02", "is a DISPOSITION"),
])
def test_an_item_that_cannot_take_an_assumption_is_refused(item: str, message: str) -> None:
    entries = register()
    snapshot = json.dumps(entries, sort_keys=True)
    with pytest.raises(da_assume.AssumeProblem, match=message):
        assume(entries, item)
    assert json.dumps(entries, sort_keys=True) == snapshot, "a refusal changed the register"


@pytest.mark.parametrize(("field", "value", "message"), [
    ("statement", "  ", "the assumption is empty"),
    ("if_wrong", "", "ID-12"),
    ("by", "", "names nobody"),
    ("by", "Someone Else", "not one of the decider's people"),
    ("on", "7 Oct", "YYYY-MM-DD"),
])
def test_an_assumption_missing_what_makes_it_auditable_is_refused(field: str, value: str, message: str) -> None:
    entries = register()
    with pytest.raises(da_assume.AssumeProblem, match=message):
        assume(entries, **{field: value})
    assert not any(e["id"] == "AS-08" for e in entries)


def test_an_if_wrong_naming_nothing_is_written_with_a_warning() -> None:
    made = assume(register(), if_wrong="the import would need another path")
    assert made.warnings and "refresh set is empty" in made.warnings[0]
    assert "F-001" in made.warnings[0], "the warning names what it could have named"


def test_the_numbering_continues_and_stops_at_the_scheme_limit() -> None:
    assert da_assume.next_id([entry("AS-41", "AS-"), entry("AS-09", "AS-")]) == "AS-42"
    assert da_assume.next_id([]) == "AS-01"
    with pytest.raises(da_assume.AssumeProblem, match="two digits"):
        da_assume.next_id([entry("AS-99", "AS-")])


def test_the_document_edits_name_the_row_and_the_table() -> None:
    made = assume(register())
    edits = da_assume.document_edits(made, ["A99_Phase1_Data_EN.md"])
    assert "Q5" in edits[0] and "`AS-08`" in edits[0]
    assert "Assumptions table" in edits[1] and THAT in edits[1]


# --- the command ------------------------------------------------------------

def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "A99"
    (root / "input" / "decisions").mkdir(parents=True)
    (root / "input" / "decisions" / "parties.yaml").write_text(
        "parties:\n  Operations:\n    aliases: [Warehouse operations]\n"
        "  decider:\n    people: [Person One]\n", encoding="utf-8")
    out = root / "output"
    out.mkdir()
    (out / "A99_Identifiers.json").write_text(
        dr.format_register({"app_id": "A99", "entries": register()}), encoding="utf-8", newline="\n")
    (out / "A99_Phase1_Data_EN.md").write_text("# A99 - Phase 1\n", encoding="utf-8")
    return root


def run(monkeypatch: pytest.MonkeyPatch, root: Path, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["build_decisions.py", "--app-root", str(root), *args])
    return build_decisions.main()


ASSUME = ("--assume", "Q5", "--that", THAT, "--if-wrong", IF_WRONG, "--by", "Person One",
          "--on", "2026-10-07")


def test_the_command_writes_the_register_with_a_backup_and_names_the_edits(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = workspace(tmp_path)
    run(monkeypatch, root, *ASSUME)
    out = capsys.readouterr().out
    assert "assumed: AS-08 for Q5" in out
    assert "A99_Phase1_Data_EN.md: the Questions row for Q5" in out
    written = {e["id"]: e for e in json.loads(
        (root / "output" / "A99_Identifiers.json").read_text(encoding="utf-8"))["entries"]}
    assert written["Q5"]["needs"]["default"] == "AS-08"
    assert list((root / ".ak" / "backups").glob("A99_Identifiers.*.json"))


def test_a_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                  capsys: pytest.CaptureFixture) -> None:
    root = workspace(tmp_path)
    before = (root / "output" / "A99_Identifiers.json").read_bytes()
    run(monkeypatch, root, *ASSUME, "--dry-run")
    assert "assumed: AS-08" in capsys.readouterr().out
    assert (root / "output" / "A99_Identifiers.json").read_bytes() == before


def test_a_refusal_exits_two_and_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = workspace(tmp_path)
    before = (root / "output" / "A99_Identifiers.json").read_bytes()
    assert run(monkeypatch, root, "--assume", "Q6", "--that", THAT, "--if-wrong", IF_WRONG,
               "--by", "Person One") == 2
    assert (root / "output" / "A99_Identifiers.json").read_bytes() == before


def test_assume_without_its_three_parts_is_a_usage_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = workspace(tmp_path)
    with pytest.raises(SystemExit):
        run(monkeypatch, root, "--assume", "Q5", "--that", THAT)
