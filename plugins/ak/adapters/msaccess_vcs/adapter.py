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
