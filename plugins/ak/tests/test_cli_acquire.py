from __future__ import annotations

import json
import shutil
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


def _copy_minimal_app(tmp_path: Path) -> Path:
    target = tmp_path / "DEMO"
    shutil.copytree(PACKAGE / "examples" / "minimal-app", target)
    return target


def _as_legacy_layout(app: Path) -> Path:
    """The same fixture as a pre-2.10.0 workspace: input/ back to sources/.

    The shipped example teaches the layout `init` creates now, so without this the
    legacy path would lose its only end-to-end coverage through the real CLI - and
    the whole point of reading both layouts is that a workspace mid-investigation
    keeps working.
    """
    (app / "input").rename(app / "sources")
    manifest = app / "manifest.yaml"
    manifest.write_text(
        manifest.read_text(encoding="utf-8").replace("input/", "sources/"), encoding="utf-8")
    return app


def test_minimal_app_preflight_and_acquisition_contract(tmp_path: Path) -> None:
    app = _copy_minimal_app(tmp_path)
    preflight = _run([
        "preflight", "--app-root", str(app), "--runtime", "generic",
    ], app)
    assert preflight["status"] == "PASS"
    assert preflight["input_preconditions"]["mode"] == "export"
    assert preflight["input_preconditions"]["present"]["vba"] is True
    assert preflight["input_preconditions"]["present"]["sql"] is True

    manifest = app / "manifest.yaml"
    plan = _run(["acquire", "plan", "--manifest", str(manifest)], app)
    assert plan["adapters"] == {
        "imported_sources": ["DEMO_VBA_FORM"],
        "sql_server": ["DEMO_SQL_SCHEMA", "DEMO_SQL_CATALOG"],
    }

    result = _run([
        "acquire", "run", "--manifest", str(manifest),
        "--output-root", str(app / "acquired"),
    ], app)
    assert result["status"] == "VALID"
    bundle = Path(result["bundle_dir"])
    validated = _run(["bundle", "validate", "--bundle-dir", str(bundle)], app)
    assert validated["bundle_id"] == result["bundle_id"]
    assert not list((app / "acquired").rglob("bundle-approval.json"))

    assert json.loads((bundle / "code" / "vba" / "inventory.json").read_text(encoding="utf-8"))
    assert json.loads((bundle / "code" / "sql-server" / "inventory.json").read_text(encoding="utf-8"))
    tables = json.loads((bundle / "databases" / "tables.json").read_text(encoding="utf-8"))
    assert [(table["schema"], table["name"]) for table in tables] == [("dbo", "DemoOrders")]

    readiness = json.loads((bundle / "phase-readiness.json").read_text(encoding="utf-8"))
    assert {phase: readiness[phase]["status"] for phase in (
        "phase1", "phase2", "phase3", "phase4", "phase5", "phase6",
    )} == {
        "phase1": "BLOCKED",
        "phase2": "BLOCKED",
        "phase3": "BLOCKED",
        "phase4": "BLOCKED",
        # This read LIMITED until the orchestrator started passing `package_root`, and
        # LIMITED was the capability half answering alone. The fixture supplies no
        # documents at all, and BLOCKED is what both `skills/investigate/SKILL.md` and
        # AUDIT-PLAN.md already said Phase 5 is without DOCUMENT evidence. The old
        # value was not a different opinion; it was the class half not running.
        "phase5": "BLOCKED",
        "phase6": "BLOCKED",
    }
    # The bundle's own readiness is where every later step reads this from, so the
    # class half has to be recorded here and not only in `$ak phase requirements`.
    # An empty map is the exact signature of the defect: it is what a caller that
    # omits `package_root` writes, on a workspace that has evidence to observe.
    classes = readiness["_meta"]["evidence_classes_present"]
    assert "CODE" in classes, classes
    assert "SCHEMA" in classes, classes
    assert "DOCUMENT" not in classes, classes


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


def test_the_same_fixture_acquires_in_the_pre_2_10_layout(tmp_path: Path) -> None:
    """Upgrading the kit must not strand a workspace that is already under way."""
    app = _as_legacy_layout(_copy_minimal_app(tmp_path))
    preflight = _run(["preflight", "--app-root", str(app), "--runtime", "generic"], app)
    assert preflight["status"] == "PASS"
    assert preflight["input_preconditions"]["present"]["vba"] is True

    result = _run([
        "acquire", "run", "--manifest", str(app / "manifest.yaml"),
        "--output-root", str(app / "acquired"),
    ], app)
    assert result["status"] == "VALID"
    # Written under the legacy root, and found there by every reader.
    assert (app / "acquired" / "bundles").is_dir()
