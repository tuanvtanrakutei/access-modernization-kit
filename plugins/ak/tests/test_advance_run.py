"""The wave names in advance_run must be names orchestration/waves.json actually declares.

They drifted once already. When the Graphify waves were removed from the sequence,
`advance_run` kept a `gate_graph_phase2` key in its readiness map, so completing any
wave left Phase 2 at PENDING forever. Nothing failed: a lookup against a dict just
misses, and a miss here is silent. These tests turn that silence into a failure.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

import advance_run  # noqa: E402


def declared_waves() -> list[str]:
    data = json.loads((PACKAGE / "orchestration" / "waves.json").read_text(encoding="utf-8"))
    return [wave["id"] for wave in data["waves"]]


def test_every_readiness_key_is_a_declared_wave() -> None:
    unknown = sorted(set(advance_run.READY_AFTER) - set(declared_waves()))
    assert not unknown, (
        f"{unknown} name no wave in waves.json, so the phases they unlock can never "
        "become READY"
    )


def test_every_publication_key_is_a_declared_wave() -> None:
    unknown = sorted(set(advance_run.PUBLISH_PHASES) - set(declared_waves()))
    assert not unknown, f"{unknown} name no wave in waves.json"


def test_every_phase_has_a_wave_that_makes_it_ready() -> None:
    ready = {phase for phases in advance_run.READY_AFTER.values() for phase in phases}
    missing = sorted({f"phase{n}" for n in range(1, 7)} - ready)
    assert not missing, f"{missing} can never be marked READY by completing any wave"


def test_a_phase_becomes_ready_before_it_can_be_published() -> None:
    order = declared_waves()
    for wave, phases in advance_run.READY_AFTER.items():
        for phase in phases:
            number = int(phase.removeprefix("phase"))
            publishing = next(
                (w for w, n in advance_run.PUBLISH_PHASES.items() if n == number), None
            )
            assert publishing is not None, f"{phase} becomes READY but is never published"
            assert order.index(wave) < order.index(publishing), (
                f"{phase} is published at {publishing}, which runs before {wave} makes "
                "it READY"
            )
