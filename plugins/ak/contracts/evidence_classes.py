"""Observe which classes of evidence a workspace actually holds, and what is missing.

Readiness measured capabilities, and every capability a bundle can produce on its
own is structural. So a phase gate could be fully satisfied by two `.mdb` files and
still be unable to say what any table is for - which is what happened, and what the
run said about itself: "purpose not established from schema alone".

This module reads `specifications/evidence-classes.yaml` and answers two questions
readiness could not:

- which evidence classes are present, and on what basis;
- for a phase, which required class is absent (it blocks) and which optional class
  is absent (it publishes, and the document loses something this names).

It decides nothing. Blocking stays the caller's decision, as with every other
contract here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

SPEC_NAME = "evidence-classes.yaml"

# A capability is evidence that a class is present: the bundle could only report it
# by having read the thing. The reverse does not hold - no capability can prove a
# document exists, which is exactly why the structural gates were not enough.
CLASS_FROM_CAPABILITY: dict[str, str] = {
    "access_schema_inventory": "SCHEMA",
    "server_object_inventory": "SCHEMA",
    "external_schema_inventory": "SCHEMA",
    "field_inventory": "SCHEMA",
    "key_index_inventory": "SCHEMA",
    "boundary_inventory": "SCHEMA",
    "vba_query_inventory": "CODE",
    "compiled_object_inventory": "CODE",
    "access_object_inventory": "UI_DEFINITION",
    "ui_object_inventory": "UI_DEFINITION",
    "document_inventory": "DOCUMENT",
    "backend_authority_declared": "OPERATOR_DECLARATION",
}

# Where an operator puts each kind of input. A class is present when at least one
# file sits under one of its locations - an empty directory is not evidence, and
# scaffolding creates empty directories.
# Both layouts, because a workspace acquired before 2.10.0 keeps sources/ and a
# class present there is present.
CLASS_LOCATIONS: dict[str, tuple[str, ...]] = {
    "SCREENSHOT": ("input/screenshots", "sources/screenshots"),
    "SAMPLE_DATA": ("input/samples", "sources/samples"),
    "OUTPUT_SAMPLE": ("input/report-samples", "sources/reports-out"),
    # Only where a person puts a document. The normalizer's corpus is not a
    # location: it holds every normalized source, so reading it as document
    # evidence let a project with no documents at all satisfy Phase 5.
    "DOCUMENT": ("input/documents", "input/shared-docs", "sources/documents", "shared-docs"),
    "INTERVIEW": ("input/interviews", "sources/interviews", "decisions/interviews"),
}


def load_contract(package_root: Path) -> dict[str, Any]:
    path = Path(package_root) / "specifications" / SPEC_NAME
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


# Files that sit in an evidence directory without being evidence. The question
# `_has_files` answers is "did a person put evidence of this class here", and any file
# at all used to answer it yes - so a `Thumbs.db` Windows wrote while somebody browsed
# `input/screenshots/`, or a `.gitkeep` holding an empty directory in version control,
# reported a whole evidence class present and moved a phase's readiness with it. That
# is the same failure this module exists to prevent, arriving through the module
# itself.
#
# A closed set of names rather than a pattern, and lowercase-compared because Windows
# writes `Thumbs.db` and `desktop.ini` in the cases it feels like. A looser rule would
# eventually drop a file somebody meant as evidence, which is the more expensive
# mistake: a missing class is reported and argued about, a silently discarded one is
# not.
NOT_EVIDENCE_FILENAMES = frozenset({
    "readme.md",      # the kit's own guide to the directory it sits in
    ".gitkeep", ".keep", ".gitignore", ".gitattributes",
    "thumbs.db", "desktop.ini", ".ds_store",
})


def _has_files(directory: Path) -> bool:
    if not directory.is_dir():
        return False
    return any(
        item.is_file() and item.name.lower() not in NOT_EVIDENCE_FILENAMES
        for item in directory.rglob("*")
    )


def observe(
    capabilities: set[str] | None = None,
    app_root: Path | str | None = None,
) -> dict[str, list[str]]:
    """Present classes, each mapped to what shows it is present.

    Both inputs are optional so a caller with only one of them still gets an
    honest partial answer rather than an exception.
    """
    found: dict[str, list[str]] = {}
    for capability in sorted(capabilities or ()):
        name = CLASS_FROM_CAPABILITY.get(capability)
        if name:
            found.setdefault(name, []).append(f"capability:{capability}")
    if app_root is not None:
        root = Path(app_root)
        for name, locations in CLASS_LOCATIONS.items():
            for relative in locations:
                if _has_files(root / relative):
                    found.setdefault(name, []).append(f"path:{relative}")
    return found


def phase_status(
    phase: str,
    present: set[str],
    contract: dict[str, Any],
) -> dict[str, Any]:
    """What this phase has, lacks outright, and lacks at a cost.

    `blocking` names a class the phase cannot proceed without. `degradations` name
    a class whose absence the phase survives, with the cost stated - so an operator
    reads what the document will not be able to say, not that something is missing.
    """
    needs = (contract.get("phase_needs") or {}).get(phase)
    if not needs:
        return {"phase": phase, "known": False, "blocking": [], "degradations": []}

    required = [name for name in needs.get("required", []) if name != "PRIOR_PHASES"]
    blocking = [name for name in required if name not in present]

    degradations: list[dict[str, str]] = []
    for entry in needs.get("degraded_without") or []:
        alternatives = [entry[key] for key in ("class", "or") if key in entry]
        if any(name in present for name in alternatives):
            continue
        degradations.append({
            "classes": alternatives,
            "costs": entry.get("costs", ""),
        })

    return {
        "phase": phase,
        "known": True,
        "characteristic_claim": needs.get("characteristic_claim", ""),
        "required": required,
        "blocking": blocking,
        "degradations": degradations,
    }


def how_to_supply(class_name: str, contract: dict[str, Any]) -> dict[str, Any]:
    """What this class is, where it goes, and why nothing else will do instead."""
    entry = (contract.get("evidence_classes") or {}).get(class_name) or {}
    return {
        "class": class_name,
        "means": entry.get("means", ""),
        # The first location is where this layout puts it. The rest are read as well,
        # so a pre-2.10.0 workspace is not told to move anything, but an operator
        # being told where to put a file needs one answer.
        "put_it_in": (list(CLASS_LOCATIONS.get(class_name, ()))[:1]
                      or ["declared as a manifest artifact"]),
        "also_read": list(CLASS_LOCATIONS.get(class_name, ()))[1:],
        "supports": entry.get("supports") or [],
        "note": (entry.get("note") or "").strip(),
    }


def claim_is_supportable(
    claim_kind: str,
    class_name: str,
    contract: dict[str, Any],
) -> tuple[bool, str]:
    """Rule EC-01 and its neighbours, as a function.

    Returns whether a claim of this kind may rest on this class alone, and when it
    may not, which rule says so.
    """
    entry = (contract.get("evidence_classes") or {}).get(class_name)
    if entry is None:
        return False, f"unknown evidence class {class_name}"
    if claim_kind in (entry.get("supports") or []):
        return True, ""
    if claim_kind in (entry.get("cannot_support") or []):
        rule = "EC-02" if claim_kind == "FORMAT" else "EC-01"
        return False, f"{rule}: {class_name} cannot support a {claim_kind} claim"
    if claim_kind in (entry.get("corroborates") or []):
        return False, f"{class_name} corroborates {claim_kind}; it never settles one"
    return False, f"{class_name} does not declare support for {claim_kind}"
