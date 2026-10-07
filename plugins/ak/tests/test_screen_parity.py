"""Parity is computed from bytes, not judged by a reader (`screen_parity.py`).

The tests are the ways a byte comparison goes wrong:

  a difference is hidden: by a mask that swallows its position, by a tolerance that is too wide,
    or by comparing nothing at all and calling it a pass
  a legitimate variation fails: a timestamp, a last-digit rounding, a span of another length
  a missing or empty output counts as a match
  a version number or an integer is treated as a number that may drift
  the comparator is broken and nothing notices

Run as a process, the way the review stage runs it.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "modernize" / "scripts" / "screen_parity.py"


def run(tmp_path: Path, cases: list[dict], files: dict[str, bytes], **top: object) -> tuple[int, dict | None, str]:
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    (tmp_path / "cases.json").write_text(json.dumps({"cases": cases, **top}), encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), str(tmp_path / "cases.json")], capture_output=True, text=True)
    out = tmp_path / "PARITY.json"
    return proc.returncode, (json.loads(out.read_text(encoding="utf-8")) if out.exists() else None), proc.stderr


def case(cid: str = "P01", **extra: object) -> dict:
    return {"id": cid, "legacy": f"{cid}.old", "new": f"{cid}.new", **extra}


def pair(cid: str, old: bytes, new: bytes) -> dict[str, bytes]:
    return {f"{cid}.old": old, f"{cid}.new": new}


def state(pack: dict, cid: str = "P01") -> str:
    return next(c["state"] for c in pack["cases"] if c["id"] == cid)


def test_identical_output_is_parity(tmp_path):
    code, pack, _ = run(tmp_path, [case()], pair("P01", b"a,b\n1,2\n", b"a,b\n1,2\n"))
    assert code == 0 and pack["verdict"] == "PARITY" and state(pack) == "same"
    assert pack["selfCheck"]["passed"]


def test_one_byte_difference_fails_and_says_where(tmp_path):
    code, pack, _ = run(tmp_path, [case()], pair("P01", b"total=100\n", b"total=101\n"))
    assert code == 1 and state(pack) == "differs"
    assert pack["cases"][0]["firstDifference"]["offset"] == 8


def test_length_difference_fails(tmp_path):
    code, pack, _ = run(tmp_path, [case()], pair("P01", b"abc", b"abcd"))
    assert code == 1 and state(pack) == "differs"


def test_missing_file_is_never_a_pass(tmp_path):
    code, pack, _ = run(tmp_path, [case()], {"P01.old": b"x"})
    assert code == 1 and state(pack) == "missing"
    assert pack["counts"]["same"] == 0


def test_path_leaving_the_folder_is_missing(tmp_path):
    (tmp_path.parent / "outside.txt").write_bytes(b"x")
    code, pack, _ = run(tmp_path, [{"id": "P01", "legacy": "../outside.txt", "new": "../outside.txt"}], {})
    assert code == 1 and state(pack) == "missing"


def test_only_empty_outputs_do_not_pass(tmp_path):
    code, pack, _ = run(tmp_path, [case()], pair("P01", b"", b""))
    assert code == 1
    assert "every compared output was empty" in pack["problems"]


def test_no_case_compared_is_a_failure_not_a_pass(tmp_path):
    code, pack, _ = run(tmp_path, [case("P01"), case("P02")], {})
    assert code == 1 and "no case was compared" in pack["problems"]


def test_mask_by_bytes_hides_a_timestamp_but_not_the_rest(tmp_path):
    cases = [case(mask=[{"bytes": "0-18", "why": "run timestamp"}])]
    same = pair("P01", b"2026-01-01 10:00:00 total=5", b"2027-02-02 11:11:11 total=5")
    code, pack, _ = run(tmp_path, cases, same)
    assert code == 0 and pack["cases"][0]["masked"] == ["bytes (run timestamp)"]
    code, pack, _ = run(tmp_path, cases, pair("P01", b"2026-01-01 10:00:00 total=5", b"2027-02-02 11:11:11 total=6"))
    assert code == 1 and state(pack) == "differs"


def test_mask_by_regex_allows_a_span_of_another_length(tmp_path):
    cases = [case(mask=[{"regex": r"id=\d+", "why": "generated id"}])]
    code, pack, _ = run(tmp_path, cases, pair("P01", b"id=7 ok", b"id=12345 ok"))
    assert code == 0 and state(pack) == "same"


def test_mask_does_not_hide_where_a_difference_is(tmp_path):
    # the marker keeps the position, so moving the same text elsewhere is still a difference
    cases = [case(mask=[{"regex": r"id=\d+", "why": "generated id"}])]
    code, pack, _ = run(tmp_path, cases, pair("P01", b"id=7 ok", b"ok id=7"))
    assert code == 1 and state(pack) == "differs"


def test_overlapping_masks_cost_one_marker(tmp_path):
    cases = [case(mask=[{"bytes": "0-5", "why": "a"}, {"bytes": "3-8", "why": "b"}])]
    code, _, _ = run(tmp_path, cases, pair("P01", b"AAAAAAAAA tail", b"BBBBBBBBB tail"))
    assert code == 0


@pytest.mark.parametrize("mask", [
    {"bytes": "0-3"},                           # no reason
    {"bytes": "0-3", "regex": "x", "why": "w"},  # both kinds
    {"bytes": "5-2", "why": "w"},               # reversed range
    {"regex": "(", "why": "w"},                 # not a regex
])
def test_a_bad_mask_is_refused_not_ignored(tmp_path, mask):
    code, pack, err = run(tmp_path, [case(mask=[mask])], pair("P01", b"abcdef", b"abcdef"))
    assert code == 2 and pack is None and err


def test_tolerance_accepts_last_digit_rounding(tmp_path):
    cases = [case(tolerance={"rel": 1e-9, "why": "last-digit rounding"})]
    code, pack, _ = run(tmp_path, cases, pair("P01", b"rate=0.1234567890 n=3", b"rate=0.1234567891 n=3"))
    assert code == 0 and state(pack) == "same"
    assert pack["cases"][0]["detail"]["largestRelativeDifference"] > 0


def test_tolerance_does_not_cover_a_real_difference(tmp_path):
    cases = [case(tolerance={"rel": 1e-9, "why": "rounding"})]
    code, pack, _ = run(tmp_path, cases, pair("P01", b"rate=0.1234", b"rate=0.1235"))
    assert code == 1 and state(pack) == "differs"


def test_tolerance_never_applies_to_integers_or_versions(tmp_path):
    cases = [case(tolerance={"rel": 0.01, "why": "rounding"})]
    code, pack, _ = run(tmp_path, cases, pair("P01", b"count=1000", b"count=1001"))
    assert code == 1
    code, pack, _ = run(tmp_path, cases, pair("P01", b"v1.2.3", b"v1.2.4"))
    assert code == 1


def test_tolerance_does_not_hide_a_changed_number_of_numbers(tmp_path):
    cases = [case(tolerance={"rel": 1e-9, "why": "rounding"})]
    code, _, _ = run(tmp_path, cases, pair("P01", b"1.5 2.5", b"1.5"))
    assert code == 1


@pytest.mark.parametrize("tol", [
    {"rel": 0.5, "why": "w"},          # wider than 1%
    {"abs": 0.01, "why": "w"},         # wider than 1e-6
    {"rel": 1e-9},                     # no reason
    {"rel": 0, "abs": 0, "why": "w"},  # nothing allowed is not a tolerance
    {"rel": "x", "why": "w"},
])
def test_a_tolerance_that_hides_a_real_difference_is_refused(tmp_path, tol):
    code, pack, _ = run(tmp_path, [case(tolerance=tol)], pair("P01", b"1.0", b"1.0"))
    assert code == 2 and pack is None


def test_default_tolerance_applies_to_every_case(tmp_path):
    files = {**pair("P01", b"0.1000000000", b"0.1000000001"), **pair("P02", b"0.1000000000", b"0.1000000001")}
    code, pack, _ = run(tmp_path, [case("P01"), case("P02")], files, tolerance={"rel": 1e-8, "why": "rounding"})
    assert code == 0 and pack["counts"]["same"] == 2


def test_an_approved_difference_passes_but_is_still_listed(tmp_path):
    cases = [case(approvedDifference="the legacy rounding was a defect; the owner agreed to the fix")]
    code, pack, _ = run(tmp_path, cases + [case("P02")], {**pair("P01", b"1", b"2"), **pair("P02", b"x", b"x")})
    assert code == 0 and state(pack) == "differs-approved"
    assert pack["counts"]["differs-approved"] == 1 and "firstDifference" in pack["cases"][0]


def test_an_approval_without_a_reason_is_refused(tmp_path):
    code, pack, _ = run(tmp_path, [case(approvedDifference="  ")], pair("P01", b"1", b"2"))
    assert code == 2 and pack is None


def test_a_missing_case_is_not_approved_away(tmp_path):
    code, pack, _ = run(tmp_path, [case(approvedDifference="accepted")], {"P01.old": b"x"})
    assert code == 1 and state(pack) == "missing"


def test_one_failing_case_fails_the_run(tmp_path):
    files = {**pair("P01", b"a", b"a"), **pair("P02", b"a", b"b")}
    code, pack, _ = run(tmp_path, [case("P01"), case("P02")], files)
    assert code == 1 and pack["counts"] == {"same": 1, "differs": 1, "differs-approved": 0, "missing": 0}


def test_duplicate_or_missing_ids_are_refused(tmp_path):
    code, pack, _ = run(tmp_path, [case("P01"), case("P01")], pair("P01", b"a", b"a"))
    assert code == 2 and pack is None


@pytest.mark.parametrize("body", ["not json", "[]", '{"cases": []}'])
def test_unusable_input_exits_2(tmp_path, body):
    path = tmp_path / "cases.json"
    path.write_text(body, encoding="utf-8")
    proc = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
    assert proc.returncode == 2 and not (tmp_path / "PARITY.json").exists()


def test_writes_only_the_result_file(tmp_path):
    run(tmp_path, [case()], pair("P01", b"a", b"a"))
    assert sorted(p.name for p in tmp_path.iterdir()) == ["P01.new", "P01.old", "PARITY.json", "cases.json"]


def test_self_check_catches_a_broken_comparator():
    sys.path.insert(0, str(SCRIPT.parent))
    import screen_parity as sp

    original = sp.compare_bytes
    try:
        sp.compare_bytes = lambda a, b, tol: (True, {})  # a comparator that says everything matches
        ok, note = sp.self_check([{"_masked": (b"abc", b"abc")}])
    finally:
        sp.compare_bytes = original
    assert not ok and "not detected" in note
