"""Report one phase's evidence position for a real workspace, with runnable commands.

Two things an operator needs that nothing produced before: what is already supplied
and therefore must not be asked for again, and the exact command that would supply
what is missing. The first comes from the newest bundle's provenance, so evidence
acquired for Phase 1 is not requested again at Phase 3. The second is rendered
against this workspace's own paths, because "supply an export package" is not an
instruction anybody can follow.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import evidence_requirements
import workspace as workspace_contract
from classification import Classification
from manifest_v22 import REQUESTABLE_PHASES, load_manifest, requested_phases

PACKAGE = Path(__file__).resolve().parents[1]
PROFILES = PACKAGE / "profiles"


def newest_bundle(app_root: Path) -> Path | None:
    """The most recently written bundle, which is what the phases read from.

    Resolved by contracts/workspace.py, which knows every layout this kit has
    written: `.ak/bundles/` now, `acquired/bundles/` from 2.9.0, and the older
    `acquired/bundle-<64 hex>/`. Recency comes from the file rather than the name,
    so a workspace holding several is ordered correctly.
    """
    candidates = sorted(
        workspace_contract.find_bundle_dirs(workspace_contract.Workspace(app_root)),
        key=lambda path: (path / "bundle.json").stat().st_mtime,
    )
    return candidates[-1] if candidates else None


def supplied_capabilities(bundle_dir: Path) -> tuple[set[str], dict[str, str]]:
    """Which capabilities the bundle proves, and which adapter established each.

    Read from provenance.json, where the bundle records it. Attribution is what makes
    "already supplied" reviewable: an operator can see field_inventory came from a
    runtime extraction rather than take it on trust.
    """
    present: set[str] = set()
    origin: dict[str, str] = {}
    provenance_path = bundle_dir / "provenance.json"
    if provenance_path.is_file():
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        for capability, adapters in (provenance.get("capabilities") or {}).items():
            present.add(str(capability))
            origin[str(capability)] = ", ".join(str(item) for item in adapters) or "present"
    if present:
        return present, origin
    # A bundle written before capabilities were persisted still says which phases it
    # reached, so the phases it satisfied are treated as supplied rather than asked
    # for again. Attribution is unavailable, and says so.
    readiness_path = bundle_dir / "phase-readiness.json"
    if readiness_path.is_file():
        readiness = json.loads(readiness_path.read_text(encoding="utf-8"))
        for name, value in readiness.items():
            if not isinstance(value, dict) or value.get("status") == "BLOCKED":
                continue
            baseline = evidence_requirements.required_capabilities(name)
            for capability in baseline["all"]:
                present.add(capability)
                origin[capability] = "an earlier bundle (capabilities not recorded)"
    return present, origin


# Which supply route answers a blocking evidence class, where a command can say it.
#
# A36's last part. The remedy above is rendered for every entry in `missing`, which is
# the *capability* half - and after the class map was corrected, UI_DEFINITION blocks
# while both name capabilities stay satisfied, so `missing` is empty and no command was
# rendered at all. The class half reported `put_it_in: declared as a manifest artifact`
# and stopped, which is true and helps nobody holding an .mdb.
#
# Only classes whose remedy is a command belong here. DOCUMENT, INTERVIEW, SCREENSHOT,
# SAMPLE_DATA and OUTPUT_SAMPLE are deliberately absent: their remedy is a person
# supplying a file, which `put_it_in` already names and no command can perform.
CLASS_SUPPLY_ROUTE = {
    "UI_DEFINITION": "files",
    "CODE": "files",
    "SCHEMA": "runtime",
}


def _commands(app_root: Path, manifest_path: Path, phase: int, route: str) -> list[str]:
    """Render the command for one supply route against this workspace."""
    manifest = str(manifest_path)
    if route == "runtime":
        return [
            f'python {PACKAGE / "scripts" / "ak.py"} acquire run --manifest "{manifest}" '
            f'--authorize access_snapshot_extract --require-phases {phase}',
        ]
    if route == "files":
        # Every line here was wrong in a way only somebody following it would find, and
        # A36 is why nobody had: the block is emitted only when the class is missing,
        # and a name inventory was answering for UI_DEFINITION, so it never printed.
        # The Sub was named `ExportAll`, which does not exist - it is
        # `ExportAccessObjects` - and all three paths still said `sources/`, which
        # 2.10.0 renamed to `input/`. The dated folder is the tool's own rule:
        # `$ak completeness` compares an export against the previous reading of the
        # same object, and overwriting removes the thing it compares against.
        exports = app_root / "input" / "exports" / "<ARTIFACT_ID>-<YYYY-MM-DD>"
        return [
            "# On a machine that has Microsoft Access, for each database:",
            "#   0. open it holding SHIFT, so failing startup code cannot stop you",
            f'#   1. import {PACKAGE / "tools" / "ExportAccessObjects.bas"} into its VBA project',
            f'#   2. in the Immediate window (Ctrl+G), run:',
            f'#        ExportAccessObjects "{exports}"',
            "#      A new dated folder each time, beside the last rather than over it.",
            f'python {PACKAGE / "scripts" / "ak.py"} import-sources '
            f'--source "{exports}" '
            f'--producer-id ExportAccessObjects.bas --producer-version <YYYY-MM-DD> '
            f'--logical-id-prefix <ARTIFACT_ID> '
            f'--source-database "input/access/<FILE>.mdb"',
            "# then declare the export beside the database in the manifest, with",
            "# runtime.skip_object_inventory on the managed artifact so the same objects",
            "# are not registered twice, and:",
            f'python {PACKAGE / "scripts" / "ak.py"} acquire run --manifest "{manifest}" '
            f'--require-phases {phase}',
        ]
    if route == "declare":
        return [f'# edit {manifest_path}']
    return ["# analyst work; no command produces this"]


def phase_report(
    app_root: Path,
    phase: int,
    waived: tuple[str, ...] = (),
    reason: str | None = None,
) -> dict[str, Any]:
    manifest_path = app_root / "manifest.yaml"
    manifest = load_manifest(manifest_path)
    if manifest.classification is None:
        return {
            "phase": f"phase{phase}", "status": "BLOCKED",
            "reasons": ["manifest declares no classification; run profile detect first"],
            "satisfied": [], "missing": [], "waived": [],
        }
    classification = Classification(
        manifest.classification.topology, manifest.classification.frontend_format,
        manifest.classification.source_availability, tuple(manifest.classification.backend_kinds),
    )
    # A phase the project declined is not a phase to report evidence for. Without this
    # the same manifest answered two ways: `outputs.phases` said phase 6 is not
    # produced, and this report said phase 6 is READY - so an operator reading it would
    # go and supply evidence for a document nobody was going to write.
    if f"phase{phase}" in REQUESTABLE_PHASES and not requested_phases(
            manifest_path.read_text(encoding="utf-8")).get(f"phase{phase}", True):
        return {
            "phase": f"phase{phase}", "status": "NOT_REQUESTED",
            "reasons": [
                f"manifest outputs.phases declines phase{phase}; no evidence is needed "
                f"for a document this project does not produce. Set it to true and "
                f"re-run `$ak advance` to request it - the gate promotes, and nothing "
                f"already published is affected."
            ],
            "satisfied": [], "missing": [], "waived": [],
        }

    bundle_dir = newest_bundle(app_root)
    present, origin = supplied_capabilities(bundle_dir) if bundle_dir else (set(), {})

    # A waiver is granted against the capability, then reported, so the phase can
    # proceed while the record still says what was not proven.
    effective = set(present) | set(waived)
    report = evidence_requirements.requirements(
        phase, classification, PROFILES, effective, origin,
        package_root=PACKAGE, app_root=app_root,
    )
    report["bundle"] = str(bundle_dir) if bundle_dir else None
    report["waived"] = [{"capability": name, "reason": reason} for name in waived]
    for gap in report["missing"]:
        rendered: list[dict[str, Any]] = []
        for item in gap.get("supply", []):
            rendered.append({
                **item,
                "commands": _commands(app_root, manifest_path, phase, item["route"]),
            })
        gap["supply"] = rendered
    # And for a class that blocks with every capability satisfied, which is the state
    # A36 left behind once a name inventory stopped answering for the definitions.
    for blocked in (report.get("evidence") or {}).get("blocking") or []:
        route = CLASS_SUPPLY_ROUTE.get(blocked.get("class"))
        if route:
            blocked["commands"] = _commands(app_root, manifest_path, phase, route)
    return report
