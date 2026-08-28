from __future__ import annotations

from pathlib import Path

import preflight


def _manifest(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# A V2.2 manifest declares its inputs as artifacts, not under `sources`. Reading only
# the V2.1 shape reported every capability as unneeded - including Access itself on an
# Access-only project, and including Access itself.
def test_v22_artifacts_are_read_as_capability_needs(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, """
version: '2.2'
app:
  id: A05
  name_en: Product Assortment Support
project:
  classification:
    topology: split_file
    frontend_format: mdb
    source_availability: full
    backend_kinds:
    - access_file
artifacts:
- id: A05_DATA
  kind: access_database
  role: backend
  acquisition: managed
  required: true
  format: mdb
  source_ref:
    type: local_path
    value: sources/access/data.mdb
""".lstrip())

    needs = preflight.manifest_needs(manifest)

    assert needs["access"] is True
    assert needs["adp"] is False
    assert needs["live_sql"] is False


def test_v22_adp_and_server_artifacts_are_detected(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, """
version: '2.2'
app:
  id: A09
  name_en: Server App
artifacts:
- id: FRONTEND
  kind: access_database
  role: frontend
  acquisition: managed
  required: true
  format: adp
  source_ref:
    type: local_path
    value: sources/access/app.adp
- id: CATALOG
  kind: sql_server_catalog
  role: backend
  acquisition: imported
  required: true
  source_ref:
    type: local_path
    value: sources/sql/catalog.json
""".lstrip())

    needs = preflight.manifest_needs(manifest)

    assert needs["access"] is True
    assert needs["adp"] is True
    assert needs["live_sql"] is True


def test_v21_manifests_are_still_read(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, """
version: "2.1"
app:
  id: A01
  name_en: Legacy
sources:
  access_databases:
    - path: sources/access/app.mdb
      format: mdb
  sql_server:
    live:
      enabled: true
""".lstrip())

    needs = preflight.manifest_needs(manifest)

    assert needs["access"] is True
    assert needs["live_sql"] is True


# Discovery alone is not predictive: a registered, bitness-matched Access can still
# fail to activate. A READY status was reported for a runtime extraction could not
# use, so the report has to say whether an activation was actually attempted.
def test_access_report_states_whether_activation_was_attempted(monkeypatch) -> None:
    calls: list[bool] = []

    def fake_inspect(*, smoke_test: bool = False, **_: object) -> dict[str, object]:
        calls.append(smoke_test)
        return {
            "platform": "Windows",
            "python_process_bitness": "64-bit",
            "registry": {"views": {"32-bit": {"access": {"registered": True}, "ace_providers": {}}}},
            "selected_host": {"status": "READY", "path": "powershell.exe", "bitness": "32-bit"},
            "status": "READY",
            "runasadmin_detected": False,
            "activation": {"tested": smoke_test, "status": "READY" if smoke_test else "NOT_REQUESTED"},
            "appcompat_flags": [],
        }

    import access_runtime

    monkeypatch.setattr(access_runtime, "inspect_access_runtime", fake_inspect)

    discovered = preflight.windows_access_capabilities()
    assert discovered["runtime_status"] == "READY"
    assert discovered["activation_verified"] is False

    verified = preflight.windows_access_capabilities(verify_activation=True)
    assert verified["activation_verified"] is True
    assert calls == [False, True]


_HYBRID = """
version: '2.2'
app:
  id: A05
  name_en: Product Assortment Support
project:
  classification:
    topology: split_file
    frontend_format: mdb
    source_availability: full
    backend_kinds:
    - access_file
artifacts:
- id: A05_FRONTEND
  kind: access_database
  role: frontend
  acquisition: managed
  required: true
  format: mdb
  source_ref:
    type: local_path
    value: sources/access/app.mdb
- id: A05_FRONTEND_EXPORT
  kind: source_export
  role: frontend
  acquisition: imported
  required: true
  format: directory
  source_ref:
    type: local_path
    value: sources/A05_FRONTEND
"""


def _hybrid_workspace(tmp_path: Path) -> Path:
    manifest = _manifest(tmp_path, _HYBRID)
    (tmp_path / "sources" / "access").mkdir(parents=True)
    (tmp_path / "sources" / "access" / "app.mdb").write_bytes(b"stub")
    (tmp_path / "sources" / "A05_FRONTEND" / "forms").mkdir(parents=True)
    (tmp_path / "sources" / "A05_FRONTEND" / "forms" / "F受注入力.txt").write_text("Version =20\n", encoding="utf-8")
    return manifest


# Only a single-file export declares format: vba. A directory or zip package - the shape
# the imported adapter requires - was recognized as neither VBA nor SQL, so an application
# whose forms, reports and modules all arrived that way reported no exported sources at
# all, and a hybrid project was labelled pure extract mode.
def test_directory_export_package_counts_as_an_exported_source(tmp_path: Path) -> None:
    manifest = _hybrid_workspace(tmp_path)
    declared = preflight.manifest_source_paths(manifest)
    assert declared["source_packages"] == ["sources/A05_FRONTEND"]
    block, _ = preflight.input_preconditions(manifest, {"access": True}, {})
    assert block["present"]["source_packages"] is True
    assert block["mode"] == "mixed"


# The mode describes which inputs were provided, nothing else. It used to be derived from
# whether extraction was pending, so the same inputs read "mixed" before acquisition and
# "export" afterwards.
def _publish_bundle(app_root: Path) -> Path:
    """A bundle is a directory carrying bundle.json, not a directory with the right name.

    An aborted acquisition can leave the directory behind, and preflight reading the
    name alone would report extraction already done.
    """
    bundle = app_root / "acquired" / "bundle-abc123"
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "bundle.json").write_text('{"bundle_id": "bundle-abc123"}', encoding="utf-8")
    return bundle


