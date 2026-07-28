from __future__ import annotations

import hashlib
import json
import re
import stat
import unicodedata
import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema
import yaml

from adapters.base import (
    AcquisitionPlan, AcquisitionRequest, AcquisitionResult, BundleContribution,
    CapabilityReport, empty_sections, validate_contribution,
)

ADAPTER_ID = "imported_sources"
ADAPTER_VERSION = "1.0.0"
MAX_ARCHIVE_FILES = 10_000
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
EXECUTABLE_SUFFIXES = {".exe", ".dll", ".com", ".bat", ".cmd", ".ps1", ".msi", ".scr"}
TEXT_KINDS = {"vba", "access_sql", "sql_server", "form", "report", "macro", "metadata"}

# ponytail: ZIP-only package support; add TAR only after equivalent traversal, link, and decompression-limit tests exist.
def safe_zip_members(archive: zipfile.ZipFile) -> tuple[zipfile.ZipInfo, ...]:
    infos = archive.infolist()
    if len(infos) > MAX_ARCHIVE_FILES:
        raise ValueError("ARCHIVE_FILE_LIMIT")
    total = 0
    accepted: list[zipfile.ZipInfo] = []
    for info in infos:
        member = PurePosixPath(info.filename.replace("\\", "/"))
        if member.is_absolute() or ".." in member.parts:
            raise ValueError("ARCHIVE_PATH_ESCAPE")
        mode = info.external_attr >> 16
        if stat.S_ISLNK(mode):
            raise ValueError("ARCHIVE_SYMLINK")
        if member.suffix.lower() in EXECUTABLE_SUFFIXES:
            raise ValueError("ARCHIVE_EXECUTABLE")
        total += info.file_size
        if total > MAX_ARCHIVE_BYTES:
            raise ValueError("ARCHIVE_SIZE_LIMIT")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise ValueError("ARCHIVE_COMPRESSION_RATIO")
        accepted.append(info)
    return tuple(accepted)

def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def decode_text(raw: bytes, declared_encoding: str | None) -> tuple[str, str]:
    if declared_encoding:
        try:
            return raw.decode(declared_encoding, errors="strict"), declared_encoding
        except UnicodeDecodeError as exc:
            raise ValueError("ENCODING_REQUIRED_OR_INVALID") from exc
    for marker, encoding in ((b"\xef\xbb\xbf", "utf-8-sig"), (b"\xff\xfe", "utf-16-le"), (b"\xfe\xff", "utf-16-be")):
        if raw.startswith(marker):
            return raw.decode(encoding, errors="strict"), encoding
    try:
        return raw.decode("utf-8", errors="strict"), "utf-8"
    except UnicodeDecodeError as exc:
        raise ValueError("ENCODING_REQUIRED_OR_INVALID") from exc

def confined(root: Path, declared: str) -> Path:
    base = root.expanduser().resolve()
    candidate = (base / declared).resolve()
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ValueError("PATH_ESCAPE") from exc
    return candidate

def _safe_name(record: dict[str, Any]) -> str:
    raw = str(record.get("object_name") or Path(record["logical_id"]).stem)
    normalized = unicodedata.normalize("NFKC", raw).casefold()
    return re.sub(r"[^a-z0-9._-]+", "_", normalized).strip("._")

