from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
AK = PACKAGE / "scripts" / "ak.py"

def _write_manifest(tmp_path: Path) -> Path:
    (tmp_path / "Order.bas").write_text("Option Explicit\n", encoding="utf-8")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "version: '2.2'\n"
        "app: {id: SYN, name_en: Synthetic}\n"
        "project:\n"
        "  classification: {topology: monolith, frontend_format: exported, source_availability: exported_only, backend_kinds: [unknown_boundary]}\n"
        "artifacts:\n"
        "  - {id: VBA_ORDER, kind: source_export, role: frontend, acquisition: imported, required: true, format: vba, source_ref: {type: local_path, value: Order.bas}}\n",
        encoding="utf-8",
    )
    return manifest

def _run(args: list[str], tmp_path: Path) -> dict:
    result = subprocess.run([sys.executable, str(AK), *args], cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)

def test_acquire_plan_hides_absolute_paths(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    data = _run(["acquire", "plan", "--manifest", str(manifest)], tmp_path)
    assert data["adapters"]["imported_sources"] == ["VBA_ORDER"]
    assert str(tmp_path) not in json.dumps(data)

def test_acquire_run_produces_unapproved_bundle(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    output_root = tmp_path / "bundles"
    data = _run(["acquire", "run", "--manifest", str(manifest), "--output-root", str(output_root)], tmp_path)
    assert data["bundle_id"].startswith("bundle-")
    assert Path(data["bundle_dir"], "bundle.json").is_file()
    assert not list(output_root.rglob("bundle-approval.json"))

def test_acquire_run_bundle_passes_the_validation_gate(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    output_root = tmp_path / "bundles"
    data = _run(["acquire", "run", "--manifest", str(manifest), "--output-root", str(output_root)], tmp_path)
    validated = _run(["bundle", "validate", "--bundle-dir", data["bundle_dir"]], tmp_path)
    assert validated["bundle_id"] == data["bundle_id"]
