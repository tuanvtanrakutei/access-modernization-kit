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

import hashlib
import json
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
    # A36. `access_object_inventory` and `ui_object_inventory` both stood for
    # UI_DEFINITION, and both fire when the bundle merely holds ui *rows* - which the
    # DAO tier produces from object names, with no definition anywhere. The class says
    # what it needs in its own words: "SaveAsText form and report definitions: record
    # sources, bound fields, event procedures, embedded controls". A06 held 38 form
    # names, `$ak derive` distilled 0 UI objects from them, and phase2 read READY.
    #
    # Those two capabilities still exist and the profile rules still require them -
    # they prove the objects are *there*, which is a real and different thing. They no
    # longer answer for the definitions.
    "ui_definition_text": "UI_DEFINITION",
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
    # A38. Not `input/decisions`, which holds the two YAML files the kit manages and
    # reads by name; a scope decision is a document a person wrote, and it needs a
    # place where being there is what declares it.
    "TARGET_INTENT": ("input/target-intent",),
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


def supplied_inventory(app_root: Path | str) -> list[dict[str, Any]]:
    """Every file a person put in a class directory, with its class and its digest.

    Deliberately built from `CLASS_LOCATIONS` and `_has_files`' exclusion rule, which
    is the same pair `observe` reads. That is the whole point: A33 was the bundle and
    its own `phase-readiness.json` disagreeing about the same evidence, because
    readiness read the directories and the bundle read the manifest. Two readers of one
    map cannot drift.

    The manifest-declared artifacts stay in their own inventory under
    `evidence-sources/`, and that separation is deliberate rather than tidy: those four
    buckets are a contract the adapters write into - `adapters/base.py` and two adapter
    modules append to them, and both bundle schemas require exactly those keys. Nothing
    produces this inventory but a person putting a file somewhere, and collapsing the
    two would lose the distinction between evidence somebody declared and evidence
    somebody dropped - which is the distinction `OPERATOR_DECLARATION` exists to mark
    everywhere else in this contract.

    Sorted by path so the digest over it is stable, and carrying no timestamps for the
    same reason: re-acquiring unchanged evidence must produce the same bundle.
    """
    root = Path(app_root)
    records: list[dict[str, Any]] = []
    for name in sorted(CLASS_LOCATIONS):
        for relative in CLASS_LOCATIONS[name]:
            directory = root / relative
            if not directory.is_dir():
                continue
            for item in sorted(directory.rglob("*")):
                if not item.is_file() or item.name.lower() in NOT_EVIDENCE_FILENAMES:
                    continue
                digest = hashlib.sha256()
                with item.open("rb") as handle:
                    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                        digest.update(chunk)
                records.append({
                    "evidence_class": name,
                    "path": item.relative_to(root).as_posix(),
                    "sha256": digest.hexdigest(),
                    "bytes": item.stat().st_size,
                })
    return records


def supplied_digest(records: list[dict[str, Any]]) -> str:
    """One value for a whole evidence set, for the bundle's identity.

    A digest rather than the list itself. The list is written into the bundle where it
    can be read and followed; what the identity needs is only for a different evidence
    set to be a different bundle, and embedding fifty-four records to say that would
    put the same content in two places and make the identity grow with the project.
    """
    canonical = json.dumps(
        [[record["evidence_class"], record["path"], record["sha256"]] for record in records],
        ensure_ascii=False, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


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
    supports = entry.get("supports") or []
    if claim_kind in (entry.get("cannot_support") or []):
        # Which rule the caller is being refused by, named correctly. A class that
        # supports SCOPE is a statement about the system being built, so asking it for
        # a claim about the legacy application is EC-07 rather than EC-01 - and a
        # message naming the wrong rule sends a reader to the wrong paragraph, which
        # is its own small version of this kit's recurring defect.
        if "SCOPE" in supports:
            rule = "EC-07"
        elif claim_kind == "FORMAT":
            rule = "EC-02"
        else:
            rule = "EC-01"
        return False, f"{rule}: {class_name} cannot support a {claim_kind} claim"
    if claim_kind in (entry.get("corroborates") or []):
        return False, f"{class_name} corroborates {claim_kind}; it never settles one"
    if claim_kind == "SCOPE":
        return False, (f"EC-07: a SCOPE claim requires TARGET_INTENT; {class_name} is "
                       "evidence about the legacy application")
    return False, f"{class_name} does not declare support for {claim_kind}"
