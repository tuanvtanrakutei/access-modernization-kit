from __future__ import annotations

import argparse
from pathlib import Path

import build_import_manifest as bim
import yaml
from adapters.base import AcquisitionRequest
from adapters.imported_sources.adapter import ImportedSourcesAdapter

CLASSIFICATION = {
    "topology": "monolith", "frontend_format": "exported",
    "source_availability": "exported_only", "backend_kinds": ["unknown_boundary"],
}


def _args(**overrides) -> argparse.Namespace:
    defaults = {
        "producer_id": "ExportAccessObjects.bas", "producer_version": "2026-07",
        "logical_id_prefix": "A05_FRONTEND", "output": None,
        "allow_unclassified": False, "dry_run": False, "source_database": None,
    }
    return argparse.Namespace(**{**defaults, **overrides})


def _export(root: Path) -> Path:
    """An export tree in the shape ``tools/ExportAccessObjects.bas`` writes."""
    (root / "forms").mkdir(parents=True)
    (root / "queries").mkdir()
    (root / "modules").mkdir()
    # Genuinely cp932: Access 2003 exports its object text in the console codepage,
    # and only non-ASCII bytes distinguish that from utf-8.
    (root / "forms" / "F受注入力.txt").write_text('Version =20\nCaption = "受注入力"\n', encoding="cp932")
    (root / "queries" / "q受注データ.sql").write_text("SELECT 1;\n", encoding="utf-8")
    (root / "modules" / "共通ルーチン.bas").write_text("Option Explicit\n", encoding="utf-8")
    return root


def test_export_tree_is_classified_by_container_directory(tmp_path: Path) -> None:
    manifest, unclassified = bim.build_manifest(_export(tmp_path), _args())
    assert unclassified == []
    kinds = {item["path"]: item["kind"] for item in manifest["files"]}
    assert kinds == {
        "forms/F受注入力.txt": "form",
        "modules/共通ルーチン.bas": "vba",
        "queries/q受注データ.sql": "access_sql",
    }
    # The declared encoding has to be the one that actually decodes the bytes, or the
    # adapter rejects the file with ENCODING_REQUIRED_OR_INVALID much later.
    encodings = {item["path"]: item["encoding"] for item in manifest["files"]}
    assert encodings["forms/F受注入力.txt"] == "cp932"
    assert encodings["queries/q受注データ.sql"] == "utf-8"


def test_unrecognized_directory_is_reported_not_mislabelled(tmp_path: Path) -> None:
    root = _export(tmp_path)
    (root / "notes.txt").write_text("free text\n", encoding="utf-8")
    manifest, unclassified = bim.build_manifest(root, _args())
    assert unclassified == ["notes.txt"]
    assert all(item["path"] != "notes.txt" for item in manifest["files"])
    # With the flag it is declared, so the adapter's undeclared-member check passes.
    manifest, _ = bim.build_manifest(root, _args(allow_unclassified=True))
    declared = {item["path"]: (item["kind"], item["role"]) for item in manifest["files"]}
    assert declared["notes.txt"] == ("metadata", "unknown")


def test_binary_in_a_text_container_is_refused(tmp_path: Path) -> None:
    root = _export(tmp_path)
    (root / "queries" / "blob.sql").write_bytes(b"\xff\xfe\x00\x81\xff")
    manifest, unclassified = bim.build_manifest(root, _args())
    assert any(item.startswith("queries/blob.sql (not decodable") for item in unclassified)
    assert all(item["path"] != "queries/blob.sql" for item in manifest["files"])


def test_logical_ids_are_stable_across_runs(tmp_path: Path) -> None:
    root = _export(tmp_path)
    first, _ = bim.build_manifest(root, _args())
    second, _ = bim.build_manifest(root, _args())
    assert [item["logical_id"] for item in first["files"]] == [item["logical_id"] for item in second["files"]]
    assert all(item["logical_id"].startswith("A05_FRONTEND:") for item in first["files"])


# The whole point of the generator: what it writes must satisfy the adapter that
# refused the bare directory. Asserting the shape in isolation would not prove that.
def test_declared_producer_reaches_the_records_not_the_adapter_version(tmp_path: Path) -> None:
    """Regression: the producer manifest's whole purpose is to say what made the export.

    The bundle recorded the literal string ``declared_import`` and the *schema* version
    ``1.0.0``, so a bundle could not distinguish text exported months earlier from text
    read out of the database in this run.
    """
    root = _export(tmp_path / "PKG")
    manifest, _ = bim.build_manifest(root, _args())
    (root / bim.MANIFEST_NAME).write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    artifact = {
        "id": "PKG", "kind": "source_export", "role": "frontend", "acquisition": "imported",
        "required": True, "format": "directory",
        "source_ref": {"type": "local_path", "value": "PKG"},
    }
    adapter = ImportedSourcesAdapter()
    result = adapter.acquire(adapter.plan(AcquisitionRequest("SYN", CLASSIFICATION, (artifact,), tmp_path)))
    producers = adapter.normalize(result)["provenance"]["source_producers"]
    assert len(producers) == 3
    assert set(map(tuple, (sorted(value.items()) for value in producers.values()))) == {
        (("producer", "ExportAccessObjects.bas"), ("producer_version", "2026-07")),
    }


def test_source_database_digest_is_recorded_for_drift_detection(tmp_path: Path) -> None:
    database = tmp_path / "app.mdb"
    database.write_bytes(b"not really an mdb, but a real digest")
    root = _export(tmp_path / "PKG")
    manifest, _ = bim.build_manifest(root, _args(source_database=str(database)))
    import hashlib
    assert manifest["source_database"] == {
        "path": str(database.resolve()),
        "sha256": hashlib.sha256(database.read_bytes()).hexdigest(),
    }
    # Absent the flag nothing is claimed either way - silence must not read as a match.
    without, _ = bim.build_manifest(root, _args())
    assert "source_database" not in without


def test_generated_manifest_is_accepted_by_the_imported_adapter(tmp_path: Path) -> None:
    root = _export(tmp_path / "A05_FRONTEND")
    manifest, unclassified = bim.build_manifest(root, _args())
    assert unclassified == []
    (root / bim.MANIFEST_NAME).write_text(
        yaml.safe_dump(manifest, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    artifact = {
        "id": "A05_FRONTEND", "kind": "source_export", "role": "frontend",
        "acquisition": "imported", "required": True, "format": "directory",
        "source_ref": {"type": "local_path", "value": "A05_FRONTEND"},
    }
    adapter = ImportedSourcesAdapter()
    result = adapter.acquire(adapter.plan(AcquisitionRequest("SYN", CLASSIFICATION, (artifact,), tmp_path)))
    assert result.failures == ()
    assert result.status == "VALID"
    contribution = adapter.normalize(result)
    assert len(contribution["ui"]["forms"]) == 1
    assert len(contribution["code"]["vba"]) == 1
    assert len(contribution["code"]["access_sql"]) == 1
