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


def test_a_rule_may_not_offer_a_class_its_own_table_forbids(contract: dict) -> None:
    """A18: EC-01 required DOCUMENT, INTERVIEW *or OPERATOR_DECLARATION* for a MEANING
    claim, forty lines below the class entry saying that class cannot support one.

    Nothing compared the prose of a rule with the table it sits beside, so the file
    contradicted itself for as long as no register happened to carry the combination.
    """
    ec01 = next(r for r in contract["rules"] if r["id"] == "EC-01")["rule"]
    requires = next(s for s in ec01.split(".") if "requires" in s)
    forbidden = [name for name, spec in contract["evidence_classes"].items()
                 if "MEANING" in (spec.get("cannot_support") or [])]
    offered = [name for name in forbidden if name in requires]
    assert not offered, f"EC-01 offers {offered} for a MEANING claim"


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
    assert advice["put_it_in"] == ["input/screenshots"]
    # The pre-2.10.0 path is still read, so nobody is told to move a file.
    assert "sources/screenshots" in advice["also_read"]
    assert advice["means"]
    assert "one frame" in advice["note"].lower()


# Found by running the whole chain on a fresh workspace, which the unit tests could
# not: acquire, derive, documents, then ask for Phase 5.
def test_normalizing_sources_does_not_manufacture_document_evidence(tmp_path: Path) -> None:
    """The normalizer's corpus holds every source it read - VBA, SQL, the manifest.

    Counting that directory as a DOCUMENT location meant running `$ak documents` on
    a project with no documents at all made DOCUMENT present, and Phase 5 reported
    LIMITED instead of BLOCKED - defeating the exact gate this release tightened,
    from inside the release's own code.
    """
    corpus = tmp_path / ".ak" / "extracted" / "normalized" / "corpus" / "normalized"
    corpus.mkdir(parents=True)
    (corpus / "DemoOrderForm.bas.txt").write_text("Attribute VB_Name", encoding="utf-8")
    (tmp_path / "input" / "documents").mkdir(parents=True)

    assert "DOCUMENT" not in evidence_classes.observe(set(), tmp_path)
    assert readiness(STRUCTURAL, tmp_path)["phase5"]["status"] == "BLOCKED"


def test_a_document_a_person_supplied_still_counts(tmp_path: Path) -> None:
    documents = tmp_path / "input" / "documents"
    documents.mkdir(parents=True)
    (documents / "manual.xlsx").write_bytes(b"x")
    assert "DOCUMENT" in evidence_classes.observe(set(), tmp_path)
    assert readiness(STRUCTURAL, tmp_path)["phase5"]["status"] != "BLOCKED"


def test_a_directory_holding_only_non_evidence_is_still_empty(tmp_path: Path) -> None:
    """Existence proved nothing; any file at all proved too much.

    `_has_files` counted every file, so a `Thumbs.db` Windows wrote while somebody
    browsed `input/screenshots/`, or a `.gitkeep` holding an empty directory in
    version control, reported a whole evidence class present - and with it moved a
    phase's readiness. This is the failure the class contract exists to prevent,
    arriving through the contract itself.

    It also blocks something the kit needs to do: `input/interviews/` is the one class
    no command here can produce and the one a bare folder teaches nothing about, so
    `init` writes a guide into it. Without this rule that guide would announce
    interview evidence on every project that has none.
    """
    screenshots = tmp_path / "input" / "screenshots"
    screenshots.mkdir(parents=True)
    (screenshots / "README.md").write_text("the kit's own guide", encoding="utf-8")
    (screenshots / "Thumbs.db").write_bytes(b"\x00")
    (screenshots / ".gitkeep").write_text("", encoding="utf-8")
    assert "SCREENSHOT" not in evidence_classes.observe(set(), tmp_path)

    (screenshots / "main.png").write_bytes(b"x")
    assert "SCREENSHOT" in evidence_classes.observe(set(), tmp_path)


