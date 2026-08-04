from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import jsonschema

import bundle as bundle_contract

def _guard_no_binaries(contributions: list[dict[str, Any]]) -> None:
    for contribution in contributions:
        for value in _walk(contribution):
            if isinstance(value, dict) and (value.get("raw_binary") is True or "raw_path" in value):
                raise ValueError("Contribution carries a raw database binary")
            if isinstance(value, str) and Path(value).suffix.lower() in bundle_contract.FORBIDDEN_SUFFIXES:
                raise ValueError("Contribution references a forbidden raw binary")

def _walk(value: Any) -> list[Any]:
    found = [value]
    if isinstance(value, dict):
        for item in value.values():
            found.extend(_walk(item))
    elif isinstance(value, list):
        for item in value:
            found.extend(_walk(item))
    return found

def _logical_artifacts(contributions: list[dict[str, Any]]) -> list[dict[str, str]]:
    artifacts: dict[str, str] = {}
    for contribution in contributions:
        for logical_id, digest in contribution["provenance"]["source_hashes"].items():
            previous = artifacts.get(logical_id)
            if previous is not None and previous != digest:
                raise ValueError(f"DUPLICATE_MISMATCH:{logical_id}")
            artifacts[logical_id] = digest
    return [{"logical_id": key, "content_sha256": artifacts[key]} for key in sorted(artifacts)]


def _merge_records(target: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> None:
    keyed: dict[tuple[str, str], dict[str, Any]] = {}
    unkeyed: list[dict[str, Any]] = []
    for record in [*target, *incoming]:
        logical_id = record.get("logical_id")
        digest = record.get("sha256")
        if logical_id is None or digest is None:
            unkeyed.append(record)
            continue
        keyed.setdefault((str(logical_id), str(digest)), record)
    target[:] = [keyed[key] for key in sorted(keyed)] + sorted(
        unkeyed, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True)
    )


def _merge_sections(contributions: list[dict[str, Any]]) -> dict[str, Any]:
    from adapters.base import empty_sections

    merged = empty_sections()
    for contribution in sorted(contributions, key=lambda item: item["adapter_id"]):
        for group in ("databases", "code", "ui", "interfaces"):
            for key, values in contribution[group].items():
                _merge_records(merged[group][key], values)
        for key in ("documents", "screenshots", "reports", "samples"):
            _merge_records(
                merged["evidence_sources"][key]["inventory"],
                contribution["evidence_sources"][key]["inventory"]
            )
    return merged


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


def _publish_bundle(staged: Path, target: Path) -> None:
    if target.exists():
        if _tree_hashes(target) != _tree_hashes(staged):
            raise ValueError("BUNDLE_PATH_CONFLICT")
        return
    staged.replace(target)

def assemble_bundle(
    app_id: str,
    classification: dict[str, Any],
    rule_versions: dict[str, str],
    contributions: list[dict[str, Any]],
    normalization_config: dict[str, Any],
    profile_validation: dict[str, Any],
    phase_readiness: dict[str, Any],
    output_root: Path,
    schema_version: str = "2.7.3",
) -> dict[str, Any]:
    from adapters.base import validate_contribution

    for contribution in contributions:
        validate_contribution(contribution)
    _guard_no_binaries(contributions)

    adapters = sorted(
        {(c["adapter_id"], c["adapter_version"]) for c in contributions}
    )
    identity = {
        "app_id": app_id, "classification": classification,
        "classification_rule_versions": rule_versions,
        "artifacts": _logical_artifacts(contributions),
        "adapters": [{"id": a, "version": v} for a, v in adapters],
        "bundle_schema_version": schema_version, "normalization_config": normalization_config,
    }
    bundle_id = bundle_contract.compute_bundle_id(identity)
    merged = _merge_sections(contributions)
    worst = _worst_status(contributions)
    bundle_json = {
        "schema_version": schema_version, "bundle_id": bundle_id, "app_id": app_id,
        "classification": classification, "rule_versions": rule_versions,
        "status": worst,
        "content_roots": {"databases": "databases/", "code": "code/", "ui": "ui/", "interfaces": "interfaces/"},
        "evidence_sources": {
            "documents": {"inventory": "evidence-sources/documents/inventory.json"},
            "screenshots": {"inventory": "evidence-sources/screenshots/inventory.json"},
            "reports": {"inventory": "evidence-sources/reports/inventory.json"},
            "samples": {"inventory": "evidence-sources/samples/inventory.json"},
        },
    }
    provenance = _provenance(bundle_id, schema_version, contributions)
    output = Path(output_root).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    bundle_dir = output / bundle_id
    staged = Path(tempfile.mkdtemp(prefix=f".{bundle_id}.", dir=output))
    try:
        _write_layout(staged, merged, contributions, bundle_id, schema_version)
        _write_json(staged / "profile-validation.json", profile_validation)
        _write_json(staged / "phase-readiness.json", phase_readiness)
        _write_json(staged / "bundle.json", bundle_json)
        _write_json(staged / "provenance.json", provenance)
        _validate_json(staged / "provenance.json", "bundle-provenance.schema.json")
        _validate_json(staged / "coverage.json", "bundle-coverage.schema.json")
        _write_checksums(staged)
        bundle_contract.validate_bundle(staged)
        _publish_bundle(staged, bundle_dir)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
    return {"bundle_id": bundle_id, "bundle_dir": str(bundle_dir), "status": worst}

