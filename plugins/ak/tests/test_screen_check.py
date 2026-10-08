"""Gate G4 run for every screen a project lists (`screen_check.py`).

The script runs the three verification scripts in order for each screen. The tests build a small
synthetic project (a Python module, pytest tests that cite rule ids, a second suite driven by a
plain command) and run the real scripts on it. The ways an orchestrator lies:

  a step that did not run reads like one that ran (no result, skipped canaries, a skipped suite)
  a red suite, or a suite that could not start, still ends in "ok"
  a waiver loses who accepted it on the way to G4
  a config the run cannot honour is half-run instead of refused
  the plan and the config disagree about the rules and nothing says so

Run as a process, the way the skill runs it.
"""
from __future__ import annotations

import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
SCRIPT = PACKAGE / "modernize" / "scripts" / "screen_check.py"

MODULE = '''\
def total(price, qty):
    if qty < 0:
        raise ValueError("negative quantity")
    return price * qty
'''

TESTS = '''\
import pytest
from shop import total


def test_multiplies():
    """BR-SHP-01: the total is price times quantity."""
    assert total(3, 4) == 12


def test_refuses_a_negative_quantity():
    """BR-SHP-02"""
    with pytest.raises(ValueError):
        total(3, -1)
'''

# A second suite that is not pytest: it writes its own JUnit result and names a rule in a test name.
E2E = '''\
import sys
from pathlib import Path
out = Path(sys.argv[1])
ok = "{ok}"
case = '<testcase classname="e2e" name="BR-SHP-03 shows the total"/>' if ok == "yes" else \\
    '<testcase classname="e2e" name="BR-SHP-03 shows the total"><failure message="no"/></testcase>'
out.write_text('<testsuite tests="1">' + case + '</testsuite>', encoding="utf-8")
sys.exit(0 if ok == "yes" else 1)
'''


def project(tmp_path: Path, *, e2e_ok: bool = True) -> Path:
    root = tmp_path / "app"
    (root / "backend" / "tests").mkdir(parents=True)
    (root / "backend" / "shop.py").write_text(MODULE, encoding="utf-8")
    (root / "backend" / "conftest.py").write_text("", encoding="utf-8")
    (root / "backend" / "tests" / "test_shop.py").write_text(TESTS, encoding="utf-8")
    (root / "e2e").mkdir()
    (root / "e2e" / "run.py").write_text(E2E.replace("{ok}", "yes" if e2e_ok else "no"), encoding="utf-8")
    return root


def config(root: Path, **screen_overrides) -> dict:
    screen = {
        "key": "shop", "screen": "Shop",
        "rules": ["BR-SHP-01", "BR-SHP-02"],
        "tests": {"backend": ["tests/test_shop.py"]},
        "canaries": [{"suite": "backend", "rule": "BR-SHP-01", "file": "shop.py",
                      "find": "return price * qty", "replace": "return price + qty"}],
    }
    screen.update(screen_overrides)
    return {
        "root": ".",
        "suites": {
            "backend": {"preset": "pytest", "root": "backend"},
            "e2e": {"root": "e2e", "command": ["{python}", "run.py", "{junit}", "{tests}"],
                    "canary_command": ["{python}", "run.py", "out.xml", "{tests}"]},
        },
        "screens": [screen],
    }


def check(root: Path, cfg: dict, *extra: str) -> tuple[int, dict | None, str]:
    path = root / "screen_check.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    results = root.parent / "results"
    proc = subprocess.run([sys.executable, str(SCRIPT), "--config", str(path), "--results-dir", str(results), *extra],
                          capture_output=True, text=True, encoding="utf-8")
    summary = results / "summary.json"
    outcome = json.loads(summary.read_text(encoding="utf-8"))[0] if summary.is_file() and proc.returncode != 2 else None
    return proc.returncode, outcome, proc.stdout + proc.stderr


def severities(outcome: dict) -> list[str]:
    return [f["severity"] for f in outcome["findings"]]