def test_the_exclusion_is_by_name_and_ignores_case(tmp_path: Path) -> None:
    """Windows writes `Thumbs.db` and `desktop.ini` in whatever case it feels like."""
    interviews = tmp_path / "input" / "interviews"
    interviews.mkdir(parents=True)
    for name in ("readme.md", "README.MD", "THUMBS.DB", "Desktop.ini", ".DS_Store"):
        (interviews / name).write_text("x", encoding="utf-8")
    assert "INTERVIEW" not in evidence_classes.observe(set(), tmp_path)

    # A real answer is a file like any other. Nothing about the name of an interview
    # record is constrained, so the rule must not reach any further than the closed
    # set it declares.
    (interviews / "notes.md").write_text("Horiuchi, 2026-09-09", encoding="utf-8")
    assert "INTERVIEW" in evidence_classes.observe(set(), tmp_path)


def test_the_supplied_inventory_reads_the_same_map_observe_does(tmp_path: Path) -> None:
    """A33 was two readers of one question disagreeing.

    Readiness read the class directories; the bundle read the manifest. On a real
    workspace that meant 54 supplied files against four recorded, with the bundle's own
    readiness reporting five classes present that the bundle could not show. So this
    inventory is built from `CLASS_LOCATIONS` and `_has_files`' exclusion rule - the
    same pair `observe` uses - and this asserts they cannot drift apart again.
    """
    (tmp_path / "input" / "screenshots").mkdir(parents=True)
    (tmp_path / "input" / "interviews").mkdir(parents=True)
    (tmp_path / "input" / "screenshots" / "main.png").write_bytes(b"x")
    (tmp_path / "input" / "interviews" / "notes.md").write_text("Horiuchi, 2026-09-09", encoding="utf-8")
    # The guide `init` writes, and OS noise. Neither is evidence, and neither may make
    # a class look present - which is what A29 fixed for `observe`.
    (tmp_path / "input" / "interviews" / "README.md").write_text("guide", encoding="utf-8")
    (tmp_path / "input" / "screenshots" / "Thumbs.db").write_bytes(b"\x00")

    records = evidence_classes.supplied_inventory(tmp_path)
    by_class = {record["evidence_class"] for record in records}
    paths = {record["path"] for record in records}

    assert by_class == set(evidence_classes.observe(set(), tmp_path)), (
        "the inventory and the observation must name the same classes"
    )
    assert paths == {"input/screenshots/main.png", "input/interviews/notes.md"}
    assert all(len(record["sha256"]) == 64 for record in records)

    # Deterministic and timestamp-free, so re-acquiring unchanged evidence is the same
    # bundle. Ordered by class, then by path within it - which is what makes the digest
    # over this list stable rather than dependent on directory iteration order.
    assert records == evidence_classes.supplied_inventory(tmp_path)
    assert [(r["evidence_class"], r["path"]) for r in records] == sorted(
        (r["evidence_class"], r["path"]) for r in records
    )


def test_the_supplied_digest_moves_only_when_the_evidence_does(tmp_path: Path) -> None:
    """What the bundle identity needs, and no more.

    A digest rather than the list, because the list is written into the bundle where it
    can be followed; the identity only has to make a different evidence set a different
    bundle. Byte size is deliberately not in it - a file whose content is identical is
    the same evidence however the filesystem reports it.
    """
    directory = tmp_path / "input" / "samples"
    directory.mkdir(parents=True)
    (directory / "feed.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    first = evidence_classes.supplied_digest(evidence_classes.supplied_inventory(tmp_path))

    assert first == evidence_classes.supplied_digest(
        evidence_classes.supplied_inventory(tmp_path)
    ), "stable while nothing changes"

    (directory / "feed.csv").write_text("a,b\n1,3\n", encoding="utf-8")
    changed = evidence_classes.supplied_digest(evidence_classes.supplied_inventory(tmp_path))
    assert changed != first, "edited evidence is different evidence"

    (directory / "second.csv").write_text("a,b\n1,3\n", encoding="utf-8")
    added = evidence_classes.supplied_digest(evidence_classes.supplied_inventory(tmp_path))
    assert added != changed, "added evidence is different evidence"

    (directory / "second.csv").unlink()
    assert evidence_classes.supplied_digest(
        evidence_classes.supplied_inventory(tmp_path)
    ) == changed, "removing it again returns the previous answer"
