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


# --- A51: the kit's own tools, exported as the application's code -------------------

EXPORTER = PACKAGE / "tools" / "ExportAccessObjects.bas"


def exporter_text() -> str:
    return EXPORTER.read_text(encoding="utf-8")


def test_every_kit_tool_carries_the_marker() -> None:
    """A module the kit tells an operator to import is not application code.

    `ListStaleLinks` was imported into A06's frontend to delete 153 dead links, landed
    under Access's default name `Module1`, and was exported on 2026-09-14 as the
    application's eighth module - carrying this kit's prose about A06's own tables into
    the corpus that describes A06.
    """
    for path in BAS_FILES:
        assert "@ak-tool" in path.read_text(encoding="utf-8"), path.name


def test_the_guard_reads_content_rather_than_a_name() -> None:
    """The old guard was `If ao.Name <> MODULE_NAME`, one hard-coded string.

    It protected the file that declared it and nothing else, and no name test could
    ever have caught `Module1` - which is what Access calls a module somebody pasted
    code into.
    """
    text = exporter_text()
    assert "IsKitToolModule(modulePath)" in text
    assert "KIT_TOOL_MARKER" in text and "KIT_TOOL_ENTRY_POINTS" in text
    # Every tool's entry point is listed, so a copy imported before the marker existed
    # is still recognised - which is the copy sitting in A06 right now.
    for entry in ("Sub ListStaleLinks(", "Sub DeleteStaleLinks(", "Sub ExportAccessObjects("):
        assert entry in text, entry


def test_an_excluded_tool_is_named_in_the_manifest() -> None:
    """Silently dropping an object the operator can see in the navigation pane is how
    a count becomes unexplainable."""
    text = exporter_text()
    assert "excluded_kit_tool_modules=" in text
    assert "EXCLUDED modules (this kit's own tools, not application code):" in text


def test_the_manifest_says_which_exporter_wrote_it() -> None:
    """A06's backend has been exporting with a pre-A44 copy since 2026-09-10, printing
    `imex_specification_rows=no link declares DSN=` on a kit where that gate no longer
    exists - and nothing in the output said so. A45 solved this for the PowerShell
    route by hashing its bytes into the bundle id; this route had no equivalent."""
    text = exporter_text()
    assert "EXPORTER_VERSION" in text
    assert '"exporter_version=" & EXPORTER_VERSION' in text


def test_an_unreadable_module_is_kept_rather_than_dropped() -> None:
    """The safe error: an extra object is visible in the count, a missing one is not."""
    text = exporter_text()
    tail = text[text.index("Private Function IsKitToolModule"):]
    assert "IsKitToolModule = False" in tail.split("Fail:")[1]
