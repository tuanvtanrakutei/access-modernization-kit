#!/usr/bin/env python3
"""Prove the tests can fail: break one line in a scratch copy and see whether they notice.

    python3 screen_canary.py --root <code folder> --file <path under root> \\
        --find "<exact text>" --replace "<broken text>" --cmd "<test command>" \\
        [--junit <result file under root>] [--link <folder under root> ...] [--timeout 900] [--out CANARY.json] [--keep]

A suite that passes proves nothing until it is known to be able to fail. The canary copies the
code to a scratch folder, runs the tests once untouched, changes one line that matters (a
rounding mode, a threshold by one, a comparison), and runs them again. The verdict is computed
from the two runs:

  CAUGHT          the untouched copy is green and the broken copy has at least one failed test
  SURVIVED        the broken copy is also green: the tests cannot see this line. This is the finding
  INCONCLUSIVE    the break stopped the tests from running (an error, a collection failure, a
                  timeout, no result to read), so nothing was learned about the line. Pick another
                  break that still builds
  NO BASELINE     the untouched copy is not green, so a failure after the break proves nothing

A break that makes *every* test fail (and none pass) is INCONCLUSIVE too, not CAUGHT: in a front-end
project it is what a syntax error does when the dev server cannot build the page, and it says nothing
about the line. `--link` puts a folder the copy skips (`node_modules`, which the test command needs)
into the scratch copy as a link, never as a second copy; the link is removed before the scratch folder is.

The code under `--root` is never written. `--find` must occur exactly once in `--file`. Counts
come from a JUnit result file when `--junit` is given (deleted before each run so a stale one is
never read) and otherwise from the runner's summary line (`3 failed, 10 passed`, as pytest, jest
and vitest print it). A run with no test executed is never green. An ERROR is not a failure: the
test body never ran.

Exit status: 0 CAUGHT; 1 any other verdict; 2 the input cannot be used. Writes the result file
and the scratch folder only (removed unless --keep). Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".pytest_cache", ".mypy_cache", "dist", "build", ".tox"}
MAX_FILES = 20000
TAIL = 3000
COUNT = {k: re.compile(rf"(\d+)\s+{p}\b") for k, p in (("failed", "failed"), ("errors", "errors?"), ("passed", "passed"))}


class InputError(Exception):
    """The request cannot be run; no verdict is attempted."""


def copy_tree(root: Path, dest: Path) -> None:
    count = 0

    def ignore(folder: str, names: list[str]) -> list[str]:
        nonlocal count
        count += len(names)
        if count > MAX_FILES:
            raise InputError(f"more than {MAX_FILES} entries under --root: point --root at the smaller folder the tests need")
        return [n for n in names if n in SKIP_DIRS]

    shutil.copytree(root, dest, ignore=ignore)


def make_link(root: Path, work: Path, name: str) -> None:
    """Link a folder the copy skips into it. A junction on Windows (no privilege needed), a symlink elsewhere."""
    src = (root / name).resolve()
    if root not in src.parents or not src.is_dir():
        raise InputError(f"--link {name!r} must be a folder under --root")
    dst = work / name
    if os.path.lexists(dst):
        raise InputError(f"--link {name!r} is already in the copy; link only a folder the copy skips")
    dst.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        done = subprocess.run(["cmd", "/c", "mklink", "/J", str(dst), str(src)], capture_output=True, text=True)
        if done.returncode:
            raise InputError(f"cannot link {name}: {(done.stdout + done.stderr).strip()}")
    else:
        os.symlink(src, dst, target_is_directory=True)


def remove_scratch(scratch: Path, links: list[str]) -> bool:
    """Remove the scratch folder after taking each link out of it, so that nothing deletes what a link points at.

    `os.rmdir` removes a junction without touching its target and refuses a real folder that has content.
    When a link cannot be removed the scratch folder is left alone and False is returned.
    """
    for name in links:
        dst = scratch / "copy" / name
        try:
            if os.path.islink(dst):
                os.unlink(dst)
            elif os.path.lexists(dst):
                os.rmdir(dst)
        except OSError:
            pass
    if any(os.path.lexists(scratch / "copy" / name) for name in links):
        return False
    shutil.rmtree(scratch, ignore_errors=True)
    return True


def junit_counts(path: Path) -> dict[str, int] | None:
    try:
        tree = ET.parse(path)
    except (OSError, ET.ParseError):
        return None
    total = {"failed": 0, "errors": 0, "passed": 0}
    for suite in tree.getroot().iter("testsuite"):
        n = lambda key: int(float(suite.get(key) or 0))  # noqa: E731
        failed, errors, skipped = n("failures"), n("errors"), n("skipped")
        total["failed"] += failed
        total["errors"] += errors
        total["passed"] += max(0, n("tests") - failed - errors - skipped)
    return total


# A summary line that starts with its count: "  1 failed", "  12 passed (47s)", "1 failed, 12 passed in 3s".
SUMMARY_LINE = re.compile(r"^\s*\d+\s+(?:failed|passed|errors?|skipped|flaky|did not run)\b")


def text_counts(output: str) -> dict[str, int] | None:
    """The counts from the runner's summary: one line (pytest, jest) or several (Playwright's `1 failed`, then `12 passed`)."""
    lines = output.splitlines()
    block = [ln for ln in lines[-60:] if SUMMARY_LINE.match(ln)]
    if block:  # a summary that starts with its counts, on one line or spread over several: add them up
        return {k: sum(int(m.group(1)) for ln in block if (m := c.search(ln))) for k, c in COUNT.items()}
    found = [ln for ln in lines if any(c.search(ln) for c in COUNT.values())]
    if not found:
        return None
    last = found[-1]  # a one-line summary is the last line that carries counts
    return {k: int(m.group(1)) if (m := c.search(last)) else 0 for k, c in COUNT.items()}


def run_tests(cmd: str, cwd: Path, junit: str | None, timeout: int) -> dict[str, Any]:
    result_file = cwd / junit if junit else None
    if result_file is not None and result_file.exists():
        result_file.unlink()
    try:
        proc = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"state": "timeout", "exit": None, "counts": None, "tail": ""}
    output = (proc.stdout or "") + (proc.stderr or "")
    counts = junit_counts(result_file) if result_file is not None else text_counts(output)
    return {"state": "ran", "exit": proc.returncode, "counts": counts, "tail": output[-TAIL:]}


def green(run: dict[str, Any]) -> bool:
    c = run["counts"]
    return run["state"] == "ran" and run["exit"] == 0 and c is not None and c["failed"] == 0 and c["errors"] == 0 and c["passed"] > 0


def verdict(clean: dict[str, Any], broken: dict[str, Any]) -> tuple[str, str]:
    if not green(clean):
        return "NO BASELINE", "the untouched copy is not green (it must run, pass at least one test and have no failure or error)"
    if broken["state"] == "timeout":
        return "INCONCLUSIVE", "the broken copy timed out"
    c = broken["counts"]
    if c is None:
        return "INCONCLUSIVE", "no test result could be read from the broken copy"
    if c["errors"] and not c["failed"]:
        return "INCONCLUSIVE", "the broken copy errored before its tests ran; choose a break that still builds"
    if c["failed"] and not c["passed"] and c["failed"] > 1:
        return "INCONCLUSIVE", (f"all {c['failed']} tests failed and none passed: the break probably stopped the app or the "
                                "suite from building; choose a break that changes behaviour only")
    if c["failed"]:
        return "CAUGHT", f"{c['failed']} test(s) failed on the broken copy"
    if broken["exit"] != 0:
        return "INCONCLUSIVE", "the run exited non-zero without a failed test"
    return "SURVIVED", "every test still passed with the line broken: no test depends on it"


def build(args: argparse.Namespace) -> tuple[dict[str, Any], Path | None]:
    root = Path(args.root).resolve()
    if not root.is_dir():
        raise InputError(f"--root {args.root!r} is not a folder")
    target = (root / args.file).resolve()
    if root not in target.parents or not target.is_file():
        raise InputError("--file must be a file under --root")
    if not args.find or args.find == args.replace:
        raise InputError("--find must be non-empty and --replace must differ from it")
    if not args.cmd.strip():
        raise InputError("--cmd is empty")
    raw = target.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise InputError("--file is not UTF-8 text")
    hits = text.count(args.find)
    if hits != 1:
        raise InputError(f"--find occurs {hits} times in {args.file}; it must occur exactly once")
    for name in args.link:
        src = (root / name).resolve()
        if root not in src.parents or not src.is_dir():
            raise InputError(f"--link {name!r} must be a folder under --root")
    scratch = Path(tempfile.mkdtemp(prefix="canary-"))
    work = scratch / "copy"
    try:
        copy_tree(root, work)
        for name in args.link:
            make_link(root, work, name)
        clean = run_tests(args.cmd, work, args.junit, args.timeout)
        line = text[: text.index(args.find)].count("\n") + 1
        if green(clean):
            # bytes in, bytes out: the file keeps its own line endings
            (work / args.file).write_bytes(text.replace(args.find, args.replace).encode("utf-8"))
            broken = run_tests(args.cmd, work, args.junit, args.timeout)
        else:
            broken = {"state": "skipped", "exit": None, "counts": None, "tail": ""}
        name, why = verdict(clean, broken)
    except BaseException:
        remove_scratch(scratch, args.link)
        raise
    pack = {
        "verdict": name, "why": why,
        "break": {"file": args.file, "line": line, "find": args.find, "replace": args.replace},
        "command": args.cmd, "clean": clean, "broken": broken,
    }
    return pack, scratch


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--root", required=True)
    ap.add_argument("--file", required=True)
    ap.add_argument("--find", required=True)
    ap.add_argument("--replace", required=True)
    ap.add_argument("--cmd", required=True)
    ap.add_argument("--junit")
    ap.add_argument("--link", action="append", default=[], help="a folder under --root to link into the copy instead of copying it")
    ap.add_argument("--timeout", type=int, default=900)
    ap.add_argument("--out", default="CANARY.json")
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args(argv)
    try:
        pack, scratch = build(args)
    except InputError as err:
        print(f"screen_canary: {err}", file=sys.stderr)
        return 2
    if args.keep:
        pack["scratch"] = str(scratch)
    elif not remove_scratch(scratch, args.link):
        pack["scratch"] = str(scratch)
        print(f"screen_canary: a link could not be removed, so {scratch} was left in place; remove the link before the folder", file=sys.stderr)
    Path(args.out).write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"{pack['verdict']}: {pack['why']} ({args.file}:{pack['break']['line']})")
    return 0 if pack["verdict"] == "CAUGHT" else 1


if __name__ == "__main__":
    sys.exit(main())
