from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(PACKAGE / "contracts"))

from adapters.base import empty_sections  # noqa: E402
from bundle_assembly import assemble_bundle  # noqa: E402
import bundle as bundle_contract  # noqa: E402

def _contribution(adapter_id: str) -> dict:
    sections = empty_sections()
    sections["code"]["access_sql"].append({"logical_id": "q1", "text": "SELECT 1", "sha256": "a" * 64})
    return {
        "adapter_id": adapter_id, "adapter_version": "1.0.0", "app_id": "SYN", "status": "PARTIAL",
        **sections, "failures": [], "provenance": {"producer": adapter_id, "source_hashes": {"q1": "a" * 64}},
    }

def _classification() -> dict:
    return {"topology": "monolith", "frontend_format": "mdb", "source_availability": "exported_only", "backend_kinds": ["embedded_access"]}

def test_assemble_writes_layout_and_lock(tmp_path: Path) -> None:
    out = assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=[_contribution("imported_sources")], normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path,
    )
    bundle_dir = Path(out["bundle_dir"])
    assert (bundle_dir / "bundle.json").is_file()
    assert (bundle_dir / "checksums.sha256").is_file()
    assert (bundle_dir / "provenance.json").is_file()
    assert (bundle_dir / "profile-validation.json").is_file()
    assert (bundle_dir / "phase-readiness.json").is_file()
    assert (bundle_dir / "coverage.json").is_file()
    assert (bundle_dir / "code" / "access-sql" / "inventory.json").is_file()
    assert (bundle_dir / "databases" / "tables.json").is_file()
    assert (bundle_dir / "evidence-sources" / "documents" / "inventory.json").is_file()
    assert (bundle_dir / "failures" / "extraction-failures.json").is_file()
    data = json.loads((bundle_dir / "bundle.json").read_text(encoding="utf-8"))
    assert data["bundle_id"] == out["bundle_id"]
    assert data["bundle_id"].startswith("bundle-")
    # Reuses canonical identity from contracts/bundle.py
    assert data["bundle_id"] == bundle_contract.compute_bundle_id({
        "app_id": "SYN", "classification": _classification(),
        "classification_rule_versions": {"topology": "1.0.0"},
        "artifacts": [{"logical_id": "q1", "content_sha256": "a" * 64}],
        "adapters": [{"id": "imported_sources", "version": "1.0.0"}],
        "bundle_schema_version": data["schema_version"], "normalization_config": {"text": "utf-8-lf"},
        # Read back from the bundle rather than restated, because the point of the
        # field is that it changes whenever this module does.
        "assembly_version": json.loads(
            (bundle_dir / "provenance.json").read_text(encoding="utf-8"))["assembly_version"],
    })
    for output_name, schema_name in (
        ("provenance.json", "bundle-provenance.schema.json"),
        ("coverage.json", "bundle-coverage.schema.json"),
    ):
        output = json.loads((bundle_dir / output_name).read_text(encoding="utf-8"))
        schema = json.loads((PACKAGE / "schemas" / schema_name).read_text(encoding="utf-8"))
        jsonschema.validate(output, schema)
    assert bundle_contract.validate_bundle(bundle_dir)["bundle_id"] == out["bundle_id"]

def test_assemble_is_deterministic_across_paths(tmp_path: Path) -> None:
    first = assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=[_contribution("imported_sources")], normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path / "a",
    )
    second = assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=[_contribution("imported_sources")], normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path / "b",
    )
    assert first["bundle_id"] == second["bundle_id"]

def test_assemble_rejects_forbidden_binary(tmp_path: Path) -> None:
    bad = _contribution("managed_access")
    bad["databases"]["objects"].append({"logical_id": "db", "raw_path": "legacy.mdb", "raw_binary": True})
    try:
        assemble_bundle(
            app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
            contributions=[bad], normalization_config={"text": "utf-8-lf"},
            profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "BLOCKED"}},
            output_root=tmp_path,
        )
    except ValueError:
        return
    raise AssertionError("assembly must reject raw binary contributions")


def _assemble(tmp_path: Path, contributions: list[dict]) -> dict:
    return assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=contributions, normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path,
    )


def test_cross_adapter_hash_conflict_is_rejected(tmp_path: Path) -> None:
    first = _contribution("imported_sources")
    second = _contribution("msaccess_vcs")
    second["provenance"]["source_hashes"]["q1"] = "b" * 64
    second["code"]["access_sql"][0]["sha256"] = "b" * 64
    try:
        _assemble(tmp_path, [first, second])
    except ValueError as exc:
        assert str(exc) == "DUPLICATE_MISMATCH:q1"
        return
    raise AssertionError("cross-adapter digest conflicts must be rejected")


def test_identical_cross_adapter_record_is_deduplicated(tmp_path: Path) -> None:
    result = _assemble(tmp_path, [_contribution("imported_sources"), _contribution("msaccess_vcs")])
    inventory = json.loads(
        (Path(result["bundle_dir"]) / "code" / "access-sql" / "inventory.json").read_text(encoding="utf-8")
    )
    assert len(inventory) == 1


