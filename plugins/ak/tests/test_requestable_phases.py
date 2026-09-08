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
NL = chr(10)


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


# --- declining has to be reversible ----------------------------------------

def workspace_with(tmp_path: Path, phase6: bool) -> tuple[Path, Path]:
    """An app root holding a schema-valid manifest, and a run directory inside it.

    Copied from `examples/minimal-app` rather than hand-rolled: `phase_report` calls
    `load_manifest`, which validates, and it should - a manifest that does not parse is
    a manifest error and must not be masked by a later short-circuit. A minimal
    hand-written one fails on `project` and would have tested the validator instead.
    """
    app = tmp_path / "A05"
    run = app / ".ak" / "runs" / "R1"
    run.mkdir(parents=True)
    text = (PACKAGE / "examples" / "minimal-app" / "manifest.yaml").read_text(
        encoding="utf-8")
    assert "phase6: true" in text, "the example manifest no longer declares phase6"
    if not phase6:
        text = text.replace("phase6: true", "phase6: false")
    (app / "manifest.yaml").write_text(text, encoding="utf-8")
    return app, run


def test_a_run_finds_its_workspace_by_the_manifest_not_by_depth(tmp_path: Path) -> None:
    """`parents[2]` would work today and break the next time the layout moves.

    It moved once already: 2.10 introduced `input/` and relocated every acquired file.
    """
    app, run = workspace_with(tmp_path, phase6=False)
    assert advance_run.app_root_of(run) == app
    assert advance_run.app_root_of(tmp_path) is None


def test_changing_your_mind_promotes_the_gate(tmp_path: Path) -> None:
    """Gates are written at run creation and nothing re-read the manifest afterwards.

    Without this, declining a phase meant a new run to undo - which makes the decision
    one somebody has to get right before there is anything to base it on.
    """
    app, run = workspace_with(tmp_path, phase6=False)
    state = {"phase_gates": create_run.initial_phase_gates(
        (app / "manifest.yaml").read_text(encoding="utf-8"))}
    assert state["phase_gates"]["phase6"] == "NOT_REQUESTED"

    # Still declined: an advance changes nothing.
    assert advance_run.promote_requested(state, run) == []
    assert state["phase_gates"]["phase6"] == "NOT_REQUESTED"

    (app / "manifest.yaml").write_text(
        (app / "manifest.yaml").read_text(encoding="utf-8").replace(
            "phase6: false", "phase6: true"), encoding="utf-8")
    assert advance_run.promote_requested(state, run) == ["phase6"]
    assert state["phase_gates"]["phase6"] == "PENDING"


def test_declining_after_publication_does_not_un_publish(tmp_path: Path) -> None:
    """The document exists. Run state denying it is the same lie in the other direction.

    Promotion is one-directional for that reason: a manifest edit can add work and
    cannot retract a published phase.
    """
    app, run = workspace_with(tmp_path, phase6=True)
    state = {"phase_gates": {"phase6": "PUBLISHED"}}
    (app / "manifest.yaml").write_text(
        (app / "manifest.yaml").read_text(encoding="utf-8").replace(
            "phase6: true", "phase6: false"), encoding="utf-8")
    assert advance_run.promote_requested(state, run) == []
    assert state["phase_gates"]["phase6"] == "PUBLISHED"


def test_the_evidence_report_answers_for_a_declined_phase(tmp_path: Path) -> None:
    """One manifest was answering two ways.

    `outputs.phases` said phase 6 is not produced, and `$ak phase requirements
    --phase 6` reported what evidence phase 6 still needs - so an operator would go and
    fetch evidence for a document nobody was going to write.
    """
    import phase_evidence

    app, _run = workspace_with(tmp_path, phase6=False)
    report = phase_evidence.phase_report(app, 6)
    assert report["status"] == "NOT_REQUESTED"
    assert report["missing"] == []
    # And it says how to change the answer, because a status with no route out reads
    # like a refusal.
    assert any("true" in reason for reason in report["reasons"]), report["reasons"]


def test_a_requested_phase_is_still_reported_on(tmp_path: Path) -> None:
    import phase_evidence

    app, _run = workspace_with(tmp_path, phase6=True)
    assert phase_evidence.phase_report(app, 6)["status"] != "NOT_REQUESTED"


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

    assert "NOT_REQUESTED" not in phase_readiness.RANK, (
        "NOT_REQUESTED must not enter the readiness ranking: readiness answers what "
        "the evidence supports, and a declined deliverable is not evidence"
    )
    # There is nothing left to be confused with. `NOT_APPLICABLE` was the candidate
    # this status was careful not to borrow, and it has since been removed for being
    # unreachable (A20) - so the distinction is now structural rather than a rule
    # somebody has to remember.
    assert "NOT_APPLICABLE" not in phase_readiness.RANK
    schema = json.loads(
        (PACKAGE / "schemas" / "classification-rule.schema.json").read_text(
            encoding="utf-8"))
    assert "not_applicable_when" not in json.dumps(schema)


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
