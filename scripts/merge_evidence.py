#!/usr/bin/env python3
"""Merge role-scoped evidence fragments deterministically without resolving conflicts."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


VALID_STATUS = {"EXTRACTED", "INFERRED", "AMBIGUOUS"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True)
    parser.add_argument("--output")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def load_items(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return data["items"]
    raise ValueError("Expected a list or an object with an items list")


def main() -> int:
    args = parse_args()
    run = Path(args.run).expanduser().resolve()
    state = json.loads((run / "run-state.json").read_text(encoding="utf-8"))
    fragments = sorted((run / "evidence/fragments").glob("*.json"))
    by_id: dict[str, dict] = {}
    errors: list[str] = []

    for path in fragments:
        try:
            items = load_items(path)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{path.name}: {exc}")
            continue
        for item in items:
            evidence_id = item.get("id")
            if not evidence_id or not isinstance(evidence_id, str):
                errors.append(f"{path.name}: evidence item missing id")
                continue
            if item.get("app_id") != state["app_id"]:
                errors.append(f"{evidence_id}: app_id mismatch")
            if item.get("status") not in VALID_STATUS:
                errors.append(f"{evidence_id}: invalid status")
            confidence = item.get("confidence")
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                errors.append(f"{evidence_id}: invalid confidence")
            if not re.fullmatch(rf"{re.escape(state['app_id'])}-P[1-6]-[A-Z0-9_]+-[0-9]{{3,}}", evidence_id):
                errors.append(f"{evidence_id}: invalid V2 evidence id")
            if evidence_id in by_id and by_id[evidence_id] != item:
                errors.append(f"{evidence_id}: conflicting duplicate id")
            else:
                by_id[evidence_id] = item

    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Evidence merge failed: {len(errors)} error(s)")
        return 1
    merged = {
        "app_id": state["app_id"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "items": sorted(by_id.values(), key=lambda item: (item.get("phase", 0), item["id"])),
    }
    if args.dry_run:
        print(json.dumps({"fragment_count": len(fragments), "evidence_count": len(by_id)}, indent=2))
        return 0
    output = Path(args.output).expanduser().resolve() if args.output else run / "evidence/merged-evidence.json"
    try:
        output.relative_to(run)
    except ValueError:
        raise SystemExit("Output must remain inside the run directory")
    output.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Merged {len(by_id)} evidence item(s) from {len(fragments)} fragment(s) into {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
