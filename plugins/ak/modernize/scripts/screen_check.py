#!/usr/bin/env python3
"""Run gate G4 for the screens a project lists: tests, rule check, canaries, then G4, in that order.

    python3 screen_check.py --config <project config> [--screen KEY ...] [--skip-canary REASON]
        [--skip-suite NAME ...] [--results-dir DIR] [--timeout SECONDS]

`screen_rule_tests.py`, `screen_canary.py` and `screen_verify.py` each prove one thing. This script
runs them for each screen of a project, in the order Stage 4 needs, so a run that leaves a step out
says so instead of looking like one that did not:

  1. the plan check: where the screen plan is on disk, the rules the config lists must be the ids
     its mapping rows carry (`screen_rule_ids.py`); a list that has drifted is an error
  2. each suite the screen has tests in, with a JUnit result
  3. `screen_rule_tests.py` over every JUnit result of the screen, with the waivers and the coverage map
  4. `screen_canary.py` for each canary the screen lists, in a scratch copy of the suite's folder
  5. `screen_verify.py` (gate G4) over those results

The project keeps one JSON file and no code. Paths in it are relative to `root`, and `root` is
relative to the file:

  {
    "root": "..",
    "results_dir": "docs/Test_Instruction/check",
    "preflight": ["python", "scripts/check_database.py"],
    "suites": {
      "backend":  {"preset": "pytest", "root": "backend"},
      "frontend": {"preset": "playwright", "root": "frontend", "port": 3006}
    },
    "screens": [{
      "key": "order-entry", "screen": "OrderEntry",
      "rules": ["BR-ORD-01", "BR-ORD-02"],
      "plan": "docs/Screen_plans/OrderEntry.md",
      "coverage_map": "docs/Test_Instruction/OrderEntry.md",
      "tests": {"backend": ["app/tests/test_order_entry.py"], "frontend": ["e2e/order-entry.spec.ts"]},
      "waive": {"BR-ORD-02": {"reason": "...", "by": "A Person", "on": "2026-10-08"}},
      "canaries": [{"suite": "backend", "rule": "BR-ORD-01", "file": "app/rounding.py",
                    "find": "ROUND_HALF_UP", "replace": "ROUND_HALF_EVEN"}],
      "parity": "docs/Test_Instruction/OrderEntry.parity.json", "output_screen": true
    }]
  }

A suite is a test command run from the suite's `root`. A `preset` fills the rest; any field may be
given instead or as well:

  command         the command, as a list. `{tests}` is replaced by the screen's tests, `{junit}` by the
                  result file, `{python}` by this interpreter
  env             variables for the command (`{junit}` allowed in values)
  canary_command  the command a canary runs in the scratch copy (no result file); default `command`
                  without the argument that names `{junit}`
  canary_env      variables for the canary run
  link            folders under `root` a canary links into the copy instead of copying
  requires        files under `root` that must exist, with the reason the suite cannot run otherwise
  executables     programs that must be on PATH
  port            a port nothing may be listening on: a server already running there would be reused
                  and serve the real code, not the copy a canary breaks
  citations       true: the suite's test files are read for rule ids in docstrings and comments
                  (Python only). Default true for `pytest`
  junit_file      in place of `{junit}`: where the runner writes its result, relative to `root`. For a
                  runner inside a container, which sees the mounted folder and not the host's results
                  folder. The file is moved to the results folder after the run

  up              a command, or a list, that starts what the suite runs against (a container of the
                  built image, served as the customer serves it). Run once, before the suite's first
                  screen; if it fails, every screen's suite is unavailable
  ready           {"url", "timeout"}: wait until the url answers (anything below 500) before testing
  down            a command, or a list, run after the suite's last screen whatever happened, so the
                  next suite finds its port free. A suite with `up` takes no canary: a break would
                  need a rebuilt image

Suites run one after another, in the config's order, each for every screen that has tests in it;
the rule check, the canaries and G4 then run per screen over all of its results.

`{root}` in a command is the suite's folder; in a canary it is the scratch copy `screen_canary.py`
broke, so a container command can mount the copy (`-v {root}:/app`) and never the real code.

Before anything else, once:

  context         {"dir", "dockerfile", "forbid"}: `screen_context.py` asks Docker what the build
                  would send and the run stops if it holds `.git`, a `.env`, or a `forbid` pattern
                  (the documentation folder, data exports). Checked before the image is built
  preflight       a command, or a list of commands, run in order from `root` (build the image, check
                  the database); the first that fails stops the run with its output, so a missing
                  database reads as that and not as every test failing

A waiver is a person's decision. Give it as `{"reason", "by", "on"}`; a reason alone is passed on
and gate G4 reports it at MEDIUM, as it reports any waiver no one is recorded as accepting.

`--skip-canary REASON` leaves the canaries out of this run and tells G4 why, which G4 lists at
LOW; the reason is required so a skip is a decision someone wrote down. `--skip-suite NAME` leaves a
suite out; a rule only that suite proves then reads as not tested, which is the truth of the run.

Exit status: 0 when every screen's tests pass, nothing stopped a step, and G4 has no HIGH or MEDIUM
finding; 1 otherwise (a suite that cannot run here, a missing program, a taken port, is an error of
the screens that need it); 2 when the config, the preflight, or a kit script cannot be used. Writes only to the results folder (one JUnit, rule-test, canary and G4 file per
screen, and `summary.json`). Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path, PureWindowsPath
from typing import Any

HERE = Path(__file__).resolve().parent
SCRIPTS = ("screen_rule_tests.py", "screen_canary.py", "screen_verify.py")
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

PRESETS: dict[str, dict[str, Any]] = {
    "pytest": {
        "command": ["{python}", "-m", "pytest", "{tests}", "-q", "-p", "no:cacheprovider", "--junitxml={junit}"],
        "citations": True,
    },
    "playwright": {
        "command": ["node", "node_modules/@playwright/test/cli.js", "test", "{tests}", "--reporter=junit"],
        "env": {"PLAYWRIGHT_JUNIT_OUTPUT_FILE": "{junit}", "CI": "1"},
        "canary_command": ["node", "node_modules/@playwright/test/cli.js", "test", "{tests}", "--reporter=line"],
        "canary_env": {"CI": "1"},
        "link": ["node_modules"],
        "requires": {"node_modules/@playwright/test/cli.js": "the suite's packages are not installed (no Playwright under node_modules)"},
        "executables": ["node"],
    },
}
SUITE_FIELDS = {"preset", "root", "command", "env", "canary_command", "canary_env", "link", "requires", "executables", "port", "citations",
                "junit_file", "up", "ready", "down"}
SCREEN_FIELDS = {"key", "screen", "rules", "plan", "coverage_map", "tests", "waive", "canaries", "parity", "output_screen"}


class Problem(Exception):
    """Something the run cannot continue from: the config, a prerequisite, a missing script."""


# --- the config ------------------------------------------------------------------------------

def _strings(value: Any) -> bool:
    return isinstance(value, list) and bool(value) and all(isinstance(v, str) and v for v in value)


def _commands(value: Any, what: str) -> list[list[str]]:
    """A command (a list of strings) or a list of commands, as a list of commands; None is none."""
    if value is None:
        return []
    if _strings(value):
        return [value]
    if isinstance(value, list) and value and all(_strings(c) for c in value):
        return value
    raise Problem(f"{what} must be a command (a list), or a list of commands")


def load_suite(name: str, raw: Any, root: Path) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise Problem(f"suite {name} is not an object")
    unknown = set(raw) - SUITE_FIELDS
    if unknown:
        raise Problem(f"suite {name} has unknown fields: {', '.join(sorted(unknown))}")
    preset = raw.get("preset")
    if preset is not None and preset not in PRESETS:
        raise Problem(f"suite {name}: unknown preset {preset!r} (known: {', '.join(PRESETS)})")
    suite: dict[str, Any] = {"env": {}, "canary_env": {}, "link": [], "requires": {}, "executables": [], "port": None, "citations": False,
                             "up": None, "ready": None, "down": None}
    suite.update(json.loads(json.dumps(PRESETS.get(preset, {}))))
    suite.update({k: v for k, v in raw.items() if k != "preset"})
    suite["name"] = name
    if not _strings(suite.get("command")) or "{tests}" not in suite["command"]:
        raise Problem(f"suite {name} needs a `command` (a list) with a `{{tests}}` argument")
    junit_file = suite.get("junit_file")
    if junit_file is not None:
        if (not isinstance(junit_file, str) or not junit_file or junit_file[0] in "/\\" or Path(junit_file).is_absolute()
                or PureWindowsPath(junit_file).drive or ".." in PureWindowsPath(junit_file).parts):
            raise Problem(f"suite {name}: `junit_file` must be a path under the suite's root")
        if any("{junit}" in part for part in suite["command"]):
            raise Problem(f"suite {name}: give `{{junit}}` or `junit_file`, not both")
    elif not any("{junit}" in part for part in suite["command"]) and not any("{junit}" in v for v in suite["env"].values()):
        raise Problem(f"suite {name}: nothing in `command` or `env` names `{{junit}}` and no `junit_file` is given, so no result could be read")
    if "canary_command" not in suite:
        suite["canary_command"] = [part for part in suite["command"] if "{junit}" not in part]
    if not _strings(suite["canary_command"]) or "{tests}" not in suite["canary_command"]:
        raise Problem(f"suite {name}: `canary_command` must be a list with a `{{tests}}` argument")
    if isinstance(suite["requires"], list):
        suite["requires"] = {path: "a file the suite needs is missing" for path in suite["requires"]}
    for field in ("env", "canary_env", "requires"):
        if not isinstance(suite[field], dict) or not all(isinstance(v, str) for v in suite[field].values()):
            raise Problem(f"suite {name}: `{field}` must map names to strings")
    for field in ("link", "executables"):
        if not isinstance(suite[field], list) or not all(isinstance(v, str) and v for v in suite[field]):
            raise Problem(f"suite {name}: `{field}` must be a list of names")
    if suite["port"] is not None and not (isinstance(suite["port"], int) and 0 < suite["port"] < 65536):
        raise Problem(f"suite {name}: `port` must be a port number")
    suite["up"] = _commands(suite["up"], f"suite {name}: `up`")
    suite["down"] = _commands(suite["down"], f"suite {name}: `down`")
    ready = suite["ready"]
    if ready is not None:
        if (not isinstance(ready, dict) or set(ready) - {"url", "timeout"} or not isinstance(ready.get("url"), str)
                or not re.match(r"^https?://", ready["url"]) or not isinstance(ready.get("timeout", 300), int)
                or ready.get("timeout", 300) <= 0):
            raise Problem(f"suite {name}: `ready` is {{\"url\": \"http://...\", \"timeout\": seconds}}")
        if not suite["up"]:
            raise Problem(f"suite {name}: `ready` waits for what `up` starts, and there is no `up`")
    suite["root"] = (root / str(suite.get("root") or ".")).resolve()
    if not suite["root"].is_dir():
        raise Problem(f"suite {name}: {suite['root']} is not a folder")
    return suite


def load_waivers(key: str, raw: Any, rules: list[str]) -> dict[str, dict[str, str]]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise Problem(f"screen {key}: `waive` must map rule ids to waivers")
    out: dict[str, dict[str, str]] = {}
    for rule, given in raw.items():
        waiver = {"reason": given} if isinstance(given, str) else given
        if rule not in rules:
            raise Problem(f"screen {key} waives {rule}, which is not one of its rules")
        if not isinstance(waiver, dict) or set(waiver) - {"reason", "by", "on"}:
            raise Problem(f"screen {key}: the waiver of {rule} must be a reason or {{reason, by, on}}")
        if not str(waiver.get("reason") or "").strip():
            raise Problem(f"screen {key} waives {rule} without a reason")
        for field in ("by", "on"):
            if field in waiver and not str(waiver[field]).strip():
                raise Problem(f"screen {key}: the waiver of {rule} has an empty `{field}`")
            if ";" in str(waiver.get(field, "")):
                raise Problem(f"screen {key}: the waiver of {rule} has a `;` in `{field}`")
        if "on" in waiver and not DATE.match(str(waiver["on"])):
            raise Problem(f"screen {key}: the waiver of {rule} is dated {waiver['on']!r}, not YYYY-MM-DD")
        out[rule] = {k: str(v).strip() for k, v in waiver.items()}
    return out


def load_screen(raw: Any, suites: dict[str, dict[str, Any]], root: Path) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise Problem("a screen is not an object")
    key = raw.get("key")
    if not isinstance(key, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", key):
        raise Problem(f"screen key {key!r}: use letters, digits, `.`, `_` and `-` (it names the result files)")
    unknown = set(raw) - SCREEN_FIELDS
    if unknown:
        raise Problem(f"screen {key} has unknown fields: {', '.join(sorted(unknown))}")
    if not isinstance(raw.get("screen"), str) or not raw["screen"].strip():
        raise Problem(f"screen {key} has no `screen` name")
    if not _strings(raw.get("rules")):
        raise Problem(f"screen {key} lists no `rules`")
    tests = raw.get("tests")
    if not isinstance(tests, dict) or not tests:
        raise Problem(f"screen {key} lists no `tests`")
    for suite, files in tests.items():
        if suite not in suites:
            raise Problem(f"screen {key} has tests for suite {suite!r}, which the config does not define")
        if not _strings(files):
            raise Problem(f"screen {key}: the tests of suite {suite} must be a list of paths")
    canaries = raw.get("canaries") or []
    if not isinstance(canaries, list):
        raise Problem(f"screen {key}: `canaries` must be a list")
    for n, canary in enumerate(canaries, start=1):
        if not isinstance(canary, dict) or not all(isinstance(canary.get(f), str) and canary[f] for f in ("suite", "file", "find", "replace")):
            raise Problem(f"screen {key}: canary {n} needs `suite`, `file`, `find` and `replace`")
        if canary["suite"] not in tests:
            raise Problem(f"screen {key}: canary {n} breaks suite {canary['suite']!r}, which has no tests for this screen")
        if suites[canary["suite"]]["up"]:
            raise Problem(f"screen {key}: canary {n} breaks suite {canary['suite']}, which runs against a started service: "
                          "the break would need a rebuilt image. Break it in a suite that builds from the code")
        if canary["find"] == canary["replace"]:
            raise Problem(f"screen {key}: canary {n} replaces its text with the same text")
    screen = dict(raw)
    screen["waive"] = load_waivers(key, raw.get("waive"), raw["rules"])
    screen["canaries"] = canaries
    for field in ("plan", "coverage_map", "parity"):
        if screen.get(field) is not None:
            if not isinstance(screen[field], str) or not screen[field]:
                raise Problem(f"screen {key}: `{field}` must be a path")
            screen[field] = root / screen[field]
    if screen.get("output_screen") not in (None, True, False):
        raise Problem(f"screen {key}: `output_screen` must be true or false")
    return screen


def load_config(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as err:
        raise Problem(f"cannot read {path}: {err}")
    if not isinstance(raw, dict):
        raise Problem(f"{path.name} is not a JSON object")
    root = (path.resolve().parent / str(raw.get("root") or ".")).resolve()
    if not root.is_dir():
        raise Problem(f"`root` {root} is not a folder")
    suites_raw = raw.get("suites")
    if not isinstance(suites_raw, dict) or not suites_raw:
        raise Problem(f"{path.name} defines no `suites`")
    suites = {name: load_suite(name, s, root) for name, s in suites_raw.items()}
    screens_raw = raw.get("screens")
    if not isinstance(screens_raw, list) or not screens_raw:
        raise Problem(f"{path.name} lists no `screens`")
    screens = [load_screen(s, suites, root) for s in screens_raw]
    keys = [s["key"] for s in screens]
    if len(set(keys)) != len(keys):
        raise Problem(f"{path.name}: screen keys repeat: {', '.join(sorted({k for k in keys if keys.count(k) > 1}))}")
    preflight = _commands(raw.get("preflight"), "`preflight`")
    context = raw.get("context")
    if context is not None:
        if not isinstance(context, dict) or set(context) - {"dir", "dockerfile", "forbid"}:
            raise Problem("`context` takes `dir`, `dockerfile` and `forbid`")
        forbid = context.get("forbid") or []
        if not isinstance(forbid, list) or not all(isinstance(f, str) and f for f in forbid):
            raise Problem("`context.forbid` must be a list of patterns")
        context = {"dir": root / str(context.get("dir") or "."), "forbid": forbid,
                   "dockerfile": (root / context["dockerfile"]) if context.get("dockerfile") else None}
    results = raw.get("results_dir")
    return {"root": root, "suites": suites, "screens": screens, "preflight": preflight, "context": context,
            "results_dir": (root / results) if isinstance(results, str) and results else None}


# --- running -----------------------------------------------------------------------------------

def expand(parts: list[str], tests: list[str], junit: Path | None, root: Path | None) -> list[str]:
    """Fill the placeholders. A canary passes `root=None`: `screen_canary.py` puts its scratch copy there."""
    out: list[str] = []
    for part in parts:
        if part == "{tests}":
            out += tests
            continue
        part = part.replace("{python}", sys.executable)
        if junit is not None:
            part = part.replace("{junit}", str(junit))
        if root is not None:
            part = part.replace("{root}", str(root))
        out.append(part)
    return out


def shell_line(parts: list[str]) -> str:
    """One command line for `screen_canary.py --cmd`, which runs it through the shell."""
    return subprocess.list2cmdline(parts) if os.name == "nt" else shlex.join(parts)


def run(cmd: list[str], cwd: Path, env: dict[str, str] | None = None, timeout: int | None = None) -> subprocess.CompletedProcess:
    merged = {**os.environ, **env} if env else None
    try:
        return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=merged, timeout=timeout)
    except FileNotFoundError as err:
        return subprocess.CompletedProcess(cmd, 127, "", f"{cmd[0]}: {err}")
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", f"timed out after {timeout} s")


def tail(done: subprocess.CompletedProcess, lines: int = 12) -> str:
    return "\n".join(((done.stdout or "") + (done.stderr or "")).strip().splitlines()[-lines:])


def unavailable(suite: dict[str, Any]) -> str | None:
    """Why the suite cannot run here, or None."""
    for program in suite["executables"]:
        if not shutil.which(program):
            return f"suite {suite['name']}: {program} is not on PATH"
    for path, why in suite["requires"].items():
        if not (suite["root"] / path).exists():
            return f"suite {suite['name']}: {why} ({path} under {suite['root']})"
    if suite["port"]:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", suite["port"])) == 0:
                return (f"suite {suite['name']}: port {suite['port']} is in use. A server already running there would be reused "
                        "and would serve the real code, not the copy a canary breaks: stop it first")
    return None


def check_plan(screen: dict[str, Any]) -> tuple[str, str | None]:
    """("matches" | "skipped" | "differs", detail): the config's rules against the ids the plan's mapping rows carry."""
    plan = screen.get("plan")
    if plan is None:
        return "skipped", None
    if not plan.is_file():
        return "skipped", f"{plan} is not on disk, so the config's rule list is the only one"
    sys.path.insert(0, str(HERE))
    try:
        import screen_rule_ids as sr

        planned = {r["id"] for r in sr.mapping_rows(plan) if r["id"]}
    except Exception as err:  # the plan is unusable: say so, do not guess
        return "differs", f"cannot read the rule ids of {plan}: {err}"
    listed = set(screen["rules"])
    if planned == listed:
        return "matches", None
    return "differs", (f"{plan.name} and the config disagree: only in the plan {sorted(planned - listed)}, "
                       f"only in the config {sorted(listed - planned)}")


def waiver_arg(rule: str, waiver: dict[str, str]) -> str:
    text = f"{rule}={waiver['reason']}"
    for field in ("by", "on"):
        if waiver.get(field):
            text += f";{field}={waiver[field]}"
    return text


def new_outcome(screen: dict[str, Any]) -> dict[str, Any]:
    outcome: dict[str, Any] = {"key": screen["key"], "screen": screen["screen"], "suites": {}, "canaries": [], "findings": [],
                               "errors": [], "junits": []}
    outcome["plan"], detail = check_plan(screen)
    if outcome["plan"] == "differs":
        outcome["errors"].append(detail)
    elif detail:
        outcome["planNote"] = detail
    return outcome


def run_suite(screen: dict[str, Any], name: str, suite: dict[str, Any], results: Path, outcome: dict[str, Any]) -> None:
    junit = results / f"{screen['key']}.{name}.junit.xml"
    junit.unlink(missing_ok=True)
    written = suite["root"] / suite["junit_file"] if suite.get("junit_file") else None
    if written is not None:
        written.unlink(missing_ok=True)
    env = {k: v.replace("{junit}", str(junit)) for k, v in suite["env"].items()}
    done = run(expand(suite["command"], screen["tests"][name], junit, suite["root"]), suite["root"], env)
    outcome["suites"][name] = done.returncode
    if done.returncode:
        outcome["errors"].append(f"suite {name} exited {done.returncode}\n{tail(done)}")
    if written is not None and written.is_file():
        # a runner in a container writes under the mounted root; move the result out of the code
        shutil.move(str(written), str(junit))
    if junit.is_file():
        outcome["junits"].append(str(junit))
    else:
        outcome["errors"].append(f"suite {name} wrote no JUnit result, so no rule can be shown to be tested by it")


def wait_ready(url: str, timeout: int) -> str | None:
    """None once `url` answers with anything below 500, else why it never did."""
    deadline = time.monotonic() + timeout
    last = "no answer"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=5):
                return None  # urlopen raises HTTPError for 4xx and 5xx, so reaching here is an answer
        except urllib.error.HTTPError as err:
            if err.code < 500:
                return None
            last = f"HTTP {err.code}"
        except (urllib.error.URLError, OSError) as err:
            last = str(getattr(err, "reason", err))
        time.sleep(2)
    return f"{url} did not answer within {timeout} s (last: {last})"


def run_suites(screens: list[dict[str, Any]], config: dict[str, Any], results: Path, args: argparse.Namespace,
               outcomes: dict[str, dict[str, Any]]) -> None:
    """Run each suite, in the config's order, for every screen that has tests in it.

    A suite with `up` starts its service once, runs every screen against it, and stops it with `down`
    whatever happened, so the next suite finds its port free again.
    """
    for name, suite in config["suites"].items():
        mine = [s for s in screens if name in s["tests"]]
        if not mine:
            continue
        if name in args.skip_suite:
            for s in mine:
                outcomes[s["key"]]["suites"][name] = "skipped"
            continue
        why = unavailable(suite)
        if not why:
            for command in suite["up"]:
                done = run(command, config["root"])
                if done.returncode:
                    why = f"suite {name}: `{' '.join(command)}` exited {done.returncode}\n{tail(done)}"
                    break
            if not why and suite["ready"]:
                why = wait_ready(suite["ready"]["url"], suite["ready"].get("timeout", 300))
                why = f"suite {name}: {why}" if why else None
        try:
            for s in mine:
                if why:
                    outcomes[s["key"]]["suites"][name] = "unavailable"
                    outcomes[s["key"]]["errors"].append(why)
                else:
                    run_suite(s, name, suite, results, outcomes[s["key"]])
        finally:
            for command in suite["down"]:
                done = run(command, config["root"])
                if done.returncode:
                    for s in mine:
                        outcomes[s["key"]]["errors"].append(
                            f"suite {name}: `{' '.join(command)}` exited {done.returncode}; the service may still be running\n{tail(done)}")


def verify(screen: dict[str, Any], config: dict[str, Any], results: Path, args: argparse.Namespace,
           outcome: dict[str, Any]) -> dict[str, Any]:
    """The rule check, the canaries and G4 for one screen, over the results its suites wrote."""
    key = screen["key"]
    junits = outcome.pop("junits")
    if not junits:
        outcome["errors"].append("no suite produced a result, so nothing was checked")
        return outcome

    rule_out = results / f"{key}.rule-tests.json"
    cmd = [sys.executable, str(HERE / "screen_rule_tests.py"), "--rules", ",".join(screen["rules"]), "--junit", *junits, "--out", str(rule_out)]
    cited = [n for n in screen["tests"] if config["suites"][n]["citations"] and outcome["suites"].get(n) not in ("skipped", "unavailable")]
    if len(cited) > 1:
        outcome["errors"].append(f"suites {', '.join(cited)} are all read for citations; the rule check reads one test folder, so mark one")
    elif cited:
        suite = config["suites"][cited[0]]
        folders = {(suite["root"] / t).parent for t in screen["tests"][cited[0]]}
        if len(folders) > 1:
            outcome["errors"].append(f"the tests of suite {cited[0]} sit in more than one folder; the rule check reads one")
        else:
            cmd += ["--tests", str(folders.pop())]
    if screen.get("coverage_map") is not None:
        cmd += ["--coverage-map", str(screen["coverage_map"])]
    for rule, waiver in screen["waive"].items():
        cmd += ["--waive", waiver_arg(rule, waiver)]
    done = run(cmd, config["root"])
    if done.returncode == 2 or not rule_out.is_file():
        outcome["errors"].append(f"screen_rule_tests.py could not run:\n{tail(done)}")
        return outcome

    canary_files: list[str] = []
    if args.skip_canary is None:
        counts: dict[str, int] = {}
        for canary in screen["canaries"]:
            name = canary["suite"]
            if outcome["suites"].get(name) in ("skipped", "unavailable"):
                outcome["canaries"].append({"suite": name, "file": canary["file"], "state": "not run: the suite did not run"})
                continue
            suite = config["suites"][name]
            counts[name] = counts.get(name, 0) + 1
            out = results / f"{key}.canary-{name}-{counts[name]}.json"
            out.unlink(missing_ok=True)
            cmd = [sys.executable, str(HERE / "screen_canary.py"), "--root", str(suite["root"]), "--file", canary["file"],
                   "--find", canary["find"], "--replace", canary["replace"],
                   "--cmd", shell_line(expand(suite["canary_command"], screen["tests"][name], None, None)),
                   "--timeout", str(args.timeout), "--out", str(out)]
            for folder in suite["link"]:
                cmd += ["--link", folder]
            if suite.get("junit_file"):
                cmd += ["--junit", suite["junit_file"]]
            done = run(cmd, config["root"], suite["canary_env"] or None)
            if done.returncode == 2 or not out.is_file():
                outcome["errors"].append(f"canary {out.name} could not run:\n{tail(done)}")
                continue
            canary_files.append(str(out))
            verdict = json.loads(out.read_text(encoding="utf-8")).get("verdict")
            outcome["canaries"].append({"suite": name, "file": canary["file"], "rule": canary.get("rule"), "state": verdict})

    cmd = [sys.executable, str(HERE / "screen_verify.py"), "--screen", screen["screen"], "--rule-tests", str(rule_out), "--json"]
    if canary_files:
        cmd += ["--canary", *canary_files]
    elif args.skip_canary is not None:
        cmd += ["--canaries-skipped", args.skip_canary]
    if screen.get("parity") is not None:
        cmd += ["--parity", str(screen["parity"])]
    if screen.get("output_screen"):
        cmd += ["--output-screen"]
    done = run(cmd, config["root"])
    try:
        outcome["findings"] = json.loads(done.stdout)["findings"]
    except (ValueError, KeyError, TypeError):
        outcome["errors"].append(f"screen_verify.py gave no result:\n{tail(done)}")
    return outcome


def failed(outcome: dict[str, Any]) -> bool:
    # A red suite, a suite that could not start, and a step that could not run are all recorded as errors.
    return bool(outcome["errors"]) or any(f["severity"] in ("HIGH", "MEDIUM") for f in outcome["findings"])


def report(outcome: dict[str, Any]) -> str:
    counts = {sev: sum(1 for f in outcome["findings"] if f["severity"] == sev) for sev in ("HIGH", "MEDIUM", "LOW")}
    suites = "  ".join(f"{name}={state}" for name, state in outcome["suites"].items())
    lines = [f"{'FAIL' if failed(outcome) else 'ok':<5}{outcome['key']:<22}{suites}  plan={outcome['plan']}  "
             f"G4: {counts['HIGH']} HIGH, {counts['MEDIUM']} MEDIUM, {counts['LOW']} LOW"]
    lines += [f"        {f['severity']}: {f['text']}" for f in outcome["findings"]]
    lines += ["        error: " + e.replace("\n", "\n               ") for e in outcome["errors"]]
    if outcome.get("planNote"):
        lines.append(f"        note: {outcome['planNote']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--config", type=Path, required=True, help="the project's screen-check file")
    ap.add_argument("--screen", action="append", help="a screen key from the config (default: all)")
    ap.add_argument("--skip-canary", metavar="REASON", help="leave the canaries out of this run; G4 records the reason at LOW")
    ap.add_argument("--skip-suite", action="append", default=[], metavar="NAME", help="leave a suite out of this run")
    ap.add_argument("--results-dir", type=Path, help="where results go (default: the config's results_dir, else a new temporary folder)")
    ap.add_argument("--timeout", type=int, default=900, help="seconds allowed for one canary run")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        if args.skip_canary is not None and not args.skip_canary.strip():
            raise Problem("--skip-canary needs a reason")
        for name in SCRIPTS:
            if not (HERE / name).is_file():
                raise Problem(f"{HERE} has no {name}")
        config = load_config(args.config)
        unknown = set(args.skip_suite) - set(config["suites"])
        if unknown:
            raise Problem(f"unknown suite: {', '.join(sorted(unknown))}")
        wanted = args.screen or [s["key"] for s in config["screens"]]
        unknown = set(wanted) - {s["key"] for s in config["screens"]}
        if unknown:
            raise Problem(f"unknown screen key: {', '.join(sorted(unknown))}")
        results = args.results_dir or config["results_dir"] or Path(tempfile.mkdtemp(prefix="screen-check-"))
        results = results.resolve()
        results.mkdir(parents=True, exist_ok=True)
        if config["context"] is not None:
            ctx = config["context"]
            cmd = [sys.executable, str(HERE / "screen_context.py"), "--context", str(ctx["dir"])]
            if ctx["dockerfile"] is not None:
                cmd += ["--dockerfile", str(ctx["dockerfile"])]
            for pattern in ctx["forbid"]:
                cmd += ["--forbid", pattern]
            done = run(cmd, config["root"])
            if done.returncode:
                raise Problem(f"the build context check stopped the run (screen_context.py exited {done.returncode}):\n{tail(done, 60)}")
        for command in config["preflight"]:
            done = run(command, config["root"])
            if done.returncode:
                raise Problem(f"the preflight `{' '.join(command)}` exited {done.returncode}:\n{tail(done)}")
    except Problem as err:
        print(f"screen_check: {err}", file=sys.stderr)
        return 2

    screens = [s for s in config["screens"] if s["key"] in wanted]
    started = {s["key"]: new_outcome(s) for s in screens}
    run_suites(screens, config, results, args, started)
    outcomes = [verify(s, config, results, args, started[s["key"]]) for s in screens]
    for o in outcomes:
        print(report(o))
        (results / f"{o['key']}.g4.json").write_text(json.dumps(o, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    (results / "summary.json").write_text(json.dumps(outcomes, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"results: {results}")
    return 1 if any(failed(o) for o in outcomes) else 0


if __name__ == "__main__":
    raise SystemExit(main())
