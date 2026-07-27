from __future__ import annotations

import json
import sys
from pathlib import Path

import jsonschema
import pytest
import yaml

PACKAGE = Path(__file__).resolve().parents[1]
PROFILES = PACKAGE / "profiles"
sys.path.insert(0, str(PACKAGE / "contracts"))


def test_all_rule_fragments_validate_and_ids_are_unique() -> None:
    schema = json.loads(
        (PACKAGE / "schemas" / "classification-rule.schema.json").read_text(encoding="utf-8")
    )
    files = {
        "topology": "topology.yaml",
        "frontend": "frontend.yaml",
        "source_availability": "source-availability.yaml",
        "backend": "backend.yaml",
    }
    seen: set[str] = set()
    for dimension, filename in files.items():
        rules = yaml.safe_load((PROFILES / filename).read_text(encoding="utf-8"))["rules"]
        assert rules
        for rule in rules:
            jsonschema.validate(rule, schema)
            assert rule["dimension"] == dimension
            assert rule["id"] not in seen
            seen.add(rule["id"])


def test_adp_rule_requires_sql_server_schema() -> None:
    rules = yaml.safe_load((PROFILES / "frontend.yaml").read_text(encoding="utf-8"))["rules"]
    adp = next(rule for rule in rules if rule["id"] == "frontend.adp.sql_server_context")
    assert "sql_server_schema_evidence" in adp["require"]["all"]
    assert adp["affects"]["phase1"] == "BLOCKED"
    assert adp["affects"]["phase3"] == "BLOCKED"


def test_resolve_returns_rule_ids_and_versions() -> None:
    from classification import Classification, resolve_classification

    classification = Classification(
        "split_file", "mdb", "full", ("access_file", "text_or_csv")
    )
    resolved = resolve_classification(classification, PROFILES)
    assert "topology.split_file.backend_required" in resolved.rule_ids
    assert resolved.rule_versions["frontend.mdb.dao"] == "1.0"


def test_alias_disagreement_fails() -> None:
    from classification import Classification, ClassificationError, reconcile_alias

    classification = Classification("split_file", "mdb", "full", ("access_file",))
    reconcile_alias("access-file-split", classification)
    with pytest.raises(ClassificationError):
        reconcile_alias("access-adp-sqlserver", classification)


def test_invalid_dimension_fails() -> None:
    from classification import Classification, ClassificationError

    with pytest.raises(ClassificationError):
        Classification("galaxy", "mdb", "full", ("access_file",))
