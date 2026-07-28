from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

import yaml

from adapters.base import AcquisitionRequest
from adapters.imported_sources.adapter import (
    ImportedSourcesAdapter,
    decode_text,
    detect_record_conflicts,
    safe_zip_members,
    sha256_bytes,
)

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


def _package_manifest(path: str, raw: bytes) -> dict:
    return {
        "version": "1.0",
        "producer": {"id": "synthetic", "version": "1.0.0"},
        "files": [{
            "logical_id": "MOD_ORDER", "path": path, "kind": "vba",
            "role": "frontend", "sha256": sha256_bytes(raw), "encoding": "utf-8",
        }],
    }


def _write_zip(path: Path, members: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, raw in members.items():
            archive.writestr(name, raw)


def _zip_artifact() -> dict:
    return {
        "id": "ZIP_EXPORT", "kind": "source_export", "role": "frontend",
        "acquisition": "imported", "required": True,
        "source_ref": {"type": "local_path", "value": "export.zip"}, "format": "zip",
    }


def test_zip_with_manifest_is_acquired_without_extracting(tmp_path: Path) -> None:
    raw = b"Option Explicit\n"
    manifest = yaml.safe_dump(_package_manifest("modules/Order.bas", raw), sort_keys=False).encode()
    _write_zip(tmp_path / "export.zip", {
        "import-source-manifest.yaml": manifest,
        "modules/Order.bas": raw,
    })
    adapter = ImportedSourcesAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, _zip_artifact())))
    assert result.status == "VALID"
    assert result.records[0]["logical_id"] == "MOD_ORDER"
    assert result.records[0]["text"] == "Option Explicit\n"
    assert not (tmp_path / "modules").exists()


def test_zip_rejects_undeclared_member(tmp_path: Path) -> None:
    raw = b"Option Explicit\n"
    manifest = yaml.safe_dump(_package_manifest("modules/Order.bas", raw), sort_keys=False).encode()
    _write_zip(tmp_path / "export.zip", {
        "import-source-manifest.yaml": manifest,
        "modules/Order.bas": raw,
        "modules/Hidden.bas": b"Option Explicit\n",
    })
    adapter = ImportedSourcesAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, _zip_artifact())))
    assert result.status == "INVALID"
    assert result.failures == ({"logical_id": "ZIP_EXPORT", "reason": "UNDECLARED_PACKAGE_MEMBER"},)


def test_zip_rejects_duplicate_normalized_member(tmp_path: Path) -> None:
    raw = b"Option Explicit\n"
    manifest = yaml.safe_dump(_package_manifest("modules/Order.bas", raw), sort_keys=False).encode()
    archive = tmp_path / "export.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("import-source-manifest.yaml", manifest)
        handle.writestr("modules/Order.bas", raw)
        handle.writestr("modules\\Order.bas", raw)
    adapter = ImportedSourcesAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, _zip_artifact())))
    assert result.status == "INVALID"
    assert result.failures == ({"logical_id": "ZIP_EXPORT", "reason": "ARCHIVE_MEMBER_CONFLICT"},)


def test_directory_rejects_declared_symlink(tmp_path: Path) -> None:
    package = tmp_path / "loose"
    package.mkdir()
    outside = tmp_path / "outside.bas"
    outside.write_text("Option Explicit\n", encoding="utf-8")
    try:
        (package / "Order.bas").symlink_to(outside)
    except OSError:
        return
    manifest = _package_manifest("Order.bas", outside.read_bytes())
    (package / "import-source-manifest.yaml").write_text(
        yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8"
    )
    artifact = _zip_artifact() | {
        "id": "DIR_EXPORT", "source_ref": {"type": "local_path", "value": "loose"},
        "format": "directory",
    }
    adapter = ImportedSourcesAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, artifact)))
    assert result.status == "INVALID"
    assert result.failures == ({"logical_id": "DIR_EXPORT", "reason": "PACKAGE_SYMLINK"},)
