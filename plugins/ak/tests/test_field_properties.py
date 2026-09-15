"""A72 - the table properties the taxonomy calls a hiding place, and did not collect.

`modernize/docs/LEGACY_EVIDENCE.md` names table definitions as one of the places
business rules live, and lists `Required`, `AllowZeroLength`, `DefaultValue`,
`ValidationRule` and `ValidationText` by name, with the reason they are missed:
*validation rules are properties, invisible unless explicitly dumped*. Its
manual-export instructions then tell an operator to dump exactly those.

The extractor read `name`, `type`, `size` and `required`. So `ak`'s own Stage 0
produced weaker evidence about a table than the manual path the same package
documents - and `dao-field-types.yaml` recorded that honestly, under `not_extracted`,
which is why this went years without being a bug report.

It cost a real screen. A06's `保管場所マスタ` has two columns and no code behind the
form that maintains it, so every rule about it has to come from the table definition
or from a picture. The blank row on the screenshot shows `0` under the code column;
whether that is a `DefaultValue` or just how Access renders an empty Byte could not be
settled from the bundle, and the business flow had to say so.

These tests are static reads of the shipped script, in the shape of
`test_extractor_diagnostics.py`: the code sits behind a live Access host and a real
database, and what can be checked here is that the properties are asked for, that each
is asked for separately, and that no specification still claims they are not collected.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

PACKAGE = Path(__file__).resolve().parents[1]
PS1 = PACKAGE / "scripts" / "extract_access.ps1"
SPEC = PACKAGE / "specifications" / "dao-field-types.yaml"
TAXONOMY = PACKAGE / "modernize" / "docs" / "LEGACY_EVIDENCE.md"

# DAO property -> the key it is written to in `schema/tables.json`.
PROPERTIES = {
    "DefaultValue": "default_value",
    "ValidationRule": "validation_rule",
    "ValidationText": "validation_text",
    "AllowZeroLength": "allow_zero_length",
    "Attributes": "attributes",
}


def script() -> str:
    return PS1.read_text(encoding="utf-8")


def test_every_property_the_taxonomy_names_is_read() -> None:
    """The four the taxonomy lists, plus `Attributes` for the AutoNumber question."""
    text = script()
    for dao in PROPERTIES:
        assert "$field.%s" % dao in text, (
            "%s is named in LEGACY_EVIDENCE.md as a place a business rule hides, "
            "and the extractor does not read it" % dao
        )


def test_each_property_is_read_in_its_own_try() -> None:
    """One refusal must not cost the other four, or the field row itself.

    A linked table's fields raise on some of these depending on what the link
    supports. Reading all five inside one `try` would drop four known properties
    because a fifth was unavailable, and the field would still be written - so the
    loss would be silent, which is the failure mode worth a test.
    """
    text = script()
    for dao in PROPERTIES:
        pattern = re.compile(
            r"try \{ \$\w+ = \[[a-z]+\]\$field\.%s \} catch \{\}" % dao)
        assert pattern.search(text), (
            "%s is not read inside a try/catch of its own" % dao)


def test_unset_and_empty_stay_different_facts() -> None:
    """Access writes `""` for a text field defaulting to the empty string.

    That is not the same fact as a field with no default, and a catalogue cannot say
    which one it saw if the extractor collapses them.
    """
    text = script()
    for variable in ("$default", "$validationRule", "$validationText"):
        assert "if (%s -eq '') { %s = $null }" % (variable, variable) in text, (
            "%s does not keep unset distinct from empty" % variable)


def test_the_field_row_carries_every_collected_key() -> None:
    text = script()
    row = [line for line in text.splitlines() if "$fields += [ordered]@{" in line]
    assert len(row) == 1, "expected one field-row construction, found %d" % len(row)
    for key in PROPERTIES.values():
        assert "%s =" % key in row[0], "the field row does not carry %s" % key


def test_the_specification_no_longer_calls_them_uncollected() -> None:
    """`not_extracted` exists so every gap has a name (EC-06).

    A gap that has been closed and left named there is worse than an unnamed one: it
    tells a reader not to look for evidence that is now sitting in the bundle.
    """
    spec = yaml.safe_load(SPEC.read_text(encoding="utf-8"))
    uncollected = " ".join(entry["why"] for entry in spec["not_extracted"])
    for dao in ("Field.DefaultValue", "Field.ValidationRule"):
        assert dao not in uncollected, (
            "%s is collected since A72 and is still listed as not extracted" % dao)

    collected = {entry["key"]: entry for entry in spec["collected_field_properties"]}
    assert set(collected) == set(PROPERTIES.values())
    for entry in collected.values():
        assert entry["from"].startswith("Field."), entry
        assert entry["carries"].strip(), "a collected property with no stated use"


def test_the_taxonomy_and_the_extractor_agree() -> None:
    """The document that says where rules hide, and the tool that goes looking.

    This is the pair that drifted. Holding them together here means adding a property
    to the taxonomy's table-definition row fails this test until the extractor reads it.
    """
    row = [line for line in TAXONOMY.read_text(encoding="utf-8").splitlines()
           if line.startswith("| **Table definitions**")]
    assert len(row) == 1, "the table-definitions row moved or was renamed"
    named = set(re.findall(r"`([A-Za-z]+)`", row[0]))
    # `Required`, indexes and uniqueness were already collected; the rest are A72's.
    for dao in named - {"Required"}:
        assert "$field.%s" % dao in script(), (
            "the taxonomy names %s as a place rules hide and the extractor "
            "does not read it" % dao)
