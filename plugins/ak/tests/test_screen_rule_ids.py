"""A screen the register holds no rule for still needs rule ids (`screen_rule_ids.py`).

Every screen's flow numbers its rules from 01, so two screens each had their own `BR-02`, and a
result file could not tell whose rule a test proved. The id is `BR-<PREFIX>-nn`, minted in the
screen plan's mapping table. The tests are the ways that goes wrong:

  two screens end up with the same prefix, or a prefix that is already a register scope
  a row's id is read from a reference to another rule, not from the row's own cell
  a number is reused, or a duplicate id passes
  another screen's id, or a register-style id the register does not hold, passes
  the script writes something, or proposes a prefix as though it were declared
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "modernize" / "scripts" / "screen_rule_ids.py"
RULE_TESTS = PACKAGE / "modernize" / "scripts" / "screen_rule_tests.py"

SCREEN = "受注データ取込画面"


def registry(*rows: tuple[str, str, str]) -> str:
    """rows: (screen, screen_key, rule_prefix); the column is left out entirely when every prefix is None."""
    out = ["# Screens Registry", "", "| # | screen | screen_key | rule_prefix | status_be | status_fe |", "|---|---|---|---|---|---|"]
    for n, (screen, key, prefix) in enumerate(rows, start=1):
        out.append(f"| {n} | `{screen}` | `{key}` | `{prefix}` | `implemented` | `implemented` |")
    return "\n".join(out) + "\n"


def plan(*rule_cells: str, heading: str = "## 5. Legacy-To-New Mapping") -> str:
    out = ["# plan", "", heading, "", "| # | Rule (BF §6) | Legacy anchor | Status |", "|---|---|---|---|"]
    for n, cell in enumerate(rule_cells, start=1):
        out.append(f"| {n} | {cell} | anchor | planned |")
    out += ["", "## 6. Gap Matrix", "", "| Topic | Status |", "|---|---|", "| BR-99 not a mapping row | open |", ""]
    return "\n".join(out)


def files(tmp_path: Path, reg: str, plan_text: str | None = None, register: list[str] | None = None) -> dict[str, Path]:
    out = {"registry": tmp_path / "Screens_Registry.md"}
    out["registry"].write_text(reg, encoding="utf-8")
    if plan_text is not None:
        out["plan"] = tmp_path / "plan.md"
        out["plan"].write_text(plan_text, encoding="utf-8")
    if register is not None:
        ak = tmp_path / "output"
        ak.mkdir()
        entries = [{"id": i, "namespace": "BR-", "phase": 3, "title": "t", "evidence_ids": []} for i in register]
        (ak / "A99_Identifiers.json").write_text(json.dumps({"app_id": "A99", "entries": entries}), encoding="utf-8")
        out["ak"] = ak
    return out


def run(tmp_path: Path, reg: str, plan_text: str | None = None, register: list[str] | None = None, screen: str = SCREEN,
        *extra: str) -> tuple[int, dict | None, str]:
    f = files(tmp_path, reg, plan_text, register)
    cmd = [sys.executable, str(SCRIPT), "--registry", str(f["registry"]), "--screen", screen, "--json", *extra]
    if "plan" in f:
        cmd += ["--plan", str(f["plan"])]
    if "ak" in f:
        cmd += ["--ak", str(f["ak"])]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    return proc.returncode, (json.loads(proc.stdout) if proc.stdout.strip().startswith("{") else None), proc.stderr


REG = registry((SCREEN, "import-order-data", "IMP"), ("出荷数確認リスト印刷画面", "shipping-check-list", "SHP"))


def kinds(report: dict) -> list[str]:
    return [r["kind"] for r in report["rows"]]


def test_a_plan_whose_rows_carry_minted_ids_needs_nothing(tmp_path):
    code, report, _ = run(tmp_path, REG, plan("BR-IMP-01 codes unique", "BR-IMP-02 name at most 50"))
    assert code == 0 and report["findings"] == [] and kinds(report) == ["minted", "minted"]
    assert report["prefix"] == "IMP" and report["prefix_state"] == "declared"


def test_a_bare_local_id_becomes_a_prefixed_one_with_the_same_number(tmp_path):
    code, report, _ = run(tmp_path, REG, plan("BR-01 codes unique", "BR-02 name at most 50"))
    assert code == 1 and [r["propose"] for r in report["rows"]] == ["BR-IMP-01", "BR-IMP-02"]


def test_a_row_with_no_id_is_a_legacy_concept_and_is_left_alone(tmp_path):
    # the mapping holds one row per rule or legacy concept: a screen title, a button, an open question
    code, report, _ = run(tmp_path, REG, plan("BR-IMP-01 a", "Commit on row-leave", "Page title differs"))
    assert code == 0 and kinds(report) == ["minted", "none", "none"] and report["findings"] == []
    assert [r["propose"] for r in report["rows"]] == [None, None, None]


def test_strict_gives_a_row_with_no_id_the_next_number_and_never_a_used_one(tmp_path):
    code, report, _ = run(tmp_path, REG, plan("BR-IMP-01 a", "BR-IMP-03 b", "no id here"), None, SCREEN, "--strict")
    # 02 is not used in the plan, but a retired rule may have held it: the next number is after the highest
    assert code == 1 and [r["propose"] for r in report["rows"]] == [None, None, "BR-IMP-04"]


def test_a_bare_number_already_taken_gets_the_next_free_one(tmp_path):
    _, report, _ = run(tmp_path, REG, plan("BR-IMP-02 a", "BR-02 b"))
    assert report["rows"][1]["propose"] == "BR-IMP-03"


def test_a_reference_after_the_rows_own_id_is_not_the_rows_id(tmp_path):
    code, report, _ = run(tmp_path, REG, plan("BR-IMP-01 (BF BR-01) codes unique"))
    assert code == 0 and report["rows"][0]["id"] == "BR-IMP-01" and kinds(report) == ["minted"]


def test_an_id_that_is_not_in_the_mapping_section_is_not_read(tmp_path):
    # the Gap Matrix mentions BR-99; it is not a mapping row
    _, report, _ = run(tmp_path, REG, plan("BR-IMP-01 a"))
    assert [r["id"] for r in report["rows"]] == ["BR-IMP-01"]


def test_a_duplicate_id_is_a_finding(tmp_path):
    code, report, _ = run(tmp_path, REG, plan("BR-IMP-01 a", "BR-IMP-01 b"))
    assert code == 1 and any("rows 1 and 2" in f for f in report["findings"])


def test_another_screens_prefix_is_a_finding(tmp_path):
    code, report, _ = run(tmp_path, REG, plan("BR-SHP-01 not ours"))
    assert code == 1 and kinds(report) == ["other-screen"] and "出荷数確認リスト印刷画面" in report["findings"][0]


def test_an_unknown_scope_is_a_finding_not_a_pass(tmp_path):
    code, report, _ = run(tmp_path, REG, plan("BR-ZZZ-01 who is this"))
    assert code == 1 and kinds(report) == ["unknown-scope"]


def test_a_register_id_is_accepted_only_when_the_register_holds_it(tmp_path):
    cells = ("BR-ORD-01 real", "BR-ORD-07 not in the register")
    code, report, _ = run(tmp_path, REG, plan(*cells), ["BR-ORD-01", "BR-ORD-02"])
    assert kinds(report) == ["register", "unknown-register"] and code == 1
    assert any("BR-ORD-07" in f for f in report["findings"])


def test_without_the_register_a_register_style_id_is_an_unknown_scope(tmp_path):
    # `--ak` is what tells a register id from a minted one: without it nothing is assumed
    _, report, _ = run(tmp_path, REG, plan("BR-ORD-01 real"))
    assert kinds(report) == ["unknown-scope"]


def test_a_malformed_id_is_a_finding(tmp_path):
    _, report, _ = run(tmp_path, REG, plan("BR-IMPORTER-01 too long a scope"))
    assert kinds(report) == ["malformed"]


def test_an_undeclared_prefix_is_proposed_not_assumed(tmp_path):
    reg = registry((SCREEN, "import-order-data", ""), ("出荷数確認リスト印刷画面", "shipping-check-list", "SHP"))
    code, report, _ = run(tmp_path, reg, plan("BR-01 a"))
    assert code == 1 and report["prefix_state"] == "proposed" and report["prefix"] == "IOD"
    assert any("no rule_prefix is declared" in f for f in report["findings"])
    assert report["rows"][0]["propose"] == "BR-IOD-01"


def test_a_proposed_prefix_avoids_every_taken_one(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    # another screen already declares the first stem the key would give (IOD)
    taken = registry((SCREEN, "import-order-data", ""), ("x", "other", "IOD"))
    _, report, _ = run(tmp_path / "a", taken)
    assert report["prefix_state"] == "proposed" and report["prefix"] != "IOD"
    # and a scope the register already uses is taken too
    _, report, _ = run(tmp_path / "b", registry((SCREEN, "import-order-data", "")), None, ["BR-IOD-01"])
    assert report["prefix"] != "IOD"


def test_a_declared_prefix_must_be_well_formed_unique_and_not_a_register_scope(tmp_path):
    _, report, _ = run(tmp_path, registry((SCREEN, "a", "imp"), ("x", "b", "SHP")))
    assert any("not one to six capitals" in f for f in report["findings"])
    _, report, _ = run(tmp_path, registry((SCREEN, "a", "IMP"), ("x", "b", "IMP")))
    assert any("declared by more than one screen" in f for f in report["findings"])
    _, report, _ = run(tmp_path, registry((SCREEN, "a", "ORD"), ("x", "b", "SHP")), None, ["BR-ORD-01"])
    assert any("already a scope of the register" in f for f in report["findings"])


def test_a_prefix_option_overrides_the_registry(tmp_path):
    _, report, _ = run(tmp_path, REG, plan("BR-01 a"), None, SCREEN, "--prefix", "NEW")
    assert report["prefix"] == "NEW" and report["rows"][0]["propose"] == "BR-NEW-01"


def test_a_registry_without_the_column_still_works(tmp_path):
    reg = "| # | screen | screen_key | status_be | status_fe |\n|---|---|---|---|---|\n| 1 | `受注データ取込画面` | `import-order-data` | `implemented` | `implemented` |\n"
    code, report, _ = run(tmp_path, reg, plan("BR-01 a"))
    assert code == 1 and report["prefix_state"] == "proposed" and report["rows"][0]["propose"] == "BR-IOD-01"


def test_a_screen_the_registry_does_not_hold_is_an_input_error(tmp_path):
    code, report, err = run(tmp_path, REG, plan("BR-IMP-01 a"), None, "no such screen")
    assert code == 2 and report is None and "no row for" in err


def test_a_plan_without_a_mapping_section_is_an_input_error(tmp_path):
    code, _, err = run(tmp_path, REG, plan("BR-IMP-01 a", heading="## 5. Something else"))
    assert code == 2 and "no Legacy-To-New Mapping section" in err


def test_it_writes_nothing(tmp_path):
    f = files(tmp_path, REG, plan("BR-01 a", "no id"))
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    subprocess.run([sys.executable, str(SCRIPT), "--registry", str(f["registry"]), "--screen", SCREEN, "--plan", str(f["plan"])],
                   capture_output=True)
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_the_text_report_lists_each_row_and_what_it_needs(tmp_path):
    f = files(tmp_path, REG, plan("BR-IMP-01 a", "BR-02 b"))
    proc = subprocess.run([sys.executable, str(SCRIPT), "--registry", str(f["registry"]), "--screen", SCREEN, "--plan", str(f["plan"])],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 1 and "ok (minted)" in proc.stdout and "-> BR-IMP-02" in proc.stdout


# ---- screen_rule_tests.py --plan: the rules a screen owes are the ids its mapping rows carry

def junit(tmp_path: Path, names: list[str]) -> Path:
    body = "".join(f'<testcase classname="t.test_o" name="{n}"/>' for n in names)
    path = tmp_path / "results.xml"
    path.write_text(f"<testsuites><testsuite>{body}</testsuite></testsuites>", encoding="utf-8")
    return path


def test_rule_tests_takes_its_rules_from_the_plans_rows(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text(plan("BR-IMP-01 (BF BR-01) a", "BR-IMP-02 b"), encoding="utf-8")
    res = junit(tmp_path, ["test_br_imp_01_ok"])
    out = tmp_path / "RT.json"
    proc = subprocess.run([sys.executable, str(RULE_TESTS), "--plan", str(p), "--junit", str(res), "--out", str(out)],
                          capture_output=True, text=True, encoding="utf-8")
    states = {r["rule"]: r["state"] for r in json.loads(out.read_text(encoding="utf-8"))["rules"]}
    assert proc.returncode == 1 and states == {"BR-IMP-01": "TESTED", "BR-IMP-02": "UNTESTED"}


def test_rule_tests_ignores_legacy_concept_rows_but_needs_at_least_one_rule(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text(plan("BR-IMP-01 a", "Commit on row-leave"), encoding="utf-8")
    res = junit(tmp_path, ["test_br_imp_01_ok"])
    out = tmp_path / "RT.json"
    proc = subprocess.run([sys.executable, str(RULE_TESTS), "--plan", str(p), "--junit", str(res), "--out", str(out)],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0 and [r["rule"] for r in json.loads(out.read_text(encoding="utf-8"))["rules"]] == ["BR-IMP-01"]
    p.write_text(plan("Commit on row-leave", "Page title differs"), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(RULE_TESTS), "--plan", str(p), "--junit", str(res), "--out", str(tmp_path / "RT2.json")],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 2 and "no row of the mapping carries a rule id" in proc.stderr


def test_rule_tests_refuses_a_plan_with_a_malformed_id(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text(plan("BR-IMP-01 a", "BR-IMPORTER-01 b"), encoding="utf-8")
    res = junit(tmp_path, ["test_br_imp_01_ok"])
    proc = subprocess.run([sys.executable, str(RULE_TESTS), "--plan", str(p), "--junit", str(res), "--out", str(tmp_path / "RT.json")],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 2 and "row 2 (BR-IMPORTER-01)" in proc.stderr