def _write_layout(
    bundle_dir: Path, merged: dict[str, Any], contributions: list[dict[str, Any]],
    bundle_id: str, schema_version: str,
) -> None:
    database_names = {
        "objects": "objects.json", "tables": "tables.json", "fields": "fields.json",
        "indexes": "indexes.json", "declared_relationships": "declared-relationships.json",
    }
    for key, name in database_names.items():
        _write_json(bundle_dir / "databases" / name, merged["databases"][key])
    for key, name in (("forms", "forms"), ("reports", "reports"), ("macros", "macros")):
        _write_json(bundle_dir / "ui" / name / "inventory.json", merged["ui"][key])
    for key, name in (("linked_tables", "linked-tables.json"), ("file_interfaces", "file-interfaces.json"), ("connections_redacted", "connections.redacted.json")):
        _write_json(bundle_dir / "interfaces" / name, merged["interfaces"][key])
    for key in ("documents", "screenshots", "reports", "samples"):
        _write_json(bundle_dir / "evidence-sources" / key / "inventory.json", merged["evidence_sources"][key]["inventory"])
    for key, folder in (("vba", "vba"), ("access_sql", "access-sql"), ("sql_server", "sql-server")):
        _write_text_records(bundle_dir / "code" / folder, merged["code"][key])
    failures = [failure for contribution in contributions for failure in contribution["failures"]]
    _write_json(bundle_dir / "failures" / "extraction-failures.json", failures)
    _write_json(bundle_dir / "coverage.json", _coverage(bundle_id, schema_version, merged, failures))

def _write_text_records(root: Path, records: list[dict[str, Any]]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    inventory: list[dict[str, Any]] = []
    for record in sorted(records, key=lambda item: item["logical_id"]):
        digest = hashlib.sha256(record["logical_id"].encode("utf-8")).hexdigest()[:16]
        relative = f"{digest}.txt"
        (root / relative).write_text(record.get("text", ""), encoding="utf-8", newline="\n")
        inventory.append({key: value for key, value in record.items() if key != "text"} | {"path": relative})
    _write_json(root / "inventory.json", inventory)

def _coverage(
    bundle_id: str, schema_version: str, merged: dict[str, Any], failures: list[dict[str, Any]],
) -> dict[str, Any]:
    def counts(extracted: int, failed: int = 0) -> dict[str, int]:
        return {"extracted": extracted, "skipped": 0, "failed": failed, "unsupported": 0}

    return {
        "schema_version": schema_version,
        "bundle_id": bundle_id,
        "object_types": {
            "database": counts(sum(len(values) for values in merged["databases"].values())),
            "code": counts(sum(len(values) for values in merged["code"].values())),
            "ui": counts(sum(len(values) for values in merged["ui"].values())),
            "interface": counts(sum(len(values) for values in merged["interfaces"].values())),
            "unclassified": counts(0, len(failures)),
        },
    }

def _provenance(
    bundle_id: str, schema_version: str, contributions: list[dict[str, Any]],
) -> dict[str, Any]:
    sources: list[dict[str, str]] = []
    for contribution in sorted(contributions, key=lambda item: item["adapter_id"]):
        producer = contribution["provenance"]["producer"]
        producer_version = contribution["provenance"].get("producer_version", contribution["adapter_version"])
        for logical_id, digest in sorted(contribution["provenance"]["source_hashes"].items()):
            sources.append({
                "logical_artifact_id": logical_id, "sha256": digest,
                "producer": producer, "producer_version": producer_version,
                "transformation": contribution["adapter_id"],
            })
    return {"schema_version": schema_version, "bundle_id": bundle_id, "sources": sources}

def _validate_json(path: Path, schema_name: str) -> None:
    schema_path = Path(__file__).resolve().parents[1] / "schemas" / schema_name
    jsonschema.validate(
        json.loads(path.read_text(encoding="utf-8")),
        json.loads(schema_path.read_text(encoding="utf-8")),
    )

_STATUS_RANK = {"VALID": 0, "PARTIAL": 1, "INVALID": 2, "BLOCKED": 3}

def _worst_status(contributions: list[dict[str, Any]]) -> str:
    return max((c["status"] for c in contributions), key=lambda s: _STATUS_RANK[s])

def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

def _write_checksums(bundle_dir: Path) -> None:
    lines: list[str] = []
    for path in sorted(bundle_dir.rglob("*")):
        if path.is_file() and path.name != "checksums.sha256":
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            relative = path.relative_to(bundle_dir).as_posix()
            lines.append(f"{digest}  {relative}")
    (bundle_dir / "checksums.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
