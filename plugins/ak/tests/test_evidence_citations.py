from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

import validate_evidence_citations as checker  # noqa: E402


def write_outputs(root: Path, items: list[dict], document: str, matrix: str = "") -> Path:
    outputs = root / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    (outputs / "A99_Evidence.json").write_text(
        json.dumps({"items": items}, ensure_ascii=False), encoding="utf-8",
    )
    (outputs / "A99_Phase1_EN.md").write_text(document, encoding="utf-8")
    if matrix:
        (outputs / "A99_TraceabilityMatrix.csv").write_text(matrix, encoding="utf-8")
    return outputs


def item(identifier: str, phase: int = 1) -> dict:
    return {"id": identifier, "phase": phase, "statement": "measured"}


def run(outputs: Path) -> int:
    argv = sys.argv
    sys.argv = ["validate_evidence_citations.py", "--outputs", str(outputs)]
    try:
        return checker.main()
    finally:
        sys.argv = argv


def test_a_document_citing_an_id_that_does_not_exist_fails(tmp_path: Path) -> None:
    outputs = write_outputs(
        tmp_path,
        [item("A99-P1-NAV-021")],
        "The menu opens 17 screens (`A99-P1-NAV-001`).",
    )
    assert run(outputs) == 1


# The defect that motivated the script: a whole phase numbered from the previous
# phase's item count, so every citation in the document resolved to nothing.
def test_matching_ids_pass(tmp_path: Path) -> None:
    outputs = write_outputs(
        tmp_path,
        [item("A99-P1-NAV-001")],
        "The menu opens 17 screens (`A99-P1-NAV-001`).",
    )
    assert run(outputs) == 0


# An earlier hand-rolled check matched [A-Z]+ for the task name and so never tested
# TABLE_INVENTORY or DATA_TYPES at all - reporting "pass" while skipping the format
# the real dangling citations were in.
def test_a_task_name_containing_an_underscore_is_checked(tmp_path: Path) -> None:
    outputs = write_outputs(
        tmp_path,
        [item("A99-P1-TABLE_INVENTORY-016")],
        "The pair holds the same shape (`A99-P1-TABLE_INVENTORY-007`).",
    )
    assert run(outputs) == 1
    found = checker.CITATION_RE.findall("see `A99-P1-DATA_TYPES-019` and `A99-P2-NAV-001`")
    assert found == ["A99-P1-DATA_TYPES-019", "A99-P2-NAV-001"]


def test_the_traceability_matrix_column_is_checked_too(tmp_path: Path) -> None:
    outputs = write_outputs(
        tmp_path,
        [item("A99-P1-NAV-001")],
        "Nothing is cited here.",
        matrix=(
            "run_id,app_id,task_id,evidence_ids\n"
            "A99-P1,A99,A99-P1-NAV,A99-P1-NAV-001;A99-P1-FLOW-099\n"
        ),
    )
    assert run(outputs) == 1


# An uncited item is normal: the register may hold more than the prose quotes.
def test_an_uncited_evidence_item_is_not_an_error(tmp_path: Path) -> None:
    outputs = write_outputs(
        tmp_path,
        [item("A99-P1-NAV-001"), item("A99-P1-NAV-002")],
        "The menu opens 17 screens (`A99-P1-NAV-001`).",
    )
    assert run(outputs) == 0


# --- A50: a document citing its own register ---------------------------------------

REGISTER_DOC = "\n".join([
    "# A99 — Phase 1",
    "",
    "The frontend holds 32 table objects. [A99-P1-SCHEMA-001]",
    "",
    "| ID | Observation | Evidence |",
    "|---|---|---|",
    "| OB-01 | Zero relationships are declared | [A99-P1-SCHEMA-001] |",
    "",
    "## Evidence Register",
    "",
    "| ID | Status | Class | Source |",
    "|---|---|---|---|",
    "| A99-P1-SCHEMA-001 | EXTRACTED | SCHEMA | bundle |",
    "| A99-P1-DOCUMENT-001 | EXTRACTED | DOCUMENT | readme |",
    "",
])


def test_an_item_only_listed_in_the_register_is_not_cited(tmp_path: Path) -> None:
    """A50. This regexed the whole file, register included, so every item cited itself.

    A06's Phase 1 reported `12 of 12 items cited`; seven were. The five that were not
    included the project's only `TARGET_INTENT` item - the one record of what the
    replacement is for supported no statement in the document carrying it.
    """
    outputs = write_outputs(tmp_path, [item("A99-P1-SCHEMA-001"),
                                       item("A99-P1-DOCUMENT-001")], REGISTER_DOC)
    cited = checker.cited_in_documents(sorted(outputs.glob("*.md")))
    assert "A99-P1-SCHEMA-001" in cited, "cited in prose and in the observations table"
    assert "A99-P1-DOCUMENT-001" not in cited, "listed in the register and nowhere else"


def test_the_register_row_does_not_hide_a_real_citation(tmp_path: Path) -> None:
    """Only the listing occurrence is skipped, never the id."""
    outputs = write_outputs(tmp_path, [item("A99-P1-SCHEMA-001")], REGISTER_DOC)
    assert checker.cited_in_documents(sorted(outputs.glob("*.md")))[
        "A99-P1-SCHEMA-001"] == ["A99_Phase1_EN.md"]


def test_the_register_is_found_by_shape_not_by_an_english_heading(tmp_path: Path) -> None:
    """A49's lesson, applied here before it could be repeated.

    The heading is `## Evidence Register` in English and `## Register bằng chứng` in
    Vietnamese. Cutting the text at the English wording would have made this check the
    next thing that only works in one language.
    """
    vietnamese = REGISTER_DOC.replace("## Evidence Register", "## Register bằng chứng")
    outputs = write_outputs(tmp_path, [item("A99-P1-DOCUMENT-001")], vietnamese)
    assert "A99-P1-DOCUMENT-001" not in checker.cited_in_documents(
        sorted(outputs.glob("*.md")))
