"""The three contracts added in 2.9.0 must be internally consistent.

A specification is only worth what its consumers can rely on, and the failure mode
is silent: a misspelt claim kind or a class name that appears in `phase_needs` but
not in `evidence_classes` reads perfectly well and binds to nothing. These tests
check the references resolve, so an authoring slip fails here rather than in a run.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

PACKAGE = Path(__file__).resolve().parents[1]
SPECS = PACKAGE / "specifications"
PHASES = {f"phase{n}" for n in range(1, 7)}


def load(name: str) -> dict:
    return yaml.safe_load((SPECS / name).read_text(encoding="utf-8")) or {}


@pytest.fixture(scope="module")
def classes() -> dict:
    return load("evidence-classes.yaml")


@pytest.fixture(scope="module")
def identifiers() -> dict:
    return load("identifier-scheme.yaml")


@pytest.fixture(scope="module")
def errata() -> dict:
    return load("errata-contract.yaml")


# --- evidence classes -------------------------------------------------------

def test_every_claim_a_class_names_is_a_declared_claim_kind(classes: dict) -> None:
    known = set(classes["claim_kinds"])
    for name, entry in classes["evidence_classes"].items():
        for field in ("supports", "corroborates", "cannot_support"):
            for claim in entry.get(field) or []:
                assert claim in known, f"{name}.{field} names undeclared claim kind {claim}"


def test_a_class_never_both_supports_and_refuses_the_same_claim(classes: dict) -> None:
    for name, entry in classes["evidence_classes"].items():
        supported = set(entry.get("supports") or []) | set(entry.get("corroborates") or [])
        refused = set(entry.get("cannot_support") or [])
        overlap = supported & refused
        assert not overlap, f"{name} both supports and refuses {sorted(overlap)}"


def test_every_claim_kind_is_supported_by_at_least_one_class(classes: dict) -> None:
    """A claim no class can carry is a claim the pipeline can never make honestly."""
    supported: set[str] = set()
    for entry in classes["evidence_classes"].values():
        supported |= set(entry.get("supports") or [])
    orphans = set(classes["claim_kinds"]) - supported
    assert not orphans, f"no evidence class supports {sorted(orphans)}"


def test_phase_needs_reference_real_classes(classes: dict) -> None:
    known = set(classes["evidence_classes"]) | {"PRIOR_PHASES"}
    for phase, entry in classes["phase_needs"].items():
        assert phase in PHASES, f"unknown phase {phase}"
        for name in entry["required"]:
            assert name in known, f"{phase}.required names unknown class {name}"
        for degraded in entry.get("degraded_without") or []:
            for key in ("class", "or"):
                if key in degraded:
                    assert degraded[key] in known, f"{phase} degraded_without names unknown class {degraded[key]}"
            assert degraded.get("costs"), f"{phase} degradation states no cost"


def test_every_phase_declares_what_it_needs(classes: dict) -> None:
    assert set(classes["phase_needs"]) == PHASES


# The defect the file exists to close: a gate satisfied by structural evidence alone
# reports counts where the business needs meaning, and reports READY while doing it.
def test_meaning_usage_and_intent_cannot_rest_on_structural_evidence(classes: dict) -> None:
    for name in ("SCHEMA", "CODE", "UI_DEFINITION"):
        refused = set(classes["evidence_classes"][name]["cannot_support"])
        assert {"MEANING", "USAGE", "INTENT"} <= refused, (
            f"{name} must refuse MEANING, USAGE and INTENT; it refuses {sorted(refused)}"
        )


def test_a_format_claim_needs_a_sample(classes: dict) -> None:
    assert classes["evidence_classes"]["SAMPLE_DATA"]["supports"] == ["FORMAT"]
    assert classes["evidence_classes"]["OUTPUT_SAMPLE"]["supports"] == ["FORMAT"]
    assert "FORMAT" in (classes["evidence_classes"]["CODE"].get("corroborates") or []), \
        "code corroborates a format, it never settles one"


def test_rules_are_uniquely_identified_and_state_a_consequence(classes: dict) -> None:
    ids = [rule["id"] for rule in classes["rules"]]
    assert len(ids) == len(set(ids))
    for rule in classes["rules"]:
        assert rule.get("rule") and rule.get("on_violation"), rule["id"]


# --- identifier scheme ------------------------------------------------------

def test_every_namespace_pattern_compiles_and_matches_its_own_example(identifiers: dict) -> None:
    for name, entry in identifiers["namespaces"].items():
        pattern = re.compile(entry["pattern"])
        example = entry.get("example")
        if example is not None:
            assert pattern.fullmatch(example), f"{name} example {example!r} fails its own pattern"


def test_namespace_patterns_do_not_collide(identifiers: dict) -> None:
    """Two namespaces matching one string means an id has no single meaning."""
    examples = {
        name: entry["example"]
        for name, entry in identifiers["namespaces"].items()
        if entry.get("example")
    }
    for owner, example in examples.items():
        matched = [
            name for name, entry in identifiers["namespaces"].items()
            if re.fullmatch(entry["pattern"], example)
        ]
        assert matched == [owner], f"{example} matches {matched}, not only {owner}"


def test_namespaces_are_owned_by_real_phases(identifiers: dict) -> None:
    for name, entry in identifiers["namespaces"].items():
        for phase in entry.get("owned_by") or []:
            assert phase in PHASES, f"{name} owned_by unknown phase {phase}"


def test_business_rule_domains_are_declared_and_unique(identifiers: dict) -> None:
    domains = identifiers["namespaces"]["BR"]["domains"]
    assert domains, "BR must declare its domains"
    pattern = re.compile(identifiers["namespaces"]["BR"]["pattern"])
    for domain in domains:
        assert pattern.fullmatch(f"BR-{domain}-01"), f"domain {domain} cannot form a valid id"


def test_risk_namespaces_require_a_severity(identifiers: dict) -> None:
    for name in ("RD", "RA", "RW", "RS"):
        assert identifiers["namespaces"][name].get("requires_severity") is True, name


def test_consolidation_rule_names_the_namespaces_phase6_may_not_invent(identifiers: dict) -> None:
    rule = next(r for r in identifiers["rules"] if r["id"] == "ID-04")
    for namespace in ("BR-", "RD-", "RA-", "RW-", "RS-", "UK-", "AS-"):
        assert namespace in rule["rule"], f"ID-04 does not cover {namespace}"


# --- errata -----------------------------------------------------------------

def test_errata_entry_requires_what_makes_a_correction_auditable(errata: dict) -> None:
    required = errata["entry"]["required"]
    for field in ("id", "original", "corrected", "affected", "source", "cause"):
        assert field in required, f"an errata entry without {field} cannot be audited"


def test_every_cause_class_states_a_remedy(errata: dict) -> None:
    for name, entry in errata["cause_classes"].items():
        assert entry.get("means") and entry.get("remedy"), name


# Recorded because it is the cause class this session actually hit: eight objects were
# counted correctly, then described from the three that had been opened.
def test_the_described_not_counted_cause_is_declared(errata: dict) -> None:
    assert "DESCRIBED_NOT_COUNTED" in errata["cause_classes"]


def test_errata_id_matches_the_registered_namespace(errata: dict, identifiers: dict) -> None:
    pattern = identifiers["namespaces"]["E"]["pattern"]
    assert re.fullmatch(pattern, "E-01")
    assert "E-nn" in errata["entry"]["required"]["id"]


def test_a_superseded_evidence_item_is_never_deleted(errata: dict) -> None:
    rule = next(r for r in errata["rules"] if r["id"] == "ER-04")
    assert "never deleted" in rule["rule"]


def test_correcting_prose_without_registering_is_prohibited(errata: dict) -> None:
    assert "never silently edited" in errata["procedure"]["prohibition"]
