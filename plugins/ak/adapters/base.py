from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import jsonschema

_SCHEMAS = Path(__file__).resolve().parents[1] / "schemas"
_VALID_STATUS = frozenset({"VALID", "PARTIAL", "INVALID", "BLOCKED"})

BundleContribution = dict[str, Any]


@dataclass(frozen=True)
class AcquisitionRequest:
    app_id: str
    classification: dict[str, Any]
    artifacts: tuple[dict[str, Any], ...]
    source_root: Path
    authorization: frozenset[str] = frozenset()


@dataclass(frozen=True)
class CapabilityReport:
    adapter_id: str
    adapter_version: str
    can_acquire: bool
    missing: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class AcquisitionPlan:
    adapter_id: str
    adapter_version: str
    planned_artifacts: tuple[str, ...]
    authorization_required: tuple[str, ...] = ()
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    operations: tuple[dict[str, Any], ...] = ()
    app_id: str = ""
    acquisition_id: str = "acquire"
    granted_authorization: tuple[str, ...] = ()
    runtime_output_root: str = ""
    # Disposable copies. A sibling of staging rather than a child of it, because
    # staging is keyed by database id and the snapshot directory had to wear a
    # leading underscore to stay out of that namespace - a workaround that became
    # structure. Separate roots also make "delete after a clean run" obviously
    # safe: nothing inside the evidence is being removed.
    snapshot_root: str = ""
    keep_snapshots: bool = False


@dataclass(frozen=True)
class AcquisitionResult:
    app_id: str
    adapter_id: str
    adapter_version: str
    status: str
    records: tuple[dict[str, Any], ...]
    failures: tuple[dict[str, Any], ...]
    source_hashes: dict[str, str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in _VALID_STATUS:
            raise ValueError(f"Unknown acquisition status: {self.status}")


@runtime_checkable
class AcquisitionAdapter(Protocol):
    adapter_id: str
    adapter_version: str
    supported_profiles: tuple[str, ...]
    supported_artifact_kinds: tuple[str, ...]

    def probe(self, request: AcquisitionRequest) -> CapabilityReport: ...
    def plan(self, request: AcquisitionRequest) -> AcquisitionPlan: ...
    def acquire(self, plan: AcquisitionPlan) -> AcquisitionResult: ...
    def normalize(self, result: AcquisitionResult) -> BundleContribution: ...


def producer_version(sources: tuple[str, ...], package: Path | None = None) -> str:
    """A digest of the code that produces a contribution, for the bundle's identity.

    A45. `adapter_version` was a hand-written constant - `managed_access` had said
    "1.0.0" since it was written - and the bundle identity carries it as the only
    statement about what produced the evidence. So `scripts/extract_access.ps1` could
    change *what a bundle contains* with the bundle's address unmoved: A44 made the
    extractor read every saved import specification instead of only those a link
    pointed at, re-running the same two databases produced a bundle with different
    `imex-specs.json` and `coverage.json`, and publishing it was refused as
    `BUNDLE_PATH_CONFLICT` - a message that reads as tampering when the cause is the
    kit improving.

    This is A16 arriving on the acquisition side. A16 fixed it for assembly and its
    reasoning transfers whole: computed rather than declared, because a version somebody
    has to remember to bump is wrong exactly when it matters - the defect being fixed is
    always the one that changed the output. A comment-only edit also yields a new id and
    so a second directory, which is the cheaper mistake by a wide margin.

    The name is hashed beside the bytes, so renaming a member or reordering the tuple
    cannot produce the same digest. `package` is for the regression that proves every
    member is load-bearing.
    """
    root = Path(package) if package is not None else Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for relative in sources:
        digest.update(relative.encode("utf-8"))
        digest.update(hashlib.sha256((root / relative).read_bytes()).digest())
    return digest.hexdigest()[:12]


def empty_sections() -> dict[str, Any]:
    return {
        "databases": {"objects": [], "tables": [], "fields": [], "indexes": [], "declared_relationships": []},
        "code": {"vba": [], "access_sql": [], "sql_server": []},
        "ui": {"forms": [], "reports": [], "macros": []},
        "interfaces": {"linked_tables": [], "file_interfaces": [], "connections_redacted": [],
                       # The declared column layout of a text link. Only present
                       # when a link declares `DSN=`; backlog A17.
                       "imex_specs": []},
        "evidence_sources": {
            "documents": {"inventory": []}, "screenshots": {"inventory": []},
            "reports": {"inventory": []}, "samples": {"inventory": []},
        },
    }


def validate_contribution(contribution: BundleContribution) -> BundleContribution:
    schema = json.loads((_SCHEMAS / "bundle-contribution.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(contribution, schema)
    return contribution


def contribution_content_id(contribution: BundleContribution) -> str:
    payload = {key: value for key, value in contribution.items()}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "contribution-" + hashlib.sha256(encoded).hexdigest()
