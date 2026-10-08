"""Gate G4: "verified" is never inferred from silence (`screen_verify.py`).

The script reads the result files that `screen_parity.py`, `screen_canary.py` and
`screen_rule_tests.py` write. The fixtures here are shaped like those files; the fields read are
`verdict`, `problems` and `cases[].state` for parity, `verdict`, `why` and `break` for a canary,
and `rules[].state` for the rule tests. The tests are the ways a gate lies:

  a missing result file is read as a pass
  a failing, unrun or unproved rule is not raised, or is raised at the wrong severity
  a canary the tests did not notice is read as fine
  a difference a person accepted, or a waiver, disappears instead of being listed
  a waiver names no one who accepted it, or no date, and is still only LOW
  a coverage map cites a test that does not exist and nothing says so
  an unreadable file stops the gate instead of becoming a finding

Run as a process, the way the stage runs it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "modernize" / "scripts" / "screen_verify.py"

GOOD_PARITY = {"verdict": "PARITY", "problems": [], "cases": [{"id": "P01", "state": "same"}]}
GOOD_RULES = {"verdict": "BACKED", "rules": [{"rule": "BR-ORD-01", "state": "TESTED"}]}
GOOD_CANARY = {"verdict": "CAUGHT", "why": "1 test(s) failed", "break": {"file": "mod.py", "line": 2}}


def put(tmp_path: Path, name: str, data: object) -> Path:
    path = tmp_path / name
    path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    return path


def gate(tmp_path: Path, *, parity=None, rules=None, canaries=(), output_screen=False) -> tuple[int, list[dict], str]:
    cmd = [sys.executable, str(SCRIPT), "--screen", "OrderEntry", "--json"]
    if parity is not None:
        cmd += ["--parity", str(put(tmp_path, "PARITY.json", parity))]
    if rules is not None:
        cmd += ["--rule-tests", str(put(tmp_path, "RULE_TESTS.json", rules))]
    if canaries:
        cmd += ["--canary", *[str(put(tmp_path, f"CANARY{i}.json", c)) for i, c in enumerate(canaries)]]
    if output_screen:
        cmd += ["--output-screen"]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    findings = json.loads(proc.stdout)["findings"] if proc.stdout.strip().startswith("{") else []
    return proc.returncode, findings, proc.stderr


def severities(findings: list[dict]) -> list[str]:
    return [f["severity"] for f in findings]


def test_everything_proved_is_no_finding(tmp_path):
    code, findings, _ = gate(tmp_path, parity=GOOD_PARITY, rules=GOOD_RULES, canaries=[GOOD_CANARY], output_screen=True)
    assert code == 0 and findings == []


def test_a_missing_rule_result_is_high_not_a_pass(tmp_path):
    code, findings, _ = gate(tmp_path, canaries=[GOOD_CANARY])
    assert code == 1 and severities(findings) == ["HIGH"] and "no rule-test result" in findings[0]["text"]


def test_a_missing_parity_result_matters_only_for_a_screen_that_produces_output(tmp_path):
    assert gate(tmp_path, rules=GOOD_RULES, canaries=[GOOD_CANARY])[0] == 0
    code, findings, _ = gate(tmp_path, rules=GOOD_RULES, canaries=[GOOD_CANARY], output_screen=True)
    assert code == 1 and severities(findings) == ["HIGH"] and "no parity result" in findings[0]["text"]


def test_no_canary_is_medium(tmp_path):
    code, findings, _ = gate(tmp_path, rules=GOOD_RULES)
    assert code == 1 and severities(findings) == ["MEDIUM"] and "no canary" in findings[0]["text"]


def test_no_parity_is_high_and_names_the_reason(tmp_path):
    bad = {"verdict": "NO PARITY", "problems": ["1 case(s) differ"], "cases": []}
    code, findings, _ = gate(tmp_path, parity=bad, rules=GOOD_RULES, canaries=[GOOD_CANARY])
    assert code == 1 and severities(findings) == ["HIGH"] and "1 case(s) differ" in findings[0]["text"]


def test_only_a_fresh_input_shortfall_is_medium(tmp_path):
    short = {"verdict": "NO PARITY", "problems": ["only 4 fresh input(s) counted; 10 needed"], "cases": []}
    mixed = {"verdict": "NO PARITY", "problems": ["only 4 fresh input(s) counted; 10 needed", "1 case(s) differ"], "cases": []}
    assert severities(gate(tmp_path, parity=short, rules=GOOD_RULES, canaries=[GOOD_CANARY])[1]) == ["MEDIUM"]
    assert severities(gate(tmp_path, parity=mixed, rules=GOOD_RULES, canaries=[GOOD_CANARY])[1]) == ["HIGH"]


def test_an_accepted_difference_is_listed_as_low(tmp_path):
    accepted = {**GOOD_PARITY, "cases": [{"id": "P02", "state": "differs-approved", "approvedDifference": "legacy rounding was a defect"}]}
    code, findings, _ = gate(tmp_path, parity=accepted, rules=GOOD_RULES, canaries=[GOOD_CANARY])
    assert code == 1 and severities(findings) == ["LOW"] and "legacy rounding was a defect" in findings[0]["text"]


def test_each_rule_state_has_its_severity(tmp_path):
    rules = {"rules": [{"rule": f"BR-ORD-0{i}", "state": s} for i, s in
                       enumerate(["TESTED", "FAILING", "NOT RUN", "CLAIMED", "UNTESTED"], start=1)]
             + [{"rule": "BR-ORD-06", "state": "WAIVED", "wouldBe": "UNTESTED", "waived": "display only",
                                                  "waivedBy": "A. Reviewer", "waivedOn": "2026-10-01"}]}
    _, findings, _ = gate(tmp_path, rules=rules, canaries=[GOOD_CANARY])
    by_rule = {f["text"].split()[1]: f["severity"] for f in findings}
    assert by_rule == {"BR-ORD-02": "HIGH", "BR-ORD-03": "MEDIUM", "BR-ORD-04": "MEDIUM", "BR-ORD-05": "MEDIUM", "BR-ORD-06": "LOW"}


def test_a_canary_the_tests_did_not_notice_is_high(tmp_path):
    survived = {"verdict": "SURVIVED", "why": "every test still passed", "break": {"file": "mod.py", "line": 7}}
    code, findings, _ = gate(tmp_path, rules=GOOD_RULES, canaries=[survived])
    assert code == 1 and severities(findings) == ["HIGH"] and "mod.py:7" in findings[0]["text"]


def test_a_canary_that_learned_nothing_is_medium(tmp_path):
    for verdict in ("INCONCLUSIVE", "NO BASELINE"):
        _, findings, _ = gate(tmp_path, rules=GOOD_RULES, canaries=[{"verdict": verdict, "why": "x", "break": {}}])
        assert severities(findings) == ["MEDIUM"]


def test_one_good_canary_does_not_hide_a_bad_one(tmp_path):
    survived = {"verdict": "SURVIVED", "why": "x", "break": {"file": "mod.py", "line": 9}}
    _, findings, _ = gate(tmp_path, rules=GOOD_RULES, canaries=[GOOD_CANARY, survived])
    assert severities(findings) == ["HIGH"]


def test_a_canary_without_a_verdict_is_a_finding(tmp_path):
    _, findings, _ = gate(tmp_path, rules=GOOD_RULES, canaries=[{"why": "x"}])
    assert severities(findings) == ["MEDIUM"] and "no usable verdict" in findings[0]["text"]


def test_an_unreadable_result_is_a_finding_not_a_crash(tmp_path):
    code, findings, _ = gate(tmp_path, parity="not json", rules=GOOD_RULES, canaries=[GOOD_CANARY])
    assert code == 1 and severities(findings) == ["MEDIUM"] and "cannot be read" in findings[0]["text"]
    code, findings, _ = gate(tmp_path, rules=[1, 2], canaries=[GOOD_CANARY])
    assert code == 1 and "is not an object" in findings[0]["text"]


def test_findings_come_worst_first(tmp_path):
    survived = {"verdict": "SURVIVED", "why": "x", "break": {"file": "m.py", "line": 1}}
    rules = {"rules": [{"rule": "BR-ORD-01", "state": "UNTESTED"}]}
    accepted = {**GOOD_PARITY, "cases": [{"id": "P1", "state": "differs-approved", "approvedDifference": "ok"}]}
    _, findings, _ = gate(tmp_path, parity=accepted, rules=rules, canaries=[survived])
    assert severities(findings) == ["HIGH", "MEDIUM", "LOW"]


def test_text_output_lists_what_was_read(tmp_path):
    put(tmp_path, "R.json", GOOD_RULES)
    proc = subprocess.run([sys.executable, str(SCRIPT), "--screen", "OrderEntry", "--rule-tests", str(tmp_path / "R.json")],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 1 and "rule tests yes" in proc.stdout and "no canary" in proc.stdout


def test_writes_nothing(tmp_path):
    gate(tmp_path, parity=GOOD_PARITY, rules=GOOD_RULES, canaries=[GOOD_CANARY])
    assert sorted(p.name for p in tmp_path.iterdir()) == ["CANARY0.json", "PARITY.json", "RULE_TESTS.json"]


def test_a_waiver_that_a_test_now_makes_unneeded_is_said_so(tmp_path):
    rules = {"rules": [{"rule": "BR-ORD-01", "state": "WAIVED", "wouldBe": "TESTED", "waived": "covered by construction",
                        "waivedBy": "A. Reviewer", "waivedOn": "2026-10-01"}]}
    code, findings, _ = gate(tmp_path, rules=rules, canaries=[GOOD_CANARY])
    assert code == 1 and severities(findings) == ["LOW"]
    assert "drop the waiver" in findings[0]["text"] and "covered by construction" in findings[0]["text"]


def waived(**extra):
    return {"rules": [{"rule": "BR-ORD-01", "state": "WAIVED", "wouldBe": "UNTESTED", "waived": "display only", **extra}]}


def test_a_waiver_with_a_reviewer_and_a_date_is_low_and_says_who(tmp_path):
    _, findings, _ = gate(tmp_path, rules=waived(waivedBy="A. Reviewer", waivedOn="2026-10-01"), canaries=[GOOD_CANARY])
    assert severities(findings) == ["LOW"]
    assert "A. Reviewer" in findings[0]["text"] and "2026-10-01" in findings[0]["text"]


def test_a_waiver_missing_the_reviewer_or_the_date_is_medium_and_says_which(tmp_path):
    for extra, said in ((dict(waivedOn="2026-10-01"), "reviewer"), (dict(waivedBy="A. Reviewer"), "date"), ({}, "reviewer")):
        _, findings, _ = gate(tmp_path, rules=waived(**extra), canaries=[GOOD_CANARY])
        assert severities(findings) == ["MEDIUM"], extra
        assert said in findings[0]["text"] and "BR-ORD-01" in findings[0]["text"]


def test_a_blank_reviewer_counts_as_none(tmp_path):
    _, findings, _ = gate(tmp_path, rules=waived(waivedBy="  ", waivedOn="2026-10-01"), canaries=[GOOD_CANARY])
    assert severities(findings) == ["MEDIUM"]


def test_a_waiver_that_a_test_now_covers_still_needs_its_reviewer(tmp_path):
    rules = {"rules": [{"rule": "BR-ORD-01", "state": "WAIVED", "wouldBe": "TESTED", "waived": "by construction"}]}
    _, findings, _ = gate(tmp_path, rules=rules, canaries=[GOOD_CANARY])
    assert severities(findings) == ["MEDIUM"] and "drop the waiver" in findings[0]["text"]


def test_a_coverage_map_test_that_does_not_exist_is_medium_with_the_rule_and_the_name(tmp_path):
    pack = {**GOOD_RULES, "coverageMap": {"file": "m.md", "namesChecked": True,
                                          "unknownTests": [{"rule": "BR-ORD-01", "test": "test_wrong_name"}]}}
    code, findings, _ = gate(tmp_path, rules=pack, canaries=[GOOD_CANARY])
    assert code == 1 and severities(findings) == ["MEDIUM"]
    assert "BR-ORD-01" in findings[0]["text"] and "test_wrong_name" in findings[0]["text"]


def test_a_coverage_map_with_nothing_to_check_it_against_is_medium(tmp_path):
    pack = {**GOOD_RULES, "coverageMap": {"file": "m.md", "namesChecked": False, "unknownTests": []}}
    _, findings, _ = gate(tmp_path, rules=pack, canaries=[GOOD_CANARY])
    assert severities(findings) == ["MEDIUM"] and "not checked" in findings[0]["text"]


def test_a_coverage_map_whose_names_all_exist_is_no_finding(tmp_path):
    pack = {**GOOD_RULES, "coverageMap": {"file": "m.md", "namesChecked": True, "unknownTests": []}}
    code, findings, _ = gate(tmp_path, rules=pack, canaries=[GOOD_CANARY])
    assert code == 0 and findings == []


def test_canaries_left_out_on_purpose_are_low_with_the_reason(tmp_path):
    rules = put(tmp_path, "RULE_TESTS.json", GOOD_RULES)
    base = [sys.executable, str(SCRIPT), "--screen", "OrderEntry", "--json", "--rule-tests", str(rules)]
    proc = subprocess.run(base + ["--canaries-skipped", "a quick pass"], capture_output=True, text=True, encoding="utf-8")
    findings = json.loads(proc.stdout)["findings"]
    assert proc.returncode == 1 and severities(findings) == ["LOW"] and "a quick pass" in findings[0]["text"]


def test_a_skip_needs_a_reason_and_cannot_come_with_canary_results(tmp_path):
    rules = put(tmp_path, "RULE_TESTS.json", GOOD_RULES)
    base = [sys.executable, str(SCRIPT), "--screen", "OrderEntry", "--rule-tests", str(rules)]
    assert subprocess.run(base + ["--canaries-skipped", " "], capture_output=True).returncode == 2
    canary = put(tmp_path, "CANARY.json", GOOD_CANARY)
    both = base + ["--canaries-skipped", "why", "--canary", str(canary)]
    assert subprocess.run(both, capture_output=True).returncode == 2
