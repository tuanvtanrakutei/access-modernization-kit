from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import jsonschema

import bundle as bundle_contract

# Where a legacy system's own external dependency is recorded. A linked Access table
# keeps its target as two facts - Connect says where, SourceTableName says what - and for
# a split Access application that target is very often another .mdb. Naming it is the
# investigation's purpose, not a leak: the bundle still never carries a database and never
# reads one. The suffix rule stays in force everywhere else, so a source_path or an
# artifact reference to a raw binary is rejected exactly as before.
BOUNDARY_TARGET_KEYS = frozenset({"connect", "source_table_name"})


def _guard_no_binaries(contributions: list[dict[str, Any]]) -> None:
    for contribution in contributions:
        _guard_value(contribution, None)


def _guard_value(value: Any, key: str | None) -> None:
    if isinstance(value, dict):
        if value.get("raw_binary") is True or "raw_path" in value:
            raise ValueError("Contribution carries a raw database binary")
        for item_key, item in value.items():
            _guard_value(item, item_key)
    elif isinstance(value, list):
        for item in value:
            _guard_value(item, key)
    elif isinstance(value, str):
        if key in BOUNDARY_TARGET_KEYS:
            return
        if Path(value).suffix.lower() in bundle_contract.FORBIDDEN_SUFFIXES:
            raise ValueError("Contribution references a forbidden raw binary")

def _logical_artifacts(contributions: list[dict[str, Any]]) -> list[dict[str, str]]:
    artifacts: dict[str, str] = {}
    for contribution in contributions:
        for logical_id, digest in contribution["provenance"]["source_hashes"].items():
            previous = artifacts.get(logical_id)
            if previous is not None and previous != digest:
                raise ValueError(f"DUPLICATE_MISMATCH:{logical_id}")
            artifacts[logical_id] = digest
    return [{"logical_id": key, "content_sha256": artifacts[key]} for key in sorted(artifacts)]


def _merge_records(target: list[dict[str, Any]], incoming: list[dict[str, Any]]) -> None:
    keyed: dict[tuple[str, str], dict[str, Any]] = {}
    unkeyed: list[dict[str, Any]] = []
    for record in [*target, *incoming]:
        logical_id = record.get("logical_id")
        digest = record.get("sha256")
        if logical_id is None or digest is None:
            unkeyed.append(record)
            continue
        keyed.setdefault((str(logical_id), str(digest)), record)
    target[:] = [keyed[key] for key in sorted(keyed)] + sorted(
        unkeyed, key=lambda item: json.dumps(item, ensure_ascii=False, sort_keys=True)
    )


# A table cannot appear twice in one database, nor a field twice in one table. The
# flat schema inventories therefore have a natural key, and it is not `logical_id`:
# two routes reading the same DAO schema describe the same table in two shapes, one
# carrying `logical_id` and one not, so `_merge_records` files both as unkeyed and
# keeps both.
#
# Observed on A05, where the frontend was acquired managed for its schema and
# imported for its definition text: 22 tables, 161 fields and 46 index rows appeared
# twice, and the duplicates were reported as coverage - 1,558 database records where
# there were 1,327 - and as findings, 143 table objects of which 86 without a primary
# key, against a true 121 and 76.
SCHEMA_IDENTITY = {
    "tables": ("database_id", "name"),
    "fields": ("database_id", "table", "name"),
    "indexes": ("database_id", "table", "name"),
}

# Present because a route recorded where it read the row, not because the row says
# something different about the schema.
PROVENANCE_KEYS = frozenset({
    "logical_id", "id", "source_paths", "container", "module_hint", "depends_on",
    "metadata", "kind",
})


def _dedupe_schema(records: list[dict[str, Any]], identity: tuple[str, ...]) -> None:
    """Collapse rows describing the same schema element, unless they disagree.

    Two readings that agree on every column they share are one fact reported twice,
    and the row carrying more columns is kept. Two readings that disagree are a real
    discrepancy about the schema: both are kept, so it shows up as a duplicate in the
    catalogue rather than being resolved by whichever adapter happened to sort first.
    """
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    order: list[tuple[Any, ...]] = []
    for record in records:
        if not all(field in record for field in identity):
            key = (id(record),)
        else:
            key = tuple(record[field] for field in identity)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(record)

    collapsed: list[dict[str, Any]] = []
    for key in order:
        group = groups[key]
        if len(group) == 1:
            collapsed.extend(group)
            continue
        richest = max(group, key=len)
        agrees = all(
            record[column] == richest[column]
            for record in group
            for column in set(record) & set(richest) - PROVENANCE_KEYS
        )
        collapsed.extend([richest] if agrees else group)
    records[:] = collapsed