def test_a_screen_whose_tests_back_every_rule_and_can_fail_passes(tmp_path):
    root = project(tmp_path)
    code, outcome, out = check(root, config(root))
    assert code == 0, out
    assert outcome["suites"] == {"backend": 0}
    assert outcome["canaries"] == [{"suite": "backend", "file": "shop.py", "rule": "BR-SHP-01", "state": "CAUGHT"}]
    assert outcome["findings"] == [] and outcome["errors"] == []
    for name in ("shop.backend.junit.xml", "shop.rule-tests.json", "shop.canary-backend-1.json", "shop.g4.json"):
        assert (tmp_path / "results" / name).is_file(), name


def test_a_canary_the_tests_do_not_notice_fails_the_screen(tmp_path):
    root = project(tmp_path)
    survived = [{"suite": "backend", "file": "shop.py", "find": 'raise ValueError("negative quantity")',
                 "replace": 'raise ValueError("a negative quantity")'}]
    code, outcome, _ = check(root, config(root, canaries=survived))
    assert code == 1 and outcome["canaries"][0]["state"] == "SURVIVED" and "HIGH" in severities(outcome)


def test_skipping_the_canaries_needs_a_reason_and_g4_records_it_at_low(tmp_path):
    root = project(tmp_path)
    assert check(root, config(root), "--skip-canary", "  ")[0] == 2
    code, outcome, out = check(root, config(root), "--skip-canary", "a quick pass before review")
    assert code == 0, out
    assert severities(outcome) == ["LOW"] and "a quick pass before review" in outcome["findings"][0]["text"]
    assert not (tmp_path / "results" / "shop.canary-backend-1.json").exists()


def test_no_canary_listed_is_medium_not_a_pass(tmp_path):
    root = project(tmp_path)
    code, outcome, _ = check(root, config(root, canaries=[]))
    assert code == 1 and severities(outcome) == ["MEDIUM"] and "no canary" in outcome["findings"][0]["text"]


def test_a_rule_no_test_names_is_raised(tmp_path):
    root = project(tmp_path)
    code, outcome, _ = check(root, config(root, rules=["BR-SHP-01", "BR-SHP-02", "BR-SHP-09"]))
    assert code == 1 and any("BR-SHP-09" in f["text"] and f["severity"] == "MEDIUM" for f in outcome["findings"])


def test_a_waiver_carries_its_reviewer_through_to_g4(tmp_path):
    root = project(tmp_path)
    rules = ["BR-SHP-01", "BR-SHP-02", "BR-SHP-09"]
    named = {"BR-SHP-09": {"reason": "owned by another screen", "by": "Person One", "on": "2026-10-08"}}
    code, outcome, out = check(root, config(root, rules=rules, waive=named))
    assert code == 0, out
    assert severities(outcome) == ["LOW"] and "Person One on 2026-10-08" in outcome["findings"][0]["text"]
    code, outcome, _ = check(root, config(root, rules=rules, waive={"BR-SHP-09": "owned by another screen"}))
    assert code == 1 and severities(outcome) == ["MEDIUM"] and "no reviewer and no date" in outcome["findings"][0]["text"]


@pytest.mark.parametrize("waive", [
    {"BR-SHP-77": "not a rule of this screen"},
    {"BR-SHP-02": {"reason": " "}},
    {"BR-SHP-02": {"reason": "r", "on": "08/10/2026"}},
    {"BR-SHP-02": {"reason": "r", "by": ""}},
    {"BR-SHP-02": {"reason": "r", "by": "a;b"}},
    {"BR-SHP-02": {"reason": "r", "who": "x"}},
])
def test_a_waiver_the_run_cannot_honour_stops_it(tmp_path, waive):
    root = project(tmp_path)
    code, _, out = check(root, config(root, waive=waive))
    assert code == 2 and "waive" in out


def test_a_second_suite_is_read_together_with_the_first(tmp_path):
    root = project(tmp_path)
    cfg = config(root, rules=["BR-SHP-01", "BR-SHP-02", "BR-SHP-03"],
                 tests={"backend": ["tests/test_shop.py"], "e2e": ["shop"]})
    code, outcome, out = check(root, cfg)
    assert code == 0, out
    assert outcome["suites"] == {"backend": 0, "e2e": 0}


