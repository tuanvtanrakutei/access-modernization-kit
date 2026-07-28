# Acquisition Adapters Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn declared V2.2 artifacts into one schema-equivalent Canonical Extraction Bundle contribution through independently testable acquisition adapters, so both managed Access extraction and imported/third-party sources feed the same downstream contract.

**Architecture:** Add a pure-Python adapter contract under `plugins/ak/adapters/`, a deterministic bundle-assembly contract under `plugins/ak/contracts/bundle_assembly.py`, and four adapters (managed Access, imported sources, msaccess-vcs importer, SQL Server importer). Each adapter only produces a typed `BundleContribution`; it never writes Phase outputs or Graphify inputs. `ak.py acquire plan|run` orchestrates adapters and emits an unapproved bundle that reuses the existing V2.7 `bundle.validate`/`bundle.approve` gate.

**Tech Stack:** Python 3.11, stdlib (`argparse`, `dataclasses`, `hashlib`, `json`, `pathlib`, `csv`), PyYAML, JSON Schema draft 2020-12 via `jsonschema`, pytest. Fixtures are synthetic only.

**Design Spec:** `docs/superpowers/specs/2026-07-23-profile-driven-extraction-bundle-design.md` sections 8-13, 22-24, 25.2, 25.4, 26.

---

## Boundaries

In scope: adapter contract dataclasses/protocol; deterministic bundle assembly into the section 13 layout; managed Access normalization from existing `extract_access.py` output; imported-source adapter (signature identification, manifest validation, collision/encoding checks); msaccess-vcs producer importer; SQL Server script/catalog/DACPAC-export importer with external-only BAK reference and MDF/LDF rejection; `ak acquire plan|run`; synthetic complete/incomplete fixtures; acquisition golden tests; `docs/acquisition/*` and CODEOWNERS updates; version bump to 2.7.1.

Out of scope: SQL/VBA deterministic analyzers, analysis model, Graphify input migration, Data Model/Data Dictionary generation, Refactoring Handoff (Plan 3); live Access COM automation changes beyond consuming existing extractor output; live SQL Server connections or backup restore automation; UCanAccess/Jackcess sidecar (V2.8).

## Compatibility Invariants

- Existing `manifest.schema.json` (V2.1) and `manifest-v22.schema.json` (V2.2) are unchanged.
- Existing script arguments and output shapes do not change; `extract_access.py` is consumed, not rewritten.
- `python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .` remains green.
- `python -m pytest -q` remains green (baseline: 48 passed on July 28, 2026).
- No real MDB/ACCDB/ADP/MDE/ACCDE/BAK/MDF/LDF, credentials, connection secrets, or production rows enter fixtures or Git.
- Adapter outputs are deterministic; absolute machine paths and timestamps never affect bundle identity or contribution content identity.
- Managed and imported acquisition produce the same `BundleContribution` schema (spec acceptance 3).

## Target Module Layout

Follows spec section 21.2. Create:
- `plugins/ak/adapters/__init__.py`
- `plugins/ak/adapters/base.py`
- `plugins/ak/adapters/managed_access/__init__.py`, `plugins/ak/adapters/managed_access/adapter.py`
- `plugins/ak/adapters/imported_sources/__init__.py`, `plugins/ak/adapters/imported_sources/adapter.py`
- `plugins/ak/adapters/msaccess_vcs/__init__.py`, `plugins/ak/adapters/msaccess_vcs/adapter.py`
- `plugins/ak/adapters/sql_server/__init__.py`, `plugins/ak/adapters/sql_server/adapter.py`
- `plugins/ak/contracts/bundle_assembly.py`
- `plugins/ak/schemas/bundle-contribution.schema.json`
- `plugins/ak/tests/conftest.py`
- `plugins/ak/tests/adapters/test_base.py`
- `plugins/ak/tests/adapters/test_managed_access.py`
- `plugins/ak/tests/adapters/test_imported_sources.py`
- `plugins/ak/tests/adapters/test_msaccess_vcs.py`
- `plugins/ak/tests/adapters/test_sql_server.py`
- `plugins/ak/tests/test_bundle_assembly.py`
- `plugins/ak/tests/test_cli_acquire.py`
- `plugins/ak/fixtures/acquisition/` synthetic producer inputs (managed-access-export, imported-loose, msaccess-vcs, sql-server-scripts)
- `docs/acquisition/{decision-guide,managed-access,imported-sources,sql-server}.md`

Modify:
- `plugins/ak/scripts/ak.py` (add `acquire` subcommand and dispatch)
- `plugins/ak/scripts/validate_structure.py` (count/validate new dirs and schema)
- `plugins/ak/specifications/package.json` and both `plugin.json` files (version -> 2.7.1)
- `.github/CODEOWNERS` (adapters ownership)
- `plugins/ak/skills/ak/SKILL.md` (document `$ak acquire`)

## Key Data Types (defined once, reused by every task)

`plugins/ak/adapters/base.py` defines these; later tasks import them and MUST NOT redefine:

- `AcquisitionRequest(app_id, classification, artifacts, source_root, authorization)` - frozen dataclass.
- `CapabilityReport(adapter_id, adapter_version, can_acquire, missing, notes)` - frozen dataclass.
- `AcquisitionPlan(adapter_id, adapter_version, planned_artifacts, authorization_required, reads, writes, operations, app_id, acquisition_id, granted_authorization, runtime_output_root)` - frozen dataclass; runtime fields never enter persisted identity.
- `AcquisitionResult(app_id, adapter_id, adapter_version, status, records, failures, source_hashes, metadata)` - frozen dataclass; `status` in `VALID/PARTIAL/INVALID/BLOCKED`.
- `BundleContribution` - the one downstream contract (dict validated by `bundle-contribution.schema.json`).
- `AcquisitionAdapter` - `typing.Protocol` with `probe/plan/acquire/normalize`.
- `contribution_content_id(contribution) -> str` - deterministic sha256 over normalized contribution minus volatile fields.

---

### Task 1: Adapter contract and bundle-contribution schema

**Files:**
- Create: `plugins/ak/adapters/__init__.py`
- Create: `plugins/ak/adapters/base.py`
- Create: `plugins/ak/schemas/bundle-contribution.schema.json`
- Create: `plugins/ak/tests/conftest.py`
- Test: `plugins/ak/tests/adapters/__init__.py`, `plugins/ak/tests/adapters/test_base.py`

- [ ] **Step 1: Add the shared test import path and write the failing test**

```python
# plugins/ak/tests/conftest.py
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
for path in (PACKAGE, PACKAGE / "contracts", PACKAGE / "scripts"):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
```

```python
# plugins/ak/tests/adapters/test_base.py
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from adapters.base import (
    AcquisitionResult,
    BundleContribution,
    contribution_content_id,
    validate_contribution,
)

PACKAGE = Path(__file__).resolve().parents[2]

def _contribution() -> BundleContribution:
    return {
        "adapter_id": "imported_sources",
        "adapter_version": "1.0.0",
        "app_id": "SYN",
        "status": "PARTIAL",
        "databases": {"objects": [], "tables": [], "fields": [], "indexes": [], "declared_relationships": []},
        "code": {"vba": [], "access_sql": [], "sql_server": []},
        "ui": {"forms": [], "reports": [], "macros": []},
        "interfaces": {"linked_tables": [], "file_interfaces": [], "connections_redacted": []},
        "evidence_sources": {
            "documents": {"inventory": []}, "screenshots": {"inventory": []},
            "reports": {"inventory": []}, "samples": {"inventory": []},
        },
        "failures": [],
        "provenance": {"producer": "manual", "source_hashes": {}},
    }

def test_contribution_matches_schema() -> None:
    schema = json.loads((PACKAGE / "schemas" / "bundle-contribution.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(_contribution(), schema)

def test_content_id_is_path_and_order_stable() -> None:
    first = _contribution()
    second = _contribution()
    second["provenance"]["source_hashes"] = {"b": "2" * 64, "a": "1" * 64}
    first["provenance"]["source_hashes"] = {"a": "1" * 64, "b": "2" * 64}
    assert contribution_content_id(first) == contribution_content_id(second)

def test_content_id_changes_with_status() -> None:
    baseline = _contribution()
    changed = _contribution()
    changed["status"] = "VALID"
    assert contribution_content_id(baseline) != contribution_content_id(changed)

def test_result_rejects_unknown_status() -> None:
    try:
        AcquisitionResult(app_id="SYN", adapter_id="x", adapter_version="1", status="DONE", records=(), failures=(), source_hashes={})
    except ValueError:
        return
    raise AssertionError("AcquisitionResult must reject unknown status")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest plugins/ak/tests/adapters/test_base.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'adapters'`

