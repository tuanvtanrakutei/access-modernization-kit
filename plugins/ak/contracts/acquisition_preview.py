"""Answer two questions about a manifest before anything is acquired.

Which mode is this project actually in, and what will the declared artifacts be
able to prove? Both were previously answerable only by running acquisition and
reading the bundle afterwards, or by mentally replaying ``route_adapter`` over
every artifact and then the capability rules of each adapter. A manifest could
therefore contradict itself - declaring an imported Access database that routes
to the managed adapter regardless - and nobody found out until the run.

Nothing here executes an adapter. The capabilities reported are what the
declared artifact kinds are expected to yield, split into those a successful run
gives structurally and those that depend on what the sources turn out to hold.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import phase_readiness as phase_readiness_contract
from classification import Classification

# Kinds that say where the sources come from. Documents, screenshots and samples
# are evidence carried alongside either mode and must not decide the mode.
_EXTRACT_KINDS = {"access_database"}
_EXPORT_KINDS = {"source_export", "producer_export"}

# What a successful acquisition is expected to yield per adapter. "expected" holds
# what the adapter produces structurally; "content_dependent" names capabilities
# that exist only if the sources actually contain that kind of object, with the
# condition spelled out so a thin result is not a surprise.
_MANAGED_EXPECTED = {"access_schema_inventory", "field_inventory", "access_object_inventory"}
_MANAGED_CONDITIONAL = {
    "key_index_inventory": "at least one table declares an index",
    "ui_object_inventory": "the database contains forms, reports or macros",
    "vba_query_inventory": "the database contains modules or saved queries",
    "boundary_inventory": "at least one table is linked to an external source",
}
_IMPORTED_CONDITIONAL = {
    "ui_object_inventory": "the export package contains form, report or macro definitions",
    "boundary_inventory": "the export declares linked tables or file interfaces",
}


def route_of(artifact: dict[str, Any]) -> str:
    """Mirror acquisition_orchestrator.route_adapter without importing the orchestrator."""
    kind = artifact.get("kind", "")
    if artifact.get("acquisition") == "managed" or kind == "access_database":
        return "managed_access"
    if kind == "producer_export" and artifact.get("format") == "msaccess-vcs":
        return "msaccess_vcs"
    if kind.startswith("sql_server"):
        return "sql_server"
    return "imported_sources"


def observed_mode(artifacts: list[dict[str, Any]]) -> str:
    """Derive the mode from what the artifacts are, not from what files exist on disk."""
    has_extract = any(a.get("kind") in _EXTRACT_KINDS or a.get("acquisition") == "managed" for a in artifacts)
    has_export = any(a.get("kind") in _EXPORT_KINDS for a in artifacts)
    if has_extract and has_export:
        return "mixed"
    if has_extract:
        return "extract"
    if has_export:
        return "export"
    return "none"


def contradictions(artifacts: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Per-artifact declarations that cannot both be honoured."""
    found: list[dict[str, str]] = []
    for artifact in artifacts:
        route = route_of(artifact)
        # kind wins over acquisition in the router, so "imported" on an Access
        # database reads as a choice the operator made and the run silently ignores.
        if artifact.get("kind") == "access_database" and artifact.get("acquisition") == "imported":
            found.append({
                "artifact": str(artifact.get("id")),
                "reason": "ACQUISITION_IGNORED",
                "detail": "kind: access_database always routes to managed_access, so acquisition: imported has no effect. "
                          "Declare acquisition: managed, or export the database and declare the export as a source_export.",
            })
        if route == "managed_access" and artifact.get("kind") not in _EXTRACT_KINDS and artifact.get("acquisition") != "managed":
            found.append({
                "artifact": str(artifact.get("id")),
                "reason": "UNEXPECTED_MANAGED_ROUTE",
                "detail": f"kind {artifact.get('kind')!r} routes to managed_access unexpectedly.",
            })
    return found