def test_a_red_suite_fails_the_screen_even_when_g4_has_nothing_to_say(tmp_path):
    root = project(tmp_path, e2e_ok=False)
    cfg = config(root, rules=["BR-SHP-01", "BR-SHP-02"], tests={"backend": ["tests/test_shop.py"], "e2e": ["shop"]})
    code, outcome, out = check(root, cfg)
    assert code == 1 and outcome["suites"]["e2e"] == 1
    assert any("suite e2e exited 1" in e for e in outcome["errors"]) and "FAIL" in out


def test_a_skipped_suite_is_said_and_the_rule_only_it_proves_is_not_tested(tmp_path):
    root = project(tmp_path)
    cfg = config(root, rules=["BR-SHP-01", "BR-SHP-02", "BR-SHP-03"],
                 tests={"backend": ["tests/test_shop.py"], "e2e": ["shop"]})
    code, outcome, _ = check(root, cfg, "--skip-suite", "e2e")
    assert code == 1 and outcome["suites"]["e2e"] == "skipped"
    assert any("BR-SHP-03" in f["text"] for f in outcome["findings"])


def test_a_taken_port_stops_the_suite_that_needs_it(tmp_path):
    root = project(tmp_path)
    cfg = config(root)
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen()
        cfg["suites"]["backend"]["port"] = server.getsockname()[1]
        code, outcome, _ = check(root, cfg)
    assert code == 1 and outcome["suites"]["backend"] == "unavailable"
    assert any("in use" in e for e in outcome["errors"])


def test_a_missing_requirement_names_the_reason(tmp_path):
    root = project(tmp_path)
    cfg = config(root)
    cfg["suites"]["backend"]["requires"] = {"node_modules/x/cli.js": "the packages are not installed"}
    code, outcome, _ = check(root, cfg)
    assert code == 1 and outcome["suites"]["backend"] == "unavailable"
    assert any("the packages are not installed" in e for e in outcome["errors"])


def test_a_failing_preflight_stops_the_run_with_its_output(tmp_path):
    root = project(tmp_path)
    cfg = config(root)
    cfg["preflight"] = [sys.executable, "-c", "import sys; print('no database at localhost'); sys.exit(3)"]
    code, outcome, out = check(root, cfg)
    assert code == 2 and outcome is None and "no database at localhost" in out


PLAN = """# Shop

## 5. Legacy-To-New Mapping

| Rule | Legacy | New | Evidence |
|---|---|---|---|
| BR-SHP-01 (BF BR-01) | total | total() | E1 |
| BR-SHP-02 (BF BR-02) | negative | ValueError | E2 |
"""


def test_the_plan_and_the_config_must_agree_on_the_rules(tmp_path):
    root = project(tmp_path)
    plan = root / "plan.md"
    plan.write_text(PLAN, encoding="utf-8")
    code, outcome, out = check(root, config(root, plan="plan.md"))
    assert code == 0 and outcome["plan"] == "matches", out
    plan.write_text(PLAN.replace("| BR-SHP-02 (BF BR-02) | negative | ValueError | E2 |\n", ""), encoding="utf-8")
    code, outcome, _ = check(root, config(root, plan="plan.md"))
    assert code == 1 and outcome["plan"] == "differs" and any("BR-SHP-02" in e for e in outcome["errors"])


def test_a_plan_that_is_not_on_disk_is_noted_not_failed(tmp_path):
    root = project(tmp_path)
    code, outcome, out = check(root, config(root, plan="docs/missing.md"))
    assert code == 0 and outcome["plan"] == "skipped" and "not on disk" in out


@pytest.mark.parametrize("breakage, words", [
    (lambda c: c["screens"][0].update(key="a b"), "screen key"),
    (lambda c: c["screens"].append(dict(c["screens"][0])), "repeat"),
    (lambda c: c["screens"][0].update(tests={"web": ["x"]}), "does not define"),
    (lambda c: c["screens"][0].update(rules=[]), "rules"),
    (lambda c: c["screens"][0].update(colour="blue"), "unknown fields"),
    (lambda c: c["suites"]["backend"].update(preset="maven"), "unknown preset"),
    (lambda c: c["suites"]["e2e"].update(command=["{python}", "run.py", "{tests}"]), "junit"),
    (lambda c: c["suites"]["e2e"].update(root="nowhere"), "not a folder"),
    (lambda c: c["screens"][0]["canaries"][0].update(suite="e2e"), "no tests for this screen"),
    (lambda c: c["screens"][0]["canaries"][0].update(replace="return price * qty"), "same text"),
])
def test_a_config_the_run_cannot_honour_is_refused_before_anything_runs(tmp_path, breakage, words):
    root = project(tmp_path)
    cfg = config(root)
    breakage(cfg)
    code, outcome, out = check(root, cfg)
    assert code == 2 and outcome is None and words in out, out