def _merge_sections(contributions: list[dict[str, Any]]) -> dict[str, Any]:
    from adapters.base import empty_sections

    merged = empty_sections()
    for contribution in sorted(contributions, key=lambda item: item["adapter_id"]):
        for group in ("databases", "code", "ui", "interfaces"):
            for key, values in contribution[group].items():
                _merge_records(merged[group][key], values)
        for key in ("documents", "screenshots", "reports", "samples"):
            _merge_records(
                merged["evidence_sources"][key]["inventory"],
                contribution["evidence_sources"][key]["inventory"]
            )
    for key, identity in SCHEMA_IDENTITY.items():
        _dedupe_schema(merged["databases"][key], identity)
    return merged


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*")) if path.is_file()
    }


# Everything whose bytes decide bytes that end up inside a published bundle, relative
# to the package root. Written out rather than globbed: each entry is here because
# something it produces is stored, so adding or removing one is a decision somebody
# makes and can be argued with, not a directory sweep that quietly grows.
#
# What is deliberately absent is as much of the rule as what is present. The adapters
# state their own versions and are already in the identity; the schemas state theirs;
# `profiles/*.yaml` reaches the identity as `classification_rule_versions`. A module
# that only reads the bundle, or only decides what is *shown* rather than what is
# written, does not belong here.
_IDENTITY_SOURCES = (
    # This module: the layout, the merge, and every file written into a bundle.
    "contracts/bundle_assembly.py",
    # Computes phase-readiness.json, profile-validation.json and the mode note, all
    # three of which are stored. This is the one A28 was about.
    "contracts/acquisition_orchestrator.py",
    # Turns capabilities and classes into the statuses inside phase-readiness.json.
    "contracts/phase_readiness.py",
    # The class half of those statuses.
    "contracts/evidence_classes.py",
    # The contract that half reads. It carries a declared `version`, and a declared
    # version is not what belongs here for the reason given below - A13b already
    # found a rule set in this kit whose declared version had gone decorative.
    "specifications/evidence-classes.yaml",
)


def _assembly_version(package: Path | None = None) -> str:
    """A digest of the code that decides a bundle's contents, for its identity.

    The identity derived from the source digests alone, so fixing a defect in this
    module and re-running the same sources produced the same directory name with
    different content - refused as `BUNDLE_PATH_CONFLICT`, a message that reads as
    tampering when the cause was the kit's own code changing. Three bundles had to be
    moved aside by hand in one session. A re-assembly by different code is a different
    bundle, and both should be keepable.

    Computed rather than declared. A version somebody has to remember to bump is wrong
    exactly when it matters, because the defect being fixed is always the one that
    changed the output. The cost is that a comment-only edit also yields a new id and
    so a second directory; that is the cheaper mistake by a wide margin.

    It covered this module and no more until A28, and that boundary was too narrow by
    exactly the amount that mattered: A26 changed one call in the orchestrator, the
    statuses in `phase-readiness.json` changed completely, and the id did not move.
    The set it covers now is `_IDENTITY_SOURCES`, and the rule for membership is
    written there rather than left to be inferred from the list.

    `package` is here for one caller: the regression that proves every member of the
    set is load-bearing, by mutating each in a copied tree and asserting the digest
    moves. Omitting it gives the real package, which is the only thing production does.
    """
    package = Path(package) if package is not None else Path(__file__).resolve().parents[1]
    digest = hashlib.sha256()
    for relative in _IDENTITY_SOURCES:
        # The name is hashed alongside the bytes so that renaming a member, or
        # reordering the tuple, cannot silently produce the same digest.
        digest.update(relative.encode("utf-8"))
        digest.update(hashlib.sha256((package / relative).read_bytes()).digest())
    return digest.hexdigest()[:12]


def _publish_bundle(staged: Path, target: Path) -> None:
    if target.exists():
        if _tree_hashes(target) != _tree_hashes(staged):
            # Same sources, same assembling code, different bytes. Both of the causes
            # the kit knows about are now in the identity, so this says what is left:
            # something outside the kit wrote into a published bundle.
            raise ValueError("BUNDLE_PATH_CONFLICT")
        return
    staged.replace(target)

