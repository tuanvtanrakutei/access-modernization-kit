"""Every class that can carry a claim about meaning needs somewhere to be cited from.

`specifications/evidence-classes.yaml` rule EC-01: a MEANING, USAGE or INTENT claim
requires `DOCUMENT` or `INTERVIEW`, and no volume of schema, code or definition text
substitutes. Exactly those two classes declare `MEANING` under `supports`.

`modernize/docs/TRACEBACK_GATES.md` listed anchor forms for twelve evidence types -
exported VBA, form properties, querydefs, stored procedures, table definitions, output
samples, screenshots, business-flow and screen-plan sections, code - and for neither of
those two. So the most consequential claims a business flow can make, the ones about
what a screen is *for*, had no documented way to be anchored, while G1 checks coverage
by anchor. A reviewer either invented a form or reported a gap.

The register was never the problem: `schemas/evidence.schema.json` carries
`source_type: INTERVIEW`, `evidence_class: INTERVIEW` and an `attribution` object, and
an `allOf` makes `person` and `recorded_on` mandatory for an interview item. It was the
gate specification that had no row, and the field table that never mentioned
`attribution`.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

GATES = PACKAGE / "modernize" / "docs" / "TRACEBACK_GATES.md"
CLASSES = PACKAGE / "specifications" / "evidence-classes.yaml"


@pytest.fixture(scope="module")
def anchor_section() -> str:
    text = GATES.read_text(encoding="utf-8")
    start = text.index("## Anchor Format")
    end = text.index("\n## ", start + 1)
    return text[start:end]


@pytest.fixture(scope="module")
def meaning_classes() -> list[str]:
    contract = yaml.safe_load(CLASSES.read_text(encoding="utf-8"))
    return sorted(
        name for name, spec in contract["evidence_classes"].items()
        if "MEANING" in (spec.get("supports") or [])
    )


def test_the_two_classes_that_carry_a_meaning_are_the_two_that_do(
    meaning_classes: list[str],
) -> None:
    """If a third class gains `MEANING`, the tests below start covering it too."""
    assert meaning_classes == ["DOCUMENT", "INTERVIEW"]


def test_each_has_an_anchor_form(anchor_section: str, meaning_classes: list[str]) -> None:
    lowered = anchor_section.lower()
    for name in meaning_classes:
        assert name.lower() in lowered, (
            f"TRACEBACK_GATES.md's anchor format has no form for {name}, which EC-01 "
            f"makes one of only two classes that can carry a claim about meaning"
        )


def test_the_interview_form_carries_a_person_or_a_question_id(anchor_section: str) -> None:
    """An anchor that stops at the filename cannot be followed to one answer.

    An interview file holds a conversation. `Q-19` or a name and a date is what makes
    the citation resolve to the sentence somebody is accountable for - the same reason
    the register requires `attribution`.
    """
    rows = [line for line in anchor_section.splitlines()
            if line.startswith("|") and "interview" in line.lower()]
    assert rows, "no interview row in the anchor table"
    assert any(re.search(r"Q-N|question", row, re.IGNORECASE) for row in rows), rows
    assert any(re.search(r"YYYY-MM-DD|person", row) for row in rows), rows


def test_the_register_field_table_names_attribution(anchor_section: str) -> None:
    """The field table told a reviewer what to follow and omitted the only field that
    resolves an interview item. `source_location` is null for one; `attribution` is not.
    """
    assert "attribution" in anchor_section, (
        "the Evidence.json field table does not mention `attribution`, so a reviewer "
        "following it has no way to resolve an INTERVIEW item"
    )


def test_an_unrecorded_answer_is_named_as_uncitable(anchor_section: str) -> None:
    """The honest consequence has to be written down, or it reads as an oversight.

    An answer nobody wrote down has no anchor and cannot pass G1. That is the intended
    outcome of EC-01, not a hole in the anchor format, and the section now says so.
    """
    lowered = anchor_section.lower()
    # Not just the word "memory": the section has always opened with "verifiable by
    # grep rather than by memory", so matching that would assert nothing. The claim
    # under test is the consequence for an answer nobody recorded.
    assert "has no anchor" in lowered, (
        "the anchor format does not say that an unrecorded answer has no anchor, so "
        "the absence of an interview row reads as an oversight rather than a rule"
    )