def test_unknown_screen_and_suite_names_are_refused(tmp_path):
    root = project(tmp_path)
    assert check(root, config(root), "--screen", "nope")[0] == 2
    assert check(root, config(root), "--skip-suite", "nope")[0] == 2


def test_a_suite_that_passes_but_writes_no_result_is_an_error_not_a_pass(tmp_path):
    root = project(tmp_path)
    cfg = config(root, tests={"backend": ["tests/test_shop.py"], "e2e": ["shop"]})
    # exits 0, names {junit} only in a variable nothing reads, so no result file appears
    cfg["suites"]["e2e"] = {"root": "e2e", "command": ["{python}", "-c", "pass", "{tests}"], "env": {"UNUSED": "{junit}"}}
    code, outcome, _ = check(root, cfg)
    assert code == 1 and outcome["suites"]["e2e"] == 0
    assert any("suite e2e wrote no JUnit result" in e for e in outcome["errors"])


# A runner that, like a test container, gets its folder as {root} and writes its result inside it.
IN_ROOT = '''\
import os, sys
from pathlib import Path
here = Path(sys.argv[1])
if not here.is_dir():
    sys.exit(f"{here} is not a folder: the placeholder was not filled")
case = '<testcase classname="e2e" name="BR-SHP-03 shows the total"/>'
(here / "out" / "result.xml").parent.mkdir(exist_ok=True)
(here / "out" / "result.xml").write_text('<testsuite tests="1">' + case + '</testsuite>', encoding="utf-8")
'''


def container_like(root: Path, cfg: dict) -> dict:
    (root / "e2e" / "in_root.py").write_text(IN_ROOT, encoding="utf-8")
    cfg["suites"]["e2e"] = {"root": "e2e", "command": ["{python}", "in_root.py", "{root}", "{tests}"],
                            "junit_file": "out/result.xml"}
    cfg["screens"][0]["rules"] = ["BR-SHP-01", "BR-SHP-02", "BR-SHP-03"]
    cfg["screens"][0]["tests"] = {"backend": ["tests/test_shop.py"], "e2e": ["shop"]}
    return cfg


def test_a_result_written_inside_the_suite_folder_is_read_and_moved_out_of_the_code(tmp_path):
    root = project(tmp_path)
    code, outcome, out = check(root, container_like(root, config(root)))
    assert code == 0, out
    assert outcome["suites"]["e2e"] == 0
    assert (tmp_path / "results" / "shop.e2e.junit.xml").is_file()
    assert not (root / "e2e" / "out" / "result.xml").exists()


def test_a_stale_result_inside_the_suite_folder_is_not_read(tmp_path):
    root = project(tmp_path)
    cfg = container_like(root, config(root))
    (root / "e2e" / "out").mkdir()
    (root / "e2e" / "out" / "result.xml").write_text('<testsuite tests="1"><testcase classname="e2e" name="BR-SHP-03 x"/></testsuite>',
                                                    encoding="utf-8")
    cfg["suites"]["e2e"]["command"] = ["{python}", "-c", "pass", "{tests}"]  # writes nothing this time
    code, outcome, _ = check(root, cfg)
    assert code == 1 and any("suite e2e wrote no JUnit result" in e for e in outcome["errors"])


@pytest.mark.parametrize("change, words", [
    ({"junit_file": "/abs/result.xml"}, "under the suite's root"),
    ({"junit_file": "../result.xml"}, "under the suite's root"),
    ({"junit_file": "r.xml", "command": ["{python}", "run.py", "{junit}", "{tests}"]}, "not both"),
])
def test_a_junit_file_the_run_cannot_use_is_refused(tmp_path, change, words):
    root = project(tmp_path)
    cfg = config(root)
    cfg["suites"]["e2e"].update(change)
    code, _, out = check(root, cfg)
    assert code == 2 and words in out, out


