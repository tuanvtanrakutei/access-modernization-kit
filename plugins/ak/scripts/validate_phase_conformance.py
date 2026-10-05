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

A third group, READABILITY, measures what `references/technical-writing.md` asks of
the prose: diagrams before paragraphs, short sentences, no hedges. It warns and never
fails, because the reference set is its calibration and does not pass it either.

Exit 0 when every content check passes, 1 otherwise. `--strict` also fails on
apparatus. `--render` adds a content check that every Mermaid block renders.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
if str(PACKAGE / "contracts") not in sys.path:
    sys.path.insert(0, str(PACKAGE / "contracts"))

import decision_queue  # noqa: E402

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


def load_scheme_rules() -> dict[str, dict[str, Any]]:
    """`owned_by` and `requires_severity`, which nothing read until A56.

    The scheme declared both for every risk namespace and no code opened either, so
    A06's Phase 2 allocated five findings into `RS` - owned by Phase 5, and named
    "security and compliance" - and published them twice without anything objecting.
    A stated rule with no reader is not a rule, which is the whole of A33.

    Returns an empty mapping when the scheme cannot be read, so a checker that cannot
    see the rule skips rather than accuses.
    """
    scheme = Path(__file__).resolve().parents[1] / "specifications" / "identifier-scheme.yaml"
    try:
        import yaml

        data = yaml.safe_load(scheme.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}
    rules: dict[str, dict[str, Any]] = {}
    for name, body in (data.get("namespaces") or {}).items():
        body = body or {}
        rules[name] = {
            "owned_by": [str(p) for p in (body.get("owned_by") or [])],
            "requires_severity": bool(body.get("requires_severity")),
            "name": str(body.get("name") or name),
        }
    return rules


SCHEME_PATTERNS: dict[str, re.Pattern[str]] = load_scheme_patterns()
SCHEME_RULES: dict[str, dict[str, Any]] = load_scheme_rules()


def load_conformance_signals() -> dict[str, dict[str, tuple[str, ...]]]:
    """Per-language phrases for the two checks that read what a document says.

    A49. These were English substrings, and `$ak init --languages EN,JA,VI` offers to
    generate documents in three. A conformant Vietnamese Phase 1 failed both checks -
    its sections are `## Quy ước đặt tên` and `## Mức độ bao phủ nguồn` - and the
    failure text said the document held no such statement, which a reader would act on
    by adding a section that is already there. That is A47's defect in a different
    checker: wording that states a conclusion the evidence does not support.
    """
    try:
        import yaml
    except ImportError:
        return {}
    spec = Path(__file__).resolve().parents[1] / "specifications" / "language-support.yaml"
    if not spec.is_file():
        return {}
    try:
        data = yaml.safe_load(read(spec)) or {}
    except yaml.YAMLError:
        return {}
    signals = ((data.get("human_languages") or {}).get("conformance_signals") or {})
    return {check: {lang: tuple(str(p).casefold() for p in phrases)
                    for lang, phrases in (langs or {}).items()}
            for check, langs in signals.items()}


def signals_for(check: str, path: Path | None) -> tuple[str, ...]:
    """The phrases to look for, in the language this document is written in.

    Every language's phrases are searched when the suffix names one the spec does not
    carry, so an unrecognised variant degrades to *looser*, never to a failure about
    a section it has. Reporting a document as non-conformant because nobody has
    translated the checker is a defect in the checker.
    """
    by_language = CONFORMANCE_SIGNALS.get(check) or {}
    if not by_language:
        return ()
    match = LANGUAGE_SUFFIX.search(path.name) if path is not None else None
    if match is None:
        # No suffix at all is the EN document the kit writes when only one language
        # is asked for; no path at all is a caller that does not know, and gets the
        # union rather than an assumption.
        language = "EN" if path is not None else ""
    else:
        language = match.group(1)
    if language in by_language:
        return by_language[language]
    return tuple(phrase for phrases in by_language.values() for phrase in phrases)


def read(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, OSError):
            continue
    return ""


