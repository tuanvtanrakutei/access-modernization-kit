#!/usr/bin/env python3
"""Decide whether the new system's output matches the legacy system's output, by comparing bytes.

    python3 screen_parity.py <cases.json> [--out PARITY.json] [--quiet] [--allow-outside]

The verdict comes from the bytes, never from a reader's opinion. A report, an export or a
response that the legacy system produced is saved once; the new system produces the same
output from the same input; this script compares the two files. Input:

    {"legacy": {"label": "how the legacy output was produced"},
     "new":    {"label": "how the new output was produced"},
     "tolerance": {"rel": 1e-9, "why": "optional default for every case"},
     "cases": [{"id": "P01", "title": "Order list, one customer",
                "legacy": "out/legacy/P01.csv", "new": "out/new/P01.csv",
                "mask": [{"bytes": "0-18", "why": "run timestamp"},
                         {"regex": "\\\\d{4}-\\\\d{2}-\\\\d{2} \\\\d{2}:\\\\d{2}", "why": "print time"}],
                "tolerance": {"rel": 1e-9, "abs": 0, "why": "last-digit rounding"},
                "approvedDifference": "optional: why a person accepted a difference"}]}

Paths are relative to the cases file's folder and may not leave it unless --allow-outside is
given. `bytes` ranges are 0-based and inclusive; `regex` runs on the bytes read as latin-1.
Every masked span, on both sides, becomes one fixed marker, so a mask never hides where a
difference is, and a span of a different length still compares equal. A case is:

  same             identical after masking
  differs          different; the first difference is recorded
  differs-approved different, and the case carries a reason a person gave for accepting it
  missing          a file is absent, unreadable, too large or outside the folder: never a pass

A tolerance lets numbers written with a decimal point or an exponent differ in the last digits
(another compiler, another math library). Every other byte, every integer and every dotted run
such as 1.2.3 must match exactly. A tolerance needs a reason, and one above 1% relative or
1e-6 absolute is refused: that is a different result, not rounding.

Fresh inputs: a case may say `"origin": "fresh"`, with the `"input"` file it ran on and a `"kind"`
(boundary, empty, oversize, malformed, order, encoding...). A fresh input is one written after the
build, by someone who did not choose the recorded cases, and run on the legacy system too, so a
suite or a sample set that only passes on its author's cases is caught. With `--min-fresh N` and
`--min-kinds K` the verdict needs N fresh cases that were compared, each on input bytes no other
case used, covering K kinds. Without the options nothing is required and the count is only reported.

Self-check: before the verdict the comparator is run on a copy with one byte added; if that
does not differ, the comparator is broken and the result is a failure.

Exit status: 0 only when at least one case was compared, none is missing or differs (an
approved difference is allowed), the self-check passed and some compared output was not empty;
1 otherwise; 2 when the input cannot be used. Writes the result file and nothing else.

Stdlib only, so it runs in a project that has installed nothing.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

MARK = b"\x00<MASK>\x00"
MAX_BYTES = 64 * 1024 * 1024
MAX_TOLERANT_BYTES = 8 * 1024 * 1024
MAX_REL = 0.01
MAX_ABS = 1e-6
MAX_NUMBER_CHARS = 64
# A dotted run such as 1.2.3 is an identifier, not a number: it stays inside the text around it.
NUMBER = re.compile(
    rb"(?P<dotted>\d+(?:\.\d+){2,})|(?P<num>[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[eE][-+]?\d+)?)"
)
FLOAT_FORM = re.compile(rb"[.eE]")


class InputError(Exception):
    """The cases file cannot be used; the verdict is not attempted."""


def reason(spec: Any, what: str) -> str:
    text = spec.strip() if isinstance(spec, str) else ""
    if not text:
        raise InputError(f"{what} needs a 'why' saying what is accepted and why")
    return text[:300]


def parse_masks(specs: Any, cid: str) -> list[tuple[str, Any, str]]:
    masks: list[tuple[str, Any, str]] = []
    if specs is None:
        return masks
    if not isinstance(specs, list):
        raise InputError(f"case {cid}: 'mask' must be a list")
    for spec in specs:
        if not isinstance(spec, dict) or ("bytes" in spec) == ("regex" in spec):
            raise InputError(f"case {cid}: each mask needs exactly one of 'bytes' or 'regex'")
        why = reason(spec.get("why"), f"case {cid}: a mask")
        if "bytes" in spec:
            ranges = []
            for part in str(spec["bytes"]).split(","):
                m = re.fullmatch(r"\s*(\d+)\s*(?:-\s*(\d+))?\s*", part)
                if not m or (m.group(2) and int(m.group(2)) < int(m.group(1))):
                    raise InputError(f"case {cid}: bad byte range {part!r}")
                ranges.append((int(m.group(1)), int(m.group(2) or m.group(1))))
            masks.append(("bytes", ranges, why))
        else:
            try:
                masks.append(("regex", re.compile(str(spec["regex"])), why))
            except re.error as err:
                raise InputError(f"case {cid}: bad regex {spec['regex']!r}: {err}")
    return masks


def parse_tolerance(spec: Any, cid: str) -> dict[str, Any] | None:
    if spec is None:
        return None
    if not isinstance(spec, dict):
        raise InputError(f"case {cid}: 'tolerance' must be an object with rel, abs and why")
    try:
        rel, ab = float(spec.get("rel", 0)), float(spec.get("abs", 0))
    except (TypeError, ValueError):
        raise InputError(f"case {cid}: the tolerance's rel and abs must be numbers")
    if not (math.isfinite(rel) and math.isfinite(ab)) or rel < 0 or ab < 0 or (rel == 0 and ab == 0):
        raise InputError(f"case {cid}: give a positive rel or abs tolerance")
    if rel > MAX_REL:
        raise InputError(f"case {cid}: a relative tolerance above 1% is a different result, not rounding")
    if ab > MAX_ABS:
        raise InputError(f"case {cid}: an absolute tolerance above {MAX_ABS:g} is a different result, not rounding")
    return {"rel": rel, "abs": ab, "why": reason(spec.get("why"), f"case {cid}: a tolerance")}


def apply_masks(data: bytes, masks: list[tuple[str, Any, str]]) -> tuple[bytes, list[str]]:
    """Replace every masked span with MARK. Spans are merged first, so overlapping masks cost one marker."""
    spans: list[tuple[int, int]] = []
    used: list[str] = []
    for kind, what, why in masks:
        found = 0
        if kind == "bytes":
            for lo, hi in what:
                if lo < len(data):
                    spans.append((lo, min(hi, len(data) - 1) + 1))
                    found += 1
        else:
            text = data.decode("latin-1")
            for m in what.finditer(text):
                if m.end() > m.start():
                    spans.append((m.start(), m.end()))
                    found += 1
        if found:
            used.append(f"{kind} ({why})")
    spans.sort()
    merged: list[list[int]] = []
    for lo, hi in spans:
        if merged and lo <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], hi)
        else:
            merged.append([lo, hi])
    out, at = bytearray(), 0
    for lo, hi in merged:
        out += data[at:lo] + MARK
        at = hi
    out += data[at:]
    return bytes(out), used


def tokens(data: bytes) -> list[tuple[bool, bytes]]:
    """Cover `data` end to end as (is_float, bytes); everything that is not a float-form number is text."""
    out: list[tuple[bool, bytes]] = []
    text = bytearray()
    at = 0
    for m in NUMBER.finditer(data):
        text += data[at:m.start()]
        at = m.end()
        raw = m.group(0)
        if m.group("num") is not None and FLOAT_FORM.search(raw) and len(raw) <= MAX_NUMBER_CHARS:
            if text:
                out.append((False, bytes(text)))
                text = bytearray()
            out.append((True, raw))
        else:
            text += raw
    text += data[at:]
    if text:
        out.append((False, bytes(text)))
    return out


def within(a: bytes, b: bytes, tol: dict[str, Any]) -> tuple[bool, float]:
    try:
        x, y = Decimal(a.decode("ascii")), Decimal(b.decode("ascii"))
    except (InvalidOperation, UnicodeDecodeError):
        return False, math.inf
    if not (x.is_finite() and y.is_finite()):
        return False, math.inf
    diff = abs(x - y)
    scale = max(abs(x), abs(y))
    rel = float(diff / scale) if scale else 0.0
    ok = diff <= Decimal(repr(tol["abs"])) or (scale > 0 and rel <= tol["rel"])
    return ok, rel


def first_difference(a: bytes, b: bytes) -> dict[str, Any]:
    n = min(len(a), len(b))
    at = next((i for i in range(n) if a[i] != b[i]), n)

    def show(d: bytes) -> str:
        return d[max(0, at - 8): at + 24].decode("latin-1").encode("unicode_escape").decode("ascii")

    return {"offset": at, "legacyLength": len(a), "newLength": len(b), "legacy": show(a), "new": show(b)}


def compare_bytes(a: bytes, b: bytes, tol: dict[str, Any] | None) -> tuple[bool, dict[str, Any]]:
    """(same, detail). With a tolerance only float-form numbers may differ, and only within it."""
    if a == b:
        return True, {}
    if tol is None or max(len(a), len(b)) > MAX_TOLERANT_BYTES:
        return False, first_difference(a, b)
    ta, tb = tokens(a), tokens(b)
    if len(ta) != len(tb):
        return False, first_difference(a, b)
    worst = 0.0
    for (fa, xa), (fb, xb) in zip(ta, tb):
        if fa != fb:
            return False, first_difference(a, b)
        if xa == xb:
            continue
        if not fa:
            return False, first_difference(a, b)
        ok, rel = within(xa, xb, tol)
        if not ok:
            return False, first_difference(a, b)
        worst = max(worst, rel)
    return True, {"largestRelativeDifference": worst}


def read_side(root: Path, name: Any, allow_outside: bool) -> tuple[bytes | None, str]:
    if not isinstance(name, str) or not name:
        return None, "no path given"
    path = (root / name).resolve()
    if not allow_outside and root not in path.parents:
        return None, "path leaves the cases folder"
    try:
        if not path.is_file():
            return None, "file is absent"
        if path.stat().st_size > MAX_BYTES:
            return None, "file is larger than the limit"
        return path.read_bytes(), ""
    except OSError as err:
        return None, f"unreadable: {err.strerror or err}"


def judge(cases: list[dict[str, Any]], root: Path, default_tol: dict[str, Any] | None, allow_outside: bool) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for i, case in enumerate(cases):
        if not isinstance(case, dict):
            raise InputError(f"case {i + 1} is not an object")
        cid = str(case.get("id") or "").strip()
        if not cid or cid in seen:
            raise InputError(f"case {i + 1}: every case needs a unique 'id'")
        seen.add(cid)
        masks = parse_masks(case.get("mask"), cid)
        tol = parse_tolerance(case.get("tolerance"), cid) or default_tol
        approved = case.get("approvedDifference")
        if approved is not None:
            approved = reason(approved, f"case {cid}: an approvedDifference")
        origin = case.get("origin", "recorded")
        if origin not in ("recorded", "fresh"):
            raise InputError(f"case {cid}: 'origin' is 'recorded' or 'fresh'")
        kind = str(case.get("kind") or "").strip().lower()
        if origin == "fresh" and not (kind and case.get("input")):
            raise InputError(f"case {cid}: a fresh case needs a 'kind' (boundary, empty, malformed...) and the 'input' file it ran on")
        rec: dict[str, Any] = {"id": cid, "title": str(case.get("title") or "")[:200], "legacy": case.get("legacy"), "new": case.get("new"),
                               "origin": origin}
        if kind:
            rec["kind"] = kind
        if case.get("input"):
            raw, why_in = read_side(root, case.get("input"), allow_outside)
            if raw is None:
                rec["inputProblem"] = f"input: {why_in}"
            else:
                rec["inputHash"] = hashlib.sha256(raw).hexdigest()
        a, why_a = read_side(root, case.get("legacy"), allow_outside)
        b, why_b = read_side(root, case.get("new"), allow_outside)
        if a is None or b is None:
            rec.update(state="missing", detail=f"legacy: {why_a}" if a is None else f"new: {why_b}")
            results.append(rec)
            continue
        ma, used_a = apply_masks(a, masks)
        mb, used_b = apply_masks(b, masks)
        same, detail = compare_bytes(ma, mb, tol)
        rec["bytes"] = {"legacy": len(a), "new": len(b)}
        rec["masked"] = sorted(set(used_a + used_b))
        rec["empty"] = len(a) == 0 and len(b) == 0
        if tol is not None:
            rec["tolerance"] = tol
        rec["_masked"] = (ma, mb)
        if same:
            rec.update(state="same", **({"detail": detail} if detail else {}))
        else:
            rec.update(state="differs-approved" if approved else "differs", firstDifference=detail)
            if approved:
                rec["approvedDifference"] = approved
        results.append(rec)
    return results


def self_check(results: list[dict[str, Any]]) -> tuple[bool, str]:
    """A comparator that cannot tell a changed output from an unchanged one proves nothing."""
    for rec in results:
        if "_masked" in rec:
            ma, _ = rec["_masked"]
            same, _ = compare_bytes(ma, ma + b"\x01", None)
            return (not same), "one added byte was " + ("not detected" if same else "detected")
    return False, "no case was compared"


def fresh_report(results: list[dict[str, Any]], min_fresh: int, min_kinds: int) -> tuple[dict[str, Any], list[str]]:
    """Count the inputs that nobody had used before: written after the build, and not the same input twice.

    A suite or a sample set that only passes on the cases its author chose says little. A fresh case
    counts once, when it was compared, its input file is known, and no recorded case or earlier fresh
    case ran on the same input bytes.
    """
    used = {r["inputHash"] for r in results if r.get("origin") == "recorded" and r.get("inputHash")}
    counted: list[dict[str, Any]] = []
    not_counted: list[dict[str, str]] = []
    for r in results:
        if r.get("origin") != "fresh":
            continue
        if r["state"] == "missing":
            why = "an output file is missing"
        elif "inputProblem" in r:
            why = r["inputProblem"]
        elif r["inputHash"] in used:
            why = "its input was already used by another case"
        else:
            used.add(r["inputHash"])
            counted.append(r)
            continue
        not_counted.append({"id": r["id"], "why": why})
    kinds = sorted({r["kind"] for r in counted})
    problems = []
    if len(counted) < min_fresh:
        problems.append(f"only {len(counted)} fresh input(s) counted; {min_fresh} needed")
    if len(kinds) < min_kinds:
        problems.append(f"fresh inputs cover {len(kinds)} kind(s); {min_kinds} needed")
    return {"required": min_fresh, "requiredKinds": min_kinds, "counted": len(counted), "kinds": kinds, "notCounted": not_counted}, problems


def build(cases_path: Path, allow_outside: bool, min_fresh: int = 0, min_kinds: int = 0) -> dict[str, Any]:
    try:
        doc = json.loads(cases_path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as err:
        raise InputError(f"cannot read {cases_path.name}: {err}")
    if not isinstance(doc, dict) or not isinstance(doc.get("cases"), list) or not doc["cases"]:
        raise InputError("the cases file must be an object with a non-empty 'cases' list")
    root = cases_path.parent.resolve()
    results = judge(doc["cases"], root, parse_tolerance(doc.get("tolerance"), "(default)"), allow_outside)
    ok, note = self_check(results)
    for rec in results:
        rec.pop("_masked", None)
    counts = {s: sum(1 for r in results if r["state"] == s) for s in ("same", "differs", "differs-approved", "missing")}
    compared = counts["same"] + counts["differs"] + counts["differs-approved"]
    nonempty = any(r["state"] != "missing" and not r["empty"] for r in results)
    problems = []
    if not compared:
        problems.append("no case was compared")
    if counts["missing"]:
        problems.append(f"{counts['missing']} case(s) missing a file")
    if counts["differs"]:
        problems.append(f"{counts['differs']} case(s) differ")
    if compared and not nonempty:
        problems.append("every compared output was empty")
    if not ok:
        problems.append("comparator self-check failed: " + note)
    fresh, fresh_problems = fresh_report(results, min_fresh, min_kinds)
    problems += fresh_problems
    return {
        "legacy": doc.get("legacy"), "new": doc.get("new"),
        "verdict": "PARITY" if not problems else "NO PARITY",
        "problems": problems, "counts": counts, "selfCheck": {"passed": ok, "note": note},
        "freshInputs": fresh, "cases": results,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cases")
    ap.add_argument("--out")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--allow-outside", action="store_true")
    ap.add_argument("--min-fresh", type=int, default=0, help="fresh inputs that must be compared (the rule is 10)")
    ap.add_argument("--min-kinds", type=int, default=0, help="distinct kinds those fresh inputs must cover")
    args = ap.parse_args(argv)
    if args.min_fresh < 0 or args.min_kinds < 0:
        print("screen_parity: --min-fresh and --min-kinds cannot be negative", file=sys.stderr)
        return 2
    cases_path = Path(args.cases)
    try:
        pack = build(cases_path, args.allow_outside, args.min_fresh, args.min_kinds)
    except InputError as err:
        print(f"screen_parity: {err}", file=sys.stderr)
        return 2
    out = Path(args.out) if args.out else cases_path.with_name("PARITY.json")
    out.write_text(json.dumps(pack, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    if not args.quiet:
        for r in pack["cases"]:
            extra = r.get("detail") if isinstance(r.get("detail"), str) else ""
            if r["state"] in ("differs", "differs-approved"):
                extra = f"first difference at byte {r['firstDifference']['offset']}"
            print(f"{r['state']:<17}{r['id']}  {extra}".rstrip())
        fr = pack["freshInputs"]
        if fr["counted"] or fr["required"]:
            print(f"fresh inputs: {fr['counted']} counted, kinds: {', '.join(fr['kinds']) or 'none'}")
        print(f"{pack['verdict']}: " + ("; ".join(pack["problems"]) or f"{pack['counts']['same']} same"))
    return 0 if pack["verdict"] == "PARITY" else 1


if __name__ == "__main__":
    sys.exit(main())
