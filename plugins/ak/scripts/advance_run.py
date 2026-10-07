#!/usr/bin/env python3
"""Advance one orchestration wave only after valid completed handoffs and checkpoints."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from validate_handoffs import validate_run_handoffs

PUBLISH_PHASES = {
    f"gate{number}_publish_phase{number}": number for number in range(1, 6)
}

# A78. Phase 6 and its two waves were retired. A run created before that may still be
# sitting on one of them; advancing it moves the run to the wave that now follows Phase
# 5, writes nothing about Phase 6, and checks no handoffs, because the role that would
# have written them no longer exists.
RETIRED_WAVES = {
    "wave5_synthesis": "wave6_independent_qa",
    "gate6_publish_phase6": "wave6_independent_qa",
}

# Which phase becomes READY once a wave completes. Every key must name a wave in
# orchestration/waves.json; this used to say "gate_graph_phase2", and when the Graphify
# waves were removed nothing noticed, so Phase 2 could no longer be marked READY at all.
# test_advance_run.py now checks these keys against the declared sequence.
READY_AFTER: dict[str, tuple[str, ...]] = {
    "wave1_source_extraction": ("phase1",),
    "gate1_publish_phase1": ("phase2",),
    "wave2_logic_processing": ("phase3",),
    "wave3_workflow": ("phase4",),
    "wave4_document_integration": ("phase5",),
}


def load_waves(package: Path) -> list[dict] | None:
    try:
        value = json.loads(
            (package / "orchestration/waves.json").read_text(encoding="utf-8")
        )
    except (OSError, UnicodeError, json.JSONDecodeError):
        print("ERROR: waves.json: invalid JSON")
        return None
    waves = value.get("waves") if isinstance(value, dict) else None
    if (
        not isinstance(waves, list)
        or not waves
        or any(
            not isinstance(wave, dict)
            or not isinstance(wave.get("id"), str)
            or not wave["id"].strip()
            or not isinstance(wave.get("human_checkpoint_default"), bool)
            for wave in waves
        )
        or len({wave["id"] for wave in waves}) != len(waves)
    ):
        print("ERROR: waves.json: invalid structure")
        return None
    return waves


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--package", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--work-package-root")
    parser.add_argument("--wave", required=True)
    parser.add_argument("--approve-checkpoint", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def app_root_of(run: Path) -> Path | None:
    """The workspace a run belongs to, found by its manifest rather than by depth.

    A run lives at `<app_root>/.ak/runs/<id>`, but hard-coding `parents[2]` breaks the
    next time the layout moves - and it moved once already, when 2.10 introduced
    `input/` and relocated every acquired file.
    """
    for candidate in (run, *run.parents):
        if (candidate / "manifest.yaml").is_file():
            return candidate
    return None


def promote_requested(state: dict, run: Path) -> list[str]:
    """A phase the manifest now asks for stops being `NOT_REQUESTED`.

    Declining a phase has to be reversible, or it is not a choice - it is a decision
    somebody makes once, before there is anything to base it on. Gates are written at
    run creation and nothing re-read the manifest afterwards, so setting
    `outputs.phases.phase5` back to `true` used to require a whole new run.

    One direction only. A phase already `PUBLISHED` is not un-published by a manifest
    edit: the document exists, and run state that denied it would be the same lie as
    marking a declined phase published. So this promotes `NOT_REQUESTED` to `PENDING`
    and touches nothing else.
    """
    app_root = app_root_of(run)
    if app_root is None:
        return []
    contracts = str(Path(__file__).resolve().parent.parent / "contracts")
    if contracts not in sys.path:
        sys.path.insert(0, contracts)
    from manifest_v22 import requested_phases

    wanted = requested_phases((app_root / "manifest.yaml").read_text(encoding="utf-8"))
    promoted = [phase for phase, status in state.get("phase_gates", {}).items()
                if status == "NOT_REQUESTED" and wanted.get(phase)]
    for phase in promoted:
        state["phase_gates"][phase] = "PENDING"
    return promoted


def retire(state_path: Path, wave: str, next_wave: str, dry_run: bool) -> int:
    """Move a run off a wave that no longer exists (A78)."""
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("current_wave") != wave:
        raise SystemExit(f"Wave {wave} was retired with Phase 6, and this run is not on it")
    preview = {"retired_wave": wave, "next_wave": next_wave}
    if dry_run:
        print(json.dumps(preview, indent=2))
        return 0
    state["wave_status"][wave] = "RETIRED"
    state["current_wave"] = next_wave
    state["status"] = "RUNNING"
    state["wave_status"][next_wave] = "RUNNING"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(preview, indent=2))
    return 0


def main() -> int:
    args = parse_args()
    run = Path(args.run).expanduser().resolve()
    package = Path(args.package).expanduser().resolve()
    state_path = run / "run-state.json"
    waves = load_waves(package)
    if waves is None:
        return 1
    wave_index = {wave["id"]: index for index, wave in enumerate(waves)}
    if args.wave in RETIRED_WAVES and args.wave not in wave_index:
        return retire(state_path, args.wave, RETIRED_WAVES[args.wave], args.dry_run)
    if args.wave not in wave_index:
        raise SystemExit(f"Unknown wave: {args.wave}")
    index = wave_index[args.wave]
    wave = waves[index]

    errors, checked, pending = validate_run_handoffs(
        run,
        args.wave,
        require_complete=True,
        work_package_root=(
            Path(args.work_package_root) if args.work_package_root else None
        ),
        publication_phase=PUBLISH_PHASES.get(args.wave),
    )
    if checked == 0 and pending == 0:
        errors.append(f"No tasks found for wave {args.wave}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Wave advance blocked: {len(errors)} error(s)")
        return 1

    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state["current_wave"] != args.wave:
        raise SystemExit(f"Current wave is {state['current_wave']!r}, not {args.wave!r}")
    if wave["human_checkpoint_default"] and not args.approve_checkpoint:
        raise SystemExit(f"Wave {args.wave} requires explicit --approve-checkpoint")

    next_wave = waves[index + 1]["id"] if index + 1 < len(waves) else None
    preview = {"completed_wave": args.wave, "next_wave": next_wave, "checkpoint_approved": args.approve_checkpoint}
    if args.dry_run:
        print(json.dumps(preview, indent=2))
        return 0

    state["wave_status"][args.wave] = "COMPLETED"
    state["current_wave"] = next_wave
    state["status"] = "COMPLETED" if next_wave is None else "RUNNING"
    if next_wave:
        state["wave_status"][next_wave] = "RUNNING"
    promoted = promote_requested(state, run)
    if promoted:
        preview["requested_since_creation"] = sorted(promoted)

    # A phase the manifest did not ask for keeps `NOT_REQUESTED` all the way through.
    # Advancing past its gate has to work - `wave6_independent_qa` depends on
    # `gate5_publish_phase5`, so a run that skipped phase 5 could otherwise never
    # reach QA or rendering - but marking it `PUBLISHED` would record a document
    # nobody wrote. The wave graph is unchanged; only what the traversal writes is.
    for phase in READY_AFTER.get(args.wave, ()):
        if state["phase_gates"].get(phase) != "NOT_REQUESTED":
            state["phase_gates"][phase] = "READY"
    if args.wave in PUBLISH_PHASES:
        phase = f"phase{PUBLISH_PHASES[args.wave]}"
        if state["phase_gates"].get(phase) != "NOT_REQUESTED":
            state["phase_gates"][phase] = "PUBLISHED"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(preview, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