- [ ] **Step 3: Create the schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://sms.local/schemas/bundle-contribution.schema.json",
  "title": "Bundle Contribution",
  "type": "object",
  "additionalProperties": false,
  "required": ["adapter_id", "adapter_version", "app_id", "status", "databases", "code", "ui", "interfaces", "evidence_sources", "failures", "provenance"],
  "properties": {
    "adapter_id": {"type": "string", "minLength": 1},
    "adapter_version": {"type": "string", "minLength": 1},
    "app_id": {"type": "string", "minLength": 1},
    "status": {"enum": ["VALID", "PARTIAL", "INVALID", "BLOCKED"]},
    "databases": {
      "type": "object", "additionalProperties": false,
      "required": ["objects", "tables", "fields", "indexes", "declared_relationships"],
      "properties": {
        "objects": {"type": "array"}, "tables": {"type": "array"}, "fields": {"type": "array"},
        "indexes": {"type": "array"}, "declared_relationships": {"type": "array"}
      }
    },
    "code": {
      "type": "object", "additionalProperties": false,
      "required": ["vba", "access_sql", "sql_server"],
      "properties": {"vba": {"type": "array"}, "access_sql": {"type": "array"}, "sql_server": {"type": "array"}}
    },
    "ui": {
      "type": "object", "additionalProperties": false,
      "required": ["forms", "reports", "macros"],
      "properties": {"forms": {"type": "array"}, "reports": {"type": "array"}, "macros": {"type": "array"}}
    },
    "interfaces": {
      "type": "object", "additionalProperties": false,
      "required": ["linked_tables", "file_interfaces", "connections_redacted"],
      "properties": {"linked_tables": {"type": "array"}, "file_interfaces": {"type": "array"}, "connections_redacted": {"type": "array"}}
    },
    "evidence_sources": {
      "type": "object", "additionalProperties": false,
      "required": ["documents", "screenshots", "reports", "samples"],
      "properties": {
        "documents": {"$ref": "#/$defs/inventory"}, "screenshots": {"$ref": "#/$defs/inventory"},
        "reports": {"$ref": "#/$defs/inventory"}, "samples": {"$ref": "#/$defs/inventory"}
      }
    },
    "failures": {"type": "array", "items": {"type": "object", "required": ["logical_id", "reason"], "properties": {"logical_id": {"type": "string"}, "reason": {"type": "string"}}}},
    "provenance": {
      "type": "object", "additionalProperties": true, "required": ["producer", "source_hashes"],
      "properties": {"producer": {"type": "string"}, "source_hashes": {"type": "object", "additionalProperties": {"type": "string", "pattern": "^[a-f0-9]{64}$"}}}
    }
  },
  "$defs": {"inventory": {"type": "object", "required": ["inventory"], "properties": {"inventory": {"type": "array"}}, "additionalProperties": true}}
}
```

- [ ] **Step 4: Implement `adapters/__init__.py` and `adapters/base.py`**

```python
# plugins/ak/adapters/__init__.py
```

```python
# plugins/ak/adapters/base.py
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

def empty_sections() -> dict[str, Any]:
    return {
        "databases": {"objects": [], "tables": [], "fields": [], "indexes": [], "declared_relationships": []},
        "code": {"vba": [], "access_sql": [], "sql_server": []},
        "ui": {"forms": [], "reports": [], "macros": []},
        "interfaces": {"linked_tables": [], "file_interfaces": [], "connections_redacted": []},
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest plugins/ak/tests/adapters/test_base.py -v`
Expected: PASS (4 tests). Note: `json.dumps(sort_keys=True)` makes `source_hashes` order-independent, satisfying `test_content_id_is_path_and_order_stable`.

- [ ] **Step 6: Commit**

```bash
git add plugins/ak/adapters/__init__.py plugins/ak/adapters/base.py plugins/ak/schemas/bundle-contribution.schema.json plugins/ak/tests/conftest.py plugins/ak/tests/adapters/__init__.py plugins/ak/tests/adapters/test_base.py
git commit -m "feat(ak): add acquisition adapter contract and bundle-contribution schema"
```

---

### Task 2: Deterministic bundle assembly

**Files:**
- Create: `plugins/ak/contracts/bundle_assembly.py`
- Test: `plugins/ak/tests/test_bundle_assembly.py`

**Context:** Assembly merges one or more validated `BundleContribution` objects into the section 13 on-disk layout, computes the bundle ID via the existing `contracts/bundle.py::compute_bundle_id`, writes `checksums.sha256`, and refuses forbidden binaries. It never approves; approval stays with the existing `bundle approve` gate.

- [ ] **Step 1: Write the failing test**

```python
# plugins/ak/tests/test_bundle_assembly.py
from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(PACKAGE / "contracts"))

from adapters.base import empty_sections  # noqa: E402
from bundle_assembly import assemble_bundle  # noqa: E402
import bundle as bundle_contract  # noqa: E402

def _contribution(adapter_id: str) -> dict:
    sections = empty_sections()
    sections["code"]["access_sql"].append({"logical_id": "q1", "text": "SELECT 1", "sha256": "a" * 64})
    return {
        "adapter_id": adapter_id, "adapter_version": "1.0.0", "app_id": "SYN", "status": "PARTIAL",
        **sections, "failures": [], "provenance": {"producer": adapter_id, "source_hashes": {"q1": "a" * 64}},
    }

def _classification() -> dict:
    return {"topology": "monolith", "frontend_format": "mdb", "source_availability": "exported_only", "backend_kinds": ["embedded_access"]}

def test_assemble_writes_layout_and_lock(tmp_path: Path) -> None:
    out = assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=[_contribution("imported_sources")], normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path,
    )
    bundle_dir = Path(out["bundle_dir"])
    assert (bundle_dir / "bundle.json").is_file()
    assert (bundle_dir / "checksums.sha256").is_file()
    assert (bundle_dir / "provenance.json").is_file()
    assert (bundle_dir / "profile-validation.json").is_file()
    assert (bundle_dir / "phase-readiness.json").is_file()
    assert (bundle_dir / "coverage.json").is_file()
    assert (bundle_dir / "code" / "access-sql" / "inventory.json").is_file()
    assert (bundle_dir / "databases" / "tables.json").is_file()
    assert (bundle_dir / "evidence-sources" / "documents" / "inventory.json").is_file()
    assert (bundle_dir / "failures" / "extraction-failures.json").is_file()
    data = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    assert data["bundle_id"] == out["bundle_id"]
    assert data["bundle_id"].startswith("bundle-")
    # Reuses canonical identity from contracts/bundle.py
    assert data["bundle_id"] == bundle_contract.compute_bundle_id({
        "app_id": "SYN", "classification": _classification(),
        "classification_rule_versions": {"topology": "1.0.0"},
        "artifacts": [{"logical_id": "q1", "content_sha256": "a" * 64}],
        "adapters": [{"id": "imported_sources", "version": "1.0.0"}],
        "bundle_schema_version": data["schema_version"], "normalization_config": {"text": "utf-8-lf"},
    })
    for output_name, schema_name in (
        ("provenance.json", "bundle-provenance.schema.json"),
        ("coverage.json", "bundle-coverage.schema.json"),
    ):
        output = json.loads((bundle_dir / output_name).read_text(encoding="utf-8"))
        schema = json.loads((PACKAGE / "schemas" / schema_name).read_text(encoding="utf-8"))
        jsonschema.validate(output, schema)
    assert bundle_contract.validate_bundle(bundle_dir)["bundle_id"] == out["bundle_id"]

def test_assemble_is_deterministic_across_paths(tmp_path: Path) -> None:
    first = assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=[_contribution("imported_sources")], normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path / "a",
    )
    second = assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=[_contribution("imported_sources")], normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path / "b",
    )
    assert first["bundle_id"] == second["bundle_id"]

