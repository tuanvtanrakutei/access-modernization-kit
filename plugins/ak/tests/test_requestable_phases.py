"""Phases 4-6 are asked for, not assumed, and a phase nobody asked for stays that way.

Backlog A19: every one of those three degrades without DOCUMENT or INTERVIEW evidence,
and nothing upstream of them collects any. Phase 4's own entry in
`phase_evidence_needs` says what the degradation is - "the workflows become code paths,
not workflows" - so a run that has collected none is producing a document its own
contract says it cannot support.

Two things had to be true for that to be skippable. The gate has to survive the whole
run without being overwritten, and it has to be passable: `wave6_independent_qa`
depends on `gate6_publish_phase6`, so a run that skipped phase 6 could otherwise never
reach QA or rendering. The wave graph is unchanged - optionality lives in run state,
the way `presentation_pptx` has since 2.8.

And `NOT_REQUESTED` is not `NOT_APPLICABLE`. The second means the *evidence* ruled the
phase out - provable by a `not_applicable_when` rule, which no profile currently ships,
so the status is reachable in principle and unused in practice. An operator declining a
deliverable is a choice; evidence excluding one is a finding. Reading the same would let
a choice look like a finding, and borrowing a status nobody produces would make that
the only thing it ever meant.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
sys.path.insert(0, str(PACKAGE / "contracts"))

import advance_run  # noqa: E402
import create_run  # noqa: E402

MANIFEST = "version: '2.2'\napp:\n  id: T01\n"


def manifest_with(**phases: bool) -> str:
    body = "".join(f"    {name}: {str(value).lower()}\n"
                   for name, value in phases.items())
    return MANIFEST + "outputs:\n  phases:\n" + body


# --- what the manifest asks for ---------------------------------------------

def test_a_manifest_that_says_nothing_asks_for_every_phase() -> None:
    """The default cannot be "skip". Every manifest written before `outputs.phases`
    existed says nothing about it, and each of those runs published six documents.
    """
    gates = create_run.initial_phase_gates(MANIFEST)
    assert set(gates) == {f"phase{n}" for n in range(1, 7)}
    assert set(gates.values()) == {"PENDING"}


def test_declining_a_phase_marks_its_gate_from_creation() -> None:
    gates = create_run.initial_phase_gates(manifest_with(phase4=False, phase6=False))
    assert gates["phase4"] == "NOT_REQUESTED"
    assert gates["phase6"] == "NOT_REQUESTED"
    assert gates["phase5"] == "PENDING"
    assert gates["phase1"] == "PENDING"


@pytest.mark.parametrize("phase", ["phase1", "phase2", "phase3"])
def test_the_first_three_cannot_be_declined(phase: str) -> None:
    """An acquisition supports their characteristic claims unaided - STRUCTURE,
    UI_DEFINITION, BEHAVIOUR - so there is nothing to weigh up and no key to set.
    """
    gates = create_run.initial_phase_gates(manifest_with(**{phase: False}))
    assert gates[phase] == "PENDING"
    assert phase not in create_run.REQUESTABLE_PHASES


def test_an_unparseable_manifest_asks_for_every_phase() -> None:
    """Failing closed here would mean a YAML error silently skipping three phases."""
    gates = create_run.initial_phase_gates("outputs:\n  phases: [this is not a map\n")
    assert set(gates.values()) == {"PENDING"}


# --- what the run does with it ----------------------------------------------

def state_after(wave: str, gates: dict[str, str]) -> dict[str, str]:
    """`advance_run`'s gate writes for one wave, applied to a starting state."""
    updated = dict(gates)
    for phase in advance_run.READY_AFTER.get(wave, ()):
        if updated.get(phase) != "NOT_REQUESTED":
            updated[phase] = "READY"
    if wave in advance_run.PUBLISH_PHASES:
        phase = f"phase{advance_run.PUBLISH_PHASES[wave]}"
        if updated.get(phase) != "NOT_REQUESTED":
            updated[phase] = "PUBLISHED"
    return updated


def test_a_declined_phase_is_never_recorded_as_published() -> None:
    """Publishing a document nobody wrote is a lie the run state would carry forward.

    Anything reading `phase_gates` afterwards - the modernize pipeline's pre-flight,
    independent QA - would believe a phase 6 synthesis exists.
    """
    gates = create_run.initial_phase_gates(manifest_with(phase6=False))
    after = state_after("gate6_publish_phase6", gates)
    assert after["phase6"] == "NOT_REQUESTED"


def test_a_requested_phase_still_publishes() -> None:
    gates = create_run.initial_phase_gates(MANIFEST)
    assert state_after("gate6_publish_phase6", gates)["phase6"] == "PUBLISHED"


def test_qa_still_depends_on_the_gate_a_declined_phase_owns() -> None:
    """This is why passing the gate had to be possible rather than removed.

    If the wave graph stopped routing QA through phase 6's publication, every run would
    change shape. It does not: the graph is untouched and only the traversal differs.
    """
    waves = json.loads(
        (PACKAGE / "orchestration" / "waves.json").read_text(encoding="utf-8"))["waves"]
    qa = next(wave for wave in waves if wave["id"] == "wave6_independent_qa")
    assert "gate6_publish_phase6" in qa["depends_on"]


# --- the two statuses that must not be confused -----------------------------

def test_not_requested_is_not_the_status_the_evidence_produces() -> None:
    """`NOT_APPLICABLE` is a finding with a proof behind it; this is a choice.

    Writing this test found that no profile ships a `not_applicable_when` rule at all:
    `phase_readiness.py` ranks the status and `classification-rule.schema.json`
    declares the mechanism, and nothing produces it. So it is reachable in principle
    and unused in practice - which is a second reason not to borrow it for a declined
    deliverable. A status with no producer cannot be made to mean something else
    without becoming the only thing it means.
    """
    import phase_readiness

    assert "NOT_APPLICABLE" in phase_readiness.RANK
    assert "NOT_REQUESTED" not in phase_readiness.RANK, (
        "NOT_REQUESTED must not enter the readiness ranking: readiness answers what "
        "the evidence supports, and a declined deliverable is not evidence"
    )
    schema = json.loads(
        (PACKAGE / "schemas" / "classification-rule.schema.json").read_text(
            encoding="utf-8"))
    assert "not_applicable_when" in json.dumps(schema), (
        "the mechanism NOT_APPLICABLE depends on is no longer declared, so that status "
        "has neither a producer nor a way to gain one"
    )
    producers = [
        path.name
        for path in sorted((PACKAGE / "profiles").rglob("*.yaml"))
        if "not_applicable_when" in path.read_text(encoding="utf-8")
    ]
    assert not producers, (
        f"{producers} now produce NOT_APPLICABLE. That is an improvement, and this "
        "assertion is the note saying it used to be unreachable - re-read the two "
        "statuses' comments before deleting it"
    )


def test_the_contract_declares_which_phases_are_requestable() -> None:
    contract = yaml.safe_load(
        (PACKAGE / "specifications" / "output-contract.yaml").read_text(encoding="utf-8"))
    required = contract["required_phase_outputs"]
    requestable = contract["requestable_phase_outputs"]
    assert len(required) == 3 and len(requestable) == 3
    assert not set(required) & set(requestable)
    for number, name in ((4, "Phase4"), (5, "Phase5"), (6, "Phase6")):
        assert any(name in output for output in requestable), name
        assert f"phase{number}" in create_run.REQUESTABLE_PHASES
