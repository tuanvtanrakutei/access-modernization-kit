from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any

import jsonschema

PACKAGE = Path(__file__).resolve().parents[1]
CANONICAL_OUTPUT_MARKERS = tuple(f"_Phase{number}_" for number in range(1, 7))
FORBIDDEN_SUFFIXES = {
    ".mdb",
    ".accdb",
    ".adp",
    ".mde",
    ".accde",
    ".bak",
    ".mdf",
    ".ldf",
    ".dsn",
    ".env",
}


class CollaborationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def _schema(name: str) -> dict[str, Any]:
    return json.loads((PACKAGE / "schemas" / name).read_text(encoding="utf-8"))


def work_package_digest(value: dict[str, Any]) -> str:
    scoped = {key: item for key, item in value.items() if key != "created_at"}
    encoded = json.dumps(
        scoped, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_relative(path: str) -> None:
    normalized = path.replace("\\", "/")
    parsed = PurePosixPath(normalized)
    if (
        parsed.is_absolute()
        or PureWindowsPath(path).is_absolute()
        or re.match(r"^[A-Za-z]:/", normalized)
        or ".." in parsed.parts
        or not parsed.parts
    ):
        raise CollaborationError("COLLAB_PATH_ESCAPE", path)


def validate_work_package(value: dict[str, Any]) -> None:
    if "authority" not in value:
        raise CollaborationError("COLLAB_AUTHORITY_MISSING", "authority")
    try:
        jsonschema.validate(value, _schema("work-package.schema.json"))
    except jsonschema.ValidationError as exc:
        raise CollaborationError("COLLAB_PACKAGE_INVALID", exc.message) from exc

    paths = (
        value["input_paths"]
        + value["write_paths"]
        + [item["path"] for item in value["expected_artifacts"]]
    )
    for path in paths:
        _validate_relative(path)
        normalized = path.replace("\\", "/").lower()
        if (
            PurePosixPath(normalized).suffix in FORBIDDEN_SUFFIXES
            or normalized.startswith("secrets/")
            or "/secrets/" in normalized
        ):
            raise CollaborationError("COLLAB_SECRET_OR_BINARY_PROHIBITED", path)

    if value["publication_policy"] == "scoped_only":
        for path in value["write_paths"]:
            normalized = path.replace("\\", "/")
            if normalized.startswith("outputs/") and any(
                marker in normalized for marker in CANONICAL_OUTPUT_MARKERS
            ):
                raise CollaborationError("COLLAB_PUBLICATION_FORBIDDEN", path)


def load_work_package(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_work_package(value)
    return value