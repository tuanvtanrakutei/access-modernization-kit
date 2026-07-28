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
            extraction = _find_extraction(
                Path(plan.runtime_output_root), artifact["id"], plan.acquisition_id
            )
            if extraction.exists():
                failures.append({
                    "logical_id": artifact["id"], "reason": "STALE_EXTRACTION_RESULT"
                })
                continue
            completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
            if completed.returncode != 0:
                failures.append({
                    "logical_id": artifact["id"], "reason": "EXTRACTOR_FAILED",
                    "returncode": completed.returncode,
                })
                continue
            if not extraction.is_file():
                failures.append({
                    "logical_id": artifact["id"], "reason": "EXTRACTION_RESULT_MISSING",
                    "returncode": completed.returncode,
                })
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
