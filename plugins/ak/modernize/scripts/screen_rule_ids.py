#!/usr/bin/env python3
"""Check, and propose, the rule ids of a screen the extraction's register holds no rule for.

    python3 screen_rule_ids.py --registry Screens_Registry.md --screen <name>
        [--plan Screen_plans/<screen>.md] [--ak <register dir>] [--prefix LOC] [--strict] [--json]

Rules get their ids from the extraction when it found them: a register entry `BR-ORD-01`. A screen
the extraction never traced, or one it traced without finding a rule, still has rules, and they
are written down at Stage 2 in the screen plan's Legacy-To-New Mapping table. Those need ids a
test can cite and a result file can be read against, and ids that cannot collide with another
screen's: every screen numbers its rules from 01, so two screens each had their own `BR-02`.

The id is `BR-<PREFIX>-<nn>`, and it is minted in the plan's mapping table, one per row:

  PREFIX  one to six capitals or digits, the first a capital, declared once per screen in the
          registry's optional `rule_prefix` column and unique across the registry. It also may not
          equal a scope the register already uses (`ORD` in `BR-ORD-01`).
  nn      two digits, never renumbered and never reused, even when the rule is retired.

This script reads the registry, the plan and, with `--ak`, the register, and reports:

  - the prefix, declared or proposed (a proposal is not a decision: a person declares it);
  - for each mapping row, the id the row carries and whether it is acceptable: a register id that
    exists, or a minted id of this screen;
  - what a row needs: a bare local `BR-02` is certainly a rule and becomes `BR-<PREFIX>-02`. A row
    with no id is listed and left alone, because the mapping holds one row per rule *or legacy
    concept* (a screen title, a button, an undecided question) and only a rule carries an id;
    `--strict` treats such a row as a rule too and gives it the next free number;
  - findings: a duplicate id, another screen's prefix, an id with an unknown scope, a register id
    the register does not hold, a declared prefix that collides.

It never writes a file: the agent edits the plan, the person declares the prefix. A reference to
another id after the row's own (`BR-LOC-01 (BF BR-01)`) is not the row's id; only the first id in
the rule cell is.

Exit status: 0 nothing to do, 1 a finding or a row that needs an id, 2 an input cannot be read.
Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import screen_decisions as sd  # noqa: E402
import screen_scope as ss  # noqa: E402

PREFIX = re.compile(r"[A-Z][A-Z0-9]{0,5}")
PREFIXED = re.compile(r"BR-([A-Z][A-Z0-9]{0,5})-([0-9]{2})([a-z]?)")
BARE = re.compile(r"BR-([0-9]{2,3})")
SEPARATOR = re.compile(r"^:?-{3,}:?$")
# Anything that starts like a rule id, so a malformed one is reported and not mistaken for a row with no id.
LOOSE = re.compile(r"(?<![A-Za-z0-9_-])BR-[A-Za-z0-9][A-Za-z0-9-]*")


def cells(line: str) -> list[str]:
    return [c.strip().strip("`").strip() for c in line.strip().strip("|").split("|")]


def tables(text: str) -> list[tuple[list[str], list[list[str]]]]:
    """Every pipe table in `text` as (header cells, data rows). A table ends at the first line that is not a row."""
    out: list[tuple[list[str], list[list[str]]]] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and all(SEPARATOR.match(c) for c in cells(lines[i + 1]) if c):
            header, rows = cells(lines[i]), []
            i += 2
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append(cells(lines[i]))
                i += 1
            out.append((header, rows))
        else:
            i += 1
    return out


def registry_rows(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as err:
        raise sd.Problem(f"{path} cannot be read: {err}")
    for header, rows in tables(text):
        if "screen" in header and "screen_key" in header:
            return [{h: (r[n] if n < len(r) else "") for n, h in enumerate(header)} for r in rows]
    raise sd.Problem(f"{path} has no table with `screen` and `screen_key` columns")


def register_scopes(ak: Path | None) -> tuple[set[str], set[str]]:
    """(the scopes the register's BR- entries use, the ids it holds)."""
    if ak is None:
        return set(), set()
    register = ss.optional(ak, "*_Identifiers.json", "register")
    if register is None:
        raise sd.Problem(f"{ak} holds no *_Identifiers.json")
    scopes, ids = set(), set()
    for e in (ss.read_json(register).get("entries") or []):
        if isinstance(e, dict) and e.get("namespace") == ss.RULE_NAMESPACE:
            ids.add(str(e.get("id")))
            m = re.match(r"BR-([A-Z0-9]{1,6})-[0-9]{2}", str(e.get("id")))
            if m:
                scopes.add(m.group(1))
    return scopes, ids


def propose_prefix(key: str, taken: set[str]) -> str:
    words = [w for w in re.split(r"[^a-z0-9]+", key.lower()) if w]
    stems = ["".join(w[0] for w in words), (words[0] if words else "")[:3], (words[0] if words else "")[:6],
             "".join(w[:3] for w in words)[:6], "".join(w[:2] for w in words)[:6]]
    for stem in stems:
        cand = stem.upper()
        if PREFIX.fullmatch(cand) and cand not in taken:
            return cand
    base = (stems[1] or "R").upper()[:4] or "R"
    for n in range(1, 100):
        cand = f"{base}{n}"
        if PREFIX.fullmatch(cand) and cand not in taken:
            return cand
    return "R"


def mapping_rows(plan: Path) -> list[dict[str, Any]]:
    try:
        text = plan.read_text(encoding="utf-8-sig")
    except OSError as err:
        raise sd.Problem(f"{plan} cannot be read: {err}")
    body = ss.sections(text, ss.MAPPING_HEADING)
    if body is None:
        raise sd.Problem(f"{plan} has no Legacy-To-New Mapping section")
    rows: list[dict[str, Any]] = []
    for header, data in tables(body):
        col = next((n for n, h in enumerate(header) if "rule" in h.lower()), None)
        if col is None:
            continue
        for r in data:
            cell = r[col] if col < len(r) else ""
            found = LOOSE.search(cell)
            rows.append({"n": len(rows) + 1, "cell": cell, "id": found.group(0).rstrip("-") if found else None})
    if not rows:
        raise sd.Problem(f"{plan}: the mapping section has no table with a Rule column")
    return rows


def build(registry: Path, screen: str, plan: Path | None, ak: Path | None, prefix_arg: str | None, strict: bool = False) -> dict[str, Any]:
    rows = registry_rows(registry)
    mine = [r for r in rows if sd.norm(r.get("screen", "")) == screen]
    if len(mine) != 1:
        raise sd.Problem(f"the registry has {'no' if not mine else 'more than one'} row for `{screen}`")
    me = mine[0]
    scopes, register_ids = register_scopes(ak)
    findings: list[str] = []

    declared = {r["screen"]: r.get("rule_prefix", "").strip() for r in rows if r.get("rule_prefix", "").strip()}
    others = {p: s for s, p in declared.items() if s != me["screen"]}
    for p in {*declared.values()}:
        if not PREFIX.fullmatch(p):
            findings.append(f"declared rule_prefix `{p}` is not one to six capitals or digits starting with a capital")
    for p in sorted({p for p in declared.values() if list(declared.values()).count(p) > 1}):
        findings.append(f"rule_prefix `{p}` is declared by more than one screen")
    for p in sorted(set(declared.values()) & scopes):
        findings.append(f"rule_prefix `{p}` is already a scope of the register's rules")

    own = (prefix_arg or me.get("rule_prefix", "")).strip()
    state = "declared" if own else "proposed"
    if not own:
        own = propose_prefix(me.get("screen_key", ""), set(declared.values()) | scopes)
        findings.append(f"no rule_prefix is declared for this screen; add `rule_prefix` = `{own}` (or another) to its registry row")

    result: dict[str, Any] = {"screen": screen, "screen_key": me.get("screen_key"), "prefix": own, "prefix_state": state,
                              "rows": [], "findings": findings}
    if plan is None:
        return result

    used: dict[str, int] = {}
    numbers: set[int] = set()
    parsed = mapping_rows(plan)
    for row in parsed:
        rid = row["id"]
        m = PREFIXED.fullmatch(rid or "")
        if m and m.group(1) == own:
            numbers.add(int(m.group(2)))
    for row in parsed:
        rid, kind, want = row["id"], "", None
        m, bare = PREFIXED.fullmatch(rid or ""), BARE.fullmatch(rid or "")
        if rid is None:
            kind = "none"
        elif bare:
            kind = "bare"
        elif m and m.group(1) == own:
            kind = "minted"
        elif m and m.group(1) in others:
            kind = "other-screen"
            findings.append(f"row {row['n']} carries {rid}, which belongs to {others[m.group(1)]}")
        elif rid in register_ids:
            kind = "register"
        elif m and m.group(1) in scopes:
            kind = "unknown-register"
            findings.append(f"row {row['n']} carries {rid}, a register-style id the register does not hold")
        elif m:
            kind = "unknown-scope"
            findings.append(f"row {row['n']} carries {rid}, whose scope `{m.group(1)}` is no screen's prefix and not in the register")
        else:
            kind = "malformed"
            findings.append(f"row {row['n']} carries {rid}, which is neither `BR-<PREFIX>-nn` nor a bare `BR-nn`")
        if rid and kind in ("minted", "register"):
            if rid in used:
                findings.append(f"{rid} is carried by rows {used[rid]} and {row['n']}")
            used.setdefault(rid, row["n"])
        if kind == "bare" or (kind == "none" and strict):
            nn = int(bare.group(1)) if bare else None
            if nn is None or nn in numbers or nn > 99:
                nn = max(numbers | {0}) + 1
            numbers.add(nn)
            want = f"BR-{own}-{nn:02d}"
        row.update(kind=kind, propose=want)
        result["rows"].append(row)
    needs = [r for r in result["rows"] if r["propose"]]
    if needs:
        findings.append(f"{len(needs)} mapping row(s) need an id: " + ", ".join(f"row {r['n']} -> {r['propose']}" for r in needs))
    return result


def render(report: dict[str, Any]) -> str:
    out = [f"Rule ids of `{report['screen']}` (screen_key `{report['screen_key']}`, prefix `{report['prefix']}` {report['prefix_state']})", ""]
    for r in report["rows"]:
        label = r["id"] or "(no id)"
        note = {"none": "no id (a legacy concept, or a rule that needs one)"}.get(r["kind"], r["kind"])
        out.append(f"  row {r['n']:<3} {label:<14} " + (f"-> {r['propose']}" if r["propose"] else f"ok ({r['kind']})" if r["kind"] in ("minted", "register") else note))
    out.append("")
    if report["findings"]:
        out.append(f"## Findings ({len(report['findings'])})")
        out += [f"- {f}" for f in report["findings"]]
    else:
        out.append("Nothing to do.")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--registry", required=True, type=Path, help="Screens_Registry.md")
    ap.add_argument("--screen", required=True, help="the `screen` value of the registry, verbatim")
    ap.add_argument("--plan", type=Path, help="Screen_plans/<screen>.md: also check its mapping rows")
    ap.add_argument("--ak", type=Path, help="the extraction's register folder, to tell register ids from minted ones")
    ap.add_argument("--prefix", help="use this prefix instead of the registry's rule_prefix")
    ap.add_argument("--strict", action="store_true", help="a row with no id is a rule that needs one, not a legacy concept")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        report = build(args.registry, sd.norm(args.screen), args.plan, args.ak, args.prefix, args.strict)
    except sd.Problem as err:
        print(f"error: {err}", file=sys.stderr)
        return 2
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=1) + "\n" if args.json else render(report))
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
