#!/usr/bin/env python3
"""Say which business rules a screen's tests actually back, from the test results.

    python3 screen_rule_tests.py (--ak <dir> --screen <name> | --rules BR-A,BR-B)
        --junit <result file or folder> [--tests <test source folder>]
        [--coverage-map Test_Instruction/<screen>.md] [--waive BR-X=reason] [--out RULE_TESTS.json]

A coverage map that says "BR-014 is proved by test X" is a claim. This script reads the claim
against the runner's own result files and gives each rule one state:

  TESTED     at least one test that named the rule ran and passed, and none that named it failed
  FAILING    a test that named the rule failed or errored
  NOT RUN    only skipped tests, or a test in the source that has no result, name the rule
  CLAIMED    only the coverage map names it: nothing in the tests or their results does
  UNTESTED   nothing names it
  WAIVED     a person set it aside with a reason (`--waive BR-X=reason`); it is still listed

A test names a rule in its own name or class name (`test_br_ord_01_rounds_up`, separators may be
`-`, `_`, `.` or space), or, for Python test files read with `--tests`, anywhere inside the test
function (a decorator, docstring or comment) or in its class's decorator or docstring. A rule id
is matched whole: `BR-ORD-01` never matches `BR-ORD-011` or `BR-ORD-01a`.

The rules come from the extraction (`--ak` and `--screen`, as `screen_scope.py` reads them, so a
superset of what the screen uses) or from `--rules`. Results come from JUnit-style XML only:
a count typed into a document, or a log, shows no test names, so it backs nothing. A run that
executed no test at all is an input error: nothing was proved.

Exit status: 0 when every rule is TESTED or WAIVED; 1 otherwise; 2 when the input cannot be
used. Reads files and writes only the result file. Stdlib only.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

RULE_ID = re.compile(r"(?<![A-Za-z0-9_-])BR-[A-Z0-9]{1,6}(?:-[0-9]{2})?[a-z]?(?![A-Za-z0-9_-])")
SEPARATED = re.compile(r"(?:(?<![A-Za-z0-9])|(?<=Test))(?P<id>BR[-_. ][A-Za-z0-9]{1,6}(?:[-_. ][0-9]{2}[A-Za-z]?)?)(?![A-Za-z0-9])", re.IGNORECASE)
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
MAX_BYTES = 8 << 20
ORDER = ("FAILING", "TESTED", "NOT RUN", "CLAIMED", "UNTESTED")


class InputError(Exception):
    """The request cannot be run; no result is attempted."""


def canon(rule_id: str) -> str:
    return re.sub(r"[-_. ]", "", rule_id).upper()


def names_in(text: str) -> set[str]:
    """Rule ids written in a test's own name, with any separator, as canonical keys."""
    return {canon(m.group("id")) for m in SEPARATED.finditer(text)}


def ids_in(text: str) -> set[str]:
    return {canon(m.group(0)) for m in RULE_ID.finditer(text)} | names_in(text)


def read_results(paths: list[Path]) -> list[dict[str, str]]:
    files: list[Path] = []
    for p in paths:
        if p.is_dir():
            files += sorted(p.rglob("*.xml"))
        elif p.is_file():
            files.append(p)
        else:
            raise InputError(f"--junit {p} does not exist")
    cases: list[dict[str, str]] = []
    for f in files:
        try:
            if f.stat().st_size > MAX_BYTES:
                continue
            root = ET.parse(f).getroot()
        except (OSError, ET.ParseError):
            continue
        for tc in root.iter("testcase"):
            kids = {c.tag for c in tc}
            state = "error" if "error" in kids else "failed" if "failure" in kids else "skipped" if "skipped" in kids else "passed"
            cases.append({"classname": tc.get("classname") or "", "name": tc.get("name") or "", "state": state})
    if not any(c["state"] != "skipped" for c in cases):
        raise InputError("the result files show no test that executed: nothing was proved")
    return cases


def source_citations(tests: Path) -> dict[tuple[str, str | None, str], set[str]]:
    """(module, class or None, function) -> rule ids written inside it. Python test files only."""
    found: dict[tuple[str, str | None, str], set[str]] = {}

    def segment(lines: list[str], node: ast.AST) -> str:
        first = min([node.lineno] + [d.lineno for d in getattr(node, "decorator_list", [])])
        return "\n".join(lines[first - 1: node.end_lineno])

    def header(lines: list[str], cls: ast.ClassDef) -> str:
        first = min([cls.lineno] + [d.lineno for d in cls.decorator_list])
        doc = ast.get_docstring(cls) or ""
        return "\n".join(lines[first - 1: cls.lineno]) + "\n" + doc

    for f in sorted(tests.rglob("*.py")):
        if SKIP_DIRS & set(f.parts) or f.stat().st_size > MAX_BYTES:
            continue
        try:
            text = f.read_text(encoding="utf-8")
            tree = ast.parse(text)
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        lines = text.splitlines()
        module = f.stem
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                found.setdefault((module, None, node.name), set()).update(ids_in(segment(lines, node)))
            elif isinstance(node, ast.ClassDef):
                inherited = ids_in(header(lines, node))
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        found.setdefault((module, node.name, item.name), set()).update(inherited | ids_in(segment(lines, item)))
    return found


