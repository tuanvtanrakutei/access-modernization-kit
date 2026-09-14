"""The conformance checker, and the one regression that keeps it honest.

A checker written against a template measures conformance to that template. This
one is written against what a phase document must *establish*, and the way to prove
the difference is to run it over the reference set the kit was built from: if the
gold standard fails a content check, the contract is wrong and the document is not.

That regression runs here whenever the reference set is on this machine, and is
skipped rather than faked when it is not - a test that quietly passes because its
subject is absent is worse than no test.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

import validate_phase_conformance as checker  # noqa: E402

REFERENCE = Path("D:/Anrakutei/a01_docs")


def write(root: Path, name: str, body: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    path = root / name
    path.write_text(body, encoding="utf-8")
    return path


def run(outputs: Path, *extra: str) -> int:
    argv = sys.argv
    sys.argv = ["validate_phase_conformance.py", "--outputs", str(outputs), *extra]
    try:
        return checker.main()
    finally:
        sys.argv = argv


# --- content checks ---------------------------------------------------------

def test_a_document_with_no_diagram_fails() -> None:
    results = checker.content_checks(1, "# X\n\nNaming convention: production names.\n\nOB-01 something.\n")
    failed = {r["check"] for r in results if r["status"] == "FAIL"}
    assert "diagram_present" in failed


def test_a_document_whose_findings_have_no_address_fails() -> None:
    """A finding no later phase can cite is a finding Phase 6 cannot consolidate."""
    body = "# X\n\nProduction names are kept.\n\n```mermaid\ngraph TD\n```\n"
    results = checker.content_checks(4, body)
    failed = {r["check"] for r in results if r["status"] == "FAIL"}
    assert "identifiers:WF-" in failed and "identifiers:BR-" in failed


def test_a_document_that_never_says_how_it_treats_names_fails() -> None:
    results = checker.content_checks(2, "# X\n\n```mermaid\ngraph TD\n```\n\nF-001 something.\n")
    failed = {r["check"] for r in results if r["status"] == "FAIL"}
    assert "naming_convention" in failed


def test_unfilled_placeholders_and_left_in_instructions_fail() -> None:
    body = (
        "# {{APP_ID}}\n\nProduction names.\n\n<!-- delete this -->\n"
        "```mermaid\ngraph TD\n```\n\nOB-01 x.\n"
    )
    results = checker.content_checks(1, body)
    failed = {r["check"] for r in results if r["status"] == "FAIL"}
    assert {"no_unfilled_placeholders", "no_template_instructions"} <= failed


def test_phase4_needs_a_diagram_for_every_workflow() -> None:
    body = (
        "Production names.\n\n```mermaid\ngraph TD\n```\n\n"
        "WF-001 WF-002 WF-003 and BR-ORD-01.\n"
    )
    results = checker.content_checks(4, body)
    result = next(r for r in results if r["check"] == "diagram_per_workflow")
    assert result["status"] == "FAIL"
    assert "1 diagram(s) for 3 workflow(s)" in result["detail"]


def test_a_complete_phase1_document_passes_content() -> None:
    body = (
        "## Naming Convention\n\nProduction names, never translate. Romaji alias.\n\n"
        "```mermaid\nerDiagram\n```\n\n| OB-01 | something | evidence |\n"
    )
    results = checker.content_checks(1, body)
    assert all(r["status"] == "PASS" for r in results), [r for r in results if r["status"] == "FAIL"]


# --- apparatus checks -------------------------------------------------------

def test_a_document_citing_evidence_that_does_not_exist_fails_apparatus() -> None:
    registers = {"evidence_ids": {"A99-P1-NAV-001"}}
    results = checker.apparatus_checks(1, "See `A99-P1-NAV-007`.", registers)
    result = next(r for r in results if r["check"] == "evidence_citations_resolve")
    assert result["status"] == "FAIL" and "A99-P1-NAV-007" in result["detail"]


def test_a_document_with_no_source_coverage_fails_apparatus() -> None:
    results = checker.apparatus_checks(1, "# X", {})
    failed = {r["check"] for r in results if r["status"] == "FAIL"}
    assert "source_coverage" in failed


def test_phase6_without_an_errata_register_fails_apparatus() -> None:
    results = checker.apparatus_checks(6, "# X", {})
    failed = {r["check"] for r in results if r["status"] == "FAIL"}
    assert "errata_register" in failed


# --- end to end -------------------------------------------------------------

def test_content_failures_fail_the_run_and_apparatus_alone_does_not(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    write(outputs, "A99_Phase1_DataUnderstanding_EN.md",
          "## Naming Convention\n\nProduction names.\n\n```mermaid\ngraph TD\n```\n\nOB-01 x.\n")
    # Content complete, apparatus absent: passes by default, fails under --strict.
    assert run(outputs) == 0
    assert run(outputs, "--strict") == 1


def test_a_missing_outputs_directory_is_an_error_not_a_pass(tmp_path: Path) -> None:
    assert run(tmp_path / "nowhere") == 2


def test_a_directory_with_no_phase_documents_is_an_error(tmp_path: Path) -> None:
    outputs = tmp_path / "outputs"
    write(outputs, "notes.md", "hello")
    assert run(outputs) == 2


# --- the regression the contract is judged by -------------------------------

@pytest.mark.skipif(not REFERENCE.is_dir(), reason="reference document set not on this machine")
def test_the_reference_set_passes_every_content_check() -> None:
    """If this fails, the contract is wrong - not the reference.

    The reference set is the standard the kit was built from. A content check it
    cannot satisfy is a check demanding something that was never necessary to
    produce a document a migration team could use.
    """
    assert run(REFERENCE, "--group", "content") == 0


@pytest.mark.skipif(not REFERENCE.is_dir(), reason="reference document set not on this machine")
def test_the_reference_set_fails_apparatus_and_that_is_the_point() -> None:
    """It cites its sources in prose and has no machine-checkable trail.

    Which is precisely the gap this kit exists to close: excellent content with no
    way to verify a single citation mechanically. Asserting the failure keeps the
    two groups from quietly merging.
    """
    assert run(REFERENCE, "--strict") == 1


# --- the finder table against the scheme ------------------------------------
#
# The finder table used to be a hand-written copy of the scheme's namespaces, and it
# drifted: `RA-`, `RW-`, `RS-` and `Q` were declared in the scheme and absent here, so
# the first Phase 3 this kit produced allocated eight risks and four questions that no
# check could see. Deriving the finders from the scheme instead was worse - it made the
# finder as strict as the scheme, which hides a malformed identifier rather than
# reporting it, and failed the reference set. So the two tables stay separate and these
# tests hold them together.


def test_every_scheme_namespace_has_a_finder() -> None:
    missing = sorted(set(checker.SCHEME_PATTERNS) - set(checker.NAMESPACE_PATTERNS))
    assert not missing, (
        f"{missing} are declared in identifier-scheme.yaml but nothing looks for them, "
        "so identifiers in those namespaces are invisible to every check"
    )


def test_every_finder_has_a_scheme_namespace() -> None:
    unknown = sorted(set(checker.NAMESPACE_PATTERNS) - set(checker.SCHEME_PATTERNS))
    assert not unknown, f"{unknown} are looked for but the scheme does not declare them"


@pytest.mark.parametrize(
    "identifier",
    [
        "OB-01", "F-123", "BR-ORD-06", "BR-W001-03", "WF-004", "WF-004a", "DISC-02",
        "RD-01", "RA-08", "RW-03", "RS-02", "UK-D04", "UK-L01", "AS-05", "E-06",
        "Q16", "d01", "r07",
    ],
)
def test_the_finder_accepts_what_the_scheme_accepts(identifier: str) -> None:
    """A well-formed identifier the finder misses is one no check will ever see."""
    namespace = next(
        key for key, pattern in checker.SCHEME_PATTERNS.items()
        if pattern.match(identifier)
    )
    found = checker.NAMESPACE_PATTERNS[namespace].findall(f"see {identifier} above")
    assert identifier in found, (
        f"{identifier} matches the scheme for {namespace} but the finder does not find it"
    )


def test_the_finder_is_looser_than_the_scheme_so_malformed_ids_are_reported() -> None:
    """`BR-M01` is in the reference set and off-scheme. It must be found, then faulted.

    If the finder rejected it the document would appear clean, which is the failure
    mode this split exists to prevent.
    """
    assert checker.NAMESPACE_PATTERNS["BR-"].findall("rule BR-M01 applies") == ["BR-M01"]
    assert not checker.SCHEME_PATTERNS["BR-"].match("BR-M01")


def _register(items: list[dict]) -> dict:
    return {"app_id": "SYN", "generated_at": "2026-09-04T00:00:00+00:00",
            "items": items}


def _item(**overrides) -> dict:
    base = {
        "id": "SYN-P1-TABLE_INVENTORY-001", "run_id": "R", "app_id": "SYN",
        "phase": 1, "role": "data_understanding", "task_id": "SYN-P1-TABLE_INVENTORY",
        "statement": "22 tables carry 161 columns.", "status": "EXTRACTED",
        "source_type": "RUNTIME", "source_path": "databases/tables.json",
        "confidence": 1.0, "created_at": "2026-09-04T00:00:00+00:00",
    }
    return base | overrides


def test_evidence_register_must_conform_to_its_schema(tmp_path: Path) -> None:
    """The register carried an evidence CLASS in the source_type field for months.

    `validate_structure.py` checks that `schemas/evidence.schema.json` exists; nothing
    checked any register against it, so fifteen items whose `source_type` was
    DOCUMENT, UI_DEFINITION or OPERATOR_DECLARATION - none of them a medium the schema
    permits - passed every gate the kit has.
    """
    import json

    outputs = tmp_path / "output"
    (outputs / "registers").mkdir(parents=True)
    (outputs / "registers" / "SYN_Evidence.json").write_text(
        json.dumps(_register([_item(source_type="DOCUMENT")])), encoding="utf-8")

    errors = checker._schema_errors(outputs)
    assert errors, "an evidence class in the source_type field must be reported"
    assert "source_type" in errors[0]

    (outputs / "registers" / "SYN_Evidence.json").write_text(
        json.dumps(_register([_item(source_type="XLSX", evidence_class="DOCUMENT")])),
        encoding="utf-8")
    assert checker._schema_errors(outputs) == []


def test_ec01_is_evaluated(tmp_path: Path) -> None:
    """Rule EC-01 was prose against two fields no register populated.

    So the rule had never been evaluated once. Its first run over A05 found three
    violations: two BEHAVIOUR statements labelled INTENT, and a BEHAVIOUR conclusion
    drawn from a screenshot.
    """
    import json

    outputs = tmp_path / "output"
    (outputs / "registers").mkdir(parents=True)

    # SCHEMA cannot support MEANING: a table name is not a statement of its role.
    (outputs / "registers" / "SYN_Evidence.json").write_text(
        json.dumps(_register([
            _item(evidence_class="SCHEMA", claim_kind="MEANING")])), encoding="utf-8")
    violations = checker._class_kind_violations(outputs)
    assert violations and "SCHEMA cannot support MEANING" in violations[0]

    (outputs / "registers" / "SYN_Evidence.json").write_text(
        json.dumps(_register([
            _item(evidence_class="SCHEMA", claim_kind="STRUCTURE")])), encoding="utf-8")
    assert checker._class_kind_violations(outputs) == []


def test_an_unclassified_register_is_reported(tmp_path: Path) -> None:
    """An item stating no class cannot be checked against EC-01 to EC-06 at all."""
    import json

    outputs = tmp_path / "output"
    (outputs / "registers").mkdir(parents=True)
    (outputs / "registers" / "SYN_Evidence.json").write_text(
        json.dumps(_register([_item(), _item(id="SYN-P1-TABLE_INVENTORY-002",
                                            evidence_class="SCHEMA")])),
        encoding="utf-8")
    registers = checker.load_registers(outputs)
    assert registers["evidence_total"] == 2
    assert registers["evidence_unclassified"] == 1


# --- A49: the gate could only read English -----------------------------------------

CONFORMANT = {
    "EN": "# Phase 1\n\n## Naming Convention\n\nProduction names remain authoritative.\n"
          "\n## Source Coverage\n\n| Evidence class | Supplied |\n",
    "VI": "# Giai đoạn 1\n\n## Quy ước đặt tên\n\nTên production vẫn là tên có thẩm quyền.\n"
          "\n## Mức độ bao phủ nguồn\n\n| Lớp bằng chứng | Có |\n",
    "JA": "# フェーズ1\n\n## 命名規則\n\n本番名をそのまま使う。\n\n## ソースカバレッジ\n\n証拠クラス\n",
}
SILENT = "# Phase 1\n\n## Overview\n\nA document that says nothing about either.\n"


def status(results: list, name: str) -> str:
    return [r for r in results if r["check"] == name][0]["status"]


def both(tmp_path: Path, filename: str, body: str) -> tuple[str, str]:
    path = tmp_path / filename
    path.write_text(body, encoding="utf-8")
    return (status(checker.content_checks(1, body, path), "naming_convention"),
            status(checker.apparatus_checks(1, body, {}, path), "source_coverage"))


@pytest.mark.parametrize("language", ["EN", "VI", "JA"])
def test_a_conformant_document_passes_in_every_output_language(language, tmp_path) -> None:
    """A49. `NAMING_SIGNALS` was four English substrings and `source_coverage` tested
    `"source coverage" in lower`, while `$ak init --languages EN,JA,VI` offers three.

    A06's Vietnamese Phase 1 failed both with sections `## Quy ước đặt tên` and
    `## Mức độ bao phủ nguồn` present, and the failure text said the document held no
    such statement - which a reader would act on by adding a section already there.
    """
    assert both(tmp_path, f"A99_Phase1_X_{language}.md",
                CONFORMANT[language]) == ("PASS", "PASS")


@pytest.mark.parametrize("language", ["EN", "VI", "JA"])
def test_a_document_that_really_lacks_them_still_fails(language, tmp_path) -> None:
    """The point is to read three languages, not to stop checking."""
    assert both(tmp_path, f"A99_Phase1_X_{language}.md", SILENT) == ("FAIL", "FAIL")


def test_a_document_with_no_language_suffix_is_read_as_english(tmp_path) -> None:
    assert both(tmp_path, "A99_Phase1_X.md", CONFORMANT["EN"]) == ("PASS", "PASS")


def test_an_unknown_language_searches_every_phrase_rather_than_failing(tmp_path) -> None:
    """Degrade to looser, never to a failure about a section the document has.

    Reporting a document as non-conformant because nobody has translated the checker
    is a defect in the checker.
    """
    assert both(tmp_path, "A99_Phase1_X_DE.md", CONFORMANT["VI"]) == ("PASS", "PASS")


def test_every_output_language_the_kit_offers_has_signals() -> None:
    """A language in `output_languages` with no phrases is the defect coming back."""
    import yaml

    spec = yaml.safe_load(
        (PACKAGE / "specifications" / "language-support.yaml").read_text(encoding="utf-8"))
    human = spec["human_languages"]
    for check, by_language in human["conformance_signals"].items():
        for language in human["output_languages"]:
            assert by_language.get(language), f"{check} has no {language} phrases"


# --- A52: a column name shaped like an identifier -----------------------------------

def test_a_column_name_in_backticks_is_not_an_identifier(tmp_path: Path) -> None:
    """A06's Phase 1 names the SQL Server table 受注年月商品, whose columns are `d1` …
    `d31` - and `d31` is exactly the shape of the `d-` namespace. The checker reported a
    dangling identifier against a document that had allocated everything it cited.

    The reference set settles which way to resolve it: it writes namespace identifiers
    as plain prose in table cells (`| d01 | 店舗受注データ | …`) and column names inside
    backticks (`` `d31` ``). The same collision, already distinguished by the gold
    standard's own typography.
    """
    text = "# Phase 1\n\nThe columns are `d1` … `d31`, plus `合計数量 = d1+d2+...+d31`.\n"
    assert "d31" not in checker.prose(text)
    assert "d31" in text, "the document is untouched; only the scan is narrowed"


def test_an_identifier_in_prose_is_still_found() -> None:
    """Narrowing the scan must not stop it finding what it is for."""
    text = "| d01 | 店舗受注データ | .dat | Store ordering |\n\nSee OB-01 and WF-003.\n"
    scanned = checker.prose(text)
    assert "d01" in scanned and "OB-01" in scanned and "WF-003" in scanned


def test_a_fenced_block_is_not_scanned() -> None:
    """A mermaid diagram or a VBA excerpt is code, whatever it happens to contain."""
    text = "# Phase 1\n\n```vb\nDim d31 As Double   ' WF-999 is not a citation here\n```\n"
    scanned = checker.prose(text)
    assert "d31" not in scanned and "WF-999" not in scanned


def test_blanking_preserves_length(tmp_path: Path) -> None:
    """Blanked rather than removed, so nothing downstream depends on offsets shifting."""
    text = "a `d31` b\n\n```\nd31\n```\n"
    assert len(checker.prose(text)) == len(text)


# --- A54: malformed identifiers were invisible to the check that judges them ---------

def test_a_namespace_prefix_with_the_wrong_shape_is_reported() -> None:
    """`identifiers_wellformed` judges what the finder found, and for most namespaces the
    finder *is* the scheme - `OB-` is the same pattern on both sides. So `OB-S01` was not
    a malformed OB identifier, it was not an identifier at all, and eight of them passed
    unreported in A06's Phase 2.

    The module's own comment says deriving the finder from the scheme "means a malformed
    identifier becomes invisible rather than reported". That was fixed for `BR-` and left
    standing everywhere else.
    """
    assert checker.malformed_identifiers("See OB-S01 and RS-1 here.") == ["OB-S01", "RS-1"]


def test_a_well_formed_identifier_is_not_reported() -> None:
    assert checker.malformed_identifiers("See OB-01, RS-02, WF-003 and F-001.") == []


def test_a_word_that_merely_starts_with_a_prefix_is_not_an_identifier() -> None:
    """`E-` is a namespace. `E-mail` is not a finding, and requiring a digit is what
    separates them."""
    assert checker.malformed_identifiers("Reach us by E-mail, or by e-mail.") == []


def test_the_gold_standard_allocates_nothing_off_scheme() -> None:
    """Calibration, the same way the content checks are calibrated: if the reference set
    trips this, the scheme is written wrong and the documents are not."""
    if not REFERENCE.is_dir():
        pytest.skip(f"reference set not on this machine: {REFERENCE}")
    offenders = {}
    for path in sorted(REFERENCE.glob("*.md")):
        if not checker.PHASE_FILE.search(path.name):
            continue
        found = checker.malformed_identifiers(checker.prose(checker.read(path)))
        if found:
            offenders[path.name] = found
    assert not offenders, offenders


def test_code_spans_are_excluded_here_too(tmp_path: Path) -> None:
    """A52's rule applies: a namespace-shaped token inside backticks is code."""
    assert checker.malformed_identifiers(checker.prose("the column `OB-S01` is text")) == []


