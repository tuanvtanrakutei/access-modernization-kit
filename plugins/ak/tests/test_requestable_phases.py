"""Phases 4 and 5 are asked for, not assumed, and a phase nobody asked for stays that way.

Backlog A19: both degrade without DOCUMENT or INTERVIEW evidence, and nothing upstream of
them collects any. Phase 4's own entry in `phase_evidence_needs` says what the degradation
is - "the workflows become code paths, not workflows" - so a run that has collected none
is producing a document its own contract says it cannot support.

Two things had to be true for that to be skippable. The gate has to survive the whole
run without being overwritten, and it has to be passable: `wave6_independent_qa`
depends on `gate5_publish_phase5`, so a run that skipped phase 5 could otherwise never
reach QA or rendering. The wave graph is unchanged - optionality lives in run state.

Phase 6 was requestable too, until it was retired (A78). A manifest written before still
names it, and that has to keep working: it validates, and it creates no gate.

And `NOT_REQUESTED` is not `NOT_APPLICABLE`. The second meant the *evidence* ruled the
phase out, and no rule could ever produce it (A20). An operator declining a deliverable
is a choice; evidence excluding one is a finding.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
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
    existed says nothing about it, and each of those runs published every document.
    """
    gates = create_run.initial_phase_gates(MANIFEST)
    assert set(gates) == {f"phase{n}" for n in range(1, 6)}
    assert set(gates.values()) == {"PENDING"}


def test_declining_a_phase_marks_its_gate_from_creation() -> None:
    gates = create_run.initial_phase_gates(manifest_with(phase4=False, phase5=False))
    assert gates["phase4"] == "NOT_REQUESTED"
    assert gates["phase5"] == "NOT_REQUESTED"
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
    """Failing closed here would mean a YAML error silently skipping two phases."""
    gates = create_run.initial_phase_gates("outputs:\n  phases: [this is not a map\n")
    assert set(gates.values()) == {"PENDING"}


