from __future__ import annotations

import json
import shutil
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
        # A frontend that opens its backend as a sibling needs the backend's snapshot
        # to exist beside its own by the time it starts, so backends are acquired
        # first. Without an order the frontend could run against a directory holding
        # only itself, which is how a split application fails to open at all.
        ordered = sorted(
            request.artifacts,
            key=lambda artifact: 0 if artifact.get("role") == "backend" else 1,
        )
        operations = tuple({
            "artifact": artifact,
            "source": str((request.source_root / artifact["source_ref"]["value"]).resolve()),
            "output_subdir": artifact["id"],
        } for artifact in ordered)
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
                # One directory for every database of this application, so the sibling
                # layout the app resolves against is reproduced inside the snapshot.
                "--snapshot-dir", str(_snapshot_dir(plan)),
                "--execute",
            ]
            # Runtime choices declared per artifact in the manifest. Without this the
            # extractor's own remedies - pinning an Access install, skipping the host
            # that a broken VBA project would stall, raising the timeout, supplying a
            # password - were unreachable through acquisition.
            command += _runtime_flags(artifact.get("runtime") or {})
            extraction = _find_extraction(
                Path(plan.runtime_output_root), artifact["id"], plan.acquisition_id
            )
            if extraction.exists():
                failures.append({
                    "logical_id": artifact["id"], "reason": "STALE_EXTRACTION_RESULT"
                })
                continue
            # PowerShell writes diagnostics in the console codepage, not UTF-8. On a
            # Japanese Windows host a strict utf-8 decode raised UnicodeDecodeError
            # inside subprocess's reader threads, so the extractor's own explanation
            # of the failure never reached the caller - only a bare returncode did.
            completed = subprocess.run(
                command, check=False, capture_output=True, text=True,
                encoding="utf-8", errors="replace",
            )
            if completed.returncode != 0:
                failures.append({
                    "logical_id": artifact["id"], "reason": "EXTRACTOR_FAILED",
                    "returncode": completed.returncode,
                    "detail": _tail(completed.stderr) or _tail(completed.stdout),
                })
                continue
            if not extraction.is_file():
                failures.append({
                    "logical_id": artifact["id"], "reason": "EXTRACTION_RESULT_MISSING",
                    "returncode": completed.returncode,
                })
                continue
            # utf-8-sig, not utf-8: the PowerShell extractor writes this file with a
            # BOM, which json.loads rejects. Every real extraction failed here while
            # the tests passed, because a Python-written fixture has no BOM.
            data = json.loads(extraction.read_text(encoding="utf-8-sig"))
            records.append(data)
            hashes[artifact["id"]] = data["source"]["sha256"]
        status = "BLOCKED" if failures and not records else ("PARTIAL" if failures or any(r["status"] == "PARTIAL" for r in records) else "VALID")
        reclaimed = _reclaim_snapshots(plan, status)
        if reclaimed:
            records = [{**record, "snapshot_reclaimed_bytes": reclaimed} if index == 0 else record
                       for index, record in enumerate(records)]
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
            _route_table_detail(sections, extraction["database_id"], extraction.get("tables", []))
            # The specification tables a text link points at, carried through with the
            # database that declared them so a consumer can tell whose layout it is.
            # Absent unless some link declared `DSN=`, which is the only reason to read
            # Access's own bookkeeping at all (backlog A17).
            for record in extraction.get("imex_specs", []):
                sections["interfaces"]["imex_specs"].append(
                    {"database_id": extraction["database_id"], **record})
            # An exclusion the extractor made on purpose is not a failure to extract
            # something. Reported through the same channel it made coverage overstate
            # failure by more than a third, and a clean run look damaged.
            #
            # Three markers, because A22 gave the exclusion an evidence trail: the
            # `EXCLUDED:` summary, one `EXCLUDED table <name>: <fields>` line per table
            # the shape rule dropped, and one `KEPT table ...` line per table it nearly
            # did. Matching only the summary would have filed 208 of those lines as
            # unreadable objects on one A05 frontend - the exact defect this comment is
            # about, in the code that fixed it.
            #
            # An unmarked warning stays a failure, and that default is now correct
            # rather than merely convenient: what a run *did* travels in `notes`, so
            # nothing informational is left relying on a prefix somebody has to
            # remember. Prefixes stay for the two kinds that have their own count, and
            # for extractions written before `notes` existed - those carry their notes
            # in `warnings` and still read as failures, which is the old answer and
            # the honest one for a record this cannot re-classify after the fact.
            for warning in extraction.get("warnings", []):
                entry = {"logical_id": extraction["database_id"], "reason": warning}
                if str(warning).startswith("EXCLUDED"):
                    entry["kind"] = "exclusion"
                elif str(warning).startswith("KEPT "):
                    entry["kind"] = "observation"
                failures.append(entry)
            for note in extraction.get("notes", []):
                failures.append({"logical_id": extraction["database_id"],
                                 "reason": note, "kind": "note"})
        contribution = {
            "adapter_id": self.adapter_id, "adapter_version": self.adapter_version, "app_id": result.app_id,
            "status": result.status, **sections, "failures": failures,
            "provenance": {
                "producer": "ak-managed-access",
                "source_hashes": dict(sorted(result.source_hashes.items())),
                "capabilities": _access_capabilities(sections),
            },
        }
        return validate_contribution(contribution)


