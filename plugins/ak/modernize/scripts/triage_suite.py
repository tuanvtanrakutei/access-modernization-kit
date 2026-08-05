#!/usr/bin/env python3
"""Group a failing test suite by error signature instead of by file.

Reads a test run's output and reports the distinct *causes*, largest first. It
runs nothing and changes nothing; you pipe a run into it.

Why signature and not file: a red suite read file-by-file looks like many
independent problems and gets triaged one test at a time. Grouped by normalized
error text it usually collapses to a handful of causes. Measured on this project
twice - 24 failures turned out to be one root cause, and 49 failures resolved
into three groups of which two were fixed in a few lines each.

ERROR and FAILED are reported separately and ERROR comes first, because they are
different findings. A failure says something is wrong; an error says the test
body never ran, so the behaviour it covers has never been checked at all. A pass
count quoted from a run that had errors is misleading.

Normalization folds the parts that vary between instances of one cause: numbers,
quoted strings, hex addresses, and object reprs. So

    assert 3 == 4
    assert 17 == 20

both become `assert N == N` and group together.

Usage:
    pytest ... | python triage_suite.py
    python triage_suite.py --input run.txt --report triage.md

Exit status is always 0 - this is an analysis tool, not a gate.
"""

from __future__ import annotations

import argparse
import collections
import io
import re
import sys

# Lines pytest uses for the per-test verdict list.
VERDICT_RE = re.compile(r"^(FAILED|ERROR)\s+(\S+?)(?:\s|$)")


def is_test_node(token: str) -> bool:
    """True for a pytest node id, false for a captured log line.

    Both start with the word ERROR, which is the trap: a verdict reads
    `ERROR tests/test_x.py::test_y` while captured output reads
    `ERROR  pkg.mod.service:service.py:257 message`. Counting the second kind as
    an error is worse than a cosmetic bug here - this tool argues that an ERROR
    means a test body never ran, so inflating the count with log noise
    undermines the one distinction it exists to make. Nine log lines were
    reported as errors on the first run against a real suite.

    A node id carries `::` or is a bare path ending in `.py`; a logger target
    carries single colons separating module, file and line.
    """
    if ".py" not in token:
        return False
    head = token.split("::", 1)[0]
    if ":" in head:
        return False
    return "::" in token or head.endswith(".py")
# Lines that carry the actual error, in --tb=line or --tb=short form.
ERROR_LINE_RE = re.compile(r"^(?:[A-Za-z]:)?[^\s:]*[/\\][^\s:]+:\d+:\s*(.+)$")
ASSERT_RE = re.compile(r"^E\s+(.+)$")

SUMMARY_RE = re.compile(r"(\d+) (failed|passed|skipped|error|errors|warning|warnings)")


def normalize(text: str) -> str:
    """Fold the varying parts of one cause into a single signature."""
    t = text.strip()
    t = re.sub(r"0x[0-9a-fA-F]+", "0xADDR", t)
    t = re.sub(r"<([A-Za-z_][\w.]*)\s+[^>]*>", r"<\1 ...>", t)
    t = re.sub(r"'[^']*'", "'X'", t)
    t = re.sub(r'"[^"]*"', '"X"', t)
    t = re.sub(r"\b\d+\b", "N", t)
    t = re.sub(r"\s+", " ", t)
    return t[:200]


def parse(lines: list[str]):
    verdicts: list[tuple[str, str]] = []
    signatures: collections.Counter = collections.Counter()
    examples: dict[str, str] = {}
    summary: dict[str, int] = {}

    for line in lines:
        stripped = line.rstrip("\n")

        m = VERDICT_RE.match(stripped)
        if m and is_test_node(m.group(2)):
            verdicts.append((m.group(1), m.group(2)))
            continue

        m = ERROR_LINE_RE.match(stripped)
        if m:
            sig = normalize(m.group(1))
            if sig:
                signatures[sig] += 1
                examples.setdefault(sig, stripped.strip()[:180])
            continue

        m = ASSERT_RE.match(stripped)
        if m:
            sig = normalize(m.group(1))
            if sig and not sig.startswith("+"):
                signatures[sig] += 1
                examples.setdefault(sig, stripped.strip()[:180])
            continue

        if " failed" in stripped or " passed" in stripped:
            for count, word in SUMMARY_RE.findall(stripped):
                key = word.rstrip("s")
                summary[key] = max(summary.get(key, 0), int(count))

    return verdicts, signatures, examples, summary


