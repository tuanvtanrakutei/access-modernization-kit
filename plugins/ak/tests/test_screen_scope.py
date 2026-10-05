"""Stage 1 is computed, not written: what a screen has to cover, and gates G1 and G2 (A75, slice 4c).

Stage 1 was a business-flow document an agent wrote per screen, and gate G1 measured the copy.
Everything in it already exists in the extraction: workflows are `TraceabilityMatrix.csv` rows,
rules are `BR-` entries, legacy defects are risks with a Mitigation, and what is undecided is
the decision queue. `screen_scope.py` computes the scope from those, and G1 and G2 are read off
it. The tests are the ways that goes wrong:

  a rule or risk is linked to a screen it has nothing to do with, or to none it belongs to
  the screen name is matched loosely, so another screen's rules are planned against this one
  a gap is reported against a plan that covers it, or not reported against one that does not
  the script writes something, or reads a file it was not given

Run as a process, the way pre-flight runs it.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "modernize" / "scripts" / "screen_scope.py"

SCREEN = "受注データ取込画面"
OTHER = "受注数調整リスト印刷画面"


def entry(eid: str, namespace: str, evidence: list[str], **extra: object) -> dict:
    return {"id": eid, "namespace": namespace, "phase": 3, "title": f"title of {eid}", "evidence_ids": evidence, **extra}


REGISTER = [
    entry("BR-ORD-01", "BR-", ["A99-P3-CODE-001"]),
    entry("BR-ORD-02", "BR-", ["A99-P3-CODE-001", "A99-P3-CODE-002"]),
    entry("BR-ORD-09", "BR-", ["A99-P2-UI-001"]),                       # the other screen's
    entry("BR-ORD-11", "BR-", ["A99-P3-CODE-001"], superseded_by="BR-ORD-01"),
    entry("RA-06", "RA-", ["A99-P3-CODE-001"], severity="HIGH"),
    entry("RW-02", "RW-", ["A99-P3-CODE-001"], severity="HIGH"),
    entry("RD-01", "RD-", ["A99-P1-SCHEMA-001"], severity="LOW"),        # linked to no screen
    entry("RA-10", "RA-", ["A99-P3-CODE-001"], severity="LOW", resolved_by="A99-P3-CODE-002"),
    entry("RW-09", "RW-", ["A99-P3-CODE-001"], severity="LOW"),
    entry("RW-08", "RW-", ["A99-P3-CODE-001"], severity="LOW"),
]
MATRIX = [
    {"workflow_id": "WF-001", "step": "1", "screen": SCREEN, "evidence_ids": "A99-P3-CODE-001"},
    {"workflow_id": "WF-001", "step": "2", "screen": SCREEN, "evidence_ids": "A99-P3-CODE-001, A99-P3-CODE-002"},
    {"workflow_id": "WF-002", "step": "1", "screen": OTHER, "evidence_ids": "A99-P2-UI-001"},
]
EVIDENCE = {"app_id": "A99", "items": [{"id": "A99-P3-CODE-001"}, {"id": "A99-P3-CODE-002"}, {"id": "A99-P2-UI-001"}]}


def qitem(eid: str, blocks: list[dict], *, posture: str = "PROCEEDS_ON_DEFAULT", bucket: str = "asking", **extra: object) -> dict:
    return {"id": eid, "kind": "FACT", "title": f"title of {eid}", "posture": posture, "bucket": bucket,
            "blocks": blocks, "default": None if posture == "BLOCKING" else {"id": "AS-01", "title": "x"}, "party": "常温庫", **extra}


F_SCREEN = {"id": "F-002", "title": SCREEN}
QUEUE = {"app_id": "A99", "counts": {}, "closed": [{"id": "RW-08", "disposition": "preserve"}],
         "items": [qitem("Q117", [{"id": "WF-001", "title": "import"}, F_SCREEN]),
                   qitem("UK-W04", [{"id": "WF-001", "title": "import"}]),
                   qitem("RA-06", [], bucket="settled", settled_by="P-1", disposition="fix")]}

PLAN = """# 受注データ取込画面

## 1. Evidence