def expected_capabilities(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Capabilities the declared artifacts should yield, and what each depends on."""
    expected: set[str] = set()
    conditional: dict[str, str] = {}
    for artifact in artifacts:
        route = route_of(artifact)
        kind = artifact.get("kind", "")
        fmt = str(artifact.get("format") or "")
        if route == "managed_access":
            expected |= _MANAGED_EXPECTED
            conditional.update(_MANAGED_CONDITIONAL)
        elif route == "sql_server":
            conditional.setdefault(
                "server_object_inventory",
                "the declared catalog or schema export lists server objects",
            )
        elif route == "msaccess_vcs":
            conditional.update(_IMPORTED_CONDITIONAL)
            conditional.setdefault(
                "vba_query_inventory",
                "the msaccess-vcs export contains modules or query SQL",
            )
        elif route == "imported_sources":
            if kind == "document":
                expected.add("document_inventory")
            elif kind == "source_export":
                if fmt in {"vba", "access_sql"}:
                    expected.add("vba_query_inventory")
                else:
                    # A directory or archive package: its contents are unknown until
                    # the producer manifest is read at acquisition time.
                    conditional.update(_IMPORTED_CONDITIONAL)
                    conditional.setdefault(
                        "vba_query_inventory",
                        "the export package contains modules or query SQL",
                    )
    # Mirrors acquisition_orchestrator._declaration_capabilities: this one is a
    # statement the manifest makes, not evidence an adapter extracts, so the preview
    # can report it with certainty - and its absence is exactly what an operator who
    # left role: unknown needs to see before running anything.
    if any(
        a.get("role") == "backend" and a.get("required") and a.get("backend_kind")
        for a in artifacts
    ):
        expected.add("backend_authority_declared")
    for name in expected:
        conditional.pop(name, None)
    return {"expected": sorted(expected), "content_dependent": dict(sorted(conditional.items()))}


def phase_outlook(
    classification: Classification,
    profiles_dir: Path,
    capabilities: dict[str, Any],
) -> dict[str, Any]:
    """Phase readiness under two honest assumptions: the floor, and the ceiling."""
    guaranteed = set(capabilities["expected"])
    optimistic = guaranteed | set(capabilities["content_dependent"])

    def statuses(present: set[str]) -> dict[str, str]:
        result = phase_readiness_contract.compute_readiness(classification, profiles_dir, present)
        return {
            phase: str(value["status"])
            for phase, value in result.items()
            if isinstance(value, dict) and "status" in value
        }

    return {"guaranteed": statuses(guaranteed), "if_content_present": statuses(optimistic)}


def needs_access_host(artifacts: list[dict[str, Any]]) -> dict[str, Any]:
    """Whether this manifest starts an Access host, which is the only part that can need elevation.

    The DAO tier is an in-process COM object and activates without elevation. Only
    Access.Application does, so a manifest that skips object export imposes no
    administrator requirement at all - and saying otherwise trains operators to
    elevate a run that never needed it.
    """
    hosts = [
        str(a.get("id"))
        for a in artifacts
        if route_of(a) == "managed_access" and not (a.get("runtime") or {}).get("skip_object_export")
    ]
    return {
        "required": bool(hosts),
        "artifacts": hosts,
        "reason": (
            "These artifacts export object definition text, which starts an Access host. "
            "COM activation must succeed: an executable carrying RUNASADMIN fails with 0x800702E4 "
            "unless the flag is removed or the run is elevated."
            if hosts else
            "No Access host is started; every managed artifact acquires through the DAO tier only."
        ),
    }


def preview(
    declared_mode: str | None,
    artifacts: list[dict[str, Any]],
    classification: Classification,
    profiles_dir: Path,
) -> dict[str, Any]:
    observed = observed_mode(artifacts)
    capabilities = expected_capabilities(artifacts)
    result: dict[str, Any] = {
        "declared_mode": declared_mode,
        "observed_mode": observed,
        "mode_agrees": declared_mode is None or declared_mode == observed,
        "adapters": {},
        "capabilities": capabilities,
        "phase_outlook": phase_outlook(classification, profiles_dir, capabilities),
        "access_host": needs_access_host(artifacts),
        "contradictions": contradictions(artifacts),
    }
    for artifact in artifacts:
        result["adapters"].setdefault(route_of(artifact), []).append(str(artifact.get("id")))
    result["adapters"] = {key: sorted(value) for key, value in sorted(result["adapters"].items())}
    return result