def test_assemble_rejects_forbidden_binary(tmp_path: Path) -> None:
    bad = _contribution("managed_access")
    bad["databases"]["objects"].append({"logical_id": "db", "raw_path": "legacy.mdb", "raw_binary": True})
    try:
        assemble_bundle(
            app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
            contributions=[bad], normalization_config={"text": "utf-8-lf"},
            profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "BLOCKED"}},
            output_root=tmp_path,
        )
    except ValueError:
        return
    raise AssertionError("assembly must reject raw binary contributions")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest plugins/ak/tests/test_bundle_assembly.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'bundle_assembly'`

- [ ] **Step 3: Implement `contracts/bundle_assembly.py`**

```python
# plugins/ak/contracts/bundle_assembly.py
from __future__ import annotations

import hashlib
import json
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
            artifacts[logical_id] = digest
    return [{"logical_id": key, "content_sha256": artifacts[key]} for key in sorted(artifacts)]

def _merge_sections(contributions: list[dict[str, Any]]) -> dict[str, Any]:
    from adapters.base import empty_sections

    merged = empty_sections()
    for contribution in sorted(contributions, key=lambda item: item["adapter_id"]):
        for group in ("databases", "code", "ui", "interfaces"):
            for key, values in contribution[group].items():
                merged[group][key].extend(values)
        for key in ("documents", "screenshots", "reports", "samples"):
            merged["evidence_sources"][key]["inventory"].extend(
                contribution["evidence_sources"][key]["inventory"]
            )
    return merged

