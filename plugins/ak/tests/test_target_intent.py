"""A38 and A43 - a class for what the new system must be, and a directory that is read.

A38 was two defects wearing one name. `input/decisions/` was advertised by
`input.README.md` and `evidence-layout.yaml` as holding three evidence classes, and no
collector read it: `decisions` sits in the normalizer's `FORBIDDEN_PARTS` next to
secrets, and `CLASS_LOCATIONS` named only a pre-2.10 path. And no class fitted a scope
decision anyway - `OPERATOR_DECLARATION` says of itself that it is a statement made *in
the manifest* about the inputs.

The repair is not to open `decisions/`. That directory holds `glossary.yaml` and
`meanings.yaml`, which the kit writes and reads by name; normalizing them would report
DOCUMENT evidence for a glossary. `test_the_decisions_directory_is_still_not_collected`
is the test that keeps the fix from becoming A29.

A43 was found while wiring this: `init` places the kit's own guide inside evidence
directories, and the normalizer collected those guides as corpus documents - so the
kit's prose about what INTERVIEW evidence is would be retrievable as evidence about the
application.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))
sys.path.insert(0, str(PACKAGE / "scripts"))

import evidence_classes  # noqa: E402
import workspace as workspace_contract  # noqa: E402

LEGACY_KINDS = ("STRUCTURE", "BEHAVIOUR", "FORMAT", "MEANING", "USAGE", "INTENT")


@pytest.fixture(scope="module")
def contract() -> dict:
    return evidence_classes.load_contract(PACKAGE)


def run_script(name: str, *args: str) -> None:
    result = subprocess.run([sys.executable, str(PACKAGE / "scripts" / name), *map(str, args)],
                            cwd=PACKAGE, check=False, capture_output=True, text=True,
                            # A Japanese app name comes back through the console in the
                            # host codepage, and a strict decode turns that into a test
                            # error about nothing.
                            encoding="utf-8", errors="replace")
    assert result.returncode == 0, f"{name} failed\n{result.stdout}\n{result.stderr}"


# ------------------------------------------------------------------ the contract

def test_scope_is_a_claim_kind(contract: dict) -> None:
    assert "SCOPE" in contract["claim_kinds"]


def test_target_intent_carries_scope_and_nothing_else(contract: dict) -> None:
    entry = contract["evidence_classes"]["TARGET_INTENT"]
    assert entry["supports"] == ["SCOPE"]
    assert set(entry["cannot_support"]) == set(LEGACY_KINDS)
    assert entry["requires_attribution"] is True


@pytest.mark.parametrize("kind", LEGACY_KINDS)
def test_a_scope_decision_says_nothing_about_the_legacy_application(kind, contract) -> None:
    """The whole of EC-07. A customer dropping a screen has not described it."""
    ok, why = evidence_classes.claim_is_supportable(kind, "TARGET_INTENT", contract)
    assert not ok
    assert "EC-07" in why


@pytest.mark.parametrize("klass", ["SCHEMA", "CODE", "UI_DEFINITION", "DOCUMENT",
                                  "INTERVIEW", "OPERATOR_DECLARATION"])
def test_no_reading_of_the_legacy_application_establishes_scope(klass, contract) -> None:
    ok, why = evidence_classes.claim_is_supportable("SCOPE", klass, contract)
    assert not ok
    assert "EC-07" in why and "TARGET_INTENT" in why


def test_target_intent_supports_a_scope_claim(contract: dict) -> None:
    ok, why = evidence_classes.claim_is_supportable("SCOPE", "TARGET_INTENT", contract)
    assert ok and why == ""


def test_the_older_rules_still_name_themselves(contract: dict) -> None:
    """Adding EC-07 must not relabel EC-01 and EC-02."""
    _, meaning = evidence_classes.claim_is_supportable("MEANING", "SCHEMA", contract)
    _, fmt = evidence_classes.claim_is_supportable("FORMAT", "SCHEMA", contract)
    assert meaning.startswith("EC-01") and fmt.startswith("EC-02")


def test_ec_07_is_declared_as_a_rule(contract: dict) -> None:
    rule, = [item for item in contract["rules"] if item["id"] == "EC-07"]
    assert "TARGET_INTENT" in rule["rule"] and "SCOPE" in rule["rule"]


def test_phase_six_degrades_without_it_and_no_phase_requires_it(contract: dict) -> None:
    """Scope is about the system being built, so only the phase that plans it suffers.

    Required anywhere, it would block every project that changes nothing.
    """
    needs = contract["phase_needs"]
    assert "TARGET_INTENT" in [entry.get("class") for entry in needs["phase6"]["degraded_without"]]
    for phase, entry in needs.items():
        assert "TARGET_INTENT" not in (entry.get("required") or []), phase


def test_the_evidence_schema_accepts_the_class_and_the_kind() -> None:
    schema = json.loads((PACKAGE / "schemas" / "evidence.schema.json").read_text(encoding="utf-8"))
    item = schema["$defs"]["evidenceItem"]["properties"]
    assert "TARGET_INTENT" in item["evidence_class"]["enum"]
    assert "SCOPE" in item["claim_kind"]["enum"]


def test_the_class_is_declared_in_the_layout_a_person_reads() -> None:
    layout = (PACKAGE / "specifications" / "evidence-layout.yaml").read_text(encoding="utf-8")
    readme = (PACKAGE / "templates" / "input.README.md").read_text(encoding="utf-8")
    assert "target-intent" in layout and "TARGET_INTENT" in layout
    assert "target-intent" in readme and "TARGET_INTENT" in readme
    # A38 was a directory advertised as holding three classes and read by nothing. The
    # row must no longer make that promise.
    decisions_row, = [line for line in readme.splitlines()
                      if line.startswith("| `decisions/`")]
    for promised in ("OPERATOR_DECLARATION", "DOCUMENT", "INTERVIEW"):
        assert promised not in decisions_row


# ----------------------------------------------------------------- the wiring

def test_the_directory_is_where_the_class_is_looked_for() -> None:
    assert evidence_classes.CLASS_LOCATIONS["TARGET_INTENT"] == ("input/target-intent",)
    assert workspace_contract.INPUT_DIRS["target-intent"] == "target-intent"


def test_a_scope_record_makes_the_class_present(tmp_path: Path) -> None:
    directory = tmp_path / "input" / "target-intent"
    directory.mkdir(parents=True)
    (directory / "scope.md").write_text("| Decided by | customer |", encoding="utf-8")
    assert "path:input/target-intent" in evidence_classes.observe(app_root=tmp_path)["TARGET_INTENT"]


def test_the_guide_alone_does_not_make_the_class_present(tmp_path: Path) -> None:
    """A29's rule, on the directory whose guide `init` places."""
    directory = tmp_path / "input" / "target-intent"
    directory.mkdir(parents=True)
    (directory / "README.md").write_text("how to write one", encoding="utf-8")
    assert "TARGET_INTENT" not in evidence_classes.observe(app_root=tmp_path)