def _access_capabilities(sections: dict[str, Any]) -> list[str]:
    capabilities: set[str] = set()
    if any(sections["databases"].values()) or any(sections["ui"].values()) or any(sections["code"].values()):
        capabilities.add("access_object_inventory")
    if sections["databases"]["tables"]:
        capabilities.add("access_schema_inventory")
    if sections["databases"]["fields"]:
        capabilities.add("field_inventory")
    if sections["databases"]["indexes"]:
        capabilities.add("key_index_inventory")
    if sections["code"]["vba"] or sections["code"]["access_sql"]:
        capabilities.add("vba_query_inventory")
    if any(sections["ui"].values()):
        capabilities.add("ui_object_inventory")
    # A36. The DAO tier lists forms and reports by name and exports no definition, so
    # ui rows alone cannot answer for UI_DEFINITION - which the contract defines as the
    # SaveAsText definitions themselves. `skip_object_export: true` is the normal case
    # here, not an edge one: it is what a frontend whose startup code hangs an
    # unattended run is acquired with.
    if any(
        (row.get("text") or row.get("source_paths"))
        for rows in sections["ui"].values()
        for row in rows
    ):
        capabilities.add("ui_definition_text")
    if sections["interfaces"]["linked_tables"]:
        capabilities.add("boundary_inventory")
    return sorted(capabilities)

_RUNTIME_VALUE_FLAGS = {
    "access_progid": "--access-progid",
    "dao_progid": "--dao-progid",
    "access_path": "--access-path",
    "powershell": "--powershell",
    "password_env": "--password-env",
    "timeout": "--timeout",
    # Suppressing macros keeps an unattended run out of the VBA debugger, and on an
    # application whose startup code relinks stale table connections it also suppresses
    # the repair the application depends on. A faithful run has to be able to choose.
    "automation_security": "--automation-security",
}
_RUNTIME_SWITCH_FLAGS = {
    "skip_object_export": "--skip-object-export",
    "skip_object_inventory": "--skip-object-inventory",
    "visible_host": "--visible-host",
    "allow_run_as_invoker": "--allow-run-as-invoker",
    "skip_runtime_check": "--skip-runtime-check",
}


def _snapshot_dir(plan: Any) -> Path:
    """Where this acquisition's disposable copies live.

    Falls back inside staging when a caller built a plan without a snapshot root -
    older callers and hand-built test plans - so the change cannot silently write
    to the workspace root.
    """
    root = plan.snapshot_root or str(Path(plan.runtime_output_root) / "_snapshots")
    return Path(root) / plan.acquisition_id