BR-ORD-01 appears here, in prose, and that does not count as a mapping.

## 5. Legacy-To-New Mapping

| # | Rule | Legacy anchor | Status |
|---|---|---|---|
| 1 | BR-ORD-01 | x | implemented |
| 2 | BR-ORD-02 | y | planned |

### 5.1 Notes

BR-ORD-09 is another screen's and is cited here for no reason.

## 6. Gap Matrix

| Topic | Legacy | New | Status |
|---|---|---|---|
| Q117 which date | a | b | open |
| UK-W04 approval step | c | d | open |

## 7. Acceptance
"""


def workspace(tmp_path: Path, *, register: list[dict] | None = None, matrix: list[dict] | None = None,
              evidence: dict | None = ..., queue: dict | None = ...) -> Path:
    out = tmp_path / "output"
    out.mkdir()
    (out / "A99_Identifiers.json").write_text(json.dumps({"app_id": "A99", "entries": register or REGISTER}), encoding="utf-8")
    with (out / "A99_TraceabilityMatrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["workflow_id", "step", "screen", "evidence_ids"])
        writer.writeheader()
        writer.writerows(MATRIX if matrix is None else matrix)
    if evidence is ...:
        evidence = EVIDENCE
    if evidence is not None:
        (out / "A99_Evidence.json").write_text(json.dumps(evidence), encoding="utf-8")
    if queue is ...:
        queue = QUEUE
    if queue is not None:
        (out / "A99_DecisionQueue.json").write_text(json.dumps(queue, ensure_ascii=False), encoding="utf-8")
    return out


def run(*args: str | Path) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), *map(str, args)], capture_output=True, text=True, encoding="utf-8")


def report(out: Path, screen: str = SCREEN, *extra: str | Path) -> tuple[int, dict]:
    done = run("--ak", out, "--screen", screen, "--json", *extra)
    return done.returncode, (json.loads(done.stdout) if done.stdout.strip() else {})


# --- the scope ---------------------------------------------------------------------------------

def test_a_rule_belongs_to_a_screen_that_cites_the_evidence_it_cites(tmp_path: Path) -> None:
    _, data = report(workspace(tmp_path))
    rules = {r["id"]: r for r in data["scope"]["rules"]}
    assert set(rules) == {"BR-ORD-01", "BR-ORD-02"}
    assert rules["BR-ORD-02"]["through"] == ["A99-P3-CODE-001", "A99-P3-CODE-002"]


def test_another_screens_rule_and_a_superseded_rule_are_not_in_scope(tmp_path: Path) -> None:
    _, data = report(workspace(tmp_path))
    ids = {r["id"] for r in data["scope"]["rules"]}
    assert "BR-ORD-09" not in ids and "BR-ORD-11" not in ids
    assert data["scope"]["rules_in_register"] == 3          # the superseded one is not counted either


def test_a_risk_is_in_scope_while_open_and_not_once_resolved(tmp_path: Path) -> None:
    _, data = report(workspace(tmp_path))
    ids = {r["id"] for r in data["scope"]["risks"]}
    assert {"RA-06", "RW-02", "RW-09", "RW-08"} == ids      # RA-10 is resolved, RD-01 reaches no screen


def test_a_risks_disposition_is_read_from_the_queue(tmp_path: Path) -> None:
    _, data = report(workspace(tmp_path))
    state = {r["id"]: r["disposition"] for r in data["scope"]["risks"]}
    assert state["RA-06"] == "settled by P-1: fix"
    assert state["RW-08"] == "decided: preserve"
    assert state["RW-09"] == "not in the queue"


def test_without_a_queue_the_dispositions_say_so_and_nothing_fails(tmp_path: Path) -> None:
    code, data = report(workspace(tmp_path, queue=None))
    assert data["queue_present"] is False and code == 0
    assert {r["disposition"] for r in data["scope"]["risks"]} == {"no queue read"}


def test_the_report_says_how_many_screens_an_item_is_linked_to(tmp_path: Path) -> None:
    """A risk linked to most screens is a cross-cutting one the evidence cannot place on this
    screen in particular; on A06 six risks reach 7 of 13 screens through one shared screenshot set."""
    shared = entry("RA-01", "RA-", ["A99-P3-CODE-001", "A99-P2-UI-001"], severity="HIGH")
    out = workspace(tmp_path, register=[*REGISTER, shared])
    _, data = report(out)
    risks = {r["id"]: r for r in data["scope"]["risks"]}
    assert risks["RA-06"]["screens"] == 1 and risks["RA-01"]["screens"] == 2
    assert data["scope"]["screens_in_matrix"] == 2
    done = run("--ak", out, "--screen", SCREEN)
    assert "(reaches 2 of 2 screens)" in done.stdout and "(reaches 1 of 2 screens)" in done.stdout


def test_workflows_and_their_steps_come_from_the_matrix(tmp_path: Path) -> None:
    _, data = report(workspace(tmp_path))
    assert data["scope"]["workflows"] == {"WF-001": 2} and data["scope"]["rows"] == 2


def test_the_screen_name_is_matched_exactly(tmp_path: Path) -> None:
    """Another screen's rows are not planned against this one, and a near miss is a finding."""
    out = workspace(tmp_path)
    _, data = report(out, OTHER)
    assert {r["id"] for r in data["scope"]["rules"]} == {"BR-ORD-09"}
    code, data = report(out, "受注データ取込")
    assert code == 1 and data["scope"]["rows"] == 0
    assert [f["gate"] for f in data["findings"]] == ["G1"]