def assemble_bundle(
    app_id: str,
    classification: dict[str, Any],
    rule_versions: dict[str, str],
    contributions: list[dict[str, Any]],
    normalization_config: dict[str, Any],
    profile_validation: dict[str, Any],
    phase_readiness: dict[str, Any],
    output_root: Path,
    schema_version: str = "2.7.1",
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
    bundle_dir = Path(output_root).expanduser().resolve() / bundle_id
    merged = _merge_sections(contributions)
    _write_layout(bundle_dir, merged, contributions, bundle_id, schema_version)
    _write_json(bundle_dir / "profile-validation.json", profile_validation)
    _write_json(bundle_dir / "phase-readiness.json", phase_readiness)

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
    _write_json(bundle_dir / "bundle.json", bundle_json)
    _write_json(bundle_dir / "provenance.json", provenance)
    _validate_json(bundle_dir / "provenance.json", "bundle-provenance.schema.json")
    _validate_json(bundle_dir / "coverage.json", "bundle-coverage.schema.json")
    _write_checksums(bundle_dir)
    bundle_contract.validate_bundle(bundle_dir)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest plugins/ak/tests/test_bundle_assembly.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add plugins/ak/contracts/bundle_assembly.py plugins/ak/tests/test_bundle_assembly.py
git commit -m "feat(ak): assemble deterministic canonical bundle from contributions"
```

---

### Task 3: Imported-source adapter and strict import manifest

**Files:**
- Create: `plugins/ak/adapters/imported_sources/__init__.py`
- Create: `plugins/ak/adapters/imported_sources/adapter.py`
- Create: `plugins/ak/schemas/import-source-manifest.schema.json`
- Create: `plugins/ak/fixtures/acquisition/imported-loose/complete/import-source-manifest.yaml`
- Create: `plugins/ak/fixtures/acquisition/imported-loose/complete/modules/Order.bas`
- Create: `plugins/ak/fixtures/acquisition/imported-loose/incomplete/Order.bas`
- Test: `plugins/ak/tests/adapters/test_imported_sources.py`

**Rules:**
- A V2.2 artifact that points to one declared file can be accepted from its manifest declaration.
- A directory or ZIP package requires `import-source-manifest.yaml` inside the declared root/package.
- Loose directory contents without that manifest are classified into a proposal report only and remain `INVALID`; they never silently enter a bundle.
- Text conversion is strict. BOM/UTF-8 or explicitly declared `cp932` are supported. Ambiguous or lossy decoding is quarantined.
- ZIP is the only packaged format in Plan 2. TAR and installer formats remain unsupported until they receive equivalent traversal/link/bomb defenses.
- Original PDFs/images/Office files remain external; the contribution contains only inventory, hash, media type, logical ID, and redacted external reference.

- [ ] **Step 1: Write failing tests for confinement, encoding, and loose-source rejection**

```python
# plugins/ak/tests/adapters/test_imported_sources.py
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest plugins/ak/tests/adapters/test_imported_sources.py -v`
Expected: FAIL because `adapters.imported_sources` does not exist.

- [ ] **Step 3: Add the strict import-manifest schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://sms.local/schemas/import-source-manifest.schema.json",
  "title": "Imported Source Package Manifest",
  "type": "object",
  "additionalProperties": false,
  "required": ["version", "producer", "files"],
  "properties": {
    "version": {"const": "1.0"},
    "producer": {
      "type": "object", "additionalProperties": false,
      "required": ["id", "version"],
      "properties": {"id": {"type": "string", "minLength": 1}, "version": {"type": "string", "minLength": 1}}
    },
    "files": {
      "type": "array", "minItems": 1,
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["logical_id", "path", "kind", "role", "sha256"],
        "properties": {
          "logical_id": {"type": "string", "minLength": 1},
          "path": {"type": "string", "minLength": 1},
          "kind": {"enum": ["vba", "access_sql", "sql_server", "form", "report", "macro", "document", "screenshot", "sample", "metadata"]},
          "role": {"type": "string", "minLength": 1},
          "sha256": {"type": "string", "pattern": "^[a-f0-9]{64}$"},
          "encoding": {"enum": ["utf-8", "utf-8-sig", "utf-16-le", "utf-16-be", "cp932"]},
          "media_type": {"type": "string"},
          "object_name": {"type": "string"}
        }
      }
    }
  }
}
```

- [ ] **Step 4: Implement strict decoding, signature checks, and archive guards**

```python
# plugins/ak/adapters/imported_sources/adapter.py (helpers)
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

def load_import_manifest(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    schema_path = Path(__file__).resolve().parents[2] / "schemas" / "import-source-manifest.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)
    return data
```

- [ ] **Step 5: Implement `ImportedSourcesAdapter`**

```python
# plugins/ak/adapters/imported_sources/adapter.py (append)
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
                manifest = source / "import-source-manifest.yaml" if source.is_dir() else None
                if manifest is None or not manifest.is_file():
                    failures.append({"logical_id": artifact["id"], "reason": "IMPORT_MANIFEST_REQUIRED"})
                    continue
                for item in load_import_manifest(manifest)["files"]:
                    path = confined(source, item["path"])
                    raw = path.read_bytes()
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
```

The `AcquisitionPlan` dataclass from Task 1 must include `operations: tuple[dict[str, Any], ...] = ()`; add it before running this task. The plan JSON serializer introduced in Task 7 serializes these operations after removing absolute source paths from persisted identity.

- [ ] **Step 6: Add complete/incomplete synthetic fixtures**

`complete/import-source-manifest.yaml` must list the invented `modules/Order.bas` file with its computed SHA-256 and `encoding: utf-8`. `incomplete/` intentionally omits the package manifest. Do not include Access binaries or real object names.

- [ ] **Step 7: Run tests**

Run: `python -m pytest plugins/ak/tests/adapters/test_imported_sources.py -v`
Expected: PASS (7 tests)

- [ ] **Step 8: Commit**

```bash
git add plugins/ak/adapters/imported_sources plugins/ak/schemas/import-source-manifest.schema.json plugins/ak/fixtures/acquisition/imported-loose plugins/ak/tests/adapters/test_imported_sources.py plugins/ak/adapters/base.py
git commit -m "feat(ak): add strict imported-source acquisition adapter"
```

---

### Task 4: Managed Access adapter over the existing snapshot extractor

**Files:**
- Create: `plugins/ak/adapters/managed_access/__init__.py`
- Create: `plugins/ak/adapters/managed_access/adapter.py`
- Create: `plugins/ak/fixtures/acquisition/managed-access-export/complete/access-extraction.json`
- Create: `plugins/ak/fixtures/acquisition/managed-access-export/incomplete/access-extraction.json`
- Test: `plugins/ak/tests/adapters/test_managed_access.py`

**Safety contract:** `probe` and `plan` never open Access. `acquire` delegates to `scripts/extract_access.py --execute`, which creates and verifies a snapshot before COM automation. The adapter never invokes `extract_access.ps1` directly and never changes the original MDB/ACCDB/ADP.

- [ ] **Step 1: Write the failing tests**

```python
# plugins/ak/tests/adapters/test_managed_access.py
from __future__ import annotations

import json
from pathlib import Path

from adapters.base import AcquisitionRequest, AcquisitionResult
from adapters.managed_access.adapter import ManagedAccessAdapter

CLASSIFICATION = {
    "topology": "split_file", "frontend_format": "mdb",
    "source_availability": "full", "backend_kinds": ["access_file"],
}

def test_plan_requires_explicit_snapshot_authorization(tmp_path: Path) -> None:
    db = tmp_path / "frontend.mdb"
    db.write_bytes(b"synthetic-signature-only")
    request = AcquisitionRequest(
        "SYN", CLASSIFICATION,
        ({"id": "FRONTEND", "kind": "access_database", "role": "frontend", "acquisition": "managed", "required": True, "source_ref": {"type": "local_path", "value": "frontend.mdb"}, "format": "mdb"},),
        tmp_path,
    )
    plan = ManagedAccessAdapter().plan(request)
    assert plan.authorization_required == ("access_snapshot_extract",)
    assert "--execute" not in " ".join(plan.reads)

def test_normalize_maps_access_components() -> None:
    result = AcquisitionResult(
        app_id="SYN", adapter_id="managed_access", adapter_version="1.0.0", status="PARTIAL",
        records=({"database_id": "FRONTEND", "components": [
            {"type": "vba_module", "name": "Order", "text": "Option Explicit"},
            {"type": "query", "name": "qOrder", "sql": "SELECT 1"},
            {"type": "form", "name": "F_Order", "text": "Version =20"},
        ], "project_context": {}, "warnings": ["protected object"]},),
        failures=(), source_hashes={"FRONTEND": "a" * 64},
    )
    contribution = ManagedAccessAdapter().normalize(result)
    assert contribution["app_id"] == "SYN"
    assert len(contribution["code"]["vba"]) == 1
    assert len(contribution["code"]["access_sql"]) == 1
    assert len(contribution["ui"]["forms"]) == 1
    assert contribution["status"] == "PARTIAL"

def test_normalize_never_carries_snapshot_path() -> None:
    fixture = Path(__file__).resolve().parents[2] / "fixtures" / "acquisition" / "managed-access-export" / "complete" / "access-extraction.json"
    data = json.loads(fixture.read_text(encoding="utf-8"))
    result = ManagedAccessAdapter().result_from_extraction("SYN", data)
    rendered = json.dumps(ManagedAccessAdapter().normalize(result))
    assert "snapshot" not in rendered.lower()
    assert ".mdb" not in rendered.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest plugins/ak/tests/adapters/test_managed_access.py -v`
Expected: FAIL because the managed Access adapter does not exist.

- [ ] **Step 3: Implement the adapter**

```python
# plugins/ak/adapters/managed_access/adapter.py
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from adapters.base import (
    AcquisitionPlan, AcquisitionRequest, AcquisitionResult, BundleContribution,
    CapabilityReport, empty_sections, validate_contribution,
)

PACKAGE = Path(__file__).resolve().parents[2]
ADAPTER_ID = "managed_access"
ADAPTER_VERSION = "1.0.0"

class ManagedAccessAdapter:
    adapter_id = ADAPTER_ID
    adapter_version = ADAPTER_VERSION
    supported_profiles = ("monolith", "split_file", "client_server", "hybrid")
    supported_artifact_kinds = ("access_database",)

    def probe(self, request: AcquisitionRequest) -> CapabilityReport:
        from scripts.access_runtime import inspect_access_runtime

        report = inspect_access_runtime(smoke_test=False)
        missing = () if report.get("status") == "READY" else (str(report.get("status")),)
        return CapabilityReport(self.adapter_id, self.adapter_version, not missing, missing, ("probe_is_read_only",))

    def plan(self, request: AcquisitionRequest) -> AcquisitionPlan:
        operations = tuple({
            "artifact": artifact,
            "source": str((request.source_root / artifact["source_ref"]["value"]).resolve()),
            "output_subdir": artifact["id"],
        } for artifact in request.artifacts)
        return AcquisitionPlan(
            self.adapter_id, self.adapter_version,
            tuple(item["artifact"]["id"] for item in operations),
            authorization_required=("access_snapshot_extract",),
            reads=tuple(item["source"] for item in operations),
            writes=("staging/access/",), operations=operations, app_id=request.app_id,
        )

    def acquire(self, plan: AcquisitionPlan) -> AcquisitionResult:
        if "access_snapshot_extract" not in plan.granted_authorization:
            return AcquisitionResult(plan.app_id, self.adapter_id, self.adapter_version, "BLOCKED", (), ({"logical_id": "*", "reason": "AUTHORIZATION_REQUIRED"},), {})
        records: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        hashes: dict[str, str] = {}
        for operation in plan.operations:
            artifact = operation["artifact"]
            command = [
                sys.executable, str(PACKAGE / "scripts" / "extract_access.py"),
                "--database", operation["source"], "--database-id", artifact["id"],
                "--output-dir", plan.runtime_output_root, "--session-id", plan.acquisition_id,
                "--execute",
            ]
            completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
            extraction = _find_extraction(Path(plan.runtime_output_root), artifact["id"], plan.acquisition_id)
            if not extraction.is_file():
                failures.append({"logical_id": artifact["id"], "reason": "EXTRACTION_RESULT_MISSING", "returncode": completed.returncode})
                continue
            data = json.loads(extraction.read_text(encoding="utf-8"))
            records.append(data)
            hashes[artifact["id"]] = data["source"]["sha256"]
        status = "BLOCKED" if failures and not records else ("PARTIAL" if failures or any(r["status"] == "PARTIAL" for r in records) else "VALID")
        return AcquisitionResult(plan.app_id, self.adapter_id, self.adapter_version, status, tuple(records), tuple(failures), hashes)

    def result_from_extraction(self, app_id: str, data: dict[str, Any]) -> AcquisitionResult:
        status = "VALID" if data["status"] == "EXTRACTED" else ("PARTIAL" if data["status"] == "PARTIAL" else "BLOCKED")
        return AcquisitionResult(app_id, self.adapter_id, self.adapter_version, status, (data,), (), {data["database_id"]: data["source"]["sha256"]})

    def normalize(self, result: AcquisitionResult) -> BundleContribution:
        sections = empty_sections()
        failures = list(result.failures)
        for extraction in result.records:
            for component in extraction.get("components", []):
                _route_component(sections, extraction["database_id"], component)
            failures.extend({"logical_id": extraction["database_id"], "reason": warning} for warning in extraction.get("warnings", []))
        contribution = {
            "adapter_id": self.adapter_id, "adapter_version": self.adapter_version, "app_id": result.app_id,
            "status": result.status, **sections, "failures": failures,
            "provenance": {"producer": "ak-managed-access", "source_hashes": dict(sorted(result.source_hashes.items()))},
        }
        return validate_contribution(contribution)

def _find_extraction(root: Path, database_id: str, acquisition_id: str) -> Path:
    return root / database_id / acquisition_id / "access-extraction.json"

def _route_component(sections: dict[str, Any], database_id: str, component: dict[str, Any]) -> None:
    record = {"database_id": database_id, **{k: v for k, v in component.items() if k not in {"path", "source_path", "snapshot_path"}}}
    kind = str(component.get("type", component.get("object_type", "object"))).lower()
    if "vba" in kind or kind == "module": sections["code"]["vba"].append(record)
    elif "query" in kind: sections["code"]["access_sql"].append(record)
    elif kind == "form": sections["ui"]["forms"].append(record)
    elif kind == "report": sections["ui"]["reports"].append(record)
    elif kind == "macro": sections["ui"]["macros"].append(record)
    elif "linked" in kind: sections["interfaces"]["linked_tables"].append(record)
    else: sections["databases"]["objects"].append(record)
```

Task 1's `AcquisitionPlan` must carry `app_id`, `acquisition_id`, `operations`, `granted_authorization`, and `runtime_output_root`; they are runtime fields and are excluded from persisted bundle identity. Task 1's `AcquisitionResult` must carry `app_id` as its first field.

- [ ] **Step 4: Add synthetic extraction fixtures**

The complete fixture uses invented component names and a fake SHA-256; the incomplete fixture sets `status: PARTIAL` with one protected-object warning. Neither fixture contains a database binary or a real filesystem path.

- [ ] **Step 5: Run tests**

Run: `python -m pytest plugins/ak/tests/adapters/test_managed_access.py plugins/ak/tests/test_package_smoke.py -v`
Expected: PASS; existing extractor tests remain unchanged.

- [ ] **Step 6: Commit**

```bash
git add plugins/ak/adapters/managed_access plugins/ak/fixtures/acquisition/managed-access-export plugins/ak/tests/adapters/test_managed_access.py plugins/ak/adapters/base.py
git commit -m "feat(ak): adapt snapshot Access extraction to bundle contributions"
```

---

### Task 5: msaccess-vcs external producer importer

**Files:**
- Create: `plugins/ak/adapters/msaccess_vcs/__init__.py`
- Create: `plugins/ak/adapters/msaccess_vcs/adapter.py`
- Create: `plugins/ak/fixtures/acquisition/msaccess-vcs/complete/app.src/vcs-options.json`
- Create: synthetic files under `plugins/ak/fixtures/acquisition/msaccess-vcs/complete/app.src/{modules,forms,reports,queries,macros,tbldefs}/`
- Create: `plugins/ak/fixtures/acquisition/msaccess-vcs/incomplete/app.src/vcs-options.json`
- Test: `plugins/ak/tests/adapters/test_msaccess_vcs.py`

**Producer contract:** Detect `vcs-options.json`, read `Options.ExportFormatVersion`, support `4.1.2` and `5.0.0`, record `Info.AddinVersion`, ignore/quarantine `vcs-index.idx`, preserve recursive `@Folder` directory structure, accept both legacy overloaded `.bas` and 5.0.0 descriptive `.form/.report/.qdef/.macro` extensions. Do not vendor producer code.

- [ ] **Step 1: Write the failing tests**

```python
# plugins/ak/tests/adapters/test_msaccess_vcs.py
from pathlib import Path

from adapters.base import AcquisitionRequest
from adapters.msaccess_vcs.adapter import MsAccessVcsAdapter

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "acquisition" / "msaccess-vcs"
CLASSIFICATION = {"topology": "monolith", "frontend_format": "exported", "source_availability": "exported_only", "backend_kinds": ["embedded_access"]}

def _request(root: Path) -> AcquisitionRequest:
    return AcquisitionRequest("SYN", CLASSIFICATION, ({
        "id": "VCS_EXPORT", "kind": "producer_export", "role": "frontend", "acquisition": "imported", "required": True,
        "source_ref": {"type": "local_path", "value": "app.src"}, "format": "msaccess-vcs",
    },), root)

def test_v500_descriptive_extensions_are_mapped() -> None:
    adapter = MsAccessVcsAdapter()
    plan = adapter.plan(_request(FIXTURE / "complete"))
    result = adapter.acquire(plan)
    contribution = adapter.normalize(result)
    assert contribution["provenance"]["producer"] == "msaccess-vcs-addin"
    assert contribution["provenance"]["producer_format_version"] == "5.0.0"
    assert contribution["code"]["vba"]
    assert contribution["ui"]["forms"]
    assert contribution["code"]["access_sql"]
    assert "vcs-index.idx" not in str(contribution)

def test_unsupported_format_is_invalid() -> None:
    adapter = MsAccessVcsAdapter()
    result = adapter.acquire(adapter.plan(_request(FIXTURE / "incomplete")))
    assert result.status == "INVALID"
    assert result.failures[0]["reason"] == "UNSUPPORTED_PRODUCER_FORMAT"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest plugins/ak/tests/adapters/test_msaccess_vcs.py -v`
Expected: FAIL because the producer adapter does not exist.

- [ ] **Step 3: Implement producer detection and mapping**

```python
# plugins/ak/adapters/msaccess_vcs/adapter.py
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from adapters.base import AcquisitionPlan, AcquisitionRequest, AcquisitionResult, CapabilityReport
from adapters.imported_sources.adapter import decode_text

SUPPORTED_FORMATS = frozenset({"4.1.2", "5.0.0"})
MAPPING = {
    ".form": "form", ".report": "report", ".qdef": "access_sql", ".macro": "macro",
    ".cls": "vba", ".bas": "legacy_or_vba", ".sql": "access_sql", ".json": "metadata",
}

class MsAccessVcsAdapter:
    adapter_id = "msaccess_vcs"
    adapter_version = "1.0.0"
    supported_profiles = ("*",)
    supported_artifact_kinds = ("producer_export",)

    def probe(self, request: AcquisitionRequest) -> CapabilityReport:
        roots = tuple((request.source_root / a["source_ref"]["value"]).resolve() for a in request.artifacts)
        missing = tuple(str(root) for root in roots if not (root / "vcs-options.json").is_file())
        return CapabilityReport(self.adapter_id, self.adapter_version, not missing, missing)

    def plan(self, request: AcquisitionRequest) -> AcquisitionPlan:
        operations = tuple({"artifact": a, "source": str((request.source_root / a["source_ref"]["value"]).resolve())} for a in request.artifacts)
        return AcquisitionPlan(self.adapter_id, self.adapter_version, tuple(a["id"] for a in request.artifacts), reads=tuple(o["source"] for o in operations), operations=operations, app_id=request.app_id)

    def acquire(self, plan: AcquisitionPlan) -> AcquisitionResult:
        records: list[dict[str, Any]] = []
        failures: list[dict[str, Any]] = []
        hashes: dict[str, str] = {}
        producer_version = "unknown"
        addin_version = "unknown"
        for operation in plan.operations:
            root = Path(operation["source"])
            options = json.loads((root / "vcs-options.json").read_text(encoding="utf-8"))
            producer_version = str(options.get("Options", {}).get("ExportFormatVersion", "unknown"))
            addin_version = str(options.get("Info", {}).get("AddinVersion", "unknown"))
            if producer_version not in SUPPORTED_FORMATS:
                failures.append({"logical_id": operation["artifact"]["id"], "reason": "UNSUPPORTED_PRODUCER_FORMAT", "version": producer_version})
                continue
            for path in sorted(root.rglob("*")):
                if not path.is_file() or path.name in {"vcs-options.json", "vcs-index.idx"}:
                    continue
                kind = _kind(root, path, producer_version)
                if kind is None:
                    continue
                raw = path.read_bytes()
                text, encoding = decode_text(raw, "utf-8")
                logical_id = path.relative_to(root).as_posix()
                digest = hashlib.sha256(raw).hexdigest()
                hashes[logical_id] = digest
                records.append({"logical_id": logical_id, "kind": kind, "text": text.replace("\r\n", "\n"), "source_encoding": encoding, "sha256": digest})
        status = "INVALID" if failures else "VALID"
        metadata = {"producer_format_version": producer_version, "producer_version": addin_version}
        return AcquisitionResult(plan.app_id, self.adapter_id, self.adapter_version, status, tuple(records), tuple(failures), hashes, metadata=metadata)

    def normalize(self, result: AcquisitionResult) -> dict[str, Any]:
        from adapters.base import empty_sections, validate_contribution
        sections = empty_sections()
        for record in result.records:
            target = record["kind"]
            if target == "vba": sections["code"]["vba"].append(record)
            elif target == "access_sql": sections["code"]["access_sql"].append(record)
            elif target == "form": sections["ui"]["forms"].append(record)
            elif target == "report": sections["ui"]["reports"].append(record)
            elif target == "macro": sections["ui"]["macros"].append(record)
            else: sections["databases"]["objects"].append(record)
        return validate_contribution({
            "adapter_id": self.adapter_id, "adapter_version": self.adapter_version, "app_id": result.app_id,
            "status": result.status, **sections, "failures": list(result.failures),
            "provenance": {"producer": "msaccess-vcs-addin", "source_hashes": dict(sorted(result.source_hashes.items())), **result.metadata},
        })

def _kind(root: Path, path: Path, producer_version: str) -> str | None:
    suffix = path.suffix.lower()
    if suffix != ".bas":
        return MAPPING.get(suffix)
    top = path.relative_to(root).parts[0].lower()
    return {"forms": "form", "reports": "report", "queries": "access_sql", "macros": "macro"}.get(top, "vba")
```

Task 1's `AcquisitionResult` adds `metadata: dict[str, Any] = field(default_factory=dict)`.

- [ ] **Step 4: Add synthetic 5.0.0 and unsupported fixtures**

The complete fixture uses `Info.AddinVersion: 5.0.1`, `Options.ExportFormatVersion: 5.0.0`, descriptive extensions, and invented object names. The incomplete fixture uses `ExportFormatVersion: 9.9.9`. Add a synthetic `vcs-index.idx` placeholder and assert it never enters output.

- [ ] **Step 5: Run tests**

Run: `python -m pytest plugins/ak/tests/adapters/test_msaccess_vcs.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add plugins/ak/adapters/msaccess_vcs plugins/ak/fixtures/acquisition/msaccess-vcs plugins/ak/tests/adapters/test_msaccess_vcs.py plugins/ak/adapters/base.py
git commit -m "feat(ak): import supported msaccess-vcs producer exports"
```

---

### Task 6: SQL Server evidence importer

**Files:**
- Create: `plugins/ak/adapters/sql_server/__init__.py`
- Create: `plugins/ak/adapters/sql_server/adapter.py`
- Create: `plugins/ak/schemas/sql-server-catalog.schema.json`
- Create: `plugins/ak/fixtures/acquisition/sql-server-scripts/complete/schema.sql`
- Create: `plugins/ak/fixtures/acquisition/sql-server-scripts/complete/catalog.json`
- Create: `plugins/ak/fixtures/acquisition/sql-server-scripts/incomplete/backup-reference.yaml`
- Test: `plugins/ak/tests/adapters/test_sql_server.py`

**Rules:**
- Accept DDL/programmable-object scripts, validated catalog JSON, and deterministic metadata extracted from a DACPAC ZIP (`model.xml`).
- A BAK artifact is external-only metadata. The adapter records hash/reference/restore receipt but never copies or opens the BAK.
- MDF/LDF are always `INVALID: UNSUPPORTED_DIRECT_ATTACH` in standard V2.7.1.
- Live SQL Server connection and backup restore automation remain out of scope; a controlled external process may produce catalog/scripts plus a restore audit receipt.

- [ ] **Step 1: Write the failing tests**

```python
# plugins/ak/tests/adapters/test_sql_server.py
from pathlib import Path

from adapters.base import AcquisitionRequest
from adapters.sql_server.adapter import SqlServerAdapter

FIXTURE = Path(__file__).resolve().parents[2] / "fixtures" / "acquisition" / "sql-server-scripts"
CLASSIFICATION = {"topology": "client_server", "frontend_format": "adp", "source_availability": "full", "backend_kinds": ["sql_server"]}

def _request(root: Path, artifacts: tuple[dict, ...]) -> AcquisitionRequest:
    return AcquisitionRequest("SYN", CLASSIFICATION, artifacts, root)

def test_scripts_and_catalog_produce_server_capability() -> None:
    artifacts = (
        {"id": "DDL", "kind": "sql_server_schema", "role": "backend", "acquisition": "imported", "required": True, "source_ref": {"type": "local_path", "value": "schema.sql"}, "format": "sql"},
        {"id": "CATALOG", "kind": "sql_server_catalog", "role": "backend", "acquisition": "imported", "required": True, "source_ref": {"type": "local_path", "value": "catalog.json"}, "format": "json"},
    )
    adapter = SqlServerAdapter()
    result = adapter.acquire(adapter.plan(_request(FIXTURE / "complete", artifacts)))
    contribution = adapter.normalize(result)
    assert result.status == "VALID"
    assert contribution["code"]["sql_server"]
    assert contribution["databases"]["tables"]
    assert contribution["provenance"]["capabilities"] == ["server_object_inventory"]

def test_mdf_and_ldf_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "db.mdf").write_bytes(b"synthetic")
    artifact = {"id": "MDF", "kind": "sql_server_data_file", "role": "backend", "acquisition": "imported", "required": True, "source_ref": {"type": "external_path", "value": str(tmp_path / "db.mdf")}, "format": "mdf"}
    adapter = SqlServerAdapter()
    result = adapter.acquire(adapter.plan(_request(tmp_path, (artifact,))))
    assert result.status == "INVALID"
    assert result.failures[0]["reason"] == "UNSUPPORTED_DIRECT_ATTACH"

def test_bak_is_reference_only() -> None:
    artifact = {"id": "BAK", "kind": "sql_server_backup", "role": "backend", "acquisition": "imported", "required": False, "source_ref": {"type": "external_path", "value": "X:/external/app.bak"}, "format": "bak"}
    adapter = SqlServerAdapter()
    result = adapter.acquire(adapter.plan(_request(FIXTURE / "incomplete", (artifact,))))
    contribution = adapter.normalize(result)
    assert ".bak" not in str(contribution).lower()
    assert result.status == "PARTIAL"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest plugins/ak/tests/adapters/test_sql_server.py -v`
Expected: FAIL because the SQL Server adapter does not exist.

- [ ] **Step 3: Add the catalog schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://sms.local/schemas/sql-server-catalog.schema.json",
  "type": "object",
  "additionalProperties": false,
  "required": ["version", "database", "objects"],
  "properties": {
    "version": {"const": "1.0"},
    "database": {"type": "string", "minLength": 1},
    "objects": {
      "type": "array",
      "items": {
        "type": "object", "additionalProperties": false,
        "required": ["schema", "name", "type"],
        "properties": {
          "schema": {"type": "string"}, "name": {"type": "string"},
          "type": {"enum": ["table", "view", "procedure", "function", "trigger", "type", "sequence"]},
          "columns": {"type": "array"}, "definition": {"type": ["string", "null"]}
        }
      }
    }
  }
}
```

- [ ] **Step 4: Implement the SQL Server importer**

Implement `SqlServerAdapter` with the same `probe/plan/acquire/normalize` methods as other adapters. Use these exact routing rules:

```python
UNSUPPORTED = {"mdf", "ldf"}
SCRIPT_FORMATS = {"sql"}
CATALOG_FORMATS = {"json"}
PACKAGE_FORMATS = {"dacpac"}
BACKUP_FORMATS = {"bak"}