def _reclaim_snapshots(plan: Any, status: str) -> int:
    """Remove the snapshots once the run that needed them has fully succeeded.

    A snapshot exists because the original database must never be opened - opening
    mutates it. Once extraction has written its receipt, nothing reads the copy
    again, and on a real split application the pair was 615 MB sitting beside the
    587 MB of originals: a workspace holding 1.2 GB to analyse 3 MB of text.

    Deleting loses nothing. The originals are still in `sources/`, and the receipt
    records the snapshot's SHA-256, so a later run can prove it read the same bytes.

    Kept when the run did not fully succeed, because a PARTIAL or BLOCKED run is the
    one somebody will investigate, and kept whenever `--keep-snapshots` is passed.
    """
    if plan.keep_snapshots or status != "VALID":
        return 0
    directory = _snapshot_dir(plan)
    if not directory.is_dir():
        return 0
    size = sum(item.stat().st_size for item in directory.rglob("*") if item.is_file())
    shutil.rmtree(directory, ignore_errors=True)
    parent = directory.parent
    if parent.is_dir() and not any(parent.iterdir()):
        parent.rmdir()
    return size


def _runtime_flags(runtime: dict[str, Any]) -> list[str]:
    """Translate an artifact's declared runtime block into extractor flags.

    Unknown keys are ignored rather than passed through, so a manifest can never
    inject arbitrary arguments into the extractor's command line.
    """
    flags: list[str] = []
    for key, flag in _RUNTIME_VALUE_FLAGS.items():
        value = runtime.get(key)
        if value not in (None, ""):
            flags += [flag, str(value)]
    for key, flag in _RUNTIME_SWITCH_FLAGS.items():
        if runtime.get(key):
            flags.append(flag)
    return flags


def _route_table_detail(sections: dict[str, Any], database_id: str, tables: list[dict[str, Any]]) -> None:
    """Flatten per-table field and index detail into the bundle's own sections.

    The extractor collects both, but they arrive nested under each table rather
    than as the flat inventories the contribution declares. Without this the
    fields and indexes lists stayed empty no matter how complete the extraction
    was, and field_inventory / key_index_inventory - two of the three
    capabilities Phase 1 requires - could never be reported.
    """
    for table in tables:
        table_name = table.get("name", "")
        for field in table.get("fields", []) or []:
            sections["databases"]["fields"].append({"database_id": database_id, "table": table_name, **field})
        for index in table.get("indexes", []) or []:
            sections["databases"]["indexes"].append({"database_id": database_id, "table": table_name, **index})


def _tail(stream: str | None, limit: int = 800) -> str:
    text = (stream or "").strip()
    return text[-limit:] if text else ""


def _find_extraction(root: Path, database_id: str, acquisition_id: str) -> Path:
    return root / database_id / acquisition_id / "access-extraction.json"

def _route_component(sections: dict[str, Any], database_id: str, component: dict[str, Any]) -> None:
    record = {"database_id": database_id, **{k: v for k, v in component.items() if k not in {"path", "source_path", "snapshot_path"}}}
    # The bundle keys and sorts code records by logical_id. The extractor calls its
    # own key "id", so assembly raised KeyError on every managed-access contribution.
    record.setdefault("logical_id", record.get("id") or record.get("name", ""))
    # extract_access.ps1 emits its object class under "kind"; this router only ever
    # read "type"/"object_type", so every component - forms, reports, queries,
    # modules alike - fell through to databases.objects. The UI, code and interface
    # sections stayed empty, and with them the capabilities that unblock phases 1-3.
    kind = str(component.get("kind", component.get("type", component.get("object_type", "object")))).lower()
    metadata = component.get("metadata") or {}
    if "vba" in kind or kind == "module": sections["code"]["vba"].append(record)
    elif "query" in kind: sections["code"]["access_sql"].append(record)
    elif kind == "form": sections["ui"]["forms"].append(record)
    elif kind == "report": sections["ui"]["reports"].append(record)
    elif kind == "macro": sections["ui"]["macros"].append(record)
    elif "linked" in kind: sections["interfaces"]["linked_tables"].append(record)
    elif kind == "table":
        sections["databases"]["tables"].append(record)
        # A linked table is both schema and a boundary. It is declared by the
        # extractor as a table carrying metadata.linked, never as its own kind.
        if metadata.get("linked"):
            sections["interfaces"]["linked_tables"].append(record)
    else: sections["databases"]["objects"].append(record)
