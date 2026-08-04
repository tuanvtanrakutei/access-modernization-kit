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


def _run_raw(args: list[str], tmp_path: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(AK), *args], cwd=tmp_path,
        capture_output=True, text=True, encoding="utf-8",
    )


def _write_multi_adapter_manifest(tmp_path: Path) -> Path:
    (tmp_path / "Order.bas").write_text("Option Explicit\n", encoding="utf-8")
    (tmp_path / "catalog.json").write_text(json.dumps({
        "version": "1.0", "database": "SyntheticDb",
        "objects": [{
            "schema": "dbo", "name": "SyntheticOrder", "type": "table",
            "columns": [], "definition": None,
        }],
    }), encoding="utf-8")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "version: '2.2'\n"
        "app: {id: SYN, name_en: Synthetic}\n"
        "project:\n"
        "  classification: {topology: client_server, frontend_format: exported, source_availability: exported_only, backend_kinds: [sql_server]}\n"
        "artifacts:\n"
        "  - {id: VBA_ORDER, kind: source_export, role: frontend, acquisition: imported, required: true, format: vba, source_ref: {type: local_path, value: Order.bas}}\n"
        "  - {id: SQL_CATALOG, kind: sql_server_catalog, role: backend, acquisition: imported, required: true, format: json, source_ref: {type: local_path, value: catalog.json}}\n",
        encoding="utf-8",
    )
    return manifest


def test_multi_adapter_run_contains_vba_and_sql_catalog(tmp_path: Path) -> None:
    manifest = _write_multi_adapter_manifest(tmp_path)
    plan = _run(["acquire", "plan", "--manifest", str(manifest)], tmp_path)
    assert plan["adapters"] == {
        "imported_sources": ["VBA_ORDER"], "sql_server": ["SQL_CATALOG"]
    }
    result = _run([
        "acquire", "run", "--manifest", str(manifest),
        "--output-root", str(tmp_path / "bundles"),
    ], tmp_path)
    bundle = Path(result["bundle_dir"])
    assert json.loads((bundle / "code" / "vba" / "inventory.json").read_text(encoding="utf-8"))
    assert json.loads((bundle / "databases" / "tables.json").read_text(encoding="utf-8"))


def test_invalid_package_does_not_create_bundle(tmp_path: Path) -> None:
    loose = tmp_path / "loose"
    loose.mkdir()
    (loose / "Order.bas").write_text("Option Explicit\n", encoding="utf-8")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "version: '2.2'\n"
        "app: {id: SYN, name_en: Synthetic}\n"
        "project:\n"
        "  classification: {topology: monolith, frontend_format: exported, source_availability: exported_only, backend_kinds: [unknown_boundary]}\n"
        "artifacts:\n"
        "  - {id: LOOSE, kind: source_export, role: frontend, acquisition: imported, required: true, format: directory, source_ref: {type: local_path, value: loose}}\n",
        encoding="utf-8",
    )
    output = tmp_path / "bundles"
    completed = _run_raw([
        "acquire", "run", "--manifest", str(manifest), "--output-root", str(output)
    ], tmp_path)
    assert completed.returncode == 2
    data = json.loads(completed.stdout)
    assert data["status"] == "INVALID"
    assert data["bundle_id"] is None
    assert not list(output.glob("bundle-*"))


def test_managed_without_authorization_does_not_create_bundle(tmp_path: Path) -> None:
    (tmp_path / "frontend.mdb").write_bytes(b"synthetic-signature-only")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "version: '2.2'\n"
        "app: {id: SYN, name_en: Synthetic}\n"
        "project:\n"
        "  classification: {topology: monolith, frontend_format: mdb, source_availability: full, backend_kinds: [embedded_access]}\n"
        "artifacts:\n"
        "  - {id: FRONTEND, kind: access_database, role: frontend, acquisition: managed, required: true, format: mdb, source_ref: {type: local_path, value: frontend.mdb}}\n",
        encoding="utf-8",
    )
    output = tmp_path / "bundles"
    completed = _run_raw([
        "acquire", "run", "--manifest", str(manifest), "--output-root", str(output)
    ], tmp_path)
    assert completed.returncode == 2
    data = json.loads(completed.stdout)
    assert data["status"] == "BLOCKED"
    assert data["failures"][0]["reason"] == "AUTHORIZATION_REQUIRED"
    assert not list(output.glob("bundle-*"))


def test_streamlined_acquire_shortcut(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    data = _run(["acquire", str(tmp_path)], tmp_path)
    assert data["status"] == "VALID"
    assert data["bundle_id"].startswith("bundle-")
    assert "plan" in data


def test_init_with_source_discovery(tmp_path: Path) -> None:
    src_dir = tmp_path / "raw_sources"
    src_dir.mkdir()
    (src_dir / "Customer.bas").write_text("Attribute VB_Name = \"Customer\"", encoding="utf-8")
    (src_dir / "Orders.sql").write_text("SELECT * FROM Orders;", encoding="utf-8")

    app_root = tmp_path / "TESTAPP"
    completed = subprocess.run([
        sys.executable, str(AK), "init",
        "--app-root", str(app_root),
        "--app-id", "TESTAPP",
        "--name-en", "Test Discovery App",
        "--source", str(src_dir),
    ], capture_output=True, text=True, encoding="utf-8")
    assert completed.returncode == 0
    manifest = app_root / "manifest.yaml"
    assert manifest.is_file()

    acq = _run(["acquire", str(app_root)], app_root)
    assert acq["status"] == "VALID"
    assert acq["bundle_id"].startswith("bundle-")
