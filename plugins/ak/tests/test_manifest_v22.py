from __future__ import annotations

import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

from manifest_v22 import ManifestError, load_manifest  # noqa: E402

V22 = """
version: "2.2"
app: {id: "A05", name_en: "Product Picking Support"}
project:
  profile: "access-file-split"
  profile_version: "1.0"
  classification:
    topology: "split_file"
    frontend_format: "mdb"
    source_availability: "full"
    backend_kinds: ["access_file", "text_or_csv"]
artifacts:
  - id: "A05_FRONTEND"
    kind: "access_database"
    role: "frontend"
    format: "mdb"
    acquisition: "managed"
    required: true
    source_ref: {type: "local_path", value: "sources/access/frontend.mdb"}
"""


def test_v21_remains_readable() -> None:
    manifest = load_manifest(PACKAGE / "references" / "manifest.example.yaml")
    assert manifest.version == "2.1"
    assert manifest.classification is None
    assert manifest.artifacts == ()


def test_v21_still_uses_strict_legacy_schema(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text(
        """version: "2.1"
app: {id: "A05", name_en: "Incomplete"}
""",
        encoding="utf-8",
    )
    with pytest.raises(ManifestError):
        load_manifest(path)


def test_v22_reads_classification_and_artifacts(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text(V22, encoding="utf-8")
    manifest = load_manifest(path)
    assert manifest.classification is not None
    assert manifest.classification.topology == "split_file"
    assert manifest.artifacts[0].source_ref.type == "local_path"


def test_minimal_app_is_classified_v22_acquisition_fixture() -> None:
    manifest = load_manifest(PACKAGE / "examples" / "minimal-app" / "manifest.yaml")
    assert manifest.version == "2.2"
    assert manifest.app["id"] == "DEMO"
    assert manifest.classification is not None
    assert manifest.classification.as_dict() == {
        "topology": "client_server",
        "frontend_format": "exported",
        "source_availability": "exported_only",
        "backend_kinds": ["sql_server"],
    }
    assert [artifact.id for artifact in manifest.artifacts] == [
        "DEMO_VBA_FORM",
        "DEMO_SQL_SCHEMA",
        "DEMO_SQL_CATALOG",
    ]
    assert [artifact.source_ref.value for artifact in manifest.artifacts] == [
        "sources/vba/DemoOrderForm.bas",
        "sources/sql/demo_orders.sql",
        "sources/sql/catalog.json",
    ]
    assert all(artifact.source_ref.type == "workspace_path" for artifact in manifest.artifacts)


def test_alias_disagreement_fails(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text(V22.replace("access-file-split", "access-adp-sqlserver"), encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)


def test_local_path_must_be_relative(tmp_path: Path) -> None:
    path = tmp_path / "manifest.yaml"
    path.write_text(V22.replace("sources/access/frontend.mdb", "D:/outside/frontend.mdb"), encoding="utf-8")
    with pytest.raises(ManifestError):
        load_manifest(path)