def test_a_scope_record_is_inventoried_with_its_digest(tmp_path: Path) -> None:
    directory = tmp_path / "input" / "target-intent"
    directory.mkdir(parents=True)
    (directory / "scope.md").write_text("out of scope: 累積", encoding="utf-8")
    (directory / "README.md").write_text("the guide", encoding="utf-8")
    inventory = evidence_classes.supplied_inventory(tmp_path)
    assert [record["path"] for record in inventory] == ["input/target-intent/scope.md"]
    assert inventory[0]["evidence_class"] == "TARGET_INTENT"
    assert len(inventory[0]["sha256"]) == 64


# -------------------------------------------------- end to end, through init

@pytest.fixture(scope="module")
def workspace(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("a38")
    run_script("init_app.py", "--root", str(root), "--app-id", "T38",
               "--name-en", "Target Intent Test", "--runtime", "generic")
    app = root / "T38"
    (app / "input" / "target-intent" / "scope.md").write_text(
        "# Scope\n\n| Decided by | customer |\n| Decided on | 2026-09-08 |\n\n"
        "The six accumulation screens are out of scope.\n", encoding="utf-8")
    run_script("normalize_documents.py", "--app-root", str(app))
    return app


def test_init_places_the_guide(workspace: Path) -> None:
    guide = workspace / "input" / "target-intent" / "README.md"
    assert guide.is_file()
    text = guide.read_text(encoding="utf-8")
    assert "EC-07" in text and "Decided by" in text


def test_a_scope_record_reaches_the_corpus(workspace: Path) -> None:
    audit = json.loads((workspace / ".ak" / "extracted" / "normalized"
                        / "NORMALIZATION_AUDIT.json").read_text(encoding="utf-8"))
    statuses = {entry["source_path"]: entry["status"] for entry in audit["entries"]}
    assert statuses["input/target-intent/scope.md"] == "NORMALIZED"


def test_the_kits_own_guide_does_not_become_evidence(workspace: Path) -> None:
    """A43. `init` writes these guides; collected, they are the kit citing itself."""
    audit = json.loads((workspace / ".ak" / "extracted" / "normalized"
                        / "NORMALIZATION_AUDIT.json").read_text(encoding="utf-8"))
    statuses = {entry["source_path"]: entry["status"] for entry in audit["entries"]}
    for guide in ("input/target-intent/README.md", "input/interviews/README.md"):
        assert statuses.get(guide) == "EXCLUDED_NOT_EVIDENCE", guide
    corpus = workspace / ".ak" / "extracted" / "normalized" / "corpus"
    assert not list(corpus.rglob("README.md"))


def test_the_decisions_directory_is_still_not_collected(workspace: Path) -> None:
    """The fix for A38 must not make `glossary.yaml` a business document.

    `decisions/` holds two files the kit writes for a person to edit and reads back by
    name. Collecting them would report DOCUMENT evidence for a glossary, which is A29
    arriving through the repair for A38.
    """
    import normalize_documents

    assert "decisions" in normalize_documents.FORBIDDEN_PARTS
    decisions = workspace / "input" / "decisions"
    decisions.mkdir(parents=True, exist_ok=True)
    (decisions / "glossary.yaml").write_text("terms: []\n", encoding="utf-8")
    run_script("normalize_documents.py", "--app-root", str(workspace))
    corpus = workspace / ".ak" / "extracted" / "normalized" / "corpus"
    assert not list(corpus.rglob("glossary.yaml"))
    assert "TARGET_INTENT" not in evidence_classes.CLASS_LOCATIONS.get("DOCUMENT", ())
    assert "input/decisions" not in evidence_classes.CLASS_LOCATIONS["TARGET_INTENT"]


# ------------------------------------------------- the checker that enforces it

def test_conformance_rejects_a_scope_claim_from_a_legacy_class(tmp_path: Path) -> None:
    """Only `cannot_support` was enforced, so a kind a class merely omits passed.

    That is EC-07's other half, and the rule existed with nothing behind it.
    """
    import validate_phase_conformance as conformance

    classes = yaml.safe_load(
        (PACKAGE / "specifications" / "evidence-classes.yaml").read_text(encoding="utf-8")
    )["evidence_classes"]

    def violations(klass: str, kind: str) -> list[str]:
        """Through the real checker, on a real register file it reads from disk.

        Re-implementing the rule in the test would assert that the test agrees with
        itself. The point of this one is that the shipped function agrees with the
        specification.
        """
        outputs = tmp_path / klass / kind
        (outputs / "registers").mkdir(parents=True)
        (outputs / "registers" / "T38_Evidence.json").write_text(json.dumps({"items": [
            {"id": "T38-P1-SCOPE-001", "evidence_class": klass, "claim_kind": kind},
        ]}, ensure_ascii=False), encoding="utf-8")
        return conformance._class_kind_violations(outputs) or []

    assert violations("DOCUMENT", "SCOPE")
    assert violations("SCHEMA", "SCOPE")
    assert violations("TARGET_INTENT", "MEANING")
    assert not violations("TARGET_INTENT", "SCOPE")
    assert not violations("INTERVIEW", "MEANING")
    # A corroborating item is a real item; what EC-01 forbids is a claim resting on it
    # alone, which is a check on a document rather than on the register.
    corroborators = [(name, kind) for name, entry in classes.items()
                     for kind in (entry.get("corroborates") or [])]
    assert corroborators, "no class corroborates anything; this assertion is vacuous"
    for name, kind in corroborators:
        assert not violations(name, kind), f"{name} corroborates {kind}"
