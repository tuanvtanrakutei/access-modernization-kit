"""Pre-flight asks the extraction's decision queue what is still undecided about a screen (A75, slice 4b).

A modernize stage planned a screen over whatever the phases had raised, and the only list of
what was undecided was a hand-written question list at the end of a run. The queue knows, per
item, what it blocks and what the pipeline proceeds on meanwhile, so the screen can be told.

Two rules shape the script and each has a test that fails without it:

  names are matched exactly   `LEGACY_EVIDENCE.md` 6.3: a script that decides two strings mean one
                              screen is the unverifiable guess "machine detects, human decides"
                              rules out. An item that names a different screen is not listed.
  nothing found is not nothing open   an item that blocks nothing (a risk's disposition) reaches no
                              screen from here, so the count of those is printed.

Run as a process, the way pre-flight runs it.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "modernize" / "scripts" / "screen_decisions.py"

SCREEN = "受注データ取込画面"
OTHER = "受注数調整リスト印刷画面"


def block(identifier: str | None = None, title: str = "", obj: str | None = None) -> dict:
    return {"object": obj} if obj is not None else {"id": identifier, "title": title}


def item(eid: str, blocks: list[dict], *, posture: str = "BLOCKING", bucket: str = "blocking",
         default: dict | None = None, **extra: object) -> dict:
    return {"id": eid, "kind": "FACT", "title": f"title of {eid}", "posture": posture, "bucket": bucket,
            "blocks": blocks, "default": default, "party": "常温庫", **extra}


def queue(*items: dict) -> dict:
    return {"app_id": "A99", "items": list(items), "counts": {}}


def write(tmp_path: Path, data: dict, matrix_rows: list[dict] | None = None) -> Path:
    out = tmp_path / "output"
    out.mkdir()
    (out / "A99_DecisionQueue.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    if matrix_rows is not None:
        with (out / "A99_TraceabilityMatrix.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["run_id", "workflow_id", "screen", "processing"])
            writer.writeheader()
            writer.writerows(matrix_rows)
    return out


def run(*args: str | Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True,
                          text=True, encoding="utf-8")


def report(out: Path, screen: str = SCREEN, *extra: str) -> tuple[int, dict]:
    done = run("--queue", out, "--screen", screen, "--json", *extra)
    return done.returncode, (json.loads(done.stdout) if done.stdout.strip() else {})


F_SCREEN = block("F-002", SCREEN)
F_OTHER = block("F-006", OTHER)
MATRIX = [{"run_id": "r", "workflow_id": "WF-001", "screen": SCREEN, "processing": "x"},
          {"run_id": "r", "workflow_id": "WF-002", "screen": OTHER, "processing": "y"}]


# --- what names the screen --------------------------------------------------------------

def test_a_blocking_item_that_names_the_screen_directly_stops_pre_flight(tmp_path: Path) -> None:
    out = write(tmp_path, queue(item("Q5", [F_SCREEN])))
    code, data = report(out)
    assert code == 1
    assert [i["id"] for i in data["blocking_directly"]] == ["Q5"]
    assert data["screen_ids"] == ["F-002"]


def test_an_object_reference_with_the_production_name_names_it_too(tmp_path: Path) -> None:
    out = write(tmp_path, queue(item("Q9", [block(obj=SCREEN)])))
    code, data = report(out)
    assert code == 1 and data["blocking_directly"][0]["through"] == f"object:{SCREEN}"


def test_an_object_reference_to_a_longer_name_is_another_object(tmp_path: Path) -> None:
    out = write(tmp_path, queue(item("Q9", [block(obj=SCREEN + "サブ")])))
    code, data = report(out)
    assert code == 0 and data["blocking_directly"] == [] and data["open_items_elsewhere"] == 1


def test_an_item_that_names_another_screen_is_not_listed(tmp_path: Path) -> None:
    """The matcher is exact: Q6 blocks the adjustment-list screen and says nothing about this one."""
    out = write(tmp_path, queue(item("Q5", [F_SCREEN]), item("Q6", [F_OTHER])))
    _, data = report(out)
    assert [i["id"] for i in data["blocking_directly"]] == ["Q5"]
    assert data["open_items_elsewhere"] == 1


def test_a_name_that_differs_by_a_character_is_a_different_screen(tmp_path: Path) -> None:
    """No fuzzy matching (LEGACY_EVIDENCE.md 6.3): a near miss is a finding to raise, not a match."""
    out = write(tmp_path, queue(item("Q5", [block("F-002", SCREEN)])))
    code, data = report(out, "受注データ取込画面 ")      # a trailing space is not a difference
    assert code == 1
    code, data = report(out, "受注データ取込")
    assert code == 0 and data["screen_ids"] == [] and data["blocking_directly"] == []


def test_the_same_name_in_another_unicode_form_is_the_same_name(tmp_path: Path) -> None:
    decomposed = chr(0x30AB) + chr(0x3099)      # KA + combining dakuten, as a clipboard sometimes delivers it
    precomposed = chr(0x30AC)                  # GA
    assert decomposed != precomposed
    out = write(tmp_path, queue(item("Q5", [block("F-002", f"{precomposed}ID")])))
    code, data = report(out, f"{decomposed}ID")
    assert code == 1 and data["screen_ids"] == ["F-002"]


def test_a_workflow_through_the_screen_names_it_by_the_matrix(tmp_path: Path) -> None:
    out = write(tmp_path, queue(item("UK-W04", [block("WF-001", "import")]),
                                item("UK-W09", [block("WF-002", "print")])), MATRIX)
    code, data = report(out)
    assert code == 0                         # through a workflow: listed, pre-flight proceeds
    assert [i["id"] for i in data["blocking_by_workflow"]] == ["UK-W04"]
    assert data["workflows"] == ["WF-001"]


def test_a_matrix_row_naming_a_longer_screen_is_not_this_screen(tmp_path: Path) -> None:
    rows = [{"run_id": "r", "workflow_id": "WF-001", "screen": SCREEN + "2", "processing": "x"}]
    out = write(tmp_path, queue(item("UK-W04", [block("WF-001", "import")])), rows)
    assert report(out)[1]["workflows"] == []


def test_without_a_matrix_a_workflow_names_nothing_and_the_report_says_it_was_not_read(tmp_path: Path) -> None:
    out = write(tmp_path, queue(item("UK-W04", [block("WF-001", "import")])))
    _, data = report(out)
    assert data["blocking_by_workflow"] == [] and data["matrix_read"] is False


def test_direct_beats_workflow_when_both_hold(tmp_path: Path) -> None:
    out = write(tmp_path, queue(item("Q5", [block("WF-001", "import"), F_SCREEN])), MATRIX)
    _, data = report(out)
    assert [i["id"] for i in data["blocking_directly"]] == ["Q5"] and data["blocking_by_workflow"] == []


# --- the default it proceeds on ----------------------------------------------------------

def test_an_item_with_a_default_proceeds_and_says_what_it_proceeds_on(tmp_path: Path) -> None:
    proceeding = item("Q117", [block("WF-001", "import")], posture="PROCEEDS_ON_DEFAULT", bucket="asking",
                      default={"id": "AS-32", "title": "the table holds the day", "if_wrong": "RW-02 would not follow",
                               "refresh": ["RW-02"]})
    out = write(tmp_path, queue(proceeding), MATRIX)
    code, data = report(out)
    row = data["proceeding_on_default"][0]
    assert code == 0 and row["default"] == "AS-32 the table holds the day"
    assert row["if_wrong"] == "RW-02 would not follow"


def test_a_risks_default_is_its_own_mitigation(tmp_path: Path) -> None:
    risk = item("RW-02", [F_SCREEN], posture="PROCEEDS_ON_DEFAULT", bucket="asking", default={"mitigation": True})
    _, data = report(write(tmp_path, queue(risk)))
    assert data["proceeding_on_default"][0]["default"] == "the risk's own Mitigation"


def test_a_flag_the_extraction_raised_travels_with_the_item(tmp_path: Path) -> None:
    flagged = item("Q9", [F_SCREEN], precheck=[{"kind": "offers", "text": "`fra分類` offers `1` = 保冷品"}])
    _, data = report(write(tmp_path, queue(flagged)))
    assert data["blocking_directly"][0]["precheck"][0]["text"].startswith("`fra分類`")


def test_an_item_settled_by_policy_is_listed_apart_and_never_blocks(tmp_path: Path) -> None:
    settled = item("RA-01", [F_SCREEN], bucket="settled", settled_by="P-1", disposition="fix")
    code, data = report(write(tmp_path, queue(settled)))
    assert code == 0 and data["blocking_directly"] == []
    assert data["settled_by_policy"] == [{"id": "RA-01", "settled_by": "P-1", "disposition": "fix", "named": "directly"}]


# --- nothing found is not nothing open ----------------------------------------------------

def test_items_that_block_nothing_are_counted_so_silence_is_not_read_as_done(tmp_path: Path) -> None:
    risks = [item(f"RW-0{n}", [], posture="PROCEEDS_ON_DEFAULT", bucket="asking", default={"mitigation": True})
             for n in range(1, 4)]
    done = run("--queue", write(tmp_path, queue(*risks)), "--screen", SCREEN)
    assert done.returncode == 0
    assert "3 that name nothing at all" in done.stdout
    assert "no TraceabilityMatrix.csv given" in done.stdout


def test_the_human_report_names_what_stops_pre_flight(tmp_path: Path) -> None:
    done = run("--queue", write(tmp_path, queue(item("Q5", [F_SCREEN]))), "--screen", SCREEN)
    assert done.returncode == 1 and "pre-flight stops (1)" in done.stdout and "Q5" in done.stdout
    assert done.stdout.startswith(f"Decisions about `{SCREEN}`")       # the production name survives the pipe


# --- inputs ---------------------------------------------------------------------------------

def test_the_screen_id_can_be_given_when_the_queue_never_titles_it(tmp_path: Path) -> None:
    out = write(tmp_path, queue(item("Q5", [block("F-002", "")])))
    assert report(out)[0] == 0
    assert report(out, SCREEN, "--screen-id", "F-002")[0] == 1


def test_a_queue_can_be_given_as_a_file(tmp_path: Path) -> None:
    out = write(tmp_path, queue(item("Q5", [F_SCREEN])))
    done = run("--queue", out / "A99_DecisionQueue.json", "--screen", SCREEN)
    assert done.returncode == 1


def test_a_missing_or_wrong_queue_is_exit_2_with_the_reason(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    done = run("--queue", empty, "--screen", SCREEN)
    assert done.returncode == 2 and "expected exactly one" in done.stderr
    bad = tmp_path / "bad.json"
    bad.write_text("{\"entries\": []}", encoding="utf-8")
    done = run("--queue", bad, "--screen", SCREEN)
    assert done.returncode == 2 and "not a decision queue" in done.stderr
    bad.write_text("not json", encoding="utf-8")
    assert run("--queue", bad, "--screen", SCREEN).returncode == 2


def test_the_matrix_beside_the_queue_is_found_without_being_named(tmp_path: Path) -> None:
    out = write(tmp_path, queue(item("UK-W04", [block("WF-001", "import")])), MATRIX)
    assert report(out)[1]["workflows"] == ["WF-001"]


def test_two_matrices_beside_the_queue_are_ambiguous_and_neither_is_read(tmp_path: Path) -> None:
    out = write(tmp_path, queue(item("UK-W04", [block("WF-001", "import")])), MATRIX)
    (out / "B77_TraceabilityMatrix.csv").write_text("workflow_id,screen\nWF-001," + SCREEN + "\n", encoding="utf-8")
    assert report(out)[1]["matrix_read"] is False


def test_the_script_writes_nothing(tmp_path: Path) -> None:
    out = write(tmp_path, queue(item("Q5", [F_SCREEN])), MATRIX)
    before = {p.name: p.read_bytes() for p in out.iterdir()}
    run("--queue", out, "--screen", SCREEN)
    assert {p.name: p.read_bytes() for p in out.iterdir()} == before
