from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
AK = PACKAGE / "scripts" / "ak.py"


def run_ok(*args: str) -> dict:
    result = subprocess.run(
        [sys.executable, str(AK), *args], cwd=PACKAGE,
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


def test_profile_validate_reports_resolved_rules() -> None:
    data = run_ok(
        "profile", "validate", "--topology", "split_file", "--frontend", "mdb",
        "--source-availability", "full", "--backend", "access_file",
    )
    assert "topology.split_file.backend_required" in data["rule_ids"]


def test_manifest_migrate_is_nondestructive() -> None:
    data = run_ok("manifest", "migrate", "--manifest", str(PACKAGE / "references" / "manifest.example.yaml"))
    assert data["source_version"] == "2.1"