def test_preflight_commands_run_in_order_and_the_first_failure_stops_the_run(tmp_path):
    root = project(tmp_path)
    cfg = config(root)
    marker = root / "first-ran.txt"
    cfg["preflight"] = [[sys.executable, "-c", f"open(r'{marker}', 'w').write('1')"],
                        [sys.executable, "-c", "import sys; print('image build failed'); sys.exit(4)"],
                        [sys.executable, "-c", "raise SystemExit('the third must not run')"]]
    code, outcome, out = check(root, cfg)
    assert code == 2 and outcome is None and marker.is_file()
    assert "image build failed" in out and "the third must not run" not in out


@pytest.mark.parametrize("context", [{"dir": ".", "colour": "x"}, {"forbid": "docs"}, "."])
def test_a_context_block_the_run_cannot_use_is_refused(tmp_path, context):
    root = project(tmp_path)
    cfg = config(root)
    cfg["context"] = context
    code, _, out = check(root, cfg)
    assert code == 2 and "context" in out, out


def _docker_linux() -> bool:
    import shutil as _sh
    if not _sh.which("docker"):
        return False
    done = subprocess.run(["docker", "info", "--format", "{{.OSType}}"], capture_output=True, text=True)
    return done.returncode == 0 and done.stdout.strip() == "linux"


@pytest.mark.skipif(not _docker_linux(), reason="needs a Docker engine that builds Linux stages")
def test_a_build_context_that_holds_a_refused_folder_stops_the_run_before_any_test(tmp_path):
    root = project(tmp_path)
    (root / "docs" / "input").mkdir(parents=True)
    (root / "docs" / "input" / "customer.mdb").write_bytes(b"\0")
    cfg = config(root)
    cfg["context"] = {"dir": ".", "forbid": ["docs"]}
    code, outcome, out = check(root, cfg)
    assert code == 2 and outcome is None and "docs/input/customer.mdb" in out, out
    (root / ".dockerignore").write_text("docs\n", encoding="utf-8")
    code, outcome, out = check(root, cfg)
    assert code == 0, out


# ---- a suite that runs against a started service (up / ready / down)

SERVE = '''\
import pathlib, subprocess, sys
# starts a small web server in the background, as `docker run -d` would, and returns
port, here = sys.argv[1], pathlib.Path(__file__).parent
with open(here / "log.txt", "a") as log:
    log.write("up" + chr(10))
proc = subprocess.Popen([sys.executable, "-m", "http.server", port, "--bind", "127.0.0.1"], cwd=here,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
(here / "pid.txt").write_text(str(proc.pid))
'''

STOP = '''\
import os, pathlib, signal, sys
here = pathlib.Path(__file__).parent
with open(here / "log.txt", "a") as log:
    log.write("down" + chr(10))
pid = here / "pid.txt"
if pid.exists():
    os.kill(int(pid.read_text()), signal.SIGTERM)
    pid.unlink()
'''

AGAINST = '''\
import sys, urllib.request
from pathlib import Path
out, url = Path(sys.argv[1]), sys.argv[2]
urllib.request.urlopen(url, timeout=5).read()  # fails the suite when nothing serves the url
out.write_text('<testsuite tests="1"><testcase classname="e2e" name="BR-SHP-03 shows the total"/></testsuite>', encoding="utf-8")
'''


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def served(root: Path, two_screens: bool = False, ready: bool = True) -> dict:
    svc = root / "svc"
    svc.mkdir(exist_ok=True)
    (svc / "serve.py").write_text(SERVE, encoding="utf-8")
    (svc / "stop.py").write_text(STOP, encoding="utf-8")
    (svc / "against.py").write_text(AGAINST, encoding="utf-8")
    port = free_port()
    cfg = config(root, rules=["BR-SHP-01", "BR-SHP-02", "BR-SHP-03"],
                 tests={"backend": ["tests/test_shop.py"], "image": ["shop"]})
    cfg["suites"]["image"] = {
        "root": "svc", "port": port,
        "up": [sys.executable, "svc/serve.py", str(port)],
        "down": [sys.executable, "svc/stop.py"],
        "command": ["{python}", "against.py", "{junit}", f"http://127.0.0.1:{port}/", "{tests}"],
    }
    if ready:
        cfg["suites"]["image"]["ready"] = {"url": f"http://127.0.0.1:{port}/", "timeout": 30}
    if two_screens:
        other = dict(cfg["screens"][0], key="shop-2", screen="Shop2")
        cfg["screens"].append(other)
    return cfg


