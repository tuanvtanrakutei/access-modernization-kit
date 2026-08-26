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
from classification import Classification
from manifest_v22 import load_manifest

PACKAGE = Path(__file__).resolve().parents[1]
PROFILES = PACKAGE / "profiles"


def newest_bundle(app_root: Path) -> Path | None:
    """The most recently written bundle, which is what the phases read from."""
    candidates = sorted(
        (path for path in (app_root / "acquired").glob("bundle-*") if (path / "bundle.json").is_file()),
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


def _commands(app_root: Path, manifest_path: Path, phase: int, route: str) -> list[str]:
    """Render the command for one supply route against this workspace."""
    manifest = str(manifest_path)
    if route == "runtime":
        return [
            f'python {PACKAGE / "scripts" / "ak.py"} acquire run --manifest "{manifest}" '
            f'--authorize access_snapshot_extract --require-phases {phase}',
        ]
    if route == "files":
        return [
            "# On a machine that has Microsoft Access, for each database:",
            f'#   1. import {PACKAGE / "tools" / "ExportAccessObjects.bas"} into its VBA project',
            r'#   2. run:  ExportAll "C:\evidence\<ARTIFACT_ID>"',
            f'#   3. copy that folder to {app_root / "sources"} here, then:',
            f'python {PACKAGE / "scripts" / "ak.py"} import-sources '
            f'--source "{app_root / "sources" / "<ARTIFACT_ID>"}" '
            f'--producer-id ExportAccessObjects.bas --producer-version 1.0.0 '
            f'--logical-id-prefix <ARTIFACT_ID> --source-database "sources/access/<FILE>.mdb"',
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
    bundle_dir = newest_bundle(app_root)
    present, origin = supplied_capabilities(bundle_dir) if bundle_dir else (set(), {})

    # A waiver is granted against the capability, then reported, so the phase can
    # proceed while the record still says what was not proven.
    effective = set(present) | set(waived)
    report = evidence_requirements.requirements(
        phase, classification, PROFILES, effective, origin,
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
    return report