def _handle_artifact(artifact: dict, source_root: Path) -> tuple[list[dict], list[dict], dict[str, str]]:
    fmt = str(artifact.get("format", "")).lower()
    if fmt in UNSUPPORTED:
        return [], [{"logical_id": artifact["id"], "reason": "UNSUPPORTED_DIRECT_ATTACH"}], {}
    if fmt in BACKUP_FORMATS:
        return [{"logical_id": artifact["id"], "kind": "backup_reference", "external_only": True}], [], {}
    path = _resolve_source(artifact, source_root)
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if fmt in SCRIPT_FORMATS:
        text = raw.decode("utf-8", errors="strict").replace("\r\n", "\n")
        return [{"logical_id": artifact["id"], "kind": "sql_server", "text": text, "sha256": digest}], [], {artifact["id"]: digest}
    if fmt in CATALOG_FORMATS:
        catalog = _validate_catalog(json.loads(raw.decode("utf-8")))
        return [{"logical_id": artifact["id"], "kind": "catalog", "catalog": catalog, "sha256": digest}], [], {artifact["id"]: digest}
    if fmt in PACKAGE_FORMATS:
        objects = _read_dacpac_model(path)
        return [{"logical_id": artifact["id"], "kind": "catalog", "catalog": {"version": "1.0", "database": artifact["id"], "objects": objects}, "sha256": digest}], [], {artifact["id"]: digest}
    return [], [{"logical_id": artifact["id"], "reason": "UNSUPPORTED_SQL_ARTIFACT"}], {}
