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