def key_of(case: dict[str, str]) -> list[tuple[str, str | None, str]]:
    parts = [p for p in case["classname"].split(".") if p]
    base = case["name"].split("[")[0]
    out: list[tuple[str, str | None, str]] = []
    if len(parts) >= 2:
        out.append((parts[-2], parts[-1], base))
    if parts:
        out.append((parts[-1], None, base))
    return out


def judge(rules: list[str], cases: list[dict[str, str]], cited: dict[tuple[str, str | None, str], set[str]],
          mapped: set[str], waived: dict[str, str]) -> list[dict[str, Any]]:
    by_rule: dict[str, dict[str, list[str]]] = {canon(r): {"passed": [], "failed": [], "error": [], "skipped": []} for r in rules}
    for case in cases:
        label = f"{case['classname']}::{case['name']}"
        named = names_in(case["classname"] + " " + case["name"])
        for k in key_of(case):
            if k in cited:
                named |= cited[k]
                break
        for rid in named & by_rule.keys():
            by_rule[rid][case["state"]].append(label)
    in_source = set().union(*cited.values()) if cited else set()
    out: list[dict[str, Any]] = []
    for rule in rules:
        r = by_rule[canon(rule)]
        if r["failed"] or r["error"]:
            state = "FAILING"
        elif r["passed"]:
            state = "TESTED"
        elif r["skipped"] or canon(rule) in in_source:
            state = "NOT RUN"
        elif canon(rule) in mapped:
            state = "CLAIMED"
        else:
            state = "UNTESTED"
        rec: dict[str, Any] = {"rule": rule, "state": state, "tests": {k: v[:5] for k, v in r.items() if v},
                               "testCount": {k: len(v) for k, v in r.items() if v}}
        if rule in waived:
            rec["waived"] = waived[rule]
            rec["state"] = "WAIVED"
            rec["wouldBe"] = state
        out.append(rec)
    return out


def rules_from(args: argparse.Namespace) -> list[str]:
    if args.rules:
        ids = [r.strip() for r in args.rules.split(",") if r.strip()]
        bad = [r for r in ids if not RULE_ID.fullmatch(r)]
        if bad:
            raise InputError(f"not a rule id: {', '.join(bad)}")
    elif args.ak and args.screen:
        import screen_decisions as sd
        import screen_scope as ss

        try:
            report = ss.build(args.ak, sd.norm(args.screen), None, None)
        except sd.Problem as problem:
            raise InputError(str(problem))
        ids = [r["id"] for r in report["scope"]["rules"]]
    else:
        raise InputError("give --ak and --screen, or --rules")
    if not ids:
        raise InputError("no rule to check")
    return list(dict.fromkeys(ids))


def parse_waivers(items: list[str], rules: list[str]) -> dict[str, str]:
    waived: dict[str, str] = {}
    for item in items:
        rid, _, why = item.partition("=")
        rid, why = rid.strip(), why.strip()
        if rid not in rules:
            raise InputError(f"--waive {rid!r} is not one of the rules checked")
        if not why:
            raise InputError(f"--waive {rid} needs a reason after '='")
        waived[rid] = why[:300]
    return waived


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ak", type=Path)
    ap.add_argument("--screen")
    ap.add_argument("--rules")
    ap.add_argument("--junit", type=Path, nargs="+", required=True)
    ap.add_argument("--tests", type=Path)
    ap.add_argument("--coverage-map", type=Path)
    ap.add_argument("--waive", action="append", default=[])
    ap.add_argument("--out", type=Path, default=Path("RULE_TESTS.json"))
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        rules = rules_from(args)
        waived = parse_waivers(args.waive, rules)
        cases = read_results(args.junit)
        cited = source_citations(args.tests) if args.tests else {}
        mapped: set[str] = set()
        if args.coverage_map:
            try:
                mapped = ids_in(args.coverage_map.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError) as err:
                raise InputError(f"cannot read --coverage-map: {err}")
        results = judge(rules, cases, cited, mapped, waived)
    except InputError as err:
        print(f"screen_rule_tests: {err}", file=sys.stderr)
        return 2
    counts = {s: sum(1 for r in results if r["state"] == s) for s in (*ORDER, "WAIVED")}
    ok = all(r["state"] in ("TESTED", "WAIVED") for r in results)
    pack = {"verdict": "BACKED" if ok else "GAPS", "counts": counts, "testsRead": len(cases), "rules": results}
    args.out.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for r in results:
        print(f"{r['state']:<9}{r['rule']}" + (f"  (waived: {r['waived']})" if "waived" in r else ""))
    print(f"{pack['verdict']}: " + ", ".join(f"{n} {s}" for s, n in counts.items() if n))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
