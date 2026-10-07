"""A coverage map is a claim; the test results are the evidence (`screen_rule_tests.py`).

The tests are the ways a rule is wrongly called tested:

  a skipped, failing or errored test is counted as backing the rule
  a rule id is matched inside a longer one (BR-ORD-01 inside BR-ORD-011 or BR-ORD-01a)
  a rule named only in the coverage map, or only in a test nobody ran, counts
  a run that executed nothing, or a count typed into a document, proves anything
  a waiver hides a gap without a reason, or a rule that was never checked

Run as a process, the way the test stage runs it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "modernize" / "scripts" / "screen_rule_tests.py"
RULES = "BR-ORD-01,BR-ORD-02,BR-ORD-03,BR-ORD-04,BR-ORD-05"
INNER = {"passed": "", "failed": "<failure message='x'/>", "error": "<error message='x'/>", "skipped": "<skipped/>"}


def junit(tmp_path: Path, cases: list[tuple[str, str, str]], name: str = "results.xml") -> Path:
    body = "".join(f'<testcase classname="{c}" name="{t}">{INNER[s]}</testcase>' for c, t, s in cases)
    path = tmp_path / name
    path.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>", encoding="utf-8")
    return path


def check(tmp_path: Path, results: Path, rules: str = RULES, *extra: str) -> tuple[int, dict | None, str]:
    out = tmp_path / "RULE_TESTS.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--rules", rules, "--junit", str(results), "--out", str(out), *extra],
        capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, (json.loads(out.read_text(encoding="utf-8")) if out.exists() else None), proc.stderr


def states(pack: dict) -> dict[str, str]:
    return {r["rule"]: r["state"] for r in pack["rules"]}


SOURCE = '''import pytest


def test_total():
    """BR-ORD-01: the total rounds half up."""
    assert True


@pytest.mark.skip
def test_discount():
    # BR-ORD-02
    assert True


class TestShipping:
    """Covers BR-ORD-03."""

    def test_free_over_limit(self):
        assert True

    def test_other(self):
        # BR-ORD-04 only here
        assert True
'''


def source(tmp_path: Path) -> Path:
    folder = tmp_path / "tests"
    folder.mkdir()
    (folder / "test_order.py").write_text(SOURCE, encoding="utf-8")
    return folder


def test_a_passing_test_that_names_the_rule_backs_it(tmp_path):
    res = junit(tmp_path, [("tests.test_order", "test_br_ord_01_rounds_up", "passed")])
    code, pack, _ = check(tmp_path, res, "BR-ORD-01")
    assert code == 0 and states(pack) == {"BR-ORD-01": "TESTED"} and pack["verdict"] == "BACKED"


def test_each_state_is_told_apart(tmp_path):
    res = junit(tmp_path, [
        ("t.test_o", "test_br_ord_01_ok", "passed"),
        ("t.test_o", "test_br_ord_02_bad", "failed"),
        ("t.test_o", "test_br_ord_03_err", "error"),
        ("t.test_o", "test_br_ord_04_later", "skipped"),
    ])
    code, pack, _ = check(tmp_path, res)
    assert code == 1
    assert states(pack) == {"BR-ORD-01": "TESTED", "BR-ORD-02": "FAILING", "BR-ORD-03": "FAILING",
                            "BR-ORD-04": "NOT RUN", "BR-ORD-05": "UNTESTED"}


def test_one_failing_test_outweighs_a_passing_one(tmp_path):
    res = junit(tmp_path, [("t.test_o", "test_br_ord_01_a", "passed"), ("t.test_o", "test_br_ord_01_b", "failed")])
    _, pack, _ = check(tmp_path, res, "BR-ORD-01")
    assert states(pack) == {"BR-ORD-01": "FAILING"}
    assert pack["rules"][0]["testCount"] == {"passed": 1, "failed": 1}


def test_a_rule_id_is_matched_whole(tmp_path):
    res = junit(tmp_path, [("t.test_o", "test_br_ord_011_other", "passed"), ("t.test_o", "test_br_ord_01a_variant", "passed")])
    _, pack, _ = check(tmp_path, res, "BR-ORD-01,BR-ORD-01a")
    assert states(pack) == {"BR-ORD-01": "UNTESTED", "BR-ORD-01a": "TESTED"}


def test_any_separator_in_a_test_name_matches(tmp_path):
    res = junit(tmp_path, [("t.test_o", "BR-ORD-01 rounds", "passed"), ("t.test_o", "test_BR_ORD_02", "passed"),
                           ("t.test_o", "test BR.ORD.03 x", "passed")])
    _, pack, _ = check(tmp_path, res, "BR-ORD-01,BR-ORD-02,BR-ORD-03")
    assert set(states(pack).values()) == {"TESTED"}


def test_the_class_name_counts(tmp_path):
    res = junit(tmp_path, [("t.test_o.TestBR_ORD_01", "test_rounds", "passed")])
    _, pack, _ = check(tmp_path, res, "BR-ORD-01")
    assert states(pack) == {"BR-ORD-01": "TESTED"}


def test_a_run_that_executed_nothing_proves_nothing(tmp_path):
    res = junit(tmp_path, [("t.test_o", "test_br_ord_01", "skipped")])
    code, pack, err = check(tmp_path, res, "BR-ORD-01")
    assert code == 2 and pack is None and "no test that executed" in err
    empty = tmp_path / "empty.xml"
    empty.write_text("<testsuites/>", encoding="utf-8")
    assert check(tmp_path, empty, "BR-ORD-01")[0] == 2


def test_a_missing_or_unreadable_result_is_an_input_error(tmp_path):
    assert check(tmp_path, tmp_path / "nope.xml", "BR-ORD-01")[0] == 2
    bad = tmp_path / "bad.xml"
    bad.write_text("not xml", encoding="utf-8")
    assert check(tmp_path, bad, "BR-ORD-01")[0] == 2


def test_a_citation_inside_the_test_source_is_mapped_to_its_result(tmp_path):
    res = junit(tmp_path, [
        ("tests.test_order", "test_total", "passed"),
        ("tests.test_order", "test_discount", "skipped"),
        ("tests.test_order.TestShipping", "test_free_over_limit", "passed"),
        ("tests.test_order.TestShipping", "test_other", "failed"),
    ])
    code, pack, _ = check(tmp_path, res, RULES, "--tests", str(source(tmp_path)))
    assert states(pack) == {"BR-ORD-01": "TESTED", "BR-ORD-02": "NOT RUN", "BR-ORD-03": "FAILING",
                            "BR-ORD-04": "FAILING", "BR-ORD-05": "UNTESTED"}


def test_a_class_citation_reaches_all_its_methods_but_a_method_citation_stays_in_its_method(tmp_path):
    res = junit(tmp_path, [("tests.test_order.TestShipping", "test_other", "passed"),
                           ("tests.test_order.TestShipping", "test_free_over_limit", "failed")])
    _, pack, _ = check(tmp_path, res, "BR-ORD-03,BR-ORD-04", "--tests", str(source(tmp_path)))
    # BR-ORD-03 is on the class, so both methods carry it and one failed; BR-ORD-04 is in test_other only
    assert states(pack) == {"BR-ORD-03": "FAILING", "BR-ORD-04": "TESTED"}


def test_a_source_citation_with_no_result_is_not_run_not_tested(tmp_path):
    res = junit(tmp_path, [("tests.test_order", "test_total", "passed")])
    _, pack, _ = check(tmp_path, res, "BR-ORD-02", "--tests", str(source(tmp_path)))
    assert states(pack) == {"BR-ORD-02": "NOT RUN"}


def test_a_parametrized_result_maps_to_its_function(tmp_path):
    res = junit(tmp_path, [("tests.test_order", "test_total[0.5-1]", "passed")])
    _, pack, _ = check(tmp_path, res, "BR-ORD-01", "--tests", str(source(tmp_path)))
    assert states(pack) == {"BR-ORD-01": "TESTED"}


def test_the_coverage_map_alone_is_only_a_claim(tmp_path):
    doc = tmp_path / "Test_Instruction.md"
    doc.write_text("| BR-ORD-01 | test_total | primary | pass |\n| BR-ORD-02 | test_x | primary | pass |\n", encoding="utf-8")
    res = junit(tmp_path, [("t.test_o", "test_br_ord_02_ok", "passed")])
    code, pack, _ = check(tmp_path, res, "BR-ORD-01,BR-ORD-02", "--coverage-map", str(doc))
    assert code == 1 and states(pack) == {"BR-ORD-01": "CLAIMED", "BR-ORD-02": "TESTED"}


def test_a_waiver_needs_a_reason_and_a_rule_that_was_checked(tmp_path):
    res = junit(tmp_path, [("t.test_o", "test_br_ord_01_ok", "passed")])
    assert check(tmp_path, res, "BR-ORD-01,BR-ORD-02", "--waive", "BR-ORD-02=")[0] == 2
    assert check(tmp_path, res, "BR-ORD-01,BR-ORD-02", "--waive", "BR-ORD-09=not ours")[0] == 2


def test_a_waived_gap_passes_but_is_still_listed(tmp_path):
    res = junit(tmp_path, [("t.test_o", "test_br_ord_01_ok", "passed")])
    code, pack, _ = check(tmp_path, res, "BR-ORD-01,BR-ORD-02", "--waive", "BR-ORD-02=this screen only displays it")
    assert code == 0 and pack["counts"]["WAIVED"] == 1
    rec = next(r for r in pack["rules"] if r["rule"] == "BR-ORD-02")
    assert rec["wouldBe"] == "UNTESTED" and rec["waived"]


def test_a_folder_of_results_is_read(tmp_path):
    folder = tmp_path / "results"
    folder.mkdir()
    junit(folder, [("t.test_o", "test_br_ord_01_ok", "passed")], "a.xml")
    junit(folder, [("t.test_o", "test_br_ord_02_ok", "passed")], "b.xml")
    code, pack, _ = check(tmp_path, folder, "BR-ORD-01,BR-ORD-02")
    assert code == 0 and pack["testsRead"] == 2


def test_not_a_rule_id_or_no_rules_is_refused(tmp_path):
    res = junit(tmp_path, [("t.test_o", "test_ok", "passed")])
    assert check(tmp_path, res, "ORD-01")[0] == 2
    assert subprocess.run([sys.executable, str(SCRIPT), "--junit", str(res)], capture_output=True).returncode == 2


def test_real_pytest_output_maps_back_to_the_source(tmp_path):
    root = tmp_path / "proj"
    (root / "tests").mkdir(parents=True)
    (root / "tests" / "test_order.py").write_text(SOURCE, encoding="utf-8")
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--junitxml", str(tmp_path / "r.xml")],
                   cwd=root, capture_output=True)
    code, pack, _ = check(tmp_path, tmp_path / "r.xml", RULES, "--tests", str(root / "tests"))
    assert states(pack) == {"BR-ORD-01": "TESTED", "BR-ORD-02": "NOT RUN", "BR-ORD-03": "TESTED",
                            "BR-ORD-04": "TESTED", "BR-ORD-05": "UNTESTED"}


def test_the_rules_in_scope_come_from_the_extraction(tmp_path):
    import csv

    screen, other = "受注データ取込画面", "出荷数確認リスト印刷画面"
    ak = tmp_path / "output"
    ak.mkdir()
    entries = [{"id": f"BR-ORD-0{n}", "namespace": "BR-", "phase": 3, "title": "t", "evidence_ids": [ev]}
               for n, ev in ((1, "A99-P3-CODE-001"), (2, "A99-P3-CODE-001"), (9, "A99-P2-UI-001"))]
    (ak / "A99_Identifiers.json").write_text(json.dumps({"app_id": "A99", "entries": entries}), encoding="utf-8")
    with (ak / "A99_TraceabilityMatrix.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["workflow_id", "step", "screen", "evidence_ids"])
        writer.writeheader()
        writer.writerow({"workflow_id": "WF-1", "step": "1", "screen": screen, "evidence_ids": "A99-P3-CODE-001"})
        writer.writerow({"workflow_id": "WF-2", "step": "1", "screen": other, "evidence_ids": "A99-P2-UI-001"})
    res = junit(tmp_path, [("t.test_o", "test_br_ord_01_ok", "passed")])
    out = tmp_path / "RULE_TESTS.json"
    proc = subprocess.run([sys.executable, str(SCRIPT), "--ak", str(ak), "--screen", screen, "--junit", str(res),
                           "--out", str(out)], capture_output=True, text=True, encoding="utf-8")
    pack = json.loads(out.read_text(encoding="utf-8"))
    # BR-ORD-09 belongs to the other screen and is not asked of this one
    assert proc.returncode == 1 and states(pack) == {"BR-ORD-01": "TESTED", "BR-ORD-02": "UNTESTED"}
    bad = subprocess.run([sys.executable, str(SCRIPT), "--ak", str(tmp_path / "none"), "--screen", screen, "--junit", str(res),
                          "--out", str(out)], capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 2
