from __future__ import annotations

from pathlib import Path

import preflight


def _manifest(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "manifest.yaml"
    path.write_text(body, encoding="utf-8")
    return path


# A V2.2 manifest declares its inputs as artifacts, not under `sources`. Reading only
# the V2.1 shape reported every capability as unneeded - including Access itself on an
# Access-only project, and including graphify, whose gate is documented as mandatory.
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
graphify:
  enabled: true
""".lstrip())

    needs = preflight.manifest_needs(manifest)

    assert needs["access"] is True
    assert needs["graphify"] is True
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
graphify:
  enabled: true
""".lstrip())

    needs = preflight.manifest_needs(manifest)

    assert needs["access"] is True
    assert needs["live_sql"] is True
    assert needs["graphify"] is True


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
