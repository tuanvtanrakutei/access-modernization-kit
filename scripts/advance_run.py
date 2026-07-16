#!/usr/bin/env python3
"""Advance one orchestration wave only after valid completed handoffs and checkpoints."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from validate_handoffs import validate_run_handoffs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--package", default=str(Path(__file__).resolve().parent.parent))
    parser.add_argument("--wave", required=True)
    parser.add_argument("--approve-checkpoint", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run = Path(args.run).expanduser().resolve()
    package = Path(args.package).expanduser().resolve()
    state_path = run / "run-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    waves = json.loads((package / "orchestration/waves.json").read_text(encoding="utf-8"))["waves"]
    wave_index = {wave["id"]: index for index, wave in enumerate(waves)}
    if args.wave not in wave_index:
        raise SystemExit(f"Unknown wave: {args.wave}")
    index = wave_index[args.wave]
    wave = waves[index]
    if state["current_wave"] != args.wave:
        raise SystemExit(f"Current wave is {state['current_wave']!r}, not {args.wave!r}")
    if wave["human_checkpoint_default"] and not args.approve_checkpoint:
        raise SystemExit(f"Wave {args.wave} requires explicit --approve-checkpoint")

    errors, checked, pending = validate_run_handoffs(run, args.wave, require_complete=True)
    if checked == 0 and pending == 0:
        errors.append(f"No tasks found for wave {args.wave}")
    for path in sorted((run / "tasks").glob("*.json")):
        task = json.loads(path.read_text(encoding="utf-8"))
        if task["wave_id"] != args.wave:
            continue
        handoff = json.loads((run / "handoffs" / f"{task['task_id']}.json").read_text(encoding="utf-8")) if (run / "handoffs" / f"{task['task_id']}.json").is_file() else {}
        if handoff.get("status") != "COMPLETED":
            errors.append(f"{task['task_id']}: handoff status is {handoff.get('status')!r}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Wave advance blocked: {len(errors)} error(s)")
        return 1

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
    ready_map = {
        "wave1_source_extraction": ("phase1", "phase2"),
        "wave2_logic_alignment_graph": ("phase3",),
        "wave3_workflow_documents": ("phase4", "phase5"),
        "wave4_synthesis": ("phase6",),
    }
    publish_map = {
        "gate1_publish_phase1_phase2": ("phase1", "phase2"),
        "gate2_publish_phase3": ("phase3",),
        "gate3_publish_phase4_phase5": ("phase4", "phase5"),
        "gate4_publish_phase6": ("phase6",),
    }
    for phase in ready_map.get(args.wave, ()):
        state["phase_gates"][phase] = "READY"
    for phase in publish_map.get(args.wave, ()):
        state["phase_gates"][phase] = "PUBLISHED"
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(preview, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