```

`_read_dacpac_model` uses `zipfile.ZipFile`, requires exactly one `model.xml`, applies the imported adapter's ZIP guards, parses XML with `xml.etree.ElementTree`, and emits sorted `{schema,name,type,columns,definition}` records. It never extracts the DACPAC to disk and never copies the DACPAC into the contribution or bundle.

`normalize` routes script records to `code.sql_server`, catalog `table` objects to `databases.tables`, other catalog objects to `databases.objects`, and emits `provenance.capabilities = ["server_object_inventory"]` only when a validated catalog/DACPAC record exists. A backup reference alone remains `PARTIAL` and does not satisfy ADP Phase 1/3 readiness.

- [ ] **Step 5: Add synthetic fixtures and run tests**

Run: `python -m pytest plugins/ak/tests/adapters/test_sql_server.py plugins/ak/tests/test_phase_readiness.py -v`
Expected: PASS; ADP without `server_object_inventory` remains blocked by existing readiness rules.

- [ ] **Step 6: Commit**

```bash
git add plugins/ak/adapters/sql_server plugins/ak/schemas/sql-server-catalog.schema.json plugins/ak/fixtures/acquisition/sql-server-scripts plugins/ak/tests/adapters/test_sql_server.py
git commit -m "feat(ak): import SQL Server schema and catalog evidence"
```

---

### Task 7: `ak acquire` orchestration

**Files:**
- Modify: `plugins/ak/scripts/ak.py`
- Create: `plugins/ak/contracts/acquisition_orchestrator.py`
- Test: `plugins/ak/tests/test_cli_acquire.py`

**Behavior:** `ak.py acquire plan --manifest M` loads the V2.2 manifest, resolves classification, routes each artifact to an adapter by `acquisition` field and kind (`managed` -> managed Access; `imported` producer_export -> msaccess-vcs; imported source/document/etc -> imported sources; sql_server_* -> SQL Server), and prints a deterministic JSON plan with absolute paths removed. `ak.py acquire run --manifest M --output-root R [--authorize access_snapshot_extract]` executes adapters, assembles an unapproved bundle via Task 2, and prints `{bundle_id, bundle_dir, status}`. Approval still requires the existing `ak.py bundle approve`.

- [ ] **Step 1: Write the failing test**

```python
# plugins/ak/tests/test_cli_acquire.py
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
AK = PACKAGE / "scripts" / "ak.py"

