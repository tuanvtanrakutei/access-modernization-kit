"""A person places a rule or a risk on the screens it belongs to, and the scope obeys (A82).

An entry linked to screens only through evidence most of them cite is cross-cutting: the
evidence cannot say which screen it belongs to. `$ak decisions --place` records the person's
answer as the entry's `screens`. Each test is one way that would go wrong.
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
import decision_place as dp  # noqa: E402
import decision_queue as dq  # noqa: E402
import decision_register as dr  # noqa: E402
from test_decision_needs import entry  # noqa: E402


def parties() -> dq.Parties:
    return dq.Parties.from_mapping({"parties": {"decider": {"people": ["Person One"]}}})


def register() -> list[dict]:
    return [
        entry("F-001", "F-", 2, title="Main menu"), entry("F-002", "F-", 2, title="Import screen"),
        entry("RA-03", "RA-", 2, severity="MEDIUM"), entry("BR-W002-01", "BR-", 4),
        entry("RA-09", "RA-", 2, superseded_by="RA-03"), entry("Q5", "Q", 1),
        entry("RW-04", "RW-", 4, screens=["F-002"], placed_by="Person One", placed_on="2026-10-01"),
    ]


def place(entries: list[dict], specs: list[str], by: str = "Person One", on: str = "2026-10-07") -> list[str]:
    return dp.place(entries, dp.parse(specs), by, on, parties())


def test_a_risk_is_placed_on_its_screen_with_who_and_when() -> None:
    entries = register()
    assert place(entries, ["RA-03=F-001"]) == ["RA-03 -> F-001"]
    ra = {e["id"]: e for e in entries}["RA-03"]
    assert (ra["screens"], ra["placed_by"], ra["placed_on"]) == (["F-001"], "Person One", "2026-10-07")


def test_a_rule_can_be_placed_on_several_screens_and_by_object_name() -> None:
    entries = register()
    place(entries, ["BR-W002-01=F-002,object:出荷画面,F-002"])
    assert {e["id"]: e for e in entries}["BR-W002-01"]["screens"] == ["F-002", "object:出荷画面"]


def test_an_empty_placement_removes_it() -> None:
    entries = register()
    assert place(entries, ["RW-04="]) == ["RW-04: placement removed"]
    rw = {e["id"]: e for e in entries}["RW-04"]
    assert not {"screens", "placed_by", "placed_on"} & set(rw)


@pytest.mark.parametrize(("spec", "message"), [
    ("RA-99=F-001", "not in the register"),
    ("Q5=F-001", "only a business rule or a risk"),
    ("RA-09=F-001", "superseded by RA-03"),
    ("RA-03=F-999", "F-999 is not a screen"),
    ("RA-03=object:", "names no object"),
    ("RA-03=F-001,,F-002", "empty target"),
    ("RA-03", "wants ID=F-nnn"),
])
def test_a_placement_that_cannot_be_followed_is_refused_and_writes_nothing(spec: str, message: str) -> None:
    entries = register()
    snapshot = json.dumps(entries, sort_keys=True)
    with pytest.raises(dp.PlaceProblem, match=message):
        place(entries, [spec, "BR-W002-01=F-002"])
    assert json.dumps(entries, sort_keys=True) == snapshot, "all or nothing"


@pytest.mark.parametrize(("by", "on", "message"), [
    ("", "2026-10-07", "names nobody"),
    ("Someone Else", "2026-10-07", "not one of the decider's people"),
    ("Person One", "7 Oct", "YYYY-MM-DD"),
])
def test_a_placement_says_who_and_when(by: str, on: str, message: str) -> None:
    with pytest.raises(dp.PlaceProblem, match=message):
        place(register(), ["RA-03=F-001"], by=by, on=on)


# --- the command ------------------------------------------------------------

def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "A99"
    (root / "input" / "decisions").mkdir(parents=True)
    (root / "input" / "decisions" / "parties.yaml").write_text(
        "parties:\n  decider:\n    people: [Person One]\n", encoding="utf-8")
    (root / "output").mkdir()
    (root / "output" / "A99_Identifiers.json").write_text(
        dr.format_register({"app_id": "A99", "entries": register()}), encoding="utf-8", newline="\n")
    return root


def run(monkeypatch: pytest.MonkeyPatch, root: Path, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["build_decisions.py", "--app-root", str(root), *args])
    return build_decisions.main()


def written(root: Path) -> dict:
    return {e["id"]: e for e in json.loads(
        (root / "output" / "A99_Identifiers.json").read_text(encoding="utf-8"))["entries"]}


def test_the_command_writes_the_placement_with_a_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = workspace(tmp_path)
    run(monkeypatch, root, "--place", "RA-03=F-001", "--place", "BR-W002-01=F-002", "--by", "Person One")
    after = written(root)
    assert after["RA-03"]["screens"] == ["F-001"] and after["BR-W002-01"]["screens"] == ["F-002"]
    assert list((root / ".ak" / "backups").glob("A99_Identifiers.*.json"))


def test_a_dry_run_and_a_refusal_write_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = workspace(tmp_path)
    before = (root / "output" / "A99_Identifiers.json").read_bytes()
    run(monkeypatch, root, "--place", "RA-03=F-001", "--by", "Person One", "--dry-run")
    assert run(monkeypatch, root, "--place", "RA-03=F-999", "--by", "Person One") == 2
    assert (root / "output" / "A99_Identifiers.json").read_bytes() == before


def test_place_is_run_apart_from_the_other_writers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(SystemExit):
        run(monkeypatch, workspace(tmp_path), "--place", "RA-03=F-001", "--decide", "--by", "Person One")