def test_mode_does_not_change_once_a_bundle_exists(tmp_path: Path) -> None:
    manifest = _hybrid_workspace(tmp_path)
    before, _ = preflight.input_preconditions(manifest, {"access": True}, {})
    assert before["mode"] == "mixed"
    assert before["needs_extraction"] is True
    _publish_bundle(tmp_path)
    after, _ = preflight.input_preconditions(manifest, {"access": True}, {})
    assert after["mode"] == "mixed"
    assert after["needs_extraction"] is False
    assert after["present"]["acquisition_bundle"] is True


# A published bundle is stronger evidence that acquisition ran than the legacy
# extracted/access path, which current acquisition never writes.
def test_published_bundle_satisfies_extracted_access(tmp_path: Path) -> None:
    manifest = _hybrid_workspace(tmp_path)
    assert preflight.input_preconditions(manifest, {"access": True}, {})[0]["present"]["extracted_access"] is False
    _publish_bundle(tmp_path)
    assert preflight.input_preconditions(manifest, {"access": True}, {})[0]["present"]["extracted_access"] is True


# An export-only project must not be pushed toward the Access runtime it does not need.
def test_export_only_project_is_not_reported_as_extract(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path, _HYBRID.replace("""- id: A05_FRONTEND
  kind: access_database
  role: frontend
  acquisition: managed
  required: true
  format: mdb
  source_ref:
    type: local_path
    value: sources/access/app.mdb
""", ""))
    (tmp_path / "sources" / "A05_FRONTEND" / "forms").mkdir(parents=True)
    (tmp_path / "sources" / "A05_FRONTEND" / "forms" / "F.txt").write_text("x\n", encoding="utf-8")
    block, _ = preflight.input_preconditions(manifest, {"access": False}, {})
    assert block["mode"] == "export"
    assert block["needs_extraction"] is False


def _run_preflight(monkeypatch, package: Path, manifest: Path | None = None) -> dict:
    import io
    import json as _json
    import sys as _sys

    argv = ["preflight", "--package", str(package), "--skip-skill-scan"]
    if manifest:
        argv += ["--manifest", str(manifest)]
    monkeypatch.setattr(_sys, "argv", argv)
    captured = io.StringIO()
    monkeypatch.setattr(_sys, "stdout", captured)
    preflight.main()
    monkeypatch.undo()
    return _json.loads(captured.getvalue())


_PACKAGE = Path(preflight.__file__).resolve().parent.parent


# Installing this package as a plugin installs no Python dependency: neither plugin
# manifest declares one and there is no install hook. `init` is stdlib-only and works
# without them, so preflight used to PASS right up to `acquire`, which imports both at
# module level and dies with ModuleNotFoundError, with no document saying to pip install.
def test_missing_runtime_package_fails_preflight(monkeypatch) -> None:
    real = preflight.importlib.util.find_spec

    def absent_yaml(name: str, *args, **kwargs):
        return None if name == "yaml" else real(name, *args, **kwargs)

    monkeypatch.setattr(preflight.importlib.util, "find_spec", absent_yaml)
    report = _run_preflight(monkeypatch, _PACKAGE)
    assert report["required"]["python_package_pyyaml"] is False
    assert report["status"] == "FAIL"
    assert any("PyYAML" in line and "requirements.txt" in line for line in report["recommendations"])


def test_runtime_packages_present_keeps_preflight_passing(monkeypatch) -> None:
    report = _run_preflight(monkeypatch, _PACKAGE)
    assert report["required"]["python_package_pyyaml"] is True
    assert report["required"]["python_package_jsonschema"] is True
    assert report["status"] == "PASS"
    assert not any("requirements.txt" in line for line in report["recommendations"])


# Without PyYAML, manifest_needs falls back to a text scan. It used to report those
# guesses as facts with nothing recording that no parse happened.
def test_manifest_read_without_yaml_is_marked_as_unparsed(tmp_path: Path, monkeypatch) -> None:
    manifest = _manifest(tmp_path, _HYBRID)
    assert preflight.manifest_needs(manifest)["yaml_parsed"] is True

    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def no_yaml(name, *args, **kwargs):
        if name == "yaml":
            raise ImportError("simulated missing PyYAML")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", no_yaml)
    needs = preflight.manifest_needs(manifest)
    monkeypatch.undo()
    assert needs["yaml_parsed"] is False
    # The text-scan fallback still answers, so the flag is the only thing that
    # distinguishes a guess from a parse.
    assert needs["access"] is True