def test_the_report_says_how_much_of_the_register_the_scope_is(tmp_path: Path) -> None:
    done = run("--ak", workspace(tmp_path), "--screen", SCREEN)
    assert "Business rules in scope: 2 of 3 in the register (linked by shared evidence, so a superset)" in done.stdout


# --- G1 -----------------------------------------------------------------------------------------

def test_g1_names_evidence_the_matrix_cites_and_the_register_lacks(tmp_path: Path) -> None:
    short = {"app_id": "A99", "items": [{"id": "A99-P3-CODE-001"}]}
    code, data = report(workspace(tmp_path, evidence=short))
    assert code == 1 and data["scope"]["evidence_missing"] == ["A99-P3-CODE-002"]
    assert any(f["gate"] == "G1" and "A99-P3-CODE-002" in f["text"] for f in data["findings"])


def test_without_an_evidence_register_the_check_is_skipped_and_says_so(tmp_path: Path) -> None:
    done = run("--ak", workspace(tmp_path, evidence=None), "--screen", SCREEN)
    assert "no Evidence.json, so not checked" in done.stdout
    assert "G1" not in done.stdout.split("Findings")[-1]


def test_a_blocking_decision_that_names_the_screen_is_a_finding(tmp_path: Path) -> None:
    queue = {**QUEUE, "items": [*QUEUE["items"], qitem("Q5", [F_SCREEN], posture="BLOCKING", bucket="blocking")]}
    code, data = report(workspace(tmp_path, queue=queue))
    assert code == 1 and [f["gate"] for f in data["findings"]] == ["pre-flight"]


# --- G2 -----------------------------------------------------------------------------------------

def plan_file(tmp_path: Path, text: str = PLAN) -> Path:
    path = tmp_path / "plan.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_a_plan_that_maps_every_rule_and_cites_every_open_decision_passes(tmp_path: Path) -> None:
    code, data = report(workspace(tmp_path), SCREEN, "--plan", plan_file(tmp_path))
    assert code == 0 and data["findings"] == []
    assert data["plan"] == {"mapping_section": True, "gap_section": True, "rules_uncovered": [], "decisions_uncited": []}


def test_a_rule_cited_only_in_prose_is_not_mapped(tmp_path: Path) -> None:
    text = PLAN.replace("| 2 | BR-ORD-02 | y | planned |\n", "")
    code, data = report(workspace(tmp_path), SCREEN, "--plan", plan_file(tmp_path, text))
    assert code == 1 and data["plan"]["rules_uncovered"] == ["BR-ORD-02"]