def build_report(verdicts, signatures, examples, summary) -> str:
    errors = [name for kind, name in verdicts if kind == "ERROR"]
    failures = [name for kind, name in verdicts if kind == "FAILED"]

    out: list[str] = ["# Suite triage", ""]

    if summary:
        out.append("Run summary: " + ", ".join(
            "%s %d" % (k, summary[k]) for k in ("failed", "error", "passed", "skipped") if k in summary))
        out.append("")

    if errors:
        out.append("## Errors first - %d" % len(errors))
        out.append("")
        out.append("An ERROR means the test body never ran, so whatever it covers has never been")
        out.append("checked. Resolve these before reading failures, and do not quote a pass count")
        out.append("from this run without saying it had errors.")
        out.append("")
        for name in errors:
            out.append("- `%s`" % name)
        out.append("")

    out.append("## Distinct causes, largest first")
    out.append("")
    if not signatures:
        out.append("No error lines were recognised. Re-run with `--tb=line` or `--tb=short`;")
        out.append("`--tb=no` omits the text this tool groups on.")
    else:
        out.append("| Count | Signature | Example |")
        out.append("|---|---|---|")
        for sig, count in signatures.most_common():
            ex = examples.get(sig, "").replace("|", "\\|")
            out.append("| %d | `%s` | %s |" % (count, sig.replace("|", "\\|"), ex))
        out.append("")
        top = signatures.most_common(1)[0]
        total = sum(signatures.values())
        out.append("Largest cause covers %d of %d grouped lines (%d%%)." % (
            top[1], total, round(100 * top[1] / total)))

    if failures:
        out.append("")
        out.append("## Failing tests - %d" % len(failures))
        out.append("")
        for name in failures:
            out.append("- `%s`" % name)

    out.append("")
    out.append("## Before acting")
    out.append("")
    out.append("- **Establish the baseline.** Confirm which of these failed before your change,")
    out.append("  by stashing it and re-running. A count on its own attributes nothing.")
    out.append("- **One cause, one fix.** Take the largest signature first; the count is how many")
    out.append("  tests a single fix would clear.")
    out.append("- **A signature is not a diagnosis.** Identical text can have two causes. Open one")
    out.append("  instance of each group before deciding.")
    return "\n".join(out) + "\n"


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Group failing tests by error signature.")
    ap.add_argument("--input", default="", help="file with the run output (default: stdin)")
    ap.add_argument("--report", default="", help="write the UTF-8 report here")
    args = ap.parse_args(argv)

    if args.input:
        lines = io.open(args.input, encoding="utf-8", errors="replace").read().split("\n")
    else:
        lines = sys.stdin.read().split("\n")

    verdicts, signatures, examples, summary = parse(lines)
    report = build_report(verdicts, signatures, examples, summary)

    if args.report:
        io.open(args.report, "w", encoding="utf-8", newline="\n").write(report)

    # ASCII-only console summary: a cp932 console must not crash on a Japanese
    # assertion message and turn an analysis run into a traceback.
    errors = sum(1 for k, _ in verdicts if k == "ERROR")
    failures = sum(1 for k, _ in verdicts if k == "FAILED")
    sys.stdout.write("triage: %d failed, %d error, %d distinct cause(s)\n" % (
        failures, errors, len(signatures)))
    for sig, count in signatures.most_common(10):
        ascii_sig = sig.encode("ascii", "replace").decode("ascii")
        sys.stdout.write("  %3d  %s\n" % (count, ascii_sig[:100]))
    if args.report:
        sys.stdout.write("report: %s\n" % args.report)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
