from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import acquisition_preview
import bundle_assembly
import evidence_classes
import phase_readiness as phase_readiness_contract
from adapters.base import AcquisitionRequest
from adapters.imported_sources.adapter import ImportedSourcesAdapter
from adapters.managed_access.adapter import ManagedAccessAdapter
from adapters.msaccess_vcs.adapter import MsAccessVcsAdapter
from adapters.sql_server.adapter import SqlServerAdapter
from classification import Classification, resolve_classification
from manifest_v22 import load_manifest

PACKAGE = Path(__file__).resolve().parents[1]
PROFILES = PACKAGE / "profiles"


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
    "managed_access": ManagedAccessAdapter,
    "imported_sources": ImportedSourcesAdapter,
    "msaccess_vcs": MsAccessVcsAdapter,
    "sql_server": SqlServerAdapter,
}


def group_artifacts(artifacts: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for artifact in artifacts:
        grouped.setdefault(route_adapter(artifact), []).append(artifact)
    return grouped


def _classification_dict(manifest: Any) -> dict[str, Any]:
    classification = manifest.classification
    if classification is None:
        raise ValueError("Acquisition requires a V2.2 classified manifest")
    return {
        "topology": classification.topology,
        "frontend_format": classification.frontend_format,
        "source_availability": classification.source_availability,
        "backend_kinds": list(classification.backend_kinds),
    }


def _artifact_dict(artifact: Any) -> dict[str, Any]:
    data = {
        "id": artifact.id,
        "kind": artifact.kind,
        "role": artifact.role,
        "acquisition": artifact.acquisition,
        "required": artifact.required,
        "source_ref": {"type": artifact.source_ref.type, "value": artifact.source_ref.value},
    }
    if artifact.format:
        data["format"] = artifact.format
    if artifact.backend_kind:
        data["backend_kind"] = artifact.backend_kind
    if artifact.runtime:
        data["runtime"] = dict(artifact.runtime)
    return data


def plan_acquisition(manifest_path: Path) -> dict[str, Any]:
    manifest = load_manifest(Path(manifest_path))
    artifacts = [_artifact_dict(artifact) for artifact in manifest.artifacts]
    grouped = group_artifacts(artifacts)
    classification_dict = _classification_dict(manifest)
    classification = Classification(
        classification_dict["topology"], classification_dict["frontend_format"],
        classification_dict["source_availability"], tuple(classification_dict["backend_kinds"]),
    )
    # The plan is the last point before real work where a self-contradicting manifest
    # can still be cheap to fix, so it answers what the run will be able to prove and
    # whether the declared mode matches how the artifacts actually route.
    outlook = acquisition_preview.preview(
        manifest.acquisition_mode, artifacts, classification, PROFILES,
    )
    return {
        "app_id": manifest.app["id"],
        "classification": classification_dict,
        "adapters": {
            adapter: [artifact["id"] for artifact in items]
            for adapter, items in sorted(grouped.items())
        },
        "mode": {
            "declared": outlook["declared_mode"],
            "observed": outlook["observed_mode"],
            "agrees": outlook["mode_agrees"],
        },
        "capabilities": outlook["capabilities"],
        "phase_outlook": outlook["phase_outlook"],
        "access_host": outlook["access_host"],
        "contradictions": outlook["contradictions"],
    }


def run_acquisition(
    manifest_path: Path,
    output_root: Path,
    granted_authorization: tuple[str, ...],
    acquisition_id: str,
    required_phases: tuple[str, ...] = (),
    keep_snapshots: bool = False,
) -> dict[str, Any]:
    manifest = load_manifest(Path(manifest_path))
    source_root = Path(manifest_path).resolve().parent
    classification_dict = _classification_dict(manifest)
    classification = Classification(
        classification_dict["topology"],
        classification_dict["frontend_format"],
        classification_dict["source_availability"],
        tuple(classification_dict["backend_kinds"]),
    )
    resolved = resolve_classification(classification, PROFILES)
    artifacts = [_artifact_dict(artifact) for artifact in manifest.artifacts]
    # The mode is an observation of what the artifacts are, not a choice an operator
    # makes, so a stale label is corrected and reported rather than treated as a
    # failure: the artifacts are the truth, and refusing the run over a description of
    # them only stops work that was going to be correct anyway. What does stop the run
    # is a declaration that cannot be honoured at all - see contradictions below.
    observed = acquisition_preview.observed_mode(artifacts)
    mode_note = None
    if manifest.acquisition_mode and manifest.acquisition_mode != observed:
        mode_note = {
            "declared": manifest.acquisition_mode, "observed": observed,
            "detail": "acquisition_mode did not match the artifacts and was ignored; the observed mode was used.",
        }
    conflicts = acquisition_preview.contradictions(artifacts)
    if conflicts:
        detail = "; ".join(f"{item['artifact']}: {item['reason']}" for item in conflicts)
        raise ValueError(f"Manifest contains contradictory artifact declarations: {detail}")
    contributions: list[dict[str, Any]] = []
    for adapter_id, items in sorted(group_artifacts(artifacts).items()):
        adapter = ADAPTERS[adapter_id]()
        request = AcquisitionRequest(
            manifest.app["id"], classification_dict, tuple(items), source_root,
            frozenset(granted_authorization),
        )
        plan = dataclasses.replace(
            adapter.plan(request),
            app_id=manifest.app["id"],
            acquisition_id=acquisition_id,
            granted_authorization=tuple(granted_authorization),
            runtime_output_root=str(Path(output_root) / "staging"),
            snapshot_root=str(Path(output_root) / "snapshots"),
            keep_snapshots=keep_snapshots,
        )
        contributions.append(adapter.normalize(adapter.acquire(plan)))
    _flag_export_drift(contributions)
    with_rows = _database_ids_with_rows(contributions)
    declared = _declaration_capabilities(manifest.artifacts, with_rows)
    capabilities = _capabilities(contributions) | declared
    # Both optional arguments are passed deliberately. `compute_readiness` skips the
    # evidence-class half when `package_root` is absent, and this call - the one whose
    # answer is written into the bundle as `phase-readiness.json` and read by every
    # later step - omitted it, so the gate 2.9.0 exists for ran on `$ak phase` and
    # nowhere the result was stored. `source_root` is the workspace root, which is what
    # `evidence_classes.observe` reads `input/documents` and `input/interviews` under.
    readiness = phase_readiness_contract.compute_readiness(
        classification, PROFILES, capabilities,
        package_root=PACKAGE, app_root=source_root,
    )
    profile_validation = {"status": _worst_contribution_status(contributions)}
    worst = _worst_contribution_status(contributions)
    if worst in {"INVALID", "BLOCKED"}:
        return {
            "bundle_id": None, "bundle_dir": None, "status": worst,
            "failures": _contribution_failures(contributions),
            "mode": mode_note,
        }
    # After the return above, and that position is the point. A run that could not
    # proceed at all already reports why and with what status - a managed artifact with
    # no authorization granted is BLOCKED, and so is an adapter that never ran. Placed
    # before it, this guard fired on those too and reported that a database yielded
    # nothing, which is true and useless: it replaced "you did not authorize this" with
    # a worse diagnostic. Two tests caught that within the hour.
    #
    # What is left here is the case A34 is about: a run that did the work, is otherwise
    # publishable, and is missing a database it was told to read.
    _refuse_a_required_database_that_yielded_nothing(
        manifest.artifacts, with_rows, contributions,
    )
    # Say plainly which phases this evidence actually opened. The bundle records the
    # readiness already, but an operator running one command should not have to open a
    # file to learn that the phase they came here for is still blocked.
    unreachable = sorted(
        phase for phase, value in readiness.items()
        if isinstance(value, dict) and value.get("status") == "BLOCKED"
    )
    if required_phases:
        missing = sorted(set(required_phases) & set(unreachable))
        if missing:
            raise ValueError(
                "Acquisition completed but the evidence does not reach the phases it was "
                f"required to: {', '.join(missing)}. Reasons are in the bundle's "
                "phase-readiness.json; add the missing sources and acquire again."
            )
    return bundle_assembly.assemble_bundle(
        app_id=manifest.app["id"],
        classification=classification_dict,
        rule_versions=resolved.rule_versions,
        contributions=contributions,
        normalization_config={"text": "utf-8-lf"},
        profile_validation=profile_validation,
        phase_readiness=readiness,
        # Read here rather than inside the assembler, because this is the layer that
        # knows where the workspace is. `evidence_classes` owns which directory means
        # which class, so this inventory and the readiness above cannot disagree about
        # the same files - which is exactly what A33 was.
        supplied_evidence=evidence_classes.supplied_inventory(source_root),
        output_root=Path(output_root),
        # Attributed to the manifest, because no adapter extracted it: it is a
        # statement the project makes about which store is authoritative.
        declared_capabilities={name: ["manifest"] for name in sorted(declared)},
    )


def _flag_export_drift(contributions: list[dict[str, Any]]) -> None:
    """Record when an imported export was produced from a different database file.

    A hybrid run reads schema from the live database while taking form, report and
    module definitions from an export made earlier. That is legitimate, and it is how
    an application whose VBA project cannot be loaded unattended gets acquired at all.
    What is not legitimate is doing it silently: if the database has changed since the
    export, the bundle mixes current schema with stale definitions and nothing in it
    says so. This compares the digest each export declares it came from against the
    databases actually acquired in this run.

    Recorded as a failure rather than raised: the operator may knowingly be using an
    older export, and the existing contract is that failures are carried honestly into
    the bundle instead of aborting a run that produced real evidence. Absent a declared
    ``source_database`` nothing is claimed either way - silence is not evidence of a
    match, so no drift is reported and none is denied.
    """
    acquired: dict[str, set[str]] = {}
    for contribution in contributions:
        if contribution["adapter_id"] == "imported_sources":
            continue
        for logical_id, digest in contribution["provenance"].get("source_hashes", {}).items():
            acquired.setdefault(digest, set()).add(logical_id)
    if not acquired:
        return
    for contribution in contributions:
        origins = contribution["provenance"].get("exported_from") or {}
        seen: set[str] = set()
        for logical_id, origin in sorted(origins.items()):
            digest = origin.get("sha256")
            if not digest or digest in acquired or digest in seen:
                continue
            seen.add(digest)
            contribution["failures"].append({
                "logical_id": logical_id,
                "reason": "EXPORT_SOURCE_DRIFT",
                "detail": (
                    f"This export declares it was produced from a database with digest "
                    f"{digest[:16]}..., which is not one of the databases acquired in this run "
                    f"({', '.join(sorted(name for names in acquired.values() for name in names))}). "
                    "Its definition text may be stale relative to the schema."
                ),
            })


def _contribution_failures(contributions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [failure for contribution in contributions for failure in contribution["failures"]],
        key=lambda item: (item.get("logical_id", ""), item.get("reason", "")),
    )


def _refuse_a_required_database_that_yielded_nothing(
    artifacts: tuple[Any, ...],
    databases_with_rows: set[str],
    contributions: list[dict[str, Any]],
) -> None:
    """Stop the run rather than seal a bundle missing a database it was told to read.

    A34, measured on A06. One run's DAO tier failed on the declared authoritative
    backend - `Not a valid password`, on a file the previous run had opened from the
    same local path with no password - and the run went on to publish a bundle with
    188 tables and 730 fields where the complete one has 209 and 1,215. The whole
    backend was absent, and nothing said so:

    - `bundle validate` reported VALID, because every file the layout requires existed;
    - `phase1` reported READY, because the frontend's own rows satisfied
      `access_schema_inventory`, `field_inventory` and `key_index_inventory`;
    - `backend_authority_declared` reported satisfied, from the manifest;
    - `coverage.json` recorded 730 as the figure, with no statement that a database
      was missing.

    A Phase 1 run against it would have described 60% of the schema as all of it, and
    passed QA doing so. The only reason it surfaced is that a second run existed to
    compare against.

    So a failure that loses a whole database has to end the run. `PARTIAL` was the
    alternative and it is what the run already reported - and a `PARTIAL` bundle is
    today indistinguishable downstream from a complete one, which is precisely why a
    louder status would have been ignored the same way. A refusal cannot be.

    **The contract this creates, stated so it is not a surprise:** an artifact whose
    database is legitimately empty must be declared `required: false`. There is no way
    to tell an empty database from an unread one by looking at zero rows, and of the
    two readings the expensive one to get wrong is the second.
    """
    missing = [
        artifact for artifact in artifacts
        if artifact.required
        and artifact.kind == "access_database"
        and artifact.id not in databases_with_rows
    ]
    if not missing:
        return
    detail = []
    for artifact in missing:
        reasons = [
            str(failure.get("reason", "")).strip()
            for contribution in contributions
            for failure in contribution["failures"]
            if failure.get("logical_id") == artifact.id
            and "DAO tier failed" in str(failure.get("reason", ""))
        ]
        why = reasons[0] if reasons else "no failure was recorded against it, which is its own question"
        detail.append(f"{artifact.id} ({artifact.role}): {why}")
    raise ValueError(
        "REQUIRED_DATABASE_YIELDED_NOTHING: "
        + "; ".join(detail)
        + ". No bundle was published. Re-run, and if the database is genuinely empty "
        "declare it `required: false` - a bundle missing a database it was told to "
        "read is indistinguishable downstream from a complete one. See BACKLOG A34."
    )


def _database_ids_with_rows(contributions: list[dict[str, Any]]) -> set[str]:
    """Which databases actually yielded schema, by the id the rows carry.

    Every table row records the `database_id` it came from, and that value is the
    artifact's own id - so this answers "was this file read" exactly, rather than by
    inference from a status or a failure count.
    """
    seen: set[str] = set()
    for contribution in contributions:
        for row in contribution["databases"]["tables"]:
            identifier = row.get("database_id")
            if identifier:
                seen.add(str(identifier))
    return seen


def _declaration_capabilities(
    artifacts: tuple[Any, ...], databases_with_rows: set[str] | None = None,
) -> set[str]:
    """Capabilities the manifest itself establishes, not the extracted evidence.

    ``backend_authority_declared`` is required by the backend and split-topology
    profile rules, but no adapter could ever report it - adapters describe what they
    extracted, and this one is a statement about which store the project treats as
    authoritative. Only the manifest can make it, and until it was read here Phase 1
    stayed BLOCKED on a capability nothing in the package produced.

    **A34: a declaration about a file nobody could read is not a capability.** The
    three conditions below all read the manifest, and none of them asked whether the
    declared backend had been read - so a run whose DAO tier failed on the backend,
    losing all 21 of its tables and 485 of the workspace's 1,215 fields, still
    reported this satisfied, and Phase 1 still reported READY off the frontend's own
    rows. That is A26's shape again: a gate answering the question it set itself,
    where the question was the wrong one.

    `databases_with_rows` is optional only so the existing callers that ask what a
    manifest declares - before any acquisition exists to check against - keep
    working. When it is passed, a declared backend that yielded no schema no longer
    counts as declared.
    """
    capabilities: set[str] = set()
    for artifact in artifacts:
        if not (artifact.role == "backend" and artifact.required and artifact.backend_kind):
            continue
        if databases_with_rows is not None and artifact.id not in databases_with_rows:
            continue
        capabilities.add("backend_authority_declared")
    return capabilities


def _capabilities(contributions: list[dict[str, Any]]) -> set[str]:
    capabilities: set[str] = set()
    for contribution in contributions:
        capabilities.update(contribution["provenance"].get("capabilities", []))
    return capabilities


_STATUS_RANK = {"VALID": 0, "PARTIAL": 1, "INVALID": 2, "BLOCKED": 3}


def _worst_contribution_status(contributions: list[dict[str, Any]]) -> str:
    return max(
        (contribution["status"] for contribution in contributions),
        key=lambda status: _STATUS_RANK[status],
    )