def test_reassembly_reuses_identical_existing_bundle(tmp_path: Path) -> None:
    first = _assemble(tmp_path, [_contribution("imported_sources")])
    second = _assemble(tmp_path, [_contribution("imported_sources")])
    assert second == first


def test_reassembly_rejects_stale_extra_file_without_deleting_it(tmp_path: Path) -> None:
    first = _assemble(tmp_path, [_contribution("imported_sources")])
    stale = Path(first["bundle_dir"]) / "stale.txt"
    stale.write_text("stale", encoding="utf-8")
    try:
        _assemble(tmp_path, [_contribution("imported_sources")])
    except ValueError as exc:
        assert str(exc) == "BUNDLE_PATH_CONFLICT"
        assert stale.read_text(encoding="utf-8") == "stale"
        return
    raise AssertionError("stale target content must not be overwritten")


def _assemble_one(tmp_path: Path, contribution: dict):
    return assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=[contribution], normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path,
    )


# A linked Access table records its target as two facts: Connect says where the data
# lives, SourceTableName says what inside it. For a split Access application that target
# is very often another .mdb, and naming it is the investigation's purpose. The suffix
# rule rejected the structured field while letting the identical path through inside a
# read_error sentence, so the guard blocked the machine-readable form of a fact the
# bundle already carried as prose.
def test_linked_table_boundary_target_may_name_an_external_database(tmp_path: Path) -> None:
    contribution = _contribution("managed_access")
    contribution["interfaces"]["linked_tables"].append({
        "logical_id": "SYN:table:操作履歴", "name": "操作履歴", "database_id": "SYN",
        "metadata": {
            "linked": True,
            "connect": r";DATABASE=L:\新品揃支援\XP\品揃支援data.mdb",
            "source_table_name": "操作履歴",
        },
    })
    result = _assemble_one(tmp_path, contribution)
    assert result["bundle_id"]


# The allowance is scoped to those two keys and nothing wider.
def test_raw_binary_elsewhere_is_still_rejected(tmp_path: Path) -> None:
    contribution = _contribution("managed_access")
    contribution["databases"]["objects"].append({
        "logical_id": "SYN:table:x", "source_paths": ["snapshot/legacy.mdb"],
    })
    try:
        _assemble_one(tmp_path, contribution)
    except ValueError as exc:
        assert "forbidden raw binary" in str(exc)
        return
    raise AssertionError("a source path pointing at a raw database must still be rejected")


def test_raw_binary_flag_is_still_rejected_inside_metadata(tmp_path: Path) -> None:
    contribution = _contribution("managed_access")
    contribution["interfaces"]["linked_tables"].append({
        "logical_id": "SYN:table:y", "metadata": {"raw_path": "legacy.mdb", "raw_binary": True},
    })
    try:
        _assemble_one(tmp_path, contribution)
    except ValueError as exc:
        assert "carries a raw database binary" in str(exc)
        return
    raise AssertionError("a raw_binary marker must still be rejected")


def test_two_routes_reading_one_schema_yield_one_table() -> None:
    """A table read by both the managed and the imported route is one table.

    A05's frontend was acquired managed for its schema and imported for its
    definition text, and the same 22 tables, 161 fields and 46 indexes entered the
    bundle twice. `_merge_records` cannot see it: the two routes describe a table in
    two shapes, only one carrying a `logical_id`, so both are filed as unkeyed. The
    duplicates were then reported as coverage - 1,558 database records against a true
    1,327 - and as a finding, 143 table objects of which 86 lacked a primary key
    against a true 121 and 76.
    """
    from bundle_assembly import _dedupe_schema

    managed = {"database_id": "D", "name": "T", "attributes": 0, "connect": "",
               "logical_id": "D:table:T", "kind": "table", "container": "data"}
    imported = {"database_id": "D", "name": "T", "attributes": 0, "connect": ""}
    rows = [imported, managed]
    _dedupe_schema(rows, ("database_id", "name"))
    assert len(rows) == 1
    # The surviving row is the one carrying more, so nothing a route knew is lost.
    assert rows[0]["logical_id"] == "D:table:T"

    fields = [{"database_id": "D", "table": "T", "name": "f", "type": 10},
              {"database_id": "D", "table": "T", "name": "f", "type": 10}]
    _dedupe_schema(fields, ("database_id", "table", "name"))
    assert len(fields) == 1


def test_two_readings_that_disagree_are_both_kept() -> None:
    """Disagreement about the schema is a finding, not something to resolve by rule.

    Collapsing to whichever adapter sorted first would hide the one case where the
    duplicate matters.
    """
    from bundle_assembly import _dedupe_schema

    rows = [{"database_id": "D", "name": "T", "attributes": 0},
            {"database_id": "D", "name": "T", "attributes": 1, "logical_id": "x"}]
    _dedupe_schema(rows, ("database_id", "name"))
    assert len(rows) == 2


def test_a_row_without_the_identity_is_never_collapsed() -> None:
    from bundle_assembly import _dedupe_schema

    rows = [{"name": "T"}, {"name": "T"}]
    _dedupe_schema(rows, ("database_id", "name"))
    assert len(rows) == 2


