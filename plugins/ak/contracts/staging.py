from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StagingDecision:
    destination: str
    reason: str


def _escapes(path: Path, staging_root: Path | None) -> bool:
    if staging_root is None:
        return ".." in path.parts
    root = staging_root.expanduser().resolve()
    candidate = path.expanduser().resolve() if path.is_absolute() else (root / path).resolve()
    try:
        candidate.relative_to(root)
        return False
    except ValueError:
        return True


def classify_incoming(
    path: Path,
    declared_kind: str | None,
    signature_ok: bool,
    staging_root: Path | None = None,
    *,
    provenance_ok: bool = True,
    artifact_conflict: bool = False,
    duplicate_mismatch: bool = False,
    undeclared_binary: bool = False,
    lossless_encoding: bool = True,
    profile_allowed: bool = True,
) -> StagingDecision:
    checks = (
        (_escapes(path, staging_root), "PATH_ESCAPE"),
        (not declared_kind, "UNKNOWN_TYPE"),
        (not signature_ok, "SIGNATURE_MISMATCH"),
        (artifact_conflict, "ARTIFACT_CONFLICT"),
        (duplicate_mismatch, "DUPLICATE_MISMATCH"),
        (undeclared_binary, "UNDECLARED_BINARY"),
        (not provenance_ok, "PROVENANCE_MISSING"),
        (not lossless_encoding, "LOSSY_ENCODING"),
        (not profile_allowed, "PROFILE_PROHIBITED"),
    )
    for failed, reason in checks:
        if failed:
            return StagingDecision("quarantine", reason)
    return StagingDecision("classified", "ACCEPTED")


def acceptance_state(
    mandatory_ok: bool,
    optional_missing: bool,
    violations: list[str],
    blocked: bool,
) -> str:
    if blocked:
        return "BLOCKED"
    if violations or not mandatory_ok:
        return "INVALID"
    return "PARTIAL" if optional_missing else "VALID"
