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
        for pattern in NAMESPACE_PATTERNS.values():
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

    if phase == 6:
        errata = registers.get("errata_ids")
        if errata is None:
            results.append(check(
                "errata_register", "apparatus", False,
                "Phase 6 without an errata register cannot supersede an earlier claim",
            ))
        else:
            used = set(NAMESPACE_PATTERNS["E-"].findall(prose(text)))
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
            results += content_checks(phase, text, path)
        if args.group in ("apparatus", "all"):
            results += apparatus_checks(phase, text, registers, path)
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