def test_the_assembling_code_is_part_of_the_bundle_identity() -> None:
    """Same sources, different kit, different bundle.

    The identity derived from the source digests alone, so fixing a defect in
    `bundle_assembly` and re-running produced the same directory name with different
    content - refused as `BUNDLE_PATH_CONFLICT`, which reads as tampering when the
    cause is the kit's own code. Three bundles were moved aside by hand in one session
    before this was understood.
    """
    identity = {
        "app_id": "SYN", "classification": _classification(),
        "classification_rule_versions": {"topology": "1.0.0"},
        "artifacts": [{"logical_id": "q1", "content_sha256": "a" * 64}],
        "adapters": [{"id": "imported_sources", "version": "1.0.0"}],
        "bundle_schema_version": "2.7.3", "normalization_config": {"text": "utf-8-lf"},
        "assembly_version": "aaaaaaaaaaaa",
    }
    after = dict(identity, assembly_version="bbbbbbbbbbbb")
    assert (bundle_contract.compute_bundle_id(identity)
            != bundle_contract.compute_bundle_id(after))
    # And it is required, so a caller cannot go back to an identity without it.
    incomplete = {k: v for k, v in identity.items() if k != "assembly_version"}
    try:
        bundle_contract.compute_bundle_id(incomplete)
    except bundle_contract.BundleError as error:
        assert "assembly_version" in str(error)
        return
    raise AssertionError("an identity with no assembly_version must be refused")


def test_the_assembly_version_tracks_the_module_itself(tmp_path: Path) -> None:
    """Computed from the source, not declared.

    A version somebody has to remember to bump is wrong exactly when it matters: the
    defect being fixed is always the one that changed the output. Editing this module
    is what must change the answer, and nothing else.
    """
    import hashlib

    import bundle_assembly
    from bundle_assembly import _assembly_version

    first = _assembly_version()
    assert first == _assembly_version(), "stable while the file is unchanged"
    assert len(first) == 12

    # Recomputed here rather than by editing the module on disk: a test that rewrites
    # a file in the repository leaves it damaged if the run is interrupted, and this
    # says the same thing - the answer is that file's digest and nothing else.
    source = Path(bundle_assembly.__file__).resolve().read_bytes()
    assert first == hashlib.sha256(source).hexdigest()[:12]
    assert first != hashlib.sha256(
        source + b"# one more line of assembly code").hexdigest()[:12]


def test_a_rebuilt_bundle_says_which_code_built_it(tmp_path: Path) -> None:
    """Answerable from the bundle, which it was not before.

    The id carries the version, but a digest cannot be read back out of a digest, and
    "was this built before or after the deduplication fix" is a question people ask of
    a bundle they did not watch being built.
    """
    from bundle_assembly import _assembly_version

    out = _assemble_one(tmp_path, _contribution("imported_sources"))
    provenance = json.loads(
        (Path(out["bundle_dir"]) / "provenance.json").read_text(encoding="utf-8"))
    assert provenance["assembly_version"] == _assembly_version()


def test_coverage_counts_a_recorded_fact_as_neither_failed_nor_excluded(
    tmp_path: Path,
) -> None:
    """`failed` has to keep meaning evidence that should exist and does not.

    The failure channel carries three kinds of thing now: an object that could not be
    read, an exclusion the extractor made on purpose, and - since A22 gave the shape
    rule an evidence trail - an observation about a table it *kept*. Counting the last
    of those as a failure by subtracting only the one named kind would report a clean
    run as damaged, which is what this channel already did once.
    """
    contribution = _contribution("managed_access")
    contribution["failures"] = [
        {"logical_id": "DATA", "reason": "EXCLUDED: 3 non-model tables", "kind": "exclusion"},
        {"logical_id": "DATA", "reason": "EXCLUDED table X: A(Text) / B(Text) / C(Long)",
         "kind": "exclusion"},
        {"logical_id": "DATA", "reason": "KEPT table M: X(Text) / Y(Text) / Z(Long)",
         "kind": "observation"},
        {"logical_id": "DATA", "reason": "Could not read table T: no permission"},
    ]
    out = assemble_bundle(
        app_id="SYN", classification=_classification(), rule_versions={"topology": "1.0.0"},
        contributions=[contribution], normalization_config={"text": "utf-8-lf"},
        profile_validation={"status": "VALID"}, phase_readiness={"phase1": {"status": "LIMITED"}},
        output_root=tmp_path,
    )
    coverage = json.loads(
        (Path(out["bundle_dir"]) / "coverage.json").read_text(encoding="utf-8"))
    unclassified = coverage["object_types"]["unclassified"]
    assert unclassified["failed"] == 1, "only the unreadable table"
    assert unclassified["skipped"] == 2, "both exclusion lines"
    # And the observation is in the file, so the trail survives whatever it is counted as.
    failures = json.loads((Path(out["bundle_dir"]) / "failures"
                           / "extraction-failures.json").read_text(encoding="utf-8"))
    assert any(entry.get("kind") == "observation" for entry in failures)
