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
    violations = checker._ec01_violations(outputs)
    assert violations and "SCHEMA cannot support MEANING" in violations[0]

    (outputs / "registers" / "SYN_Evidence.json").write_text(
        json.dumps(_register([
            _item(evidence_class="SCHEMA", claim_kind="STRUCTURE")])), encoding="utf-8")
    assert checker._ec01_violations(outputs) == []


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
