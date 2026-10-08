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


def test_a_same_length_break_on_a_file_just_written_is_not_hidden_by_a_bytecode_cache(tmp_path):
    # Python's .pyc is keyed on the source's whole-second mtime and size. The baseline run caches the
    # untouched module; a break of the same length written in the same second used to be read from that
    # cache, so the tests passed and the canary SURVIVED. Seen on a fast CI runner, not on a slow machine.
    root = project(tmp_path)  # written just now, so the break lands in the same second when the run is fast
    _, pack, _ = canary(tmp_path, root, "qty * price", "qty / price", CMD, "--keep")
    kept = Path(pack["scratch"])
    try:
        assert pack["verdict"] == "CAUGHT", pack
        # the guarantee itself, independent of how fast this machine is
        assert (kept / "copy" / "mod.py").stat().st_mtime >= (root / "mod.py").stat().st_mtime + 2
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


# ---- a break that fails every test says nothing about the line; a link brings in what the copy skips

TWO_TESTS = (
    "from mod import total\n\n\n"
    "def test_a():\n    assert total(3, 1.5) == 4.5\n\n\n"
    "def test_b():\n    assert total(2, 2) == 4\n"
)


def test_a_break_that_fails_every_test_is_inconclusive_not_caught(tmp_path):
    root = project(tmp_path, tests=TWO_TESTS)
    code, pack, _ = canary(tmp_path, root, "qty * price", "qty * price + 1")
    assert code == 1 and pack["verdict"] == "INCONCLUSIVE" and "all 2 tests failed" in pack["why"]
    assert pack["broken"]["counts"]["failed"] == 2


def test_a_break_that_fails_some_tests_is_still_caught(tmp_path):
    root = project(tmp_path, tests=TWO_TESTS + "\n\ndef test_c():\n    assert True\n")
    code, pack, _ = canary(tmp_path, root, "qty * price", "qty * price + 1")
    assert code == 0 and pack["verdict"] == "CAUGHT" and pack["broken"]["counts"]["passed"] == 1


def linked_project(tmp_path: Path) -> Path:
    root = tmp_path / "code"
    (root / "node_modules").mkdir(parents=True)
    (root / "node_modules" / "data.txt").write_text("x", encoding="utf-8")
    (root / "mod.py").write_text("VALUE = 1\n", encoding="utf-8")
    (root / "check.py").write_text(
        "import sys\n"
        "ok = open('node_modules/data.txt').read() == 'x' and 'VALUE = 1' in open('mod.py').read()\n"
        "print('1 passed' if ok else '1 failed')\n"
        "sys.exit(0 if ok else 1)\n",
        encoding="utf-8",
    )
    return root


def link_canary(tmp_path: Path, root: Path, *extra: str) -> tuple[int, dict | None, str]:
    out = tmp_path / "CANARY.json"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), "--file", "mod.py", "--find", "VALUE = 1", "--replace", "VALUE = 2",
         "--cmd", f'"{sys.executable}" check.py', "--out", str(out), *extra],
        capture_output=True, text=True)
    return proc.returncode, (json.loads(out.read_text(encoding="utf-8")) if out.exists() else None), proc.stderr


def test_a_link_brings_in_a_folder_the_copy_skips_and_never_touches_it(tmp_path):
    root = linked_project(tmp_path)
    code, pack, _ = link_canary(tmp_path, root)
    assert code == 1 and pack["verdict"] == "NO BASELINE"      # without the link the suite cannot run
    code, pack, _ = link_canary(tmp_path, root, "--link", "node_modules")
    assert code == 0 and pack["verdict"] == "CAUGHT" and "scratch" not in pack
    assert (root / "node_modules" / "data.txt").read_text(encoding="utf-8") == "x"   # the real folder is intact


