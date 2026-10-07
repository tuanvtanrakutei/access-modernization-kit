#!/usr/bin/env python3
"""Gate G4: read the three verification results of one screen and say what they leave unproved.

    python3 screen_verify.py --screen <name> [--parity PARITY.json] [--canary CANARY.json ...]
        [--rule-tests RULE_TESTS.json] [--output-screen] [--json]

Stage 4 writes tests and runs them. Gates G1 to G3 check coverage; this one checks that the
verification itself is evidence and not a claim. It reads what the other scripts wrote and adds
nothing of its own:

  PARITY.json      `screen_parity.py`      does the new output match the saved legacy output
  CANARY.json      `screen_canary.py`      can the tests fail (one file per canary run)
  RULE_TESTS.json  `screen_rule_tests.py`  which rules a test that ran and passed names

Findings, with the severity ladder of `TRACEBACK_GATES.md`:

  HIGH    the parity result says NO PARITY; a rule's test failed; a canary SURVIVED (the tests
          cannot see a line that matters); the rule-test result is missing; the screen produces
          output (`--output-screen`) and has no parity result
  MEDIUM  a rule is NOT RUN, CLAIMED or UNTESTED; a canary is INCONCLUSIVE or had NO BASELINE; no
          canary was run; the fresh-input minimum was not met; a result file cannot be read
  LOW     a difference a person accepted (differs-approved); a rule a person waived

A result file that is missing is a finding, not a pass: the gate exists so that "verified" is never
inferred from silence. The file's own verdict is trusted only as far as the file says: this script
does not re-run anything and does not check how old a result is, so run the three scripts after the
last code change.

Exit status: 0 no finding, 1 at least one finding, 2 an input cannot be used. Reads files, writes
nothing. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HIGH, MEDIUM, LOW = "HIGH", "MEDIUM", "LOW"
RULE_SEVERITY = {"FAILING": HIGH, "NOT RUN": MEDIUM, "CLAIMED": MEDIUM, "UNTESTED": MEDIUM}
CANARY_SEVERITY = {"SURVIVED": HIGH, "INCONCLUSIVE": MEDIUM, "NO BASELINE": MEDIUM}
RANK = {HIGH: 0, MEDIUM: 1, LOW: 2}


def load(path: Path | None, what: str, findings: list[dict[str, str]], missing: str) -> dict[str, Any] | None:
    if path is None:
        if missing:
            findings.append(finding(missing, f"no {what} result was given"))
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as err:
        findings.append(finding(MEDIUM, f"{what} result {path.name} cannot be read: {err}"))
        return None
    if not isinstance(data, dict):
        findings.append(finding(MEDIUM, f"{what} result {path.name} is not an object"))
        return None
    return data


def finding(severity: str, text: str) -> dict[str, str]:
    return {"gate": "G4", "severity": severity, "text": text}


def check_parity(data: dict[str, Any], findings: list[dict[str, str]]) -> None:
    cases = data.get("cases") if isinstance(data.get("cases"), list) else []
    if data.get("verdict") != "PARITY":
        problems = "; ".join(str(p) for p in data.get("problems") or []) or "no reason recorded"
        fresh_only = bool(data.get("problems")) and all("fresh input" in str(p) for p in data["problems"])
        findings.append(finding(MEDIUM if fresh_only else HIGH, f"parity: {data.get('verdict') or 'no verdict'}: {problems}"))
    for case in cases:
        if isinstance(case, dict) and case.get("state") == "differs-approved":
            findings.append(finding(LOW, f"parity case {case.get('id')} differs and a person accepted it: {case.get('approvedDifference')}"))


def check_rules(data: dict[str, Any], findings: list[dict[str, str]]) -> None:
    for rule in data.get("rules") or []:
        if not isinstance(rule, dict):
            continue
        state, rid = rule.get("state"), rule.get("rule")
        if state in RULE_SEVERITY:
            findings.append(finding(RULE_SEVERITY[state], f"rule {rid} is {state}: no test that ran and passed names it"))
        elif state == "WAIVED" and rule.get("wouldBe") == "TESTED":
            findings.append(finding(LOW, f"rule {rid} is waived, but a test that ran and passed now names it: drop the waiver ({rule.get('waived')})"))
        elif state == "WAIVED":
            findings.append(finding(LOW, f"rule {rid} was waived ({rule.get('wouldBe')}): {rule.get('waived')}"))


def check_canary(data: dict[str, Any], name: str, findings: list[dict[str, str]]) -> None:
    verdict = data.get("verdict")
    where = data.get("break") if isinstance(data.get("break"), dict) else {}
    spot = f"{where.get('file')}:{where.get('line')}" if where else name
    if verdict in CANARY_SEVERITY:
        findings.append(finding(CANARY_SEVERITY[verdict], f"canary at {spot} is {verdict}: {data.get('why')}"))
    elif verdict != "CAUGHT":
        findings.append(finding(MEDIUM, f"canary {name} has no usable verdict"))


def build(args: argparse.Namespace) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    parity = load(args.parity, "parity", findings, HIGH if args.output_screen else "")
    rules = load(args.rule_tests, "rule-test", findings, HIGH)
    if parity is not None:
        check_parity(parity, findings)
    if rules is not None:
        check_rules(rules, findings)
    if not args.canary:
        findings.append(finding(MEDIUM, "no canary was run: nothing shows the tests can fail"))
    for path in args.canary:
        data = load(path, "canary", findings, "")
        if data is not None:
            check_canary(data, path.name, findings)
    findings.sort(key=lambda f: RANK[f["severity"]])
    return {"screen": args.screen, "findings": findings,
            "read": {"parity": parity is not None, "ruleTests": rules is not None, "canaries": len(args.canary)}}


def render(report: dict[str, Any]) -> str:
    out = [f"Verification of `{report['screen']}` (gate G4)", ""]
    read = report["read"]
    out.append(f"- Read: parity {'yes' if read['parity'] else 'no'}, rule tests {'yes' if read['ruleTests'] else 'no'}, "
               f"{read['canaries']} canary result(s)")
    out.append("")
    if report["findings"]:
        out.append(f"## Findings ({len(report['findings'])})")
        out += [f"- {f['gate']} {f['severity']}: {f['text']}" for f in report["findings"]]
    else:
        out.append("No findings.")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--screen", required=True)
    ap.add_argument("--parity", type=Path)
    ap.add_argument("--rule-tests", type=Path)
    ap.add_argument("--canary", type=Path, nargs="*", default=[])
    ap.add_argument("--output-screen", action="store_true", help="the screen produces a file or a response, so a parity result is required")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    if not args.screen.strip():
        print("error: --screen is empty", file=sys.stderr)
        return 2
    report = build(args)
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=1) + "\n" if args.json else render(report))
    return 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
