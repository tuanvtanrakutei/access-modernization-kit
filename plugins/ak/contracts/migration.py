from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def _artifact(
    artifact_id: str, kind: str, role: str, value: str,
    *, format: str | None = None, backend_kind: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": artifact_id, "kind": kind, "role": role, "acquisition": "imported",
        "required": False, "source_ref": {"type": "workspace_path", "value": value},
    }
    if format:
        result["format"] = format
    if backend_kind:
        result["backend_kind"] = backend_kind
    return result


def propose_migration(manifest_path: Path) -> dict[str, Any]:
    data = yaml.safe_load(Path(manifest_path).read_text(encoding="utf-8")) or {}
    if str(data.get("version")) != "2.1":
        raise ValueError("Migration source must be a V2.1 manifest")
    sources = data.get("sources", {}) or {}
    databases = sources.get("access_databases", []) or []
    artifacts: list[dict[str, Any]] = []
    ambiguous: list[str] = []

    for item in databases:
        role = "frontend" if len(databases) == 1 else "unknown"
        if role == "unknown":
            ambiguous.append(f"access_database_role:{item.get('database_id', 'unknown')}")
        artifacts.append(_artifact(
            item.get("database_id", f"ACCESS_{len(artifacts)+1}"), "access_database", role,
            item.get("path", ""), format=item.get("format"),
        ))

    path_groups = (
        ("vba_exports", "source_export", "frontend"),
        ("screenshots", "screenshot", "documentation"),
        ("reports", "report", "documentation"),
        ("sample_files", "sample", "documentation"),
        ("app_documents", "document", "documentation"),
    )
    for key, kind, role in path_groups:
        for index, value in enumerate(sources.get(key, []) or [], 1):
            artifacts.append(_artifact(f"LEGACY_{key.upper()}_{index}", kind, role, value))

    sql_paths = ((sources.get("sql_server", {}) or {}).get("exported_paths", []) or [])
    for index, value in enumerate(sql_paths, 1):
        artifacts.append(_artifact(
            f"LEGACY_SQL_{index}", "sql_server_schema", "backend", value,
            backend_kind="sql_server",
        ))

    formats = {item.get("format") for item in databases if item.get("format")}
    if "adp" in formats:
        topology, frontend = "client_server", "adp"
    elif len(databases) > 1:
        topology, frontend = "split_file", next(iter(formats), "mdb")
    elif len(databases) == 1:
        topology, frontend = "monolith", next(iter(formats), "mdb")
    else:
        topology, frontend = None, "exported"
        ambiguous.append("topology:no_access_database_declared")

    backend_kinds: list[str] = []
    if len(databases) > 1:
        backend_kinds.append("access_file")
    elif len(databases) == 1:
        backend_kinds.append("embedded_access")
    if sql_paths or "adp" in formats:
        backend_kinds.append("sql_server")
    if not backend_kinds:
        backend_kinds.append("unknown_boundary")

    missing: list[str] = []
    if not databases:
        missing.append("authoritative_access_project_or_validated_export")
    if "adp" in formats and not sql_paths:
        missing.append("sql_server_schema_evidence")

    return {
        "source_version": "2.1", "target_version": "2.2",
        "candidate_classification": {
            "topology": topology, "frontend_format": frontend,
            "source_availability": "full" if databases else "exported_only",
            "backend_kinds": sorted(set(backend_kinds)),
        },
        "mapped_artifacts": artifacts, "ambiguous_roles": sorted(set(ambiguous)),
        "missing_mandatory_inputs": missing, "quarantined_paths": [],
        "required_bundle_rebuild": True, "required_graphify_rebuild": True,
    }
