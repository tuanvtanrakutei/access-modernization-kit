from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import jsonschema
import yaml

from classification import Classification, ClassificationError, reconcile_alias

_SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class SourceRef:
    type: str
    value: str


@dataclass(frozen=True)
class Artifact:
    id: str
    kind: str
    role: str
    acquisition: str
    required: bool
    source_ref: SourceRef
    format: str | None = None
    backend_kind: str | None = None


@dataclass(frozen=True)
class Manifest:
    version: str
    app: dict[str, Any]
    classification: Classification | None
    profile: str | None
    artifacts: tuple[Artifact, ...] = field(default_factory=tuple)


def _validate_schema(data: dict[str, Any], schema_name: str) -> None:
    try:
        schema = json.loads((_SCHEMAS / schema_name).read_text(encoding="utf-8"))
        jsonschema.validate(data, schema)
    except jsonschema.ValidationError as exc:
        raise ManifestError(str(exc.message)) from exc


def _build_artifact(raw: dict[str, Any]) -> Artifact:
    source_ref = SourceRef(**raw["source_ref"])
    if source_ref.type == "local_path":
        normalized = source_ref.value.replace("\\", "/")
        candidate = PurePosixPath(normalized)
        if candidate.is_absolute() or ".." in candidate.parts or (len(normalized) > 1 and normalized[1] == ":"):
            raise ManifestError(f"local_path must be relative: {source_ref.value}")
    return Artifact(
        id=raw["id"], kind=raw["kind"], role=raw["role"], acquisition=raw["acquisition"],
        required=bool(raw["required"]), source_ref=source_ref, format=raw.get("format"),
        backend_kind=raw.get("backend_kind"),
    )


def load_manifest(path: Path) -> Manifest:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ManifestError("Manifest root must be a mapping")
    version = str(data["version"])
    _validate_schema(data, "manifest.schema.json" if version == "2.1" else "manifest-v22.schema.json")
    if version == "2.1":
        return Manifest(version, data.get("app", {}), None, None)

    project = data["project"]
    raw = project["classification"]
    try:
        classification = Classification(
            raw["topology"], raw["frontend_format"], raw["source_availability"], tuple(raw["backend_kinds"])
        )
        if project.get("profile"):
            reconcile_alias(project["profile"], classification)
    except (KeyError, ClassificationError) as exc:
        raise ManifestError(f"Invalid classification: {exc}") from exc
    return Manifest(
        version, data.get("app", {}), classification, project.get("profile"),
        tuple(_build_artifact(item) for item in data.get("artifacts", [])),
    )