@pytest.mark.parametrize("value", [True, False])
def test_a_manifest_that_still_names_phase_six_creates_no_gate_for_it(value: bool) -> None:
    """A78. The key is accepted and ignored, whichever way it was set."""
    gates = create_run.initial_phase_gates(manifest_with(phase6=value))
    assert "phase6" not in gates
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
    independent QA - would believe a phase 5 document exists.
    """
    gates = create_run.initial_phase_gates(manifest_with(phase5=False))
    after = state_after("gate5_publish_phase5", gates)
    assert after["phase5"] == "NOT_REQUESTED"


def test_a_requested_phase_still_publishes() -> None:
    gates = create_run.initial_phase_gates(MANIFEST)
    assert state_after("gate5_publish_phase5", gates)["phase5"] == "PUBLISHED"


def test_qa_follows_the_last_phase_publication() -> None:
    """QA depends on the gate a declined phase owns, which is why passing it had to be
    possible rather than removed. With Phase 6 retired, that gate is Phase 5's.
    """
    waves = json.loads(
        (PACKAGE / "orchestration" / "waves.json").read_text(encoding="utf-8"))["waves"]
    ids = [wave["id"] for wave in waves]
    qa = next(wave for wave in waves if wave["id"] == "wave6_independent_qa")
    assert qa["depends_on"] == ["gate5_publish_phase5"]
    assert "wave5_synthesis" not in ids and "gate6_publish_phase6" not in ids


def test_a_run_state_with_a_declined_phase_is_schema_valid() -> None:
    """`create_run` wrote `NOT_REQUESTED` and the run-state schema did not list it, so
    `validate_run_handoffs` refused every run that had declined a phase.
    """
    schema = json.loads(
        (PACKAGE / "schemas" / "run-state.schema.json").read_text(encoding="utf-8"))
    gates = schema["properties"]["phase_gates"]["patternProperties"]["^phase[1-6]$"]["enum"]
    assert "NOT_REQUESTED" in gates
    assert "RETIRED" in schema["properties"]["wave_status"]["additionalProperties"]["enum"]


# --- a run created before Phase 6 was retired -------------------------------

def old_run(tmp_path: Path, current: str) -> Path:
    run = tmp_path / "R1"
    run.mkdir()
    state = {"current_wave": current, "status": "RUNNING",
             "wave_status": {"gate5_publish_phase5": "COMPLETED", current: "RUNNING"},
             "phase_gates": {f"phase{n}": "PUBLISHED" for n in range(1, 6)} | {"phase6": "PENDING"},
             "updated_at": "2026-01-01T00:00:00+00:00"}
    (run / "run-state.json").write_text(json.dumps(state), encoding="utf-8")
    return run


@pytest.mark.parametrize("wave", ["wave5_synthesis", "gate6_publish_phase6"])
def test_a_run_on_a_retired_wave_moves_to_qa(tmp_path: Path, wave: str) -> None:
    run = old_run(tmp_path, wave)
    assert advance_run.retire(run / "run-state.json", wave,
                              advance_run.RETIRED_WAVES[wave], dry_run=False) == 0
    state = json.loads((run / "run-state.json").read_text(encoding="utf-8"))
    assert state["current_wave"] == "wave6_independent_qa"
    assert state["wave_status"][wave] == "RETIRED"
    # Nothing is written about a document nobody produced.
    assert state["phase_gates"]["phase6"] == "PENDING"


def test_a_retired_wave_is_refused_for_a_run_that_is_not_on_it(tmp_path: Path) -> None:
    run = old_run(tmp_path, "wave6_independent_qa")
    with pytest.raises(SystemExit):
        advance_run.retire(run / "run-state.json", "wave5_synthesis",
                           "wave6_independent_qa", dry_run=False)


def test_every_retired_wave_is_gone_from_the_graph() -> None:
    waves = json.loads(
        (PACKAGE / "orchestration" / "waves.json").read_text(encoding="utf-8"))["waves"]
    ids = {wave["id"] for wave in waves}
    assert not set(advance_run.RETIRED_WAVES) & ids
    assert set(advance_run.RETIRED_WAVES.values()) <= ids


# --- declining has to be reversible ----------------------------------------

def workspace_with(tmp_path: Path, phase5: bool) -> tuple[Path, Path]:
    """An app root holding a schema-valid manifest, and a run directory inside it.

    Copied from `examples/minimal-app` rather than hand-rolled: `phase_report` calls
    `load_manifest`, which validates, and it should - a manifest that does not parse is
    a manifest error and must not be masked by a later short-circuit.
    """
    app = tmp_path / "A99"
    run = app / ".ak" / "runs" / "R1"
    run.mkdir(parents=True)
    text = (PACKAGE / "examples" / "minimal-app" / "manifest.yaml").read_text(
        encoding="utf-8")
    assert "phase5: true" in text, "the example manifest no longer declares phase5"
    if not phase5:
        text = text.replace("phase5: true", "phase5: false")
    (app / "manifest.yaml").write_text(text, encoding="utf-8")
    return app, run


def test_a_run_finds_its_workspace_by_the_manifest_not_by_depth(tmp_path: Path) -> None:
    """`parents[2]` would work today and break the next time the layout moves.

    It moved once already: 2.10 introduced `input/` and relocated every acquired file.
    """
    app, run = workspace_with(tmp_path, phase5=False)
    assert advance_run.app_root_of(run) == app
    assert advance_run.app_root_of(tmp_path) is None


def test_changing_your_mind_promotes_the_gate(tmp_path: Path) -> None:
    """Gates are written at run creation and nothing re-read the manifest afterwards.

    Without this, declining a phase meant a new run to undo - which makes the decision
    one somebody has to get right before there is anything to base it on.
    """
    app, run = workspace_with(tmp_path, phase5=False)
    state = {"phase_gates": create_run.initial_phase_gates(
        (app / "manifest.yaml").read_text(encoding="utf-8"))}
    assert state["phase_gates"]["phase5"] == "NOT_REQUESTED"

    # Still declined: an advance changes nothing.
    assert advance_run.promote_requested(state, run) == []
    assert state["phase_gates"]["phase5"] == "NOT_REQUESTED"

    (app / "manifest.yaml").write_text(
        (app / "manifest.yaml").read_text(encoding="utf-8").replace(
            "phase5: false", "phase5: true"), encoding="utf-8")
    assert advance_run.promote_requested(state, run) == ["phase5"]
    assert state["phase_gates"]["phase5"] == "PENDING"


def test_declining_after_publication_does_not_un_publish(tmp_path: Path) -> None:
    """The document exists. Run state denying it is the same lie in the other direction.

    Promotion is one-directional for that reason: a manifest edit can add work and
    cannot retract a published phase.
    """
    app, run = workspace_with(tmp_path, phase5=True)
    state = {"phase_gates": {"phase5": "PUBLISHED"}}
    (app / "manifest.yaml").write_text(
        (app / "manifest.yaml").read_text(encoding="utf-8").replace(
            "phase5: true", "phase5: false"), encoding="utf-8")
    assert advance_run.promote_requested(state, run) == []
    assert state["phase_gates"]["phase5"] == "PUBLISHED"


def test_the_evidence_report_answers_for_a_declined_phase(tmp_path: Path) -> None:
    """One manifest was answering two ways.

    `outputs.phases` said a phase is not produced, and `$ak phase requirements` reported
    what evidence it still needs - so an operator would go and fetch evidence for a
    document nobody was going to write.
    """
    import phase_evidence

    app, _run = workspace_with(tmp_path, phase5=False)
    report = phase_evidence.phase_report(app, 5)
    assert report["status"] == "NOT_REQUESTED"
    assert report["missing"] == []
    # And it says how to change the answer, because a status with no route out reads
    # like a refusal.
    assert any("true" in reason for reason in report["reasons"]), report["reasons"]


def test_a_requested_phase_is_still_reported_on(tmp_path: Path) -> None:
    import phase_evidence

    app, _run = workspace_with(tmp_path, phase5=True)
    assert phase_evidence.phase_report(app, 5)["status"] != "NOT_REQUESTED"


def test_a_manifest_written_before_the_retirement_still_validates(tmp_path: Path) -> None:
    """A78. Every existing project's manifest says `phase6` and `presentation_pptx`."""
    import manifest_v22

    data = yaml.safe_load((PACKAGE / "references" / "manifest.example.yaml").read_text(
        encoding="utf-8"))
    assert str(data["version"]) == "2.1"
    data["outputs"]["phases"]["phase6"] = True
    data["outputs"]["presentation_template"] = ""
    data["outputs"]["derived"]["presentation_pptx"] = False
    data["multi_agent"]["human_checkpoints"].append("phase6")
    schema = json.loads(
        (PACKAGE / "schemas" / "manifest.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)

    text = (PACKAGE / "examples" / "minimal-app" / "manifest.yaml").read_text(encoding="utf-8")
    old = tmp_path / "manifest.yaml"
    old.write_text(text.replace("phase5: true", "phase5: true\n    phase6: true"), encoding="utf-8")
    manifest_v22.load_manifest(old)


# --- the two statuses that must not be confused -----------------------------

def test_not_requested_is_not_the_status_the_evidence_produces() -> None:
    """`NOT_APPLICABLE` was a finding with a proof behind it; this is a choice.

    It was removed for being unreachable (A20), so the distinction is now structural
    rather than a rule somebody has to remember.
    """
    import phase_readiness

    assert "NOT_REQUESTED" not in phase_readiness.RANK, (
        "NOT_REQUESTED must not enter the readiness ranking: readiness answers what "
        "the evidence supports, and a declined deliverable is not evidence"
    )
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
    assert len(required) == 3 and len(requestable) == 2
    assert not set(required) & set(requestable)
    for number, name in ((4, "Phase4"), (5, "Phase5")):
        assert any(name in output for output in requestable), name
        assert f"phase{number}" in create_run.REQUESTABLE_PHASES
    assert not any("Phase6" in output for output in required + requestable)
