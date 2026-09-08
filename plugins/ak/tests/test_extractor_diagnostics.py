"""Two channels out of the extractor, and which line belongs in which.

Every diagnostic used to travel as a warning. The bundle classifies a warning by its
opening word - `EXCLUDED` is a deliberate exclusion, `KEPT ` an observation - and a
line carrying no marker is counted as an object that could not be read. Two of the
extractor's lines say what the run *did*: which optional tier was skipped, and that it
read the specification tables a link asked for. Both appear on every managed
acquisition in this configuration, so a perfect run reported `failed=2`. Backlog A25.

The fix is a second collection rather than a third prefix, because a prefix convention
puts the burden on whoever adds the next diagnostic and its default is "failure". The
rule the two channels encode:

    warnings  something a person must act on, whether the fault is the kit's (a table
              that would not read) or the application's (an ActiveX control that
              cannot load, which is a finding about the application and not noise)
    notes     what this run chose to do, so a reader can weigh the evidence it made

These tests hold the shipped script to that rule. They are static reads of the text:
the lines sit in branches that need a live Access host and a broken database to reach,
and asserting on the channel each one is written to is what can actually be checked
here.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
PS1 = PACKAGE / "scripts" / "extract_access.ps1"
SCHEMA = PACKAGE / "schemas" / "access-extraction.schema.json"

# The four lines that state what the run did. Each is quoted here by a fragment long
# enough to be unambiguous, so moving one back to `$warnings` fails this file.
NOTES = (
    "linked table(s) declare a DSN; read the import specification tables",
    "Object definition export was skipped; the inventory carries names only",
    "Access host ran visible: an operator may have dismissed dialogs",
    "Automation macros were allowed to run: startup code executed",
)


def adding_calls() -> list[tuple[str, str]]:
    """Every `$<channel>.Add(...)` in the script, as (channel, the rest of the line).

    Taken to the end of the line rather than to a matching paren, because three of
    these sit inside an inline `catch { ... }` and a pattern anchored on the closing
    paren read 17 of the 20 - which would have let a diagnostic move channel without
    this file noticing.
    """
    pattern = re.compile(r"\$(?:script:)?(warnings|notes)\.Add\((.*)")
    return [(match.group(1), match.group(2))
            for line in PS1.read_text(encoding="utf-8").splitlines()
            for match in pattern.finditer(line)]


def test_every_diagnostic_in_the_script_is_read_by_this_file() -> None:
    """The count is the guard: a call this cannot parse is a call it cannot check."""
    text = PS1.read_text(encoding="utf-8")
    declared = len(re.findall(r"\$(?:script:)?(?:warnings|notes)\.Add\(", text))
    assert len(adding_calls()) == declared and declared >= 20


def test_the_script_writes_to_both_channels() -> None:
    channels = {channel for channel, _ in adding_calls()}
    assert channels == {"warnings", "notes"}, adding_calls()


@pytest.mark.parametrize("fragment", NOTES)
def test_a_line_that_says_what_the_run_did_is_a_note(fragment: str) -> None:
    matching = [channel for channel, text in adding_calls() if fragment in text]
    assert matching, f"no diagnostic carries {fragment!r} any more"
    assert matching == ["notes"], (
        f"{fragment!r} states what the run did, so as a warning it is counted as an "
        "object that could not be read")


def test_a_line_that_says_something_went_wrong_stays_a_warning() -> None:
    """The default that has to keep working.

    `Could not read table X` is evidence that should exist and does not, and `failed=N`
    has to keep meaning exactly that. Every one of these is checked rather than a
    sample, because the cost of moving one into `notes` is a failure nobody is told
    about - the opposite defect, and the worse one.
    """
    went_wrong = re.compile(r"^'?\(?'?(Could not |Failed to |DAO tier failed|"
                            r"Access host failed|ActiveX class )")
    for channel, text in adding_calls():
        if went_wrong.search(text.lstrip("(").lstrip("'")):
            assert channel == "warnings", text


def test_the_result_carries_the_channel_and_the_schema_declares_it() -> None:
    """`additionalProperties: false`, so the key is not optional in the loose sense:
    an extraction emitting `notes` against the old schema does not validate at all."""
    assert re.search(r"^\s*notes = \$notes\s*$", PS1.read_text(encoding="utf-8"),
                     re.MULTILINE), "the result no longer carries the notes channel"
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert schema["additionalProperties"] is False, "the premise of this test"
    notes = schema["properties"]["notes"]
    assert notes["type"] == "array" and notes["items"] == {"type": "string"}
    assert "A25" in notes["description"], (
        "the description is where the reason lives; a bare type says nothing about "
        "which channel a new diagnostic belongs in")
    assert "notes" not in schema["required"], (
        "an extraction written before this channel existed still has to validate")