def assemble_bundle(
    app_id: str,
    classification: dict[str, Any],
    rule_versions: dict[str, str],
    contributions: list[dict[str, Any]],
    normalization_config: dict[str, Any],
    profile_validation: dict[str, Any],
    phase_readiness: dict[str, Any],
    output_root: Path,
    declared_capabilities: dict[str, list[str]] | None = None,
    schema_version: str = "2.7.3",
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
        "assembly_version": _assembly_version(),
    }
    bundle_id = bundle_contract.compute_bundle_id(identity)
    merged = _merge_sections(contributions)
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
    provenance = _provenance(bundle_id, schema_version, contributions, declared_capabilities)
    output = Path(output_root).expanduser().resolve() / "bundles"
    output.mkdir(parents=True, exist_ok=True)
    bundle_dir = output / bundle_contract.bundle_dir_name(bundle_id)
    # The staging prefix used the full id and produced a path long enough to hit the
    # Windows limit on a deep workspace. Eight characters distinguish it just as well
    # inside a directory that holds one temporary at a time.
    staged = Path(tempfile.mkdtemp(prefix=f".{bundle_dir.name}.", dir=output))
    try:
        _write_layout(staged, merged, contributions, bundle_id, schema_version)
        _write_json(staged / "profile-validation.json", profile_validation)
        _write_json(staged / "phase-readiness.json", phase_readiness)
        _write_json(staged / "bundle.json", bundle_json)
        _write_json(staged / "provenance.json", provenance)
        _validate_json(staged / "provenance.json", "bundle-provenance.schema.json")
        _validate_json(staged / "coverage.json", "bundle-coverage.schema.json")
        _write_checksums(staged)
        bundle_contract.validate_bundle(staged)
        _publish_bundle(staged, bundle_dir)
    finally:
        if staged.exists():
            shutil.rmtree(staged)
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
    for key, name in (("linked_tables", "linked-tables.json"),
                      ("file_interfaces", "file-interfaces.json"),
                      ("connections_redacted", "connections.redacted.json"),
                      # The declared column layout of a text link, which is the only
                      # copy that does not need the upstream file to be reachable.
                      ("imex_specs", "imex-specs.json")):
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
    def counts(extracted: int, failed: int = 0, skipped: int = 0) -> dict[str, int]:
        return {"extracted": extracted, "skipped": skipped, "failed": failed, "unsupported": 0}

    # "This object could not be read" and "this object was excluded on purpose" are
    # different facts. Sharing one channel made a clean run report failures it never
    # had; "failed" has to keep meaning evidence that should exist and does not.
    # Counted by what an entry declares itself to be, not by subtracting the one kind
    # that had a name. An entry carrying any kind is a fact the extractor chose to
    # record; only an unclassified one is evidence that should exist and does not.
    excluded = sum(1 for item in failures if item.get("kind") == "exclusion")
    unreadable = sum(1 for item in failures if not item.get("kind"))

    return {
        "schema_version": schema_version,
        "bundle_id": bundle_id,
        "object_types": {
            "database": counts(sum(len(values) for values in merged["databases"].values())),
            "code": counts(sum(len(values) for values in merged["code"].values())),
            "ui": counts(sum(len(values) for values in merged["ui"].values())),
            "interface": counts(sum(len(values) for values in merged["interfaces"].values())),
            "unclassified": counts(0, unreadable, excluded),
        },
    }

def _capability_origins(contributions: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Which adapter established each capability.

    The readiness verdict was persisted while the capabilities behind it were not, so
    a later phase could read that Phase 1 was READY and still not know what had been
    supplied - and would ask for it again.
    """
    origins: dict[str, set[str]] = {}
    for contribution in contributions:
        adapter = str(contribution.get("adapter_id", "unknown"))
        for capability in contribution.get("provenance", {}).get("capabilities", []) or []:
            origins.setdefault(str(capability), set()).add(adapter)
    return {name: sorted(adapters) for name, adapters in sorted(origins.items())}


def _provenance(
    bundle_id: str, schema_version: str, contributions: list[dict[str, Any]],
    declared_capabilities: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    sources: list[dict[str, str]] = []
    for contribution in sorted(contributions, key=lambda item: item["adapter_id"]):
        producer = contribution["provenance"]["producer"]
        producer_version = contribution["provenance"].get("producer_version", contribution["adapter_version"])
        # An adapter may name a producer per source. One run can import several export
        # packages made by different tools at different times, and recording only the
        # adapter-level producer made the bundle claim they all came from one place -
        # with the adapter's own version standing in for the producer's.
        per_source = contribution["provenance"].get("source_producers") or {}
        exported_from = contribution["provenance"].get("exported_from") or {}
        for logical_id, digest in sorted(contribution["provenance"]["source_hashes"].items()):
            declared = per_source.get(logical_id) or {}
            source = {
                "logical_artifact_id": logical_id, "sha256": digest,
                "producer": declared.get("producer", producer),
                "producer_version": declared.get("producer_version", producer_version),
                "transformation": contribution["adapter_id"],
            }
            origin = exported_from.get(logical_id)
            if origin:
                source["exported_from"] = origin
            sources.append(source)
    return {
        "schema_version": schema_version, "bundle_id": bundle_id, "sources": sources,
        # Which code assembled this. It is part of the identity, so it is already
        # implied by the id; stated here because a digest cannot be read back, and
        # "was this built before or after the deduplication fix" is a question people
        # ask of a bundle they did not watch being built.
        "assembly_version": _assembly_version(),
        "capabilities": {**_capability_origins(contributions), **(declared_capabilities or {})},
    }

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
