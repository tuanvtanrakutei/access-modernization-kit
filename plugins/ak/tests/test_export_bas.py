"""The shipped VBA must be valid VBA, and its JSON escapes must be escapes.

`JsonEscape` shipped with a real carriage return, line feed and tab inside its string
literals instead of the two-character sequences `\\r`, `\\n` and `\\t`. In VBA a
backslash is not an escape character, so `"\\r"` is exactly what you want to write
into JSON - and a raw control character inside a literal both breaks the VBA parse
(Access showed two lines in red) and, where it parsed, wrote an unescaped control
character into a JSON string.

Nothing in the Python test suite could have caught it: the file is data as far as
Python is concerned, and no test read it. It surfaced when a person imported the
module into Access and saw red.

The specific reason it mattered when it did: table and field names cannot contain a
newline, so `schema/tables.json` was fine in practice for years. Access *captions*
can - a two-line button label is stored as one string containing CRLF - so the control
inventory added in 2.10 would have produced invalid JSON on the first form with a
multi-line label, and the A05 main menu has several.
"""
from __future__ import annotations

from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
BAS_FILES = sorted((PACKAGE / "tools").glob("*.bas"))


def test_there_is_at_least_one_bas_to_check() -> None:
    assert BAS_FILES, "no .bas shipped; this test would pass vacuously"


@pytest.mark.parametrize("path", BAS_FILES, ids=lambda p: p.name)
def test_no_string_literal_contains_a_raw_control_character(path: Path) -> None:
    """A literal is opened and closed on one physical line, with no CR/LF/TAB inside.

    Checked on bytes rather than text: a lone CR does not end a line, so a scan that
    splits on newlines never sees `"<CR>"` at all - which is why only two of the three
    broken lines were visible when this was found.
    """
    raw = path.read_bytes()
    # Normalise line endings so a CRLF file and an LF file are checked identically.
    body = raw.replace(b"\r\n", b"\n")
    for number, line in enumerate(body.split(b"\n"), 1):
        quotes = line.count(b'"')
        assert quotes % 2 == 0, (
            f"{path.name}:{number} has an unterminated string literal, which means a "
            f"real newline is inside one: {line[:70]!r}"
        )
        # Anything between the first and last quote on the line.
        if quotes >= 2:
            inner = line[line.index(b'"'): line.rindex(b'"')]
            for bad, name in ((b"\r", "carriage return"), (b"\t", "tab")):
                assert bad not in inner, (
                    f"{path.name}:{number} has a raw {name} inside a string literal; "
                    f"write the two characters instead: {line[:70]!r}"
                )


@pytest.mark.parametrize("path", BAS_FILES, ids=lambda p: p.name)
def test_json_escapes_are_two_character_sequences(path: Path) -> None:
    """Only for a file that escapes JSON at all."""
    raw = path.read_bytes()
    if b"JsonEscape" not in raw:
        pytest.skip("no JSON escaping in this module")
    backslash = chr(92).encode("ascii")
    for control, escape in ((b"vbCr", b"r"), (b"vbLf", b"n"), (b"vbTab", b"t")):
        wanted = control + b', "' + backslash + escape + b'")'
        assert wanted in raw, (
            f"{path.name} must escape {control.decode()} as "
            f"{backslash.decode()}{escape.decode()}; found "
            f"{raw[raw.index(control):raw.index(control) + 24]!r}"
        )


@pytest.mark.parametrize("path", BAS_FILES, ids=lambda p: p.name)
def test_every_sub_and_function_is_closed(path: Path) -> None:
    """A cheap structural check. It would not have caught the escape bug, and saying
    so is the point: this file is shipped code that nothing else in the suite reads."""
    import re

    text = path.read_text(encoding="utf-8")
    opens = len(re.findall(r"^\s*(?:Public |Private |Friend )?(?:Static )?Sub ",
                           text, re.MULTILINE))
    closes = len(re.findall(r"^\s*End Sub\b", text, re.MULTILINE))
    assert opens == closes, f"{path.name}: {opens} Sub, {closes} End Sub"
    opens = len(re.findall(r"^\s*(?:Public |Private |Friend )?(?:Static )?Function ",
                           text, re.MULTILINE))
    closes = len(re.findall(r"^\s*End Function\b", text, re.MULTILINE))
    assert opens == closes, f"{path.name}: {opens} Function, {closes} End Function"


@pytest.mark.parametrize("path", BAS_FILES, ids=lambda p: p.name)
def test_option_explicit_is_declared(path: Path) -> None:
    """Without it a typo becomes a silent Variant, which in an exporter means a
    silently empty field rather than an error."""
    assert "Option Explicit" in path.read_text(encoding="utf-8"), path.name
