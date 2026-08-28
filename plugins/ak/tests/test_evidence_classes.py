"""Readiness must answer "can this phase say what it means", not only "can it count".

Before this, A05 reported phase1/2/3 READY from two `.mdb` files. The documents it
then produced were inventories, and the run said so about itself: "purpose not
established from schema alone". Nothing was wrong with the analysis - the gate had
asked for four structural capabilities and got them.

With the class contract wired in, the same bundle reports phase1 LIMITED with the
cost named ("§2 and §3 become an inventory"), phase2 LIMITED for want of
screenshots and documents, phase3 LIMITED for want of samples, and phase5 BLOCKED
for want of documents. Those degradations are the same gaps the run eventually
raised as open questions - the gate now predicts them instead of discovering them.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))
sys.path.insert(0, str(PACKAGE / "scripts"))

import evidence_classes  # noqa: E402
import phase_readiness  # noqa: E402
from classification import Classification  # noqa: E402

PROFILES = PACKAGE / "profiles"
SPLIT = Classification("split_file", "mdb", "full", ("access_file",))

# What a real Access-only acquisition yields: schema, code, definition text, and the
# operator's statement of which database is authoritative. Nothing semantic.
STRUCTURAL = {
    "access_schema_inventory", "field_inventory", "key_index_inventory",
    "boundary_inventory", "access_object_inventory", "ui_object_inventory",
    "vba_query_inventory", "backend_authority_declared",
}


@pytest.fixture(scope="module")
def contract() -> dict:
    return evidence_classes.load_contract(PACKAGE)


def readiness(capabilities: set[str], app_root: Path | None = None) -> dict:
    return phase_readiness.compute_readiness(
        SPLIT, PROFILES, capabilities, package_root=PACKAGE, app_root=app_root,
    )


# --- observation ------------------------------------------------------------

def test_capabilities_map_to_the_classes_that_produced_them(contract: dict) -> None:
    found = evidence_classes.observe(STRUCTURAL)
    assert set(found) == {"SCHEMA", "CODE", "UI_DEFINITION", "OPERATOR_DECLARATION"}
    assert "capability:field_inventory" in found["SCHEMA"]


def test_no_capability_can_prove_a_document_exists() -> None:
    """Which is the whole reason capability gating was not enough."""
    semantic = {"DOCUMENT", "INTERVIEW", "SCREENSHOT", "SAMPLE_DATA", "OUTPUT_SAMPLE"}
    produced = set(evidence_classes.CLASS_FROM_CAPABILITY.values())
    assert not (semantic - {"DOCUMENT"}) & produced
    # DOCUMENT is the one exception, and only via document_inventory, which is itself
    # derived from documents an operator supplied.
    assert evidence_classes.CLASS_FROM_CAPABILITY["document_inventory"] == "DOCUMENT"


def test_an_empty_directory_is_not_evidence(tmp_path: Path) -> None:
    """`init` scaffolds these directories, so existence proves nothing."""
    (tmp_path / "sources" / "screenshots").mkdir(parents=True)
    assert "SCREENSHOT" not in evidence_classes.observe(set(), tmp_path)
    (tmp_path / "sources" / "screenshots" / "main.png").write_bytes(b"x")
    assert "SCREENSHOT" in evidence_classes.observe(set(), tmp_path)


# --- gating -----------------------------------------------------------------

def test_structural_evidence_alone_no_longer_reports_a_phase_ready(tmp_path: Path) -> None:
    result = readiness(STRUCTURAL, tmp_path)
    assert result["phase1"]["status"] == "LIMITED"
    reasons = " ".join(result["phase1"]["reasons"])
    assert "DOCUMENT|INTERVIEW" in reasons
    assert "become an inventory" in reasons, "the cost must be named, not merely counted"


def test_phase5_is_blocked_without_documents_rather_than_limited(tmp_path: Path) -> None:
    """It was `LIMITED`, which read as optional.

    Phase 5's characteristic claim is what the business says the system does. With
    no document there is nothing for it to do, and calling that a degraded run
    invited it to be skipped.
    """
    result = readiness(STRUCTURAL, tmp_path)
    assert result["phase5"]["status"] == "BLOCKED"
    assert result["phase5"]["evidence_classes"]["blocking"] == ["DOCUMENT"]


def test_supplying_the_missing_class_clears_the_degradation(tmp_path: Path) -> None:
    documents = tmp_path / "sources" / "documents"
    documents.mkdir(parents=True)
    (documents / "manual.xlsx").write_bytes(b"x")

    before = readiness(STRUCTURAL, None)
    after = readiness(STRUCTURAL, tmp_path)
    assert any("DOCUMENT" in r for r in before["phase1"]["reasons"])
    assert not any("degraded_without:DOCUMENT" in r for r in after["phase1"]["reasons"])
    assert after["phase5"]["status"] != "BLOCKED"


def test_phase2_names_screenshots_and_phase3_names_samples(tmp_path: Path) -> None:
    """Each phase loses something different, and says which."""
    result = readiness(STRUCTURAL, tmp_path)
    phase2 = " ".join(result["phase2"]["reasons"])
    assert "SCREENSHOT" in phase2 and "tab structure" in phase2
    phase3 = " ".join(result["phase3"]["reasons"])
    assert "SAMPLE_DATA" in phase3 and "OUTPUT_SAMPLE" in phase3


def test_the_meta_block_records_why_each_class_was_counted_present(tmp_path: Path) -> None:
    result = readiness(STRUCTURAL, tmp_path)
    present = result["_meta"]["evidence_classes_present"]
    assert present["SCHEMA"], "a present class must say what showed it"
    assert all(why.startswith(("capability:", "path:")) for why in present["SCHEMA"])


# The class half is additive: every existing caller passes no package_root.
def test_omitting_the_package_root_leaves_behaviour_exactly_as_before() -> None:
    without = phase_readiness.compute_readiness(SPLIT, PROFILES, STRUCTURAL)
    assert without["phase1"]["status"] == "READY"
    assert "evidence_classes" not in without["phase1"]
    assert without["_meta"]["evidence_classes_present"] == {}


# --- the rules as a function ------------------------------------------------

def test_a_meaning_claim_may_not_rest_on_schema(contract: dict) -> None:
    ok, why = evidence_classes.claim_is_supportable("MEANING", "SCHEMA", contract)
    assert not ok and "EC-01" in why


def test_a_format_claim_may_not_rest_on_code(contract: dict) -> None:
    """Code shows what a reader accepts, not what the producer writes."""
    ok, why = evidence_classes.claim_is_supportable("FORMAT", "CODE", contract)
    assert not ok and "corroborates" in why
    ok, _ = evidence_classes.claim_is_supportable("FORMAT", "SAMPLE_DATA", contract)
    assert ok


def test_a_structural_claim_on_schema_is_exactly_what_schema_is_for(contract: dict) -> None:
    ok, why = evidence_classes.claim_is_supportable("STRUCTURE", "SCHEMA", contract)
    assert ok and why == ""


def test_how_to_supply_tells_an_operator_where_to_put_it(contract: dict) -> None:
    advice = evidence_classes.how_to_supply("SCREENSHOT", contract)
    assert advice["put_it_in"] == ["sources/screenshots"]
    assert advice["means"]
    assert "one frame" in advice["note"].lower()
