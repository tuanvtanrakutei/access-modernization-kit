#!/usr/bin/env python3
"""Check that a published phase document carries what the phase contract promises.

Structure was the only thing the kit ever specified, and structure is the one thing
a thin document has: a run can fill every declared heading and still say nothing a
migration team can use. So the checks here are about what a document *establishes* -
does it name its production terms, does it draw the relationships, does it give its
findings addresses other phases can cite - not about whether its headings match a
template's.

That distinction is not cosmetic. The reference set this kit was built from uses
different heading text in every phase, and a checker that demanded template headings
would fail the gold standard while passing a document that copied the template and
filled it with counts. It would be measuring the wrong thing precisely.

Two groups, and the split is the honest part:

  CONTENT   - what makes a phase document worth reading. Calibrated against the
              reference set, which passes all of it. A content check that the
              reference fails is a contract written wrong, not a document at fault.

  APPARATUS - the evidence machinery this kit adds: a source-coverage block by
              evidence class, a resolvable evidence register, an identifier
              register, an errata register. The reference set has none of it - it
              cites its sources in prose and has no machine-checkable trail - so it
              is expected to fail this group, and that gap is exactly what the kit
              exists to close.

Exit 0 when every content check passes, 1 otherwise. `--strict` also fails on
apparatus.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PHASE_FILE = re.compile(r"Phase([1-6])_", re.IGNORECASE)
MERMAID = re.compile(r"^```mermaid", re.MULTILINE)
PLACEHOLDER = re.compile(r"\{\{[A-Z_]+\}\}")
INSTRUCTION = re.compile(r"<!--")
CITATION = re.compile(r"\b[A-Z][A-Z0-9_-]{1,15}-P[1-6]-[A-Z][A-Z0-9_]*-\d{3,}\b")

# The namespaces a phase cannot do its job without. Calibrated against the reference
# set: it allocates OB- in Phase 1, F- in Phase 2, BR- from Phase 3 onward, WF- in
# Phase 4, DISC- in Phase 5, and the risk, unknown and errata registers in Phase 6.
# Phase 1 is deliberately not required to carry RD- or UK-, because the reference
# does not - it records risks and unknowns as prose there and gives them addresses
# only in Phase 6. That is a weakness worth naming, not one to enforce retroactively
# against a document that predates the scheme.
REQUIRED_NAMESPACES: dict[int, tuple[str, ...]] = {
    1: ("OB-",),
    2: ("F-",),
    3: ("BR-",),
    4: ("WF-", "BR-"),
    5: ("DISC-", "BR-"),
    6: ("BR-", "RD-", "UK-", "AS-", "E-"),
}

# Finding an identifier in prose and judging whether it is well formed are two jobs,
# and one pattern cannot do both. Deriving the finder from the scheme's own pattern
# made the finder as strict as the scheme, which means a malformed identifier becomes
# invisible rather than reported - and it failed the reference set, whose Phase 3
# writes `BR-M01`. The finder below is deliberately permissive; SCHEME_PATTERNS judges
# the shape, in the apparatus group, where the reference is expected to fall short.
#
# The finder is still checked against the scheme: test_phase_conformance asserts that
# every namespace the scheme declares has one here, and that each accepts everything
# its scheme pattern accepts. That is what was missing when `RA-`, `RW-`, `RS-` and `Q`
# were absent from this table while the scheme declared all four.
NAMESPACE_PATTERNS: dict[str, re.Pattern[str]] = {
    "OB-": re.compile(r"\bOB-\d{2}\b"),
    "F-": re.compile(r"\bF-\d{3}\b"),
    "BR-": re.compile(r"\bBR-[A-Z0-9]{1,6}(?:-\d{2}|\d{2})\b"),
    "WF-": re.compile(r"\bWF-\d{3}[a-z]?\b"),
    "DISC-": re.compile(r"\bDISC-\d{2}\b"),
    "RD-": re.compile(r"\bRD-\d{2}\b"),
    "RA-": re.compile(r"\bRA-\d{2}\b"),
    "RW-": re.compile(r"\bRW-\d{2}\b"),
    "RS-": re.compile(r"\bRS-\d{2}\b"),
    "UK-": re.compile(r"\bUK-[A-Z]?\d{2}\b"),
    "AS-": re.compile(r"\bAS-\d{2}\b"),
    "E-": re.compile(r"\bE-\d{2}\b"),
    "Q-": re.compile(r"\bQ\d{1,3}\b"),
    "d-": re.compile(r"\bd\d{2}\b"),
    "r-": re.compile(r"\br\d{2}\b"),
}


def load_scheme_patterns() -> dict[str, re.Pattern[str]]:
    """The scheme's own patterns, keyed the way NAMESPACE_PATTERNS is keyed.

    Returns an empty mapping when the scheme cannot be read, which turns the
    wellformedness check into a skip rather than a false accusation.
    """
    scheme = Path(__file__).resolve().parents[1] / "specifications" / "identifier-scheme.yaml"
    try:
        import yaml

        data = yaml.safe_load(scheme.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    patterns: dict[str, re.Pattern[str]] = {}
    for name, body in (data.get("namespaces") or {}).items():
        pattern = (body or {}).get("pattern")
        if pattern:
            patterns[f"{name}-"] = re.compile(pattern)
    return patterns


SCHEME_PATTERNS: dict[str, re.Pattern[str]] = load_scheme_patterns()


# Words that show the document said what its terms mean rather than translating them.
NAMING_SIGNALS = ("naming convention", "production name", "romaji", "never translate")


def read(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, OSError):
            continue
    return ""


def check(name: str, group: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"check": name, "group": group, "status": "PASS" if ok else "FAIL", "detail": detail}


# --- content ----------------------------------------------------------------

def content_checks(phase: int, text: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    lower = text.lower()

    hits = [signal for signal in NAMING_SIGNALS if signal in lower]
    results.append(check(
        "naming_convention", "content", bool(hits),
        f"signals found: {hits}" if hits
        else "no statement about how production names are treated; a reader cannot tell "
             "a real table name from a gloss",
    ))

    diagrams = len(MERMAID.findall(text))
    results.append(check(
        "diagram_present", "content", diagrams >= 1,
        f"{diagrams} mermaid diagram(s)",
    ))

    if phase == 4:
        workflows = set(NAMESPACE_PATTERNS["WF-"].findall(text))
        enough = diagrams >= len(workflows) if workflows else diagrams >= 1
        results.append(check(
            "diagram_per_workflow", "content", enough,
            f"{diagrams} diagram(s) for {len(workflows)} workflow(s)",
        ))

    for namespace in REQUIRED_NAMESPACES.get(phase, ()):
        found = set(NAMESPACE_PATTERNS[namespace].findall(text))
        results.append(check(
            f"identifiers:{namespace}", "content", bool(found),
            f"{len(found)} allocated" if found
            else f"no {namespace} identifiers; findings in this phase have no address "
                 "another phase can cite",
        ))

    leftovers = sorted(set(PLACEHOLDER.findall(text)))
    results.append(check(
        "no_unfilled_placeholders", "content", not leftovers,
        f"unfilled: {leftovers[:6]}" if leftovers else "none",
    ))

    instructions = len(INSTRUCTION.findall(text))
    results.append(check(
        "no_template_instructions", "content", instructions == 0,
        f"{instructions} instruction comment block(s) left in the published document"
        if instructions else "none",
    ))
    return results


# --- apparatus --------------------------------------------------------------

def apparatus_checks(phase: int, text: str, registers: dict[str, Any]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    lower = text.lower()

    results.append(check(
        "source_coverage", "apparatus", "source coverage" in lower,
        "present" if "source coverage" in lower
        else "no per-class statement of what was available and what its absence cost "
             "(evidence-classes.yaml, rule EC-06)",
    ))

    cited = set(CITATION.findall(text))
    known = registers.get("evidence_ids")
    if known is None:
        results.append(check("evidence_register", "apparatus", False, "no evidence register found"))
    else:
        dangling = sorted(cited - known)
        results.append(check(
            "evidence_citations_resolve", "apparatus", not dangling,
            f"dangling: {dangling[:6]}" if dangling else f"{len(cited)} citation(s), all resolve",
        ))
        results.append(check(
            "claims_are_cited", "apparatus", bool(cited),
            f"{len(cited)} citation(s)" if cited else "no evidence cited anywhere in the document",
        ))

    allocated = registers.get("identifier_ids")
    if allocated is None:
        results.append(check(
            "identifier_register", "apparatus", False,
            "no identifier register; a finding's address cannot be checked for collision or reuse",
        ))
    else:
        used: set[str] = set()
        for pattern in NAMESPACE_PATTERNS.values():
            used |= set(pattern.findall(text))
        dangling = sorted(used - allocated)
        results.append(check(
            "identifiers_resolve", "apparatus", not dangling,
            f"{len(dangling)} dangling, first: {dangling[:6]}" if dangling
            else f"{len(used)} identifier(s), all allocated",
        ))

    if SCHEME_PATTERNS:
        malformed: list[str] = []
        for namespace, finder in NAMESPACE_PATTERNS.items():
            shape = SCHEME_PATTERNS.get(namespace)
            if shape is None:
                continue
            malformed += [i for i in set(finder.findall(text)) if not shape.match(i)]
        results.append(check(
            "identifiers_wellformed", "apparatus", not malformed,
            f"{len(malformed)} off-scheme: {sorted(malformed)[:6]}" if malformed
            else "every identifier matches its namespace pattern",
        ))

    if phase == 6:
        errata = registers.get("errata_ids")
        if errata is None:
            results.append(check(
                "errata_register", "apparatus", False,
                "Phase 6 without an errata register cannot supersede an earlier claim",
            ))
        else:
            used = set(NAMESPACE_PATTERNS["E-"].findall(text))
            dangling = sorted(used - errata)
            results.append(check(
                "errata_resolve", "apparatus", not dangling,
                f"{len(dangling)} dangling, first: {dangling[:6]}" if dangling
                else f"{len(used)} entry reference(s)",
            ))
    return results


def load_registers(outputs: Path) -> dict[str, Any]:
    registers: dict[str, Any] = {}

    def ids_from(pattern: str, key: str, field: str) -> None:
        matches = sorted(outputs.glob(pattern))
        if len(matches) != 1:
            return
        try:
            data = json.loads(read(matches[0]) or "{}")
        except json.JSONDecodeError:
            return
        items = data.get("items") or data.get("entries") or []
        registers[key] = {item[field] for item in items if isinstance(item, dict) and field in item}

    ids_from("*_Evidence.json", "evidence_ids", "id")
    ids_from("*_Identifiers.json", "identifier_ids", "id")
    ids_from("*_Errata.json", "errata_ids", "id")
    return registers


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--outputs", required=True, type=Path,
                        help="Directory holding the published phase documents")
    parser.add_argument("--strict", action="store_true",
                        help="Fail on apparatus checks as well as content")
    parser.add_argument("--group", choices=("content", "apparatus", "all"), default="all")
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    # The documents this reads are Japanese and the report quotes their names back.
    # On a cp932 console that kills the whole report after the summary line - the
    # same defect this kit already fixed once in `ak.py print_json`, arriving in a
    # new script because the fix lived in one function rather than in a habit.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
    outputs: Path = args.outputs
    if not outputs.is_dir():
        print(f"error: no such directory: {outputs}", file=sys.stderr)
        return 2

    registers = load_registers(outputs)
    documents: list[tuple[int, Path]] = []
    for path in sorted(outputs.glob("*.md")):
        match = PHASE_FILE.search(path.name)
        if match:
            documents.append((int(match.group(1)), path))
    if not documents:
        print(f"error: no phase documents found in {outputs}", file=sys.stderr)
        return 2

    report: dict[str, Any] = {"outputs": str(outputs), "phases": []}
    content_failed = apparatus_failed = 0

    for phase, path in documents:
        text = read(path)
        results = []
        if args.group in ("content", "all"):
            results += content_checks(phase, text)
        if args.group in ("apparatus", "all"):
            results += apparatus_checks(phase, text, registers)
        content_failed += sum(1 for r in results if r["group"] == "content" and r["status"] == "FAIL")
        apparatus_failed += sum(1 for r in results if r["group"] == "apparatus" and r["status"] == "FAIL")
        report["phases"].append({"phase": phase, "document": path.name, "checks": results})

    report["content_failures"] = content_failed
    report["apparatus_failures"] = apparatus_failed
    report["status"] = "FAIL" if content_failed or (args.strict and apparatus_failed) else "PASS"

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{report['status']}: {len(documents)} phase document(s); "
              f"{content_failed} content failure(s), {apparatus_failed} apparatus failure(s)")
        for entry in report["phases"]:
            failures = [r for r in entry["checks"] if r["status"] == "FAIL"]
            marker = "ok" if not failures else f"{len(failures)} failure(s)"
            print(f"  Phase {entry['phase']} — {entry['document']}: {marker}")
            for result in failures:
                print(f"      [{result['group']}] {result['check']}: {result['detail']}")

    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