def test_a_kept_scratch_copy_holds_a_link_not_a_second_copy(tmp_path):
    import os
    import shutil

    root = linked_project(tmp_path)
    _, pack, _ = link_canary(tmp_path, root, "--link", "node_modules", "--keep")
    kept = Path(pack["scratch"])
    try:
        assert os.path.lexists(kept / "copy" / "node_modules") and (kept / "copy" / "node_modules" / "data.txt").is_file()
    finally:
        # take the link out first, as the script does: rmtree must never reach the real folder
        link = kept / "copy" / "node_modules"
        os.unlink(link) if os.path.islink(link) else os.rmdir(link)
        shutil.rmtree(kept, ignore_errors=True)
    assert (root / "node_modules" / "data.txt").is_file()


def test_a_link_must_be_a_folder_under_the_root_that_the_copy_skips(tmp_path):
    root = linked_project(tmp_path)
    (tmp_path / "outside").mkdir()
    (root / "src").mkdir()
    for bad in ("../outside", "missing", "src"):
        code, pack, err = link_canary(tmp_path, root, "--link", bad)
        assert code == 2 and pack is None, bad


# ---- reading the runner's summary: one line, or several

def counts_of(output: str):
    sys.path.insert(0, str(SCRIPT.parent))
    import screen_canary as sc

    return sc.text_counts(output)


def test_a_playwright_summary_spread_over_lines_is_added_up():
    output = "\n".join([
        "Running 13 tests using 4 workers",
        "  1 failed",
        "    [chrome] > e2e/x.spec.ts:143:3 > a test whose title says it passed and failed",
        "  12 passed (47.5s)",
    ])
    assert counts_of(output) == {"failed": 1, "errors": 0, "passed": 12}


def test_a_playwright_summary_with_skipped_and_flaky_counts_only_what_it_knows():
    output = "  1 flaky\n    [chrome] > e2e/x.spec.ts:1:1 > a\n  12 passed (30s)\n  13 skipped\n"
    assert counts_of(output) == {"failed": 0, "errors": 0, "passed": 12}


def test_one_line_summaries_still_read_as_before():
    assert counts_of("collected 13 items\n=== 1 failed, 12 passed in 3.2s ===\n") == {"failed": 1, "errors": 0, "passed": 12}
    assert counts_of("1 failed, 12 passed in 3.2s\n") == {"failed": 1, "errors": 0, "passed": 12}
    assert counts_of("Tests:       2 failed, 10 passed, 12 total\n") == {"failed": 2, "errors": 0, "passed": 10}
    assert counts_of("12 passed (47.5s)\n") == {"failed": 0, "errors": 0, "passed": 12}
    assert counts_of("nothing countable here\n") is None


def test_a_title_that_mentions_a_count_is_not_a_summary_line():
    # an indented test title is not at the start of a count, so it adds nothing
    assert counts_of("  12 passed (1s)\n    [chrome] > x > the 3 failed rows are listed\n") == {"failed": 0, "errors": 0, "passed": 12}


RUN_IN_ROOT = '''\
import os, subprocess, sys
# stands in for `docker run -v {root}:/app`: the tests run in the folder the command was given
here = sys.argv[1]
if not os.path.isdir(here):
    sys.exit(f"{here!r} is not a folder: the placeholder was not filled")
sys.exit(subprocess.call([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], cwd=here))
'''


def test_root_in_the_command_is_the_scratch_copy_never_the_real_code(tmp_path):
    root = project(tmp_path)
    (root / "run_in.py").write_text(RUN_IN_ROOT, encoding="utf-8", newline="\n")
    cmd = f'"{sys.executable}" run_in.py "{{root}}"'
    code, pack, err = canary(tmp_path, root, "qty * price", "qty / price", cmd, "--keep")
    kept = Path(pack["scratch"])
    try:
        assert code == 0 and pack["verdict"] == "CAUGHT", (pack, err)
        assert pack["command"] == cmd  # the template is recorded, not one run's path
        assert "qty * price" in (root / "mod.py").read_text(encoding="utf-8")
    finally:
        import shutil
        shutil.rmtree(kept, ignore_errors=True)
    # pointed at the real code instead, the break is invisible: that is what the placeholder prevents
    code, pack, _ = canary(tmp_path, root, "qty * price", "qty / price", f'"{sys.executable}" run_in.py "{root}"')
    assert pack["verdict"] == "SURVIVED"
