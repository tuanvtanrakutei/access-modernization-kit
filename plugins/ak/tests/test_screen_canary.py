"""A green suite proves nothing until it is known to be able to fail (`screen_canary.py`).

The tests are the ways a canary lies:

  a break that stops the tests from running is read as "the tests caught it"
  a break no test depends on is read as fine
  a red baseline makes any later failure look like a catch
  the break leaks into the real code, or is applied to the wrong place
  a stale result file from an earlier run is read as this run's

Run as a process, the way the test stage runs it, against a real pytest run in a scratch project.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "modernize" / "scripts" / "screen_canary.py"

MODULE = "def total(qty, price):\n    return round(qty * price, 2)\n\n\ndef unused(x):\n    return x + 1\n"
TESTS = "from mod import total\n\n\ndef test_total():\n    assert total(3, 1.5) == 4.5\n"
CMD = f'"{sys.executable}" -m pytest -q -p no:cacheprovider'


def project(tmp_path: Path, module: str = MODULE, tests: str = TESTS) -> Path:
    root = tmp_path / "code"
    root.mkdir()
    (root / "mod.py").write_text(module, encoding="utf-8", newline="\n")
    (root / "test_mod.py").write_text(tests, encoding="utf-8", newline="\n")
    return root


def canary(tmp_path: Path, root: Path, find: str, replace: str, cmd: str = CMD, *extra: str) -> tuple[int, dict | None, str]:
    out = tmp_path / "CANARY.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--file", "mod.py", "--find", find, "--replace", replace,
         "--cmd", cmd, "--out", str(out), *extra],
        capture_output=True, text=True,
    )
    return proc.returncode, (json.loads(out.read_text(encoding="utf-8")) if out.exists() else None), proc.stderr


def test_a_break_the_tests_notice_is_caught(tmp_path):
    root = project(tmp_path)
    code, pack, _ = canary(tmp_path, root, "qty * price", "qty * price + 1")
    assert code == 0 and pack["verdict"] == "CAUGHT"
    assert pack["clean"]["counts"]["passed"] == 1 and pack["broken"]["counts"]["failed"] == 1
    assert pack["break"]["line"] == 2


def test_a_break_no_test_depends_on_survives(tmp_path):
    root = project(tmp_path)
    code, pack, _ = canary(tmp_path, root, "x + 1", "x + 2")
    assert code == 1 and pack["verdict"] == "SURVIVED"


def test_a_break_that_stops_the_tests_running_is_inconclusive_not_caught(tmp_path):
    root = project(tmp_path)
    code, pack, _ = canary(tmp_path, root, "return round(", "return (((round(")
    assert code == 1 and pack["verdict"] == "INCONCLUSIVE"
    assert pack["broken"]["counts"]["errors"] >= 1 and "errored" in pack["why"]


def test_a_red_baseline_proves_nothing(tmp_path):
    root = project(tmp_path, tests=TESTS.replace("4.5", "9.9"))
    code, pack, _ = canary(tmp_path, root, "qty * price", "qty * price + 1")
    assert code == 1 and pack["verdict"] == "NO BASELINE" and pack["broken"]["state"] == "skipped"


def test_a_run_that_executed_no_test_is_not_green(tmp_path):
    root = project(tmp_path, tests="def helper():\n    pass\n")
    code, pack, _ = canary(tmp_path, root, "qty * price", "qty * price + 1")
    assert code == 1 and pack["verdict"] == "NO BASELINE"


def test_the_real_code_is_never_written(tmp_path):
    root = project(tmp_path)
    before = {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()}
    canary(tmp_path, root, "qty * price", "qty * price + 1")
    assert {p.name: p.read_bytes() for p in root.iterdir() if p.is_file()} == before
    assert not (root / "__pycache__").exists()


def test_the_scratch_copy_is_removed_unless_kept(tmp_path):
    root = project(tmp_path)
    _, pack, _ = canary(tmp_path, root, "qty * price", "qty * price + 1")
    assert "scratch" not in pack
    _, pack, _ = canary(tmp_path, root, "qty * price", "qty * price + 1", CMD, "--keep")
    kept = Path(pack["scratch"])
    try:
        assert "+ 1" in (kept / "copy" / "mod.py").read_text(encoding="utf-8")
    finally:
        import shutil
        shutil.rmtree(kept, ignore_errors=True)


def test_find_must_occur_exactly_once(tmp_path):
    root = project(tmp_path, module=MODULE + "\n\ndef again(a):\n    return a + 1\n")
    code, pack, err = canary(tmp_path, root, "+ 1", "+ 9")
    assert code == 2 and pack is None and "2 times" in err
    code, pack, err = canary(tmp_path, root, "nowhere", "x")
    assert code == 2 and "0 times" in err


def test_a_file_outside_the_root_is_refused(tmp_path):
    root = project(tmp_path)
    (tmp_path / "other.py").write_text("x = 1\n", encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--file", "../other.py", "--find", "x = 1", "--replace", "x = 2",
         "--cmd", CMD, "--out", str(tmp_path / "CANARY.json")], capture_output=True, text=True)
    assert proc.returncode == 2


def test_a_no_op_break_is_refused(tmp_path):
    root = project(tmp_path)
    code, pack, _ = canary(tmp_path, root, "x + 1", "x + 1")
    assert code == 2 and pack is None


def test_a_timeout_is_inconclusive(tmp_path):
    root = project(tmp_path)
    sleeper = f'"{sys.executable}" -c "import time; time.sleep(30)"'
    code, pack, _ = canary(tmp_path, root, "qty * price", "qty * price + 1", sleeper, "--timeout", "1")
    assert code == 1 and pack["verdict"] == "NO BASELINE" and pack["clean"]["state"] == "timeout"


def test_junit_is_read_and_a_stale_result_is_not(tmp_path):
    root = project(tmp_path)
    stale = root / "results.xml"
    stale.write_text('<testsuite tests="9" failures="0" errors="0" skipped="0"/>', encoding="utf-8")
    cmd = f'{CMD} --junitxml=results.xml'
    code, pack, _ = canary(tmp_path, root, "qty * price", "qty * price + 1", cmd, "--junit", "results.xml")
    assert code == 0 and pack["verdict"] == "CAUGHT"
    assert pack["clean"]["counts"]["passed"] == 1  # not the stale 9
    # a command that writes no result file leaves nothing to read: nothing is invented
    code, pack, _ = canary(tmp_path, root, "qty * price", "qty * price + 1", CMD, "--junit", "never.xml")
    assert code == 1 and pack["verdict"] == "NO BASELINE" and pack["clean"]["counts"] is None


def test_a_runner_that_exits_zero_having_run_nothing_is_not_green(tmp_path):
    # pytest exits 5 when it finds no test; other runners exit 0, so the exit code alone is not enough
    root = project(tmp_path)
    quiet = f'"{sys.executable}" -c "print(0, \'failed\')"'
    code, pack, _ = canary(tmp_path, root, "qty * price", "qty * price + 1", quiet)
    assert code == 1 and pack["verdict"] == "NO BASELINE" and pack["clean"]["counts"]["passed"] == 0
