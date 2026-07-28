from __future__ import annotations

import hashlib
from pathlib import Path

from adapters.base import AcquisitionRequest
from adapters.imported_sources.adapter import ImportedSourcesAdapter, decode_text, detect_record_conflicts, safe_zip_members

CLASSIFICATION = {
    "topology": "monolith", "frontend_format": "exported",
    "source_availability": "exported_only", "backend_kinds": ["unknown_boundary"],
}

def _request(root: Path, artifact: dict) -> AcquisitionRequest:
    return AcquisitionRequest("SYN", CLASSIFICATION, (artifact,), root)

def test_declared_single_file_is_planned(tmp_path: Path) -> None:
    source = tmp_path / "Order.bas"
    source.write_text("Option Explicit\n", encoding="utf-8")
    artifact = {
        "id": "VBA_ORDER", "kind": "source_export", "role": "frontend", "acquisition": "imported",
        "required": True, "source_ref": {"type": "local_path", "value": "Order.bas"}, "format": "vba",
    }
    plan = ImportedSourcesAdapter().plan(_request(tmp_path, artifact))
    assert plan.planned_artifacts == ("VBA_ORDER",)
    assert plan.authorization_required == ()

def test_directory_without_import_manifest_is_invalid(tmp_path: Path) -> None:
    (tmp_path / "loose").mkdir()
    (tmp_path / "loose" / "Order.bas").write_text("Option Explicit\n", encoding="utf-8")
    artifact = {
        "id": "LOOSE", "kind": "source_export", "role": "frontend", "acquisition": "imported",
        "required": True, "source_ref": {"type": "local_path", "value": "loose"}, "format": "directory",
    }
    result = ImportedSourcesAdapter().acquire(ImportedSourcesAdapter().plan(_request(tmp_path, artifact)))
    assert result.status == "INVALID"
    assert result.failures[0]["reason"] == "IMPORT_MANIFEST_REQUIRED"

def test_cp932_requires_declaration_when_utf8_is_not_valid() -> None:
    raw = "注文".encode("cp932")
    text, encoding = decode_text(raw, declared_encoding="cp932")
    assert text == "注文"
    assert encoding == "cp932"

def test_lossy_or_unknown_encoding_is_rejected() -> None:
    try:
        decode_text(b"\x81", declared_encoding=None)
    except ValueError as exc:
        assert str(exc) == "ENCODING_REQUIRED_OR_INVALID"
        return
    raise AssertionError("invalid text must not be replacement-decoded")

def test_zip_path_escape_is_rejected(tmp_path: Path) -> None:
    import zipfile
    archive = tmp_path / "bad.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../escape.bas", "Option Explicit")
    with zipfile.ZipFile(archive) as handle:
        try:
            safe_zip_members(handle)
        except ValueError as exc:
            assert str(exc) == "ARCHIVE_PATH_ESCAPE"
            return
    raise AssertionError("archive traversal must be rejected")

def test_duplicate_logical_id_with_different_hash_is_rejected() -> None:
    failures = detect_record_conflicts([
        {"logical_id": "MOD_ORDER", "kind": "vba", "sha256": "a" * 64},
        {"logical_id": "MOD_ORDER", "kind": "vba", "sha256": "b" * 64},
    ])
    assert failures == [{"logical_id": "MOD_ORDER", "reason": "DUPLICATE_MISMATCH"}]

def test_safe_name_collision_is_rejected() -> None:
    failures = detect_record_conflicts([
        {"logical_id": "FORM_A", "kind": "form", "object_name": "Order/Form", "sha256": "a" * 64},
        {"logical_id": "FORM_B", "kind": "form", "object_name": "Order:Form", "sha256": "b" * 64},
    ])
    assert failures == [{"logical_id": "FORM_B", "reason": "ARTIFACT_CONFLICT"}]