def detect_record_conflicts(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    logical_ids: dict[str, str] = {}
    safe_names: dict[tuple[str, str], tuple[str, str]] = {}
    for record in records:
        logical_id = record["logical_id"]
        digest = record["sha256"]
        if logical_id in logical_ids and logical_ids[logical_id] != digest:
            failures.append({"logical_id": logical_id, "reason": "DUPLICATE_MISMATCH"})
        logical_ids.setdefault(logical_id, digest)
        name_key = (record["kind"], _safe_name(record))
        previous = safe_names.get(name_key)
        if previous and previous[0] != logical_id and previous[1] != digest:
            failures.append({"logical_id": logical_id, "reason": "ARTIFACT_CONFLICT"})
        safe_names.setdefault(name_key, (logical_id, digest))
    return sorted(failures, key=lambda item: (item["logical_id"], item["reason"]))

def load_import_manifest_bytes(raw: bytes) -> dict[str, Any]:
    data = yaml.safe_load(raw.decode("utf-8", errors="strict")) or {}
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "import-source-manifest.schema.json"
    jsonschema.validate(data, json.loads(schema_path.read_text(encoding="utf-8")))
    return data


def load_import_manifest(path: Path) -> dict[str, Any]:
    return load_import_manifest_bytes(path.read_bytes())


def _normalized_member_name(value: str) -> str:
    member = PurePosixPath(value.replace("\\", "/"))
    if member.is_absolute() or ".." in member.parts:
        raise ValueError("ARCHIVE_PATH_ESCAPE")
    return member.as_posix()


def _zip_member_map(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    result: dict[str, zipfile.ZipInfo] = {}
    for info in safe_zip_members(archive):
        if info.is_dir():
            continue
        name = _normalized_member_name(info.filename)
        if name in result:
            raise ValueError("ARCHIVE_MEMBER_CONFLICT")
        result[name] = info
    return result


def _read_directory_package(source: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    manifest_path = source / "import-source-manifest.yaml"
    if not manifest_path.is_file():
        raise ValueError("IMPORT_MANIFEST_REQUIRED")
    manifest = load_import_manifest(manifest_path)
    declared = {_normalized_member_name(item["path"]): item for item in manifest["files"]}
    actual = {
        path.relative_to(source).as_posix()
        for path in source.rglob("*")
        if path.is_file() and path != manifest_path
    }
    if actual != set(declared):
        raise ValueError("UNDECLARED_PACKAGE_MEMBER")
    payloads: dict[str, bytes] = {}
    for name in sorted(declared):
        path = source / Path(*PurePosixPath(name).parts)
        if path.is_symlink():
            raise ValueError("PACKAGE_SYMLINK")
        payloads[name] = confined(source, name).read_bytes()
    return manifest, payloads


def _read_zip_package(source: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    with zipfile.ZipFile(source) as archive:
        members = _zip_member_map(archive)
        manifest_info = members.get("import-source-manifest.yaml")
        if manifest_info is None:
            raise ValueError("IMPORT_MANIFEST_REQUIRED")
        manifest = load_import_manifest_bytes(archive.read(manifest_info))
        declared = {_normalized_member_name(item["path"]): item for item in manifest["files"]}
        if set(members) != set(declared) | {"import-source-manifest.yaml"}:
            raise ValueError("UNDECLARED_PACKAGE_MEMBER")
        return manifest, {name: archive.read(members[name]) for name in sorted(declared)}


def _read_package(source: Path) -> tuple[dict[str, Any], dict[str, bytes]]:
    return _read_directory_package(source) if source.is_dir() else _read_zip_package(source)

class ImportedSourcesAdapter:
    adapter_id = ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    supported_profiles = ("*",)
    supported_artifact_kinds = ("source_export", "document", "screenshot", "report", "sample", "metadata")

    def probe(self, request: AcquisitionRequest) -> CapabilityReport:
        missing = tuple(
            artifact["id"] for artifact in request.artifacts
            if not confined(request.source_root, artifact["source_ref"]["value"]).exists()
        )
        return CapabilityReport(self.adapter_id, self.adapter_version, not missing, missing)

    def plan(self, request: AcquisitionRequest) -> AcquisitionPlan:
        operations: list[dict[str, Any]] = []
        for artifact in request.artifacts:
            path = confined(request.source_root, artifact["source_ref"]["value"])
            operations.append({"artifact": artifact, "source": str(path), "is_package": path.is_dir() or path.suffix.lower() == ".zip"})
        return AcquisitionPlan(
            self.adapter_id, self.adapter_version,
            tuple(item["artifact"]["id"] for item in operations),
            authorization_required=(),
            reads=tuple(item["source"] for item in operations),
            writes=(),
            operations=tuple(operations), app_id=request.app_id,
        )

    def acquire(self, plan: AcquisitionPlan) -> AcquisitionResult:
        records: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        hashes: dict[str, str] = {}
        for operation in plan.operations:
            artifact = operation["artifact"]
            source = Path(operation["source"])
            if operation["is_package"]:
                try:
                    manifest, payloads = _read_package(source)
                except (OSError, UnicodeError, ValueError, zipfile.BadZipFile, jsonschema.ValidationError) as exc:
                    reason = str(exc) if str(exc).isupper() else "INVALID_IMPORT_PACKAGE"
                    failures.append({"logical_id": artifact["id"], "reason": reason})
                    continue
                for item in manifest["files"]:
                    name = _normalized_member_name(item["path"])
                    raw = payloads[name]
                    if sha256_bytes(raw) != item["sha256"]:
                        failures.append({"logical_id": item["logical_id"], "reason": "HASH_MISMATCH"})
                        continue
                    records.append(_record(item, raw))
                    hashes[item["logical_id"]] = item["sha256"]
                continue
            raw = source.read_bytes()
            digest = sha256_bytes(raw)
            item = {
                "logical_id": artifact["id"], "path": source.name,
                "kind": _declared_kind(artifact), "role": artifact["role"],
                "sha256": digest, "encoding": artifact.get("encoding"),
            }
            records.append(_record(item, raw))
            hashes[artifact["id"]] = digest
        failures.extend(detect_record_conflicts(records))
        status = "INVALID" if failures else "VALID"
        return AcquisitionResult(plan.app_id, self.adapter_id, self.adapter_version, status, tuple(records), tuple(failures), hashes)

    def normalize(self, result: AcquisitionResult) -> BundleContribution:
        sections = empty_sections()
        for record in result.records:
            _route_record(sections, record)
        contribution = {
            "adapter_id": self.adapter_id, "adapter_version": self.adapter_version,
            "app_id": result.app_id,
            "status": result.status, **sections, "failures": list(result.failures),
            "provenance": {"producer": "declared_import", "source_hashes": dict(sorted(result.source_hashes.items()))},
        }
        return validate_contribution(contribution)

def _declared_kind(artifact: dict[str, Any]) -> str:
    return {
        "source_export": "vba" if artifact.get("format") == "vba" else "metadata",
        "document": "document", "screenshot": "screenshot", "report": "report", "sample": "sample",
    }.get(artifact["kind"], "metadata")

def _record(item: dict[str, Any], raw: bytes) -> dict[str, Any]:
    record = {key: item.get(key) for key in ("logical_id", "kind", "role", "sha256", "media_type", "object_name") if item.get(key) is not None}
    if item["kind"] in TEXT_KINDS:
        text, encoding = decode_text(raw, item.get("encoding"))
        record.update({"text": text.replace("\r\n", "\n").replace("\r", "\n"), "source_encoding": encoding})
    else:
        record["external_only"] = True
    return record

def _route_record(sections: dict[str, Any], record: dict[str, Any]) -> None:
    kind = record["kind"]
    if kind == "vba": sections["code"]["vba"].append(record)
    elif kind == "access_sql": sections["code"]["access_sql"].append(record)
    elif kind == "sql_server": sections["code"]["sql_server"].append(record)
    elif kind == "form": sections["ui"]["forms"].append(record)
    elif kind == "report": sections["ui"]["reports"].append(record)
    elif kind == "macro": sections["ui"]["macros"].append(record)
    elif kind in {"document", "screenshot", "sample"}:
        bucket = {"document": "documents", "screenshot": "screenshots", "sample": "samples"}[kind]
        sections["evidence_sources"][bucket]["inventory"].append(record)
    else: sections["databases"]["objects"].append(record)