CONFORMANCE_SIGNALS = load_conformance_signals()

# `A06_Phase1_DataUnderstanding_VI.md`. The kit names its own variants this way, and a
# document with no suffix is the EN one.
LANGUAGE_SUFFIX = re.compile(r"_([A-Z]{2})(?:\.[^.]+)?$")


# An identifier is prose; a column name is code. A52: A06's Phase 1 names the SQL Server
# table `受注年月商品`, whose columns are `d1` … `d31`, and `d31` is exactly the shape of
# the `d-` namespace - so the checker reported a dangling identifier against a document
# that had allocated everything it cited.
#
# The reference set settles which way to resolve it. It writes namespace identifiers as
# plain prose in table cells (`| d01 | 店舗受注データ | …`) and writes column names inside
# backticks (`` `d31` ``, `` `合計数量 = d1+d2+...+d31` ``) - the same collision, already
# distinguished by the gold standard's own typography. So code spans are not scanned.
CODE_SPAN = re.compile(r"```.*?```|`[^`\n]*`", re.DOTALL)


def prose(text: str) -> str:
    """The document with its code spans blanked, for finding identifiers in.

    Blanked rather than removed so that nothing downstream depends on offsets shifting.
    """
    return CODE_SPAN.sub(lambda m: " " * len(m.group(0)), text)


# A54. `identifiers_wellformed` judges what the finder found, and for most namespaces the
# finder is the scheme: `OB-` is `\bOB-\d{2}\b` on both sides. So `OB-S01` is not a
# malformed OB identifier - it is not an identifier at all, and eight of them passed
# unreported. The module comment above says deriving the finder from the scheme "means a
# malformed identifier becomes invisible rather than reported"; that was fixed for `BR-`
# and left standing everywhere else.
#
# Relaxing the finders themselves would be the wrong repair: they feed
# `identifiers_resolve`, and a loose finder there invents dangling identifiers (A52).
# Instead this looks for tokens that wear a namespace's prefix and are not what that
# namespace accepts. At least one digit is required, so `E-mail` is not an `E-` finding.
NEAR_MISS_TOKEN = r"(?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,8}\d(?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,8}"


def malformed_identifiers(text: str) -> list[str]:
    """Tokens carrying a namespace prefix that the namespace does not accept."""
    found: set[str] = set()
    for namespace, finder in NAMESPACE_PATTERNS.items():
        prefix = namespace.rstrip("-")
        if not prefix.isupper() or len(prefix) > 4:
            continue          # `d-` and `r-` are lowercase indexes; too short to key on
        near = re.compile(rf"\b{re.escape(prefix)}-{NEAR_MISS_TOKEN}\b")
        for token in near.findall(text):
            if not finder.fullmatch(token):
                shape = SCHEME_PATTERNS.get(namespace)
                if shape is None or not shape.match(token):
                    found.add(token)
    return sorted(found)


def check(name: str, group: str, ok: bool, detail: str) -> dict[str, Any]:
    return {"check": name, "group": group, "status": "PASS" if ok else "FAIL", "detail": detail}


# --- content ----------------------------------------------------------------