def _write_manifest(tmp_path: Path) -> Path:
    (tmp_path / "Order.bas").write_text("Option Explicit\n", encoding="utf-8")
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "version: '2.2'\n"
        "app: {id: SYN, name_en: Synthetic}\n"
        "project:\n"
        "  classification: {topology: monolith, frontend_format: exported, source_availability: exported_only, backend_kinds: [unknown_boundary]}\n"
        "artifacts:\n"
        "  - {id: VBA_ORDER, kind: source_export, role: frontend, acquisition: imported, required: true, format: vba, source_ref: {type: local_path, value: Order.bas}}\n",
        encoding="utf-8",
    )
    return manifest

def _run(args: list[str], tmp_path: Path) -> dict:
    result = subprocess.run([sys.executable, str(AK), *args], cwd=tmp_path, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)

def test_acquire_plan_hides_absolute_paths(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    data = _run(["acquire", "plan", "--manifest", str(manifest)], tmp_path)
    assert data["adapters"]["imported_sources"] == ["VBA_ORDER"]
    assert str(tmp_path) not in json.dumps(data)

def test_acquire_run_produces_unapproved_bundle(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    output_root = tmp_path / "bundles"
    data = _run(["acquire", "run", "--manifest", str(manifest), "--output-root", str(output_root)], tmp_path)
    assert data["bundle_id"].startswith("bundle-")
    assert Path(data["bundle_dir"], "bundle.json").is_file()
    assert not list(output_root.rglob("bundle-approval.json"))

def test_acquire_run_bundle_passes_the_validation_gate(tmp_path: Path) -> None:
    manifest = _write_manifest(tmp_path)
    output_root = tmp_path / "bundles"
    data = _run(["acquire", "run", "--manifest", str(manifest), "--output-root", str(output_root)], tmp_path)
    validated = _run(["bundle", "validate", "--bundle-dir", data["bundle_dir"]], tmp_path)
    assert validated["bundle_id"] == data["bundle_id"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest plugins/ak/tests/test_cli_acquire.py -v`
Expected: FAIL with `invalid choice: 'acquire'`

- [ ] **Step 3: Implement the orchestrator**

Create `contracts/acquisition_orchestrator.py` with:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from adapters.base import AcquisitionRequest
from adapters.imported_sources.adapter import ImportedSourcesAdapter
from adapters.managed_access.adapter import ManagedAccessAdapter
from adapters.msaccess_vcs.adapter import MsAccessVcsAdapter
from adapters.sql_server.adapter import SqlServerAdapter

def route_adapter(artifact: dict[str, Any]) -> str:
    kind = artifact["kind"]
    if artifact["acquisition"] == "managed" or kind == "access_database":
        return "managed_access"
    if kind == "producer_export" and artifact.get("format") == "msaccess-vcs":
        return "msaccess_vcs"
    if kind.startswith("sql_server"):
        return "sql_server"
    return "imported_sources"

ADAPTERS = {
    "managed_access": ManagedAccessAdapter, "imported_sources": ImportedSourcesAdapter,
    "msaccess_vcs": MsAccessVcsAdapter, "sql_server": SqlServerAdapter,
}

def group_artifacts(artifacts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for artifact in artifacts:
        grouped.setdefault(route_adapter(artifact), []).append(artifact)
    return grouped
```

Then add `plan_acquisition` and `run_acquisition`. `run_acquisition` MUST rebind runtime-only fields onto each plan via `dataclasses.replace` before calling `acquire`, otherwise the managed adapter never receives `granted_authorization` and always returns `BLOCKED`:

```python
import dataclasses

from classification import Classification, resolve_classification
from manifest_v22 import load_manifest
import bundle_assembly
import phase_readiness as phase_readiness_contract

PACKAGE = Path(__file__).resolve().parents[1]
PROFILES = PACKAGE / "profiles"

def _classification_dict(manifest) -> dict[str, Any]:
    c = manifest.classification
    return {"topology": c.topology, "frontend_format": c.frontend_format, "source_availability": c.source_availability, "backend_kinds": list(c.backend_kinds)}

def _artifact_dict(artifact) -> dict[str, Any]:
    data = {"id": artifact.id, "kind": artifact.kind, "role": artifact.role, "acquisition": artifact.acquisition, "required": artifact.required, "source_ref": {"type": artifact.source_ref.type, "value": artifact.source_ref.value}}
    if artifact.format: data["format"] = artifact.format
    if artifact.backend_kind: data["backend_kind"] = artifact.backend_kind
    return data

def plan_acquisition(manifest_path: Path) -> dict[str, Any]:
    manifest = load_manifest(Path(manifest_path))
    artifacts = [_artifact_dict(a) for a in manifest.artifacts]
    grouped = group_artifacts(artifacts)
    return {"app_id": manifest.app["id"], "classification": _classification_dict(manifest), "adapters": {adapter: [a["id"] for a in items] for adapter, items in sorted(grouped.items())}}

def run_acquisition(manifest_path: Path, output_root: Path, granted_authorization: tuple[str, ...], acquisition_id: str) -> dict[str, Any]:
    manifest = load_manifest(Path(manifest_path))
    source_root = Path(manifest_path).resolve().parent
    classification_dict = _classification_dict(manifest)
    classification = Classification(classification_dict["topology"], classification_dict["frontend_format"], classification_dict["source_availability"], tuple(classification_dict["backend_kinds"]))
    resolved = resolve_classification(classification, PROFILES)
    artifacts = [_artifact_dict(a) for a in manifest.artifacts]
    contributions: list[dict[str, Any]] = []
    for adapter_id, items in group_artifacts(artifacts).items():
        adapter = ADAPTERS[adapter_id]()
        request = AcquisitionRequest(manifest.app["id"], classification_dict, tuple(items), source_root, frozenset(granted_authorization))
        plan = dataclasses.replace(adapter.plan(request), app_id=manifest.app["id"], acquisition_id=acquisition_id, granted_authorization=tuple(granted_authorization), runtime_output_root=str(Path(output_root) / "staging"))
        contributions.append(adapter.normalize(adapter.acquire(plan)))
    capabilities = _capabilities(contributions)
    readiness = phase_readiness_contract.compute_readiness(classification, PROFILES, capabilities)
    profile_validation = {"status": _worst_contribution_status(contributions)}
    return bundle_assembly.assemble_bundle(app_id=manifest.app["id"], classification=classification_dict, rule_versions=resolved.rule_versions, contributions=contributions, normalization_config={"text": "utf-8-lf"}, profile_validation=profile_validation, phase_readiness=readiness, output_root=Path(output_root))
```

Add small helpers `_capabilities(contributions)` (derive the readiness capability set, for example `vba_query_inventory` when any contribution has `code.vba` or `code.access_sql`, `server_object_inventory` when a SQL Server catalog record exists) and `_worst_contribution_status`. Producer exports whose `format` is not `msaccess-vcs` are routed to `imported_sources`, which records them under `failures` rather than guessing a producer.

- [ ] **Step 4: Wire the subcommand into `ak.py`**

In `parse_args`, add:

```python
def configure_acquire_parser(commands: argparse._SubParsersAction) -> None:
    acquire = commands.add_parser("acquire", help="Route declared artifacts through acquisition adapters.")
    acquire_commands = acquire.add_subparsers(dest="acquire_action", required=True)
    acquire_plan = acquire_commands.add_parser("plan")
    acquire_plan.add_argument("--manifest", required=True)
    acquire_run = acquire_commands.add_parser("run")
    acquire_run.add_argument("--manifest", required=True)
    acquire_run.add_argument("--output-root", required=True)
    acquire_run.add_argument("--authorize", action="append", default=[])
    acquire_run.add_argument("--acquisition-id", default="acquire")
```

Call `configure_acquire_parser(commands)` once inside `parse_args` after the existing `bundle` parser is configured.

In `main`, add dispatch that inserts `str(PACKAGE)` onto `sys.path` (the parent of the `adapters` package), imports `acquisition_orchestrator`, and prints the deterministic JSON. Absolute paths are stripped from the plan output before printing.

- [ ] **Step 5: Run the acquire and full suite**

Run: `python -m pytest plugins/ak/tests/test_cli_acquire.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Commit**

```bash
git add plugins/ak/scripts/ak.py plugins/ak/contracts/acquisition_orchestrator.py plugins/ak/tests/test_cli_acquire.py
git commit -m "feat(ak): orchestrate adapters into an unapproved bundle via ak acquire"
```

---

### Task 8: Structure validation, version bump, docs, and ownership

**Files:**
- Modify: `.github/workflows/validate.yml`
- Modify: `plugins/ak/scripts/validate_structure.py`
- Modify: `plugins/ak/specifications/package.json`, `plugins/ak/.claude-plugin/plugin.json`, `plugins/ak/.codex-plugin/plugin.json`
- Modify: `plugins/ak/skills/ak/SKILL.md`
- Modify: `.github/CODEOWNERS`
- Create: `docs/acquisition/decision-guide.md`, `docs/acquisition/managed-access.md`, `docs/acquisition/imported-sources.md`, `docs/acquisition/sql-server.md`

- [ ] **Step 1: Extend CI compilation and structure checks**

In `.github/workflows/validate.yml`, replace the compile command with:

```yaml
      - name: Compile Python package and tests
        run: python -m compileall -q plugins/ak/contracts plugins/ak/adapters plugins/ak/scripts plugins/ak/tests
```

Then extend `validate_structure.py` with assertions that `plugins/ak/adapters/` exists with the four adapter packages, that `bundle-contribution.schema.json`, `import-source-manifest.schema.json`, and `sql-server-catalog.schema.json` are valid JSON Schema, and that `docs/acquisition/` has the four files. Keep the existing counts logic; only extend it.

- [ ] **Step 2: Run compilation and structure validation**

Run: `python -m compileall -q plugins/ak/contracts plugins/ak/adapters plugins/ak/scripts plugins/ak/tests`
Expected: exit 0 with no syntax errors.

Run: `python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .`
Expected: `Validation passed` with the new file counts and 0 warnings.

- [ ] **Step 3: Bump version to 2.7.1 and document `$ak acquire`**

Set `version` to `2.7.1` in `package.json` and both `plugin.json` files. In `SKILL.md`, add `$ak acquire <APP_ID>` between assess and phase with a one-line description and the snapshot/authorization boundary note. Keep contract version 2.2.

- [ ] **Step 4: Write English-canonical acquisition docs**

Each doc covers only prerequisites, commands, adapter-specific failures, and bundle contribution behavior (spec section 19). `decision-guide.md` maps classification to the right adapter. Do not duplicate the shared pipeline already documented in `docs/architecture/`.

- [ ] **Step 5: Update CODEOWNERS**

Add ownership lines for `plugins/ak/adapters/managed_access/`, `plugins/ak/adapters/imported_sources/`, `plugins/ak/adapters/msaccess_vcs/`, `plugins/ak/adapters/sql_server/`, and `docs/acquisition/`.

- [ ] **Step 6: Run the full suite and structure validation together**

Run: `python -m pytest -q` then `python plugins/ak/scripts/validate_structure.py --package plugins/ak --repository-root .`
Expected: all tests pass (48 baseline + new adapter/orchestration tests) and structure validation passes with 0 warnings.

- [ ] **Step 7: Commit**

```bash
git add .github/workflows/validate.yml plugins/ak/scripts/validate_structure.py plugins/ak/specifications/package.json plugins/ak/.claude-plugin/plugin.json plugins/ak/.codex-plugin/plugin.json plugins/ak/skills/ak/SKILL.md .github/CODEOWNERS docs/acquisition
git commit -m "chore(ak): validate adapters, bump to 2.7.1, add acquisition docs"
```

---

## Shared Dataclass Consolidation

Tasks 3-7 incrementally add fields to `AcquisitionPlan` and `AcquisitionResult`. Before starting Task 3, update `adapters/base.py` once so both dataclasses carry every field the later tasks rely on, then keep them stable:

- `AcquisitionPlan` fields: `adapter_id`, `adapter_version`, `planned_artifacts`, `authorization_required=()`, `reads=()`, `writes=()`, `operations=()`, `app_id=""`, `acquisition_id="acquire"`, `granted_authorization=()`, `runtime_output_root=""`.
- `AcquisitionResult` fields (in order): `app_id`, `adapter_id`, `adapter_version`, `status`, `records`, `failures`, `source_hashes`, `metadata=field(default_factory=dict)`.

Runtime-only fields (`operations`, `app_id`, `acquisition_id`, `granted_authorization`, `runtime_output_root`, `metadata`) never participate in bundle identity, which is computed solely from `contribution` content and `contracts/bundle.py::compute_bundle_id`.

## Self-Review

Spec coverage check against acceptance criteria (section 26):
- AC3 (schema-equivalent managed/imported bundles): Tasks 1, 3, 4 share `bundle-contribution.schema.json`.
- AC4 (ADP without SQL schema blocks): Task 6 + existing readiness rules.
- AC6 (compiled frontend no false complete-VBA): managed adapter preserves `PARTIAL`; msaccess-vcs only reports present objects.
- AC7 (no raw DB/backup in bundle): Task 2 `_guard_no_binaries`, imported executable/suffix guards, SQL Server BAK external-only, MDF/LDF rejected.
- AC11 (adapter tests independent of Phase generation): all adapter tests run without Phase docs.
- AC12 (deterministic reproducibility): content-id and bundle-id tests.
- AC14 (contributors share one bundle without canonical write paths): adapters write only to staging/output-root; approval is separate.

Placeholder scan: every code step ships runnable content; the only prose-only step is doc writing (Task 8 Step 4), which is acceptable for narrative docs.

Type consistency: `probe/plan/acquire/normalize` names are identical across adapters; `AcquisitionResult.app_id` is first everywhere; `empty_sections`, `validate_contribution`, `decode_text`, and `safe_zip_members` are defined once and imported.

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-07-28-acquisition-adapters.md`. Two execution options:

1. Subagent-Driven (recommended) - fresh subagent per task, review between tasks.
2. Inline Execution - execute tasks in this session with checkpoints.
