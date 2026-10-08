#!/usr/bin/env python3
"""Say which business rules a screen's tests actually back, from the test results.

    python3 screen_rule_tests.py (--ak <dir> --screen <name> | --plan <screen plan> | --rules BR-A,BR-B)
        --junit <result file or folder> [--tests <test source folder>]
        [--coverage-map Test_Instruction/<screen>.md] [--waive "BR-X=reason;by=NAME;on=YYYY-MM-DD"] [--out RULE_TESTS.json]

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
is matched whole: `BR-ORD-01` never matches `BR-ORD-011` or `BR-ORD-01a`. A citation in a
test file that has no result in this run is not counted, because rule ids are often local to a
screen: it is listed as `citedOutsideRun` on a rule that is otherwise CLAIMED or UNTESTED. Point
`--tests` and `--junit` at the same screen's tests.

The rules come from the extraction (`--ak` and `--screen`, as `screen_scope.py` reads them, so a
superset of what the screen uses), from the rows of a screen plan's Legacy-To-New Mapping table
(`--plan`: the id each row carries, as `screen_rule_ids.py` mints them, for a screen the register
holds no rule for), or from `--rules`.

A waiver names who accepted it and when, as two trailing fields: `BR-X=reason;by=NAME;on=YYYY-MM-DD`.
A waiver without both is still honoured here and recorded as given; gate G4 reports it.

A coverage map also names tests, in backticks. With `--tests`, every test name a table row of the map
gives is looked up among the test functions and classes of the Python files read; a name no file
defines is listed as `coverageMap.unknownTests` with the rule of its row, because a map that cites a
test nobody wrote is a claim about nothing. A map read with no Python test to look in is recorded as
not checked. This does not change the exit status; gate G4 reports it.

Results come from JUnit-style XML only: a count typed into a document, or a log, shows no test names, so it backs nothing. A run that
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
from datetime import date
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

RULE_ID = re.compile(r"(?<![A-Za-z0-9_-])BR-[A-Z0-9]{1,6}(?:-[0-9]{2})?[a-z]?(?![A-Za-z0-9_-])")
SEPARATED = re.compile(r"(?:(?<![A-Za-z0-9])|(?<=Test))(?P<id>BR[-_. ][A-Za-z0-9]{1,6}(?:[-_. ][0-9]{2}[A-Za-z]?)?)(?![A-Za-z0-9])", re.IGNORECASE)
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"}
MAX_BYTES = 8 << 20
WAIVER_FIELD = re.compile(r"\s*(by|on)\s*=(.*)", re.IGNORECASE | re.DOTALL)
WAIVER_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
TEST_SPAN = re.compile(r"`([^`\n]+)`")
TEST_SUFFIX = re.compile(r"(?:\[[^\]]*\])?(?:\(\))?$")
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
          mapped: set[str], waived: dict[str, dict[str, str]]) -> list[dict[str, Any]]:
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
    # A citation counts as "a test with no result" only when its file took part in this run. A citation in
    # a file with no result at all belongs to another run, and rule ids are often local to a screen.
    ran = {m for case in cases for m, _, _ in key_of(case)}
    in_source: set[str] = set()
    outside: dict[str, set[str]] = {}
    for (module, _cls, _fn), ids in cited.items():
        if module in ran:
            in_source |= ids
        else:
            for rid in ids:
                outside.setdefault(rid, set()).add(module)
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
        if state in ("CLAIMED", "UNTESTED") and outside.get(canon(rule)):
            rec["citedOutsideRun"] = sorted(outside[canon(rule)])
        if rule in waived:
            rec["waived"] = waived[rule]["reason"]
            for key, field in (("by", "waivedBy"), ("on", "waivedOn")):
                if key in waived[rule]:
                    rec[field] = waived[rule][key]
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
    elif args.plan:
        import screen_decisions as sd
        import screen_rule_ids as sr

        try:
            rows = sr.mapping_rows(args.plan)
        except sd.Problem as problem:
            raise InputError(str(problem))
        # A row with no id is a legacy concept, not a rule: the mapping holds both.
        wrong = [f"row {r['n']} ({r['id']})" for r in rows if r["id"] and not RULE_ID.fullmatch(r["id"])]
        if wrong:
            raise InputError(f"{', '.join(wrong)} carry no valid rule id: run screen_rule_ids.py on the plan")
        ids = [r["id"] for r in rows if r["id"]]
        if not ids:
            raise InputError("no row of the mapping carries a rule id: run screen_rule_ids.py on the plan")
    elif args.ak and args.screen:
        import screen_decisions as sd
        import screen_scope as ss

        try:
            report = ss.build(args.ak, sd.norm(args.screen), None, None)
        except sd.Problem as problem:
            raise InputError(str(problem))
        ids = [r["id"] for r in report["scope"]["rules"]]
    else:
        raise InputError("give --ak and --screen, or --plan, or --rules")
    if not ids:
        raise InputError("no rule to check")
    return list(dict.fromkeys(ids))


def parse_waivers(items: list[str], rules: list[str]) -> dict[str, dict[str, str]]:
    waived: dict[str, dict[str, str]] = {}
    for item in items:
        rid, _, why = item.partition("=")
        rid = rid.strip()
        if rid not in rules:
            raise InputError(f"--waive {rid!r} is not one of the rules checked")
        parts = why.split(";")
        fields: dict[str, str] = {}
        # Trailing `by=` and `on=` fields only: a `;` inside the reason is the reason's own.
        while len(parts) > 1 and (m := WAIVER_FIELD.fullmatch(parts[-1])):
            key = m.group(1).lower()
            if key in fields:
                raise InputError(f"--waive {rid} gives {key}= twice")
            fields[key] = m.group(2).strip()
            parts.pop()
        reason = ";".join(parts).strip()
        if not reason:
            raise InputError(f"--waive {rid} needs a reason after '='")
        if "by" in fields and not fields["by"]:
            raise InputError(f"--waive {rid} has an empty by=")
        if "on" in fields and not WAIVER_DATE.fullmatch(fields["on"]):
            raise InputError(f"--waive {rid} has on={fields['on']!r}: write the date as YYYY-MM-DD")
        if "on" in fields:
            try:
                date.fromisoformat(fields["on"])
            except ValueError:
                raise InputError(f"--waive {rid} has on={fields['on']!r}: not a calendar date")
        waived[rid] = {"reason": reason[:300], **fields}
    return waived


def test_names(tests: Path) -> set[str]:
    """Every function and class name defined in the Python files under `tests`."""
    names: set[str] = set()
    for f in sorted(tests.rglob("*.py")):
        if SKIP_DIRS & set(f.parts) or f.stat().st_size > MAX_BYTES:
            continue
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (OSError, SyntaxError, UnicodeDecodeError):
            continue
        names |= {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
    return names


def unknown_tests(map_text: str, known: set[str]) -> list[dict[str, str]]:
    """Test names a coverage map gives, in backticks inside a row of a table whose first column is the rule,
    that no read test file defines. Other tables of the same document (known issues, commands) are not read."""
    out: list[dict[str, str]] = []
    head: list[str] = []
    in_rule_table = False
    for line in map_text.splitlines():
        if "|" not in line:
            head, in_rule_table = [], False
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{3,}:?", c) for c in cells):
            in_rule_table = bool(head) and "rule" in head[0].lower()
            continue
        if not in_rule_table:
            head = cells
            continue
        found = RULE_ID.search(cells[0])
        rule = found.group(0) if found else cells[0][:40]
        for cell in cells[1:]:
            for span in TEST_SPAN.findall(cell):
                name = TEST_SUFFIX.sub("", re.split(r"::|\.", span.strip())[-1]) if " " not in span.strip() else ""
                if name.lower().startswith("test") and name not in known and {"rule": rule, "test": name} not in out:
                    out.append({"rule": rule, "test": name})
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ak", type=Path)
    ap.add_argument("--screen")
    ap.add_argument("--rules")
    ap.add_argument("--plan", type=Path, help="Screen_plans/<screen>.md: the rules are the ids its mapping rows carry")
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
        coverage: dict[str, Any] | None = None
        if args.coverage_map:
            try:
                map_text = args.coverage_map.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError) as err:
                raise InputError(f"cannot read --coverage-map: {err}")
            mapped = ids_in(map_text)
            known = test_names(args.tests) if args.tests else set()
            coverage = {"file": args.coverage_map.name, "namesChecked": bool(known),
                        "unknownTests": unknown_tests(map_text, known) if known else []}
        results = judge(rules, cases, cited, mapped, waived)
    except InputError as err:
        print(f"screen_rule_tests: {err}", file=sys.stderr)
        return 2
    counts = {s: sum(1 for r in results if r["state"] == s) for s in (*ORDER, "WAIVED")}
    ok = all(r["state"] in ("TESTED", "WAIVED") for r in results)
    pack = {"verdict": "BACKED" if ok else "GAPS", "counts": counts, "testsRead": len(cases), "rules": results}
    if coverage is not None:
        pack["coverageMap"] = coverage
    args.out.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for r in results:
        print(f"{r['state']:<9}{r['rule']}" + (f"  (waived: {r['waived']})" if "waived" in r else ""))
    for u in (coverage or {}).get("unknownTests", []):
        print(f"NO SUCH TEST  {u['rule']}: the coverage map names {u['test']}")
    print(f"{pack['verdict']}: " + ", ".join(f"{n} {s}" for s, n in counts.items() if n))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