def test_a_service_is_started_once_for_every_screen_and_stopped_after(tmp_path):
    root = project(tmp_path)
    cfg = served(root, two_screens=True)
    path = root / "screen_check.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    results = tmp_path / "results"
    proc = subprocess.run([sys.executable, str(SCRIPT), "--config", str(path), "--results-dir", str(results)],
                          capture_output=True, text=True, encoding="utf-8")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    summary = json.loads((results / "summary.json").read_text(encoding="utf-8"))
    assert [o["suites"]["image"] for o in summary] == [0, 0]
    assert (root / "svc" / "log.txt").read_text().split() == ["up", "down"]


def test_a_service_that_does_not_start_makes_its_suite_unavailable_and_is_still_stopped(tmp_path):
    root = project(tmp_path)
    cfg = served(root)
    cfg["suites"]["image"]["up"] = [[sys.executable, "svc/serve.py", "1"], [sys.executable, "-c", "import sys; print('pull denied'); sys.exit(5)"]]
    code, outcome, out = check(root, cfg)
    assert code == 1 and outcome["suites"]["image"] == "unavailable"
    assert any("pull denied" in e for e in outcome["errors"])
    assert (root / "svc" / "log.txt").read_text().split() == ["up", "down"]


def test_a_service_that_never_answers_is_a_timeout_not_a_red_suite(tmp_path):
    root = project(tmp_path)
    cfg = served(root)
    cfg["suites"]["image"]["up"] = [sys.executable, "-c", "pass"]  # starts nothing
    cfg["suites"]["image"]["ready"]["timeout"] = 3
    code, outcome, _ = check(root, cfg)
    assert code == 1 and outcome["suites"]["image"] == "unavailable"
    assert any("did not answer within 3 s" in e for e in outcome["errors"])


def test_a_stop_that_fails_is_said(tmp_path):
    root = project(tmp_path)
    cfg = served(root)
    cfg["suites"]["image"]["down"] = [[sys.executable, "svc/stop.py"], [sys.executable, "-c", "import sys; sys.exit(3)"]]
    code, outcome, _ = check(root, cfg)
    assert code == 1 and any("may still be running" in e for e in outcome["errors"])


@pytest.mark.parametrize("change, words", [
    (lambda s: s.update(ready={"url": "localhost:1", "timeout": 5}), "ready"),
    (lambda s: s.update(ready={"url": "http://x/", "timeout": 0}), "ready"),
    (lambda s: (s.pop("up"), s.pop("down")), "no `up`"),
    (lambda s: s.update(up="docker run x"), "`up` must be a command"),
])
def test_a_service_block_the_run_cannot_use_is_refused(tmp_path, change, words):
    root = project(tmp_path)
    cfg = served(root)
    change(cfg["suites"]["image"])
    code, _, out = check(root, cfg)
    assert code == 2 and words in out, out


def test_a_canary_on_a_suite_with_a_service_is_refused(tmp_path):
    root = project(tmp_path)
    cfg = served(root)
    cfg["screens"][0]["canaries"].append({"suite": "image", "file": "against.py", "find": "timeout=5", "replace": "timeout=6"})
    code, _, out = check(root, cfg)
    assert code == 2 and "rebuilt image" in out, out


def test_waiting_for_a_service_treats_a_server_error_as_not_ready_and_a_404_as_ready():
    import http.server
    import threading
    sys.path.insert(0, str(SCRIPT.parent))
    import screen_check as sc

    class Answer(http.server.BaseHTTPRequestHandler):
        code = 503

        def do_GET(self):
            self.send_response(Answer.code)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Answer)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    try:
        why = sc.wait_ready(url, 3)
        assert why is not None and "HTTP 503" in why  # still starting: a 5xx is not an answer
        Answer.code = 404
        assert sc.wait_ready(url, 3) is None  # up, even if the path is not served
    finally:
        server.shutdown()
