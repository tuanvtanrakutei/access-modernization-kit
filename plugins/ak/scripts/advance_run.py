#!/usr/bin/env python3
"""Advance one orchestration wave only after valid completed handoffs and checkpoints."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from validate_handoffs import validate_run_handoffs

PUBLISH_PHASES = {
    f"gate{number}_publish_phase{number}": number for number in range(1, 7)
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
    "wave5_synthesis": ("phase6",),
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


def main() -> int:
    args = parse_args()
    run = Path(args.run).expanduser().resolve()
    package = Path(args.package).expanduser().resolve()
    state_path = run / "run-state.json"
    waves = load_waves(package)
    if waves is None:
        return 1
    wave_index = {wave["id"]: index for index, wave in enumerate(waves)}
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
    for phase in READY_AFTER.get(args.wave, ()):
        state["phase_gates"][phase] = "READY"
    if args.wave in PUBLISH_PHASES:
        state["phase_gates"][f"phase{PUBLISH_PHASES[args.wave]}"] = "PUBLISHED"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(preview, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
