"""A74 - the class list and the schema enum could drift, and nothing said so.

`specifications/evidence-classes.yaml` is where a class is defined: what it means, what
it supports, what it may only corroborate. `schemas/evidence.schema.json` is what decides
whether a register carrying that class validates at all. They are two files and were
joined by nothing.

The drift is silent in both directions and fails at a distance:

  in the yaml, not the schema  a register using the new class is rejected as invalid,
                               and the message names the enum rather than the class
  in the schema, not the yaml  the class validates and then has no `supports` table, so
                               `claim_is_supportable` has nothing to answer from

Found when `DATA_STATE` was added for a runtime measurement of table contents, which had
no class to sit in - the same reason `ENVIRONMENT` was added before it. Adding it to the
yaml alone left the schema rejecting the very item the class was created for.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

PACKAGE = Path(__file__).resolve().parents[1]
SPEC = PACKAGE / "specifications" / "evidence-classes.yaml"
SCHEMA = PACKAGE / "schemas" / "evidence.schema.json"


def specification() -> dict:
    return yaml.safe_load(SPEC.read_text(encoding="utf-8"))


def classes() -> dict:
    spec = specification()
    for key in ("evidence_classes", "classes"):
        if key in spec:
            return spec[key]
    raise AssertionError("evidence-classes.yaml carries no class table")


def schema_enum() -> list:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return schema["$defs"]["evidenceItem"]["properties"]["evidence_class"]["enum"]


def test_every_defined_class_is_accepted_by_the_schema() -> None:
    missing = sorted(set(classes()) - set(schema_enum()))
    assert not missing, (
        "defined in evidence-classes.yaml and rejected by evidence.schema.json, so a "
        "register using one is invalid and the error names the enum rather than the "
        "class: %s" % missing)


def test_every_class_the_schema_accepts_is_defined() -> None:
    undefined = sorted(set(schema_enum()) - set(classes()))
    assert not undefined, (
        "accepted by evidence.schema.json and defined nowhere, so an item carrying one "
        "validates and then has no supports table to check a claim against: %s" % undefined)


def test_every_class_states_what_it_supports_and_what_it_cannot() -> None:
    """A class with no table is a class that permits everything by omission."""
    for name, body in classes().items():
        assert body.get("means", "").strip(), "%s has no `means`" % name
        assert body.get("supports"), "%s states nothing it supports" % name
        # `supports` and `cannot_support` must not overlap, or the rule is unanswerable.
        overlap = set(body.get("supports", [])) & set(body.get("cannot_support", []))
        assert not overlap, "%s both supports and forbids %s" % (name, sorted(overlap))


def test_a_runtime_measurement_of_data_corroborates_usage_rather_than_supporting_it() -> None:
    """The distinction DATA_STATE exists to keep.

    That no row uses a code is a fact about the data. That nobody ever wanted to is a
    reading of it, and EC-01 reserves that for a DOCUMENT or an INTERVIEW. A class which
    `supports: [USAGE]` would erase the difference, which is the mistake this class was
    created out of - the first item written for it claimed USAGE and was refused.
    """
    data_state = classes()["DATA_STATE"]
    assert "USAGE" in data_state["corroborates"]
    assert "USAGE" not in data_state["supports"]
    assert "MEANING" in data_state["cannot_support"]
    assert "INTENT" in data_state["cannot_support"]