def test_a_rule_cited_under_a_subheading_of_the_mapping_section_is_mapped(tmp_path: Path) -> None:
    text = PLAN.replace("| 2 | BR-ORD-02 | y | planned |\n", "").replace("BR-ORD-09 is another", "BR-ORD-02 is mapped here; BR-ORD-09 is another")
    _, data = report(workspace(tmp_path), SCREEN, "--plan", plan_file(tmp_path, text))
    assert data["plan"]["rules_uncovered"] == []


def test_a_rule_cited_after_the_mapping_section_ends_does_not_count(tmp_path: Path) -> None:
    text = PLAN.replace("| 2 | BR-ORD-02 | y | planned |\n", "").replace("| Q117 which date |", "| BR-ORD-02 elsewhere | Q117 which date |")
    _, data = report(workspace(tmp_path), SCREEN, "--plan", plan_file(tmp_path, text))
    assert data["plan"]["rules_uncovered"] == ["BR-ORD-02"]


def test_a_decision_the_gap_matrix_leaves_out_is_a_finding(tmp_path: Path) -> None:
    text = PLAN.replace("| UK-W04 approval step | c | d | open |\n", "")
    code, data = report(workspace(tmp_path), SCREEN, "--plan", plan_file(tmp_path, text))
    assert code == 1 and data["plan"]["decisions_uncited"] == ["UK-W04"]
    assert any("UK-W04" in f["text"] for f in data["findings"])


def test_a_decision_cited_outside_the_gap_matrix_is_not_acknowledged(tmp_path: Path) -> None:
    text = PLAN.replace("| UK-W04 approval step | c | d | open |\n", "")
    text = text.replace("## 7. Acceptance", "## 7. Acceptance\n\nUK-W04 is discussed here.")
    _, data = report(workspace(tmp_path), SCREEN, "--plan", plan_file(tmp_path, text))
    assert data["plan"]["decisions_uncited"] == ["UK-W04"]


def test_a_decision_a_policy_settled_is_not_owed_a_row(tmp_path: Path) -> None:
    """RA-06 is settled by P-1; it is neither a Q nor a UK and the plan is not asked to cite it."""
    _, data = report(workspace(tmp_path), SCREEN, "--plan", plan_file(tmp_path))
    assert "RA-06" not in data["plan"]["decisions_uncited"]


def test_a_plan_with_no_mapping_or_no_gap_section_is_a_finding_for_each(tmp_path: Path) -> None:
    code, data = report(workspace(tmp_path), SCREEN, "--plan", plan_file(tmp_path, "# plan\n\nnothing here\n"))
    texts = [f["text"] for f in data["findings"] if f["gate"] == "G2"]
    assert code == 1 and any("Mapping section" in t for t in texts) and any("Gap Matrix section" in t for t in texts)


# --- inputs -------------------------------------------------------------------------------------

def test_a_directory_without_the_register_or_the_matrix_is_exit_2(tmp_path: Path) -> None:
    done = run("--ak", tmp_path, "--screen", SCREEN)
    assert done.returncode == 2 and "needs an Identifiers.json" in done.stderr


def test_a_plan_that_cannot_be_read_is_exit_2(tmp_path: Path) -> None:
    done = run("--ak", workspace(tmp_path), "--screen", SCREEN, "--plan", tmp_path / "missing.md")
    assert done.returncode == 2 and "cannot be read" in done.stderr


def test_two_registers_are_ambiguous_and_neither_is_read(tmp_path: Path) -> None:
    out = workspace(tmp_path)
    (out / "B77_Identifiers.json").write_text("{}", encoding="utf-8")
    done = run("--ak", out, "--screen", SCREEN)
    assert done.returncode == 2 and "more than one" in done.stderr


def test_the_script_writes_nothing(tmp_path: Path) -> None:
    out = workspace(tmp_path)
    plan = plan_file(tmp_path)
    before = {p.name: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    run("--ak", out, "--screen", SCREEN, "--plan", plan)
    assert {p.name: p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()} == before


def test_the_production_name_survives_the_pipe(tmp_path: Path) -> None:
    done = run("--ak", workspace(tmp_path), "--screen", SCREEN)
    assert done.stdout.startswith(f"Scope of `{SCREEN}`")