def content_checks(phase: int, text: str, path: Path | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    lower = text.casefold()

    hits = [signal for signal in signals_for("naming_convention", path)
            if signal in lower]
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
        workflows = set(NAMESPACE_PATTERNS["WF-"].findall(prose(text)))
        enough = diagrams >= len(workflows) if workflows else diagrams >= 1
        results.append(check(
            "diagram_per_workflow", "content", enough,
            f"{diagrams} diagram(s) for {len(workflows)} workflow(s)",
        ))

    for namespace in REQUIRED_NAMESPACES.get(phase, ()):
        found = set(NAMESPACE_PATTERNS[namespace].findall(prose(text)))
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


# --- readability ------------------------------------------------------------
#
# What `references/technical-writing.md` asks of the prose, measured. A phase document
# is read once by a developer under time pressure, and the two habits that cost that
# reader most are a paragraph describing a picture nobody drew and a sentence too long to
# hold in one read.
#
# These WARN and never FAIL. The calibration is the reference set, and it does not pass
# them: its synthesis has a section with far more prose than diagrams, and more than ten
# sentences over the limit. A check the gold standard fails is a contract written wrong
# if it gates, and a question worth asking if it only reports.
#
# EN only. A word count is whitespace, which Japanese does not have, and a Vietnamese
# word is a syllable, so one threshold would mean three different things. The VI and JA
# documents translate the EN one and share its structure, so measuring EN measures them.

FENCE = re.compile(r"```.*?```", re.DOTALL)
COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
INLINE_CODE = re.compile(r"`[^`\n]*`")
LIST_MARKER = re.compile(r"^(?:[-*+]|\d+[.)])\s+")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z`(\"'*])")
# Lowercase `may` only: `May 2025` is a month. These are the modals SimpleEnglish bans
# because a reader cannot tell whether the system does the thing.
HEDGE = re.compile(r"\b(?:[Ss]hould|may|[Mm]ight|[Ww]ould)\b")

PROSE_WORDS_PER_DIAGRAM = 300
SENTENCE_WORD_LIMIT = 30          # the guidance says 25; this reports the clear cases
LONG_SENTENCES_PER_DOCUMENT = 10


def document_language(path: Path | None) -> str:
    match = LANGUAGE_SUFFIX.search(path.name) if path is not None else None
    return match.group(1) if match else "EN"


def prose_sentences(body: str) -> list[str]:
    """The running prose of a section: no fences, comments, tables, headings, quotes."""
    body = FENCE.sub("", COMMENT.sub("", body))
    # A paragraph wraps over lines; a blank line or a list item starts a new one. Joining
    # everything instead turned a table of contents into one 80-word sentence.
    units: list[list[str]] = [[]]
    for line in body.splitlines():
        stripped = line.strip()
        if not stripped or stripped[0] in "|#>" or stripped == "---":
            units.append([])
            continue
        if LIST_MARKER.match(stripped):
            units.append([])
        units[-1].append(LIST_MARKER.sub("", stripped))
    sentences: list[str] = []
    for unit in units:
        # A code span is one token to the reader, however long the identifier inside it.
        joined = INLINE_CODE.sub("CODE", " ".join(unit))
        sentences += [s for s in SENTENCE_END.split(joined) if s.strip()]
    return sentences


def h2_sections(text: str) -> list[tuple[str, str]]:
    parts = re.split(r"(?m)^## ", text)
    return [(head.strip(), body) for head, _, body in
            (part.partition("\n") for part in parts[1:])]


def readability_checks(phase: int, text: str, path: Path | None = None) -> list[dict[str, Any]]:
    def result(name: str, warn: bool, detail: str) -> dict[str, Any]:
        return {"check": name, "group": "readability",
                "status": "WARN" if warn else "PASS", "detail": detail}

    if document_language(path) != "EN":
        return [{"check": "readability", "group": "readability", "status": "SKIP",
                 "detail": "measured on the EN document only"}]

    results: list[dict[str, Any]] = []
    dense: list[str] = []
    sentences: list[str] = []
    for head, body in h2_sections(text):
        section = prose_sentences(body)
        sentences += section
        words = sum(len(s.split()) for s in section)
        diagrams = len(MERMAID.findall(body))
        if words / max(diagrams, 1) > PROSE_WORDS_PER_DIAGRAM:
            dense.append(f"{head[:50]} ({words} words, {diagrams} diagram(s))")
    results.append(result(
        "prose_per_diagram", bool(dense),
        f"over {PROSE_WORDS_PER_DIAGRAM} words of prose per diagram: {dense[:5]}" if dense
        else "every section within the limit",
    ))

    long = [s for s in sentences if len(s.split()) > SENTENCE_WORD_LIMIT]
    results.append(result(
        "long_sentences", len(long) >= LONG_SENTENCES_PER_DOCUMENT,
        f"{len(long)} of {len(sentences)} sentence(s) over {SENTENCE_WORD_LIMIT} words"
        + (f"; first: {long[0][:90]!r}" if long else ""),
    ))

    hedges = [m.group(0) for s in sentences for m in HEDGE.finditer(s)]
    examples = [s[:90] for s in sentences if HEDGE.search(s)][:2]
    results.append(result(
        "hedges", bool(hedges),
        f"{len(hedges)} hedge(s) about the system; state the fact or give it a UK- "
        f"identifier: {examples}" if hedges else "none",
    ))
    return results


def render_check(path: Path) -> dict[str, Any]:
    """Whether every Mermaid block in the document renders, by mermaid-cli.

    The templates say that a diagram which does not render is not evidence a reader can
    see, and nothing checked it. One `mmdc` call renders the
    whole document; only when it fails is each block rendered alone, to say which.
    """
    import shutil
    import subprocess
    import tempfile

    mmdc = shutil.which("mmdc")
    if mmdc is None:
        return {"check": "diagrams_render", "group": "content", "status": "SKIP",
                "detail": "mmdc not on PATH (npm install -g @mermaid-js/mermaid-cli)"}

    def renders(source: Path, out: Path) -> bool:
        return subprocess.run([mmdc, "-q", "-i", str(source), "-o", str(out)],
                              capture_output=True, timeout=300).returncode == 0

    text = read(path)
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        document = work / "document.md"
        document.write_bytes(text.encode("utf-8"))
        if renders(document, work / "out.md"):
            return check("diagrams_render", "content", True,
                         f"{len(MERMAID.findall(text))} diagram(s) render")
        broken = []
        for index, match in enumerate(re.finditer(r"(?ms)^```mermaid\n(.*?)^```", text)):
            block = work / f"block{index}.mmd"
            block.write_bytes(match.group(1).encode("utf-8"))
            if not renders(block, work / f"block{index}.svg"):
                broken.append(f"line {text.count(chr(10), 0, match.start()) + 1}")
        return check("diagrams_render", "content", False,
                     f"diagram(s) that do not render: {broken or ['unknown']}")


# --- apparatus --------------------------------------------------------------

def apparatus_checks(phase: int, text: str, registers: dict[str, Any],
                     path: Path | None = None) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    lower = text.casefold()

    coverage = [signal for signal in signals_for("source_coverage", path)
                if signal in lower]
    results.append(check(
        "source_coverage", "apparatus", bool(coverage),
        f"signals found: {coverage}" if coverage
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

    # The register is a contract, and until this check existed nothing held it to it.
    schema_errors = registers.get("evidence_schema_errors")
    if schema_errors is not None:
        results.append(check(
            "evidence_register_conforms", "apparatus", not schema_errors,
            f"{len(schema_errors)} violation(s): {schema_errors[:3]}" if schema_errors
            else "conforms to evidence.schema.json",
        ))

    # Named for what it checks rather than for the first rule it checked. It enforces
    # EC-01, EC-02 and EC-07, and a label naming one of the three sends a reader to the
    # wrong paragraph - the same stale-label defect this kit keeps finding elsewhere.
    mismatches = registers.get("class_kind_violations")
    if mismatches is not None:
        results.append(check(
            "evidence_class_supports_claim", "apparatus", not mismatches,
            f"{len(mismatches)} class/claim violation(s): {mismatches[:3]}" if mismatches
            else "every classified item makes a claim its class can support (EC-01, EC-02, EC-07)",
        ))

    # `evidence_class` and `claim_kind` are what rules EC-01 to EC-06 are written
    # against - a MEANING claim on a SCHEMA item is EC-01. An item that states
    # neither cannot be checked against any of them, so an unpopulated register makes
    # the whole rule set decorative. Reported as a count rather than a failure,
    # because the reference application does not populate them either.
    unclassified = registers.get("evidence_unclassified")
    if unclassified is not None:
        total = registers.get("evidence_total", 0)
        results.append(check(
            "evidence_classes_stated", "apparatus", not unclassified,
            f"conforms" if not unclassified
            else f"{unclassified} of {total} items state no evidence_class, so rules "
                 f"EC-01 to EC-06 cannot be checked against them",
        ))

    allocated = registers.get("identifier_ids")
    if allocated is None:
        results.append(check(
            "identifier_register", "apparatus", False,
            "no identifier register; a finding's address cannot be checked for collision or reuse",
        ))
    else:
        used: set[str] = set()
        scanned = prose(text)
        for namespace, pattern in NAMESPACE_PATTERNS.items():
            # A67. `E-` lives in the errata register, which is where the contract puts
            # it and where `errata_resolve` looks. Requiring it here too would mean
            # registering every correction twice to satisfy two checks.
            if namespace == "E-":
                continue
            used |= set(pattern.findall(scanned))
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
            malformed += [i for i in set(finder.findall(prose(text))) if not shape.match(i)]
        # And the ones no finder sees, which is where they hide (A54).
        malformed += malformed_identifiers(prose(text))
        results.append(check(
            "identifiers_wellformed", "apparatus", not malformed,
            f"{len(malformed)} off-scheme: {sorted(malformed)[:6]}" if malformed
            else "every identifier matches its namespace pattern",
        ))

    entries = registers.get("identifier_entries")
    if entries is not None and SCHEME_RULES:
        mine = [e for e in entries if e.get("phase") == phase]

        # Allocated into a namespace this phase does not own. A06's Phase 2 took five
        # numbers out of RS, which is Phase 5's and means security - so a screen-layout
        # finding was filed as a compliance one, and Phase 5's RS-01 was gone before
        # Phase 5 ran.
        trespass = []
        for entry in mine:
            rule = SCHEME_RULES.get(str(entry.get("namespace") or "").rstrip("-"))
            if rule and rule["owned_by"] and f"phase{phase}" not in rule["owned_by"]:
                trespass.append(f"{entry.get('id')} in {rule['name']} "
                                f"({', '.join(rule['owned_by'])})")
        results.append(check(
            "identifier_namespace_owned", "apparatus", not trespass,
            f"{len(trespass)} in a namespace this phase does not own: {trespass[:4]}"
            if trespass else f"{len(mine)} allocation(s), every namespace owned",
        ))

        # `requires_severity` was declared on every risk namespace and read by nothing,
        # so twelve risks reached the register with none. Phase 6 consolidates from the
        # register, not from the prose table, and would have had nothing to rank by.
        unrated = [str(entry.get("id")) for entry in mine
                   if (SCHEME_RULES.get(str(entry.get("namespace") or "").rstrip("-"))
                       or {}).get("requires_severity")
                   and not str(entry.get("severity") or "").strip()]
        results.append(check(
            "severity_recorded", "apparatus", not unrated,
            f"{len(unrated)} risk(s) with no severity: {sorted(unrated)[:6]}"
            if unrated else "every risk that requires a severity carries one",
        ))

    # Every unknown and question an earlier phase left open has to be accounted for
    # here, not silently carried to Phase 6. A06's Phase 2 named none of Phase 1's
    # fifteen, and allocated `Q108` asking what `Q103` already asked of the same owner
    # about the same file.
    if entries is not None and phase > 1:
        carried = [e for e in entries
                   if str(e.get("namespace") or "") in ("UK-", "Q")
                   and isinstance(e.get("phase"), int) and e["phase"] < phase
                   and not str(e.get("resolved_by") or "").strip()
                   and not str(e.get("superseded_by") or "").strip()]
        scanned = prose(text)
        unaccounted = sorted(str(e.get("id")) for e in carried
                             if not re.search(rf"\b{re.escape(str(e.get('id')))}\b",
                                              scanned))
        results.append(check(
            "prior_unknowns_accounted", "apparatus", not unaccounted,
            f"{len(unaccounted)} open item(s) from an earlier phase are never mentioned: "
            f"{unaccounted[:6]}" if unaccounted
            else f"{len(carried)} open item(s) from earlier phases, each accounted for",
        ))

    # A75. A person was asked in ten places and the register knew none of it: the owner of
    # a question, what waited on it, and what the pipeline did meanwhile were prose in four
    # tables. These two checks hold the fields where a program can read them, and hold the
    # document to the register (ID-07 to ID-11, and `register.needs` in the scheme). Risks
    # joined in slice 3: each one's Mitigation is a recommended answer, routed to the decider.
    if entries is not None:
        parties = registers.get("parties")
        mine = [e for e in entries if e.get("phase") == phase]
        asks = [e for e in mine if e.get("namespace") in ("Q", "UK-")]
        risks = [e for e in mine if e.get("namespace") in decision_queue.RISK_NAMESPACES]
        assumptions = [e for e in mine if e.get("namespace") == "AS-"]
        problems = decision_queue.validate_register(entries, parties, phase,
                                                    registers.get("errata_entries"))
        if parties is None and (asks or risks or any(isinstance(e.get("needs"), dict) for e in mine)):
            problems.append(
                "there is no input/decisions/parties.yaml, so no party can be checked and "
                "no question routed")
        elif parties is not None:
            problems += [f"parties.yaml: {p}" for p in parties.problems]
        results.append(check(
            "decision_fields_present", "apparatus", not problems,
            f"{len(problems)} problem(s), first: {problems[:3]}" if problems
            else f"{len(asks)} question(s) and unknown(s), {len(risks)} risk(s) and "
                 f"{len(assumptions)} assumption(s) allocated here, each routable"
            if asks or risks or assumptions else "no question, unknown, risk or assumption allocated in this phase",
        ))

        comparison = decision_queue.compare_document(
            text, phase, entries, parties, signals_for("closed_item", path))
        note = (f"; {comparison.unstructured} cell(s) are prose, name nothing a program can "
                f"follow, and were not compared" if comparison.unstructured else "")
        results.append(check(
            "decision_tables_agree", "apparatus", not comparison.findings,
            f"{len(comparison.findings)} disagreement(s), first: {comparison.findings[:3]}"
            if comparison.findings
            else f"{comparison.compared} row(s) compared against the register{note}",
        ))

    # A67. Errata was checked in Phase 6 only, and corrections do not wait for Phase 6.
    # A06's Phase 3 corrected two published Phase 1 risks - the actor behind the `99`
    # placeholders, and what destroys `準備数` - wrote **corrected** in its
    # carried-forward table, and registered neither. The contract already allows this
    # (ER-06: an entry may correct a claim in any phase); nothing enforced it, and `E-`
    # was owned by Phase 6 alone, so the remedy could not be carried out before Phase 6
    # existed.
    errata = registers.get("errata_ids")
    cited_errata = set(NAMESPACE_PATTERNS["E-"].findall(prose(text)))
    if phase == 6 and errata is None:
        results.append(check(
            "errata_register", "apparatus", False,
            "Phase 6 without an errata register cannot supersede an earlier claim",
        ))
    if cited_errata or errata is not None:
        dangling = sorted(cited_errata - (errata or set()))
        results.append(check(
            "errata_resolve", "apparatus", not dangling,
            f"{len(dangling)} dangling, first: {dangling[:6]}" if dangling
            else f"{len(cited_errata)} entry reference(s)",
        ))

    # A correction a document announces and does not register is the prohibition in
    # errata-contract.yaml: the prose stops saying the wrong thing and the record that
    # the analysis changed its mind is gone, which is the record a reviewer needs.
    if phase > 1:
        announced = [signal for signal in signals_for("correction", path)
                     if signal in lower]
        results.append(check(
            "corrections_registered", "apparatus", not announced or bool(cited_errata),
            f"this document says an earlier claim was corrected ({announced[:3]}) and "
            f"cites no E- entry; errata-contract.yaml forbids correcting a published "
            f"claim without registering it" if announced and not cited_errata
            else f"{len(cited_errata)} correction(s) registered" if cited_errata
            else "no correction announced",
        ))
    return results


def load_registers(outputs: Path) -> dict[str, Any]:
    registers: dict[str, Any] = {}

    def ids_from(pattern: str, key: str, field: str) -> None:
        # `registers/` as well as the top level: the registers moved down a level when
        # the published set grew catalogues, and a checker that only looked at the top
        # reported every register missing on a correctly published run.
        matches = [m for where in (".", "registers")
                   for m in sorted((outputs / where).glob(pattern))]
        if len(matches) != 1:
            return
        try:
            data = json.loads(read(matches[0]) or "{}")
        except json.JSONDecodeError:
            return
        items = data.get("items") or data.get("entries") or []
        registers[key] = {item[field] for item in items if isinstance(item, dict) and field in item}

    def entries_from(pattern: str, key: str) -> None:
        """The whole row, not just its id - ownership and severity live in the row."""
        matches = [m for where in (".", "registers")
                   for m in sorted((outputs / where).glob(pattern))]
        if len(matches) != 1:
            return
        try:
            data = json.loads(read(matches[0]) or "{}")
        except json.JSONDecodeError:
            return
        registers[key] = [item for item in (data.get("items") or data.get("entries") or [])
                          if isinstance(item, dict)]

    ids_from("*_Evidence.json", "evidence_ids", "id")
    ids_from("*_Identifiers.json", "identifier_ids", "id")
    ids_from("*_Errata.json", "errata_ids", "id")
    entries_from("*_Identifiers.json", "identifier_entries")
    entries_from("*_Errata.json", "errata_entries")
    # Next to glossary.yaml and meanings.yaml, which `outputs.parent` already reaches for
    # the same reason (annotate_bilingual). None when the file is absent, which the check
    # reports; a project that predates the file is not the same as one that wrote it wrong.
    registers["parties"] = decision_queue.load_parties(
        outputs.parent / "input" / "decisions" / "parties.yaml")
    registers["evidence_schema_errors"] = _schema_errors(outputs)
    registers["class_kind_violations"] = _class_kind_violations(outputs)
    matches = [m for where in (".", "registers")
               for m in sorted((outputs / where).glob("*_Evidence.json"))]
    if len(matches) == 1:
        try:
            items = (json.loads(read(matches[0]) or "{}").get("items") or [])
        except json.JSONDecodeError:
            items = []
        registers["evidence_total"] = len(items)
        registers["evidence_unclassified"] = sum(
            1 for item in items
            if isinstance(item, dict) and not item.get("evidence_class"))
    return registers


def _class_kind_violations(outputs: Path) -> list[str] | None:
    """Items making a claim their evidence class cannot support - EC-01, EC-02, EC-07.

    The rule was prose in `specifications/evidence-classes.yaml` and the two fields
    it is written against were unpopulated in every register, so it had never once
    been evaluated. Its first run found three: two BEHAVIOUR statements labelled
    INTENT, and a BEHAVIOUR conclusion drawn from a screenshot.
    """
    matches = [m for where in (".", "registers")
               for m in sorted((outputs / where).glob("*_Evidence.json"))]
    spec = Path(__file__).resolve().parents[1] / "specifications" / "evidence-classes.yaml"
    if len(matches) != 1 or not spec.is_file():
        return None
    try:
        import yaml
    except ImportError:
        return None
    try:
        classes = (yaml.safe_load(read(spec)) or {}).get("evidence_classes") or {}
        items = (json.loads(read(matches[0]) or "{}").get("items") or [])
    except (json.JSONDecodeError, yaml.YAMLError):
        return None
    violations = []
    for item in items:
        if not isinstance(item, dict):
            continue
        klass, kind = item.get("evidence_class"), item.get("claim_kind")
        if not klass or not kind:
            continue
        entry = classes.get(klass) or {}
        if kind in (entry.get("cannot_support") or []):
            violations.append(f"{item.get('id')}: {klass} cannot support {kind}")
            continue
        # Only half of every EC rule was enforced here: the explicit `cannot_support`
        # list. A claim kind a class simply does not declare - not forbidden, not
        # listed - passed. That let `DOCUMENT` carry a `SCOPE` claim, which is EC-07's
        # other half: no reading of the legacy application establishes what the
        # replacement should contain. The rule was written and nothing enforced it,
        # which is A13 in the checker that A13 was about.
        #
        # `corroborates` is deliberately not a violation. An item whose class only
        # corroborates a kind is a real item and belongs in the register; what EC-01
        # forbids is a *claim in a document* resting on it alone, and that is a
        # different check on a different artifact.
        if kind not in (entry.get("supports") or []) and kind not in (entry.get("corroborates") or []):
            violations.append(
                f"{item.get('id')}: {klass} does not declare support for {kind}"
                + (f"; a {kind} claim requires TARGET_INTENT (EC-07)" if kind == "SCOPE" else "")
            )
    return violations


def _schema_errors(outputs: Path) -> list[str] | None:
    """What the evidence register violates in `schemas/evidence.schema.json`.

    None when the register or the schema cannot be found, which the caller reports
    differently from a register that is present and wrong.
    """
    matches = [m for where in (".", "registers")
               for m in sorted((outputs / where).glob("*_Evidence.json"))]
    if len(matches) != 1:
        return None
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / "evidence.schema.json"
    if not schema_path.is_file():
        return None
    try:
        import jsonschema
    except ImportError:
        return None
    try:
        schema = json.loads(read(schema_path) or "{}")
        data = json.loads(read(matches[0]) or "{}")
    except json.JSONDecodeError as error:
        return [f"unreadable: {error}"]
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for error in sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path)):
        where = "/".join(str(part) for part in error.absolute_path) or "(root)"
        errors.append(f"{where}: {error.message}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--outputs", required=True, type=Path,
                        help="Directory holding the published phase documents")
    parser.add_argument("--strict", action="store_true",
                        help="Fail on apparatus checks as well as content")
    parser.add_argument("--group", choices=("content", "apparatus", "readability", "all"),
                        default="all")
    parser.add_argument("--render", action="store_true",
                        help="Render every Mermaid block with mmdc; a broken one fails content")
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
    content_failed = apparatus_failed = readability_warned = 0

    for phase, path in documents:
        text = read(path)
        results = []
        if args.group in ("content", "all"):
            results += content_checks(phase, text, path)
            if args.render:
                results.append(render_check(path))
        if args.group in ("apparatus", "all"):
            results += apparatus_checks(phase, text, registers, path)
        if args.group in ("readability", "all"):
            results += readability_checks(phase, text, path)
        content_failed += sum(1 for r in results if r["group"] == "content" and r["status"] == "FAIL")
        apparatus_failed += sum(1 for r in results if r["group"] == "apparatus" and r["status"] == "FAIL")
        readability_warned += sum(1 for r in results if r["status"] == "WARN")
        report["phases"].append({"phase": phase, "document": path.name, "checks": results})

    report["content_failures"] = content_failed
    report["apparatus_failures"] = apparatus_failed
    report["readability_warnings"] = readability_warned
    report["status"] = "FAIL" if content_failed or (args.strict and apparatus_failed) else "PASS"

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"{report['status']}: {len(documents)} phase document(s); "
              f"{content_failed} content failure(s), {apparatus_failed} apparatus failure(s), "
              f"{readability_warned} readability warning(s)")
        for entry in report["phases"]:
            failures = [r for r in entry["checks"] if r["status"] == "FAIL"]
            warnings = [r for r in entry["checks"] if r["status"] == "WARN"]
            marker = "ok" if not failures else f"{len(failures)} failure(s)"
            if warnings:
                marker += f", {len(warnings)} warning(s)"
            print(f"  Phase {entry['phase']} — {entry['document']}: {marker}")
            for result in failures + warnings:
                print(f"      [{result['group']}] {result['check']}: {result['detail']}")

    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