# --- the two scheme fields nothing read until A56 ----------------------------
#
# `owned_by` and `requires_severity` were declared on every risk namespace and opened
# by no code. A06's Phase 2 allocated five findings into RS - Phase 5's namespace,
# named "security and compliance", one of them about line and rectangle controls -
# and eight into OB, and published them twice with nothing objecting.


def test_a_phase_allocating_outside_its_namespaces_fails_apparatus() -> None:
    registers = {"identifier_entries": [
        {"id": "RS-01", "namespace": "RS-", "phase": 2, "severity": "HIGH"},
    ]}
    results = checker.apparatus_checks(2, "# X", registers)
    result = next(r for r in results if r["check"] == "identifier_namespace_owned")
    assert result["status"] == "FAIL" and "RS-01" in result["detail"]


def test_the_owning_phase_may_allocate() -> None:
    registers = {"identifier_entries": [
        {"id": "RS-01", "namespace": "RS-", "phase": 5, "severity": "HIGH"},
    ]}
    results = checker.apparatus_checks(5, "# X", registers)
    result = next(r for r in results if r["check"] == "identifier_namespace_owned")
    assert result["status"] == "PASS"


def test_a_risk_without_a_severity_fails_apparatus() -> None:
    """Phase 6 consolidates from the register, not from the prose table, so a severity
    printed in a document and absent from the register leaves nothing to rank by."""
    registers = {"identifier_entries": [
        {"id": "RD-05", "namespace": "RD-", "phase": 1},
        {"id": "RD-06", "namespace": "RD-", "phase": 1, "severity": "  "},
        {"id": "OB-01", "namespace": "OB-", "phase": 1},
    ]}
    results = checker.apparatus_checks(1, "# X", registers)
    result = next(r for r in results if r["check"] == "severity_recorded")
    assert result["status"] == "FAIL"
    assert "RD-05" in result["detail"] and "RD-06" in result["detail"]
    # OB- does not require one, so it must not be accused of lacking it.
    assert "OB-01" not in result["detail"]


def test_every_risk_namespace_is_owned_by_some_phase() -> None:
    """A risk namespace nobody owns is one a phase will take from another - which is
    what Phase 2 did, there being no risk namespace owned by phase 2 at all."""
    risks = {n: r for n, r in checker.SCHEME_RULES.items() if r["requires_severity"]}
    assert risks, "no namespace declares requires_severity; the rule has gone missing"
    owners = {phase for rule in risks.values() for phase in rule["owned_by"]}
    for phase in ("phase1", "phase2", "phase3", "phase4", "phase5"):
        assert phase in owners, (
            f"{phase} owns no risk namespace, so a risk it finds has nowhere to go"
        )
