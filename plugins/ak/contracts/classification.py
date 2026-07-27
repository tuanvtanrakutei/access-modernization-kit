from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

TOPOLOGIES = {"monolith", "split_file", "client_server", "hybrid"}
FRONTEND_FORMATS = {"mdb", "accdb", "adp", "mde", "accde", "exported"}
SOURCE_AVAILABILITY = {"full", "compiled_only", "exported_only", "mixed"}
BACKEND_KINDS = {
    "embedded_access", "access_file", "sql_server", "odbc_database",
    "text_or_csv", "spreadsheet", "external_application", "unknown_boundary",
}


class ClassificationError(ValueError):
    pass


@dataclass(frozen=True)
class Classification:
    topology: str
    frontend_format: str
    source_availability: str
    backend_kinds: tuple[str, ...]

    def __post_init__(self) -> None:
        checks = (
            ("topology", self.topology, TOPOLOGIES),
            ("frontend_format", self.frontend_format, FRONTEND_FORMATS),
            ("source_availability", self.source_availability, SOURCE_AVAILABILITY),
        )
        for name, value, allowed in checks:
            if value not in allowed:
                raise ClassificationError(f"Invalid {name}: {value}")
        unknown = sorted(set(self.backend_kinds) - BACKEND_KINDS)
        if not self.backend_kinds or unknown:
            raise ClassificationError(f"Invalid backend_kinds: {unknown or 'empty'}")
        object.__setattr__(self, "backend_kinds", tuple(sorted(set(self.backend_kinds))))

    def as_dict(self) -> dict[str, Any]:
        return {
            "topology": self.topology,
            "frontend_format": self.frontend_format,
            "source_availability": self.source_availability,
            "backend_kinds": list(self.backend_kinds),
        }


@dataclass(frozen=True)
class ResolvedClassification:
    classification: Classification
    rule_ids: tuple[str, ...]
    rule_versions: dict[str, str]
    rules: tuple[dict[str, Any], ...]


def _rules(profiles_dir: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for name in ("topology.yaml", "frontend.yaml", "source-availability.yaml", "backend.yaml"):
        data = yaml.safe_load((profiles_dir / name).read_text(encoding="utf-8")) or {}
        result.extend(data.get("rules", []))
    return result


def _matches(rule: dict[str, Any], classification: Classification) -> bool:
    when = rule.get("when", {})
    for key, value in when.items():
        if key == "backend_kind":
            if value not in classification.backend_kinds:
                return False
        elif getattr(classification, key, None) != value:
            return False
    return True


def resolve_classification(
    classification: Classification, profiles_dir: Path
) -> ResolvedClassification:
    matched = tuple(sorted(
        (rule for rule in _rules(profiles_dir) if _matches(rule, classification)),
        key=lambda rule: rule["id"],
    ))
    return ResolvedClassification(
        classification=classification,
        rule_ids=tuple(rule["id"] for rule in matched),
        rule_versions={rule["id"]: str(rule["version"]) for rule in matched},
        rules=matched,
    )


ALIASES: dict[str, dict[str, set[str]]] = {
    "access-file-monolith": {
        "topology": {"monolith"}, "frontend_format": {"mdb", "accdb"},
        "source_availability": {"full", "exported_only"}, "backend_kinds": {"embedded_access"},
    },
    "access-file-split": {
        "topology": {"split_file"}, "frontend_format": {"mdb", "accdb", "mde", "accde"},
        "backend_kinds": {"access_file"},
    },
    "access-adp-sqlserver": {
        "topology": {"client_server"}, "frontend_format": {"adp"},
        "source_availability": {"full", "exported_only"}, "backend_kinds": {"sql_server"},
    },
    "access-compiled-frontend": {
        "frontend_format": {"mde", "accde"}, "source_availability": {"compiled_only"},
    },
}


def reconcile_alias(alias: str, classification: Classification) -> None:
    expected = ALIASES.get(alias)
    if expected is None:
        raise ClassificationError(f"Unknown profile alias: {alias}")
    values = classification.as_dict()
    for field, allowed in expected.items():
        actual = set(values[field]) if field == "backend_kinds" else {str(values[field])}
        if not actual.intersection(allowed):
            raise ClassificationError(
                f"Profile alias {alias} disagrees with classification field {field}"
            )
