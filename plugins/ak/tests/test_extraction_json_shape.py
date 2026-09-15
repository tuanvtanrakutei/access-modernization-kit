"""A73 - an empty collection wrote no file, and a one-item collection wrote no array.

`Write-Extraction` serialised its two schema files by piping:

    $relations | ConvertTo-Json -Depth 12 | Set-Content ... 'schema/relations.json'

Piping an **empty** collection sends ConvertTo-Json nothing, so it emits nothing and
Set-Content writes no file at all. Measured in PowerShell 5.1 on this host:

    [System.Collections.ArrayList]::new() | ConvertTo-Json     ->  (no output)
    ConvertTo-Json -InputObject @([System.Collections.ArrayList]::new())  ->  []

So `schema/relations.json` was absent from every database that declares zero
relationships - and absent is indistinguishable from what an older extractor that never
wrote the file leaves behind.

That ambiguity cost a real decision. A06's bundle has no `relations.json`, which was read
as "this export predates the feature", so whether the Jet engine declared referential
integrity between `商品情報.保管場所` and `保管場所マスタ` was recorded as unknowable
(A06 Known_Issues #5) and a screen could not say whether its refusal to delete a
referenced row restored legacy behaviour or invented it. Re-running the fixed extractor
answered it in one line: `[]`. The database declares none.

The single-item case is the worse half and has never been hit only by luck: a pipe unrolls
a one-element collection into a scalar, so a database with exactly one table would write
`{...}` where every consumer expects `[{...}]`. `@()` forces array shape both ways.

These tests are static reads of the shipped script, like `test_field_properties.py`: the
code needs a live Access host to run, and what is checkable here is that neither write can
go back to a bare pipe.
"""
from __future__ import annotations

import re
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
PS1 = PACKAGE / "scripts" / "extract_access.ps1"

# The files Write-Extraction serialises from a collection rather than from one object.
COLLECTION_FILES = {
    "schema/tables.json": "$tables",
    "schema/relations.json": "$relations",
}


def script() -> str:
    return PS1.read_text(encoding="utf-8")


def test_each_collection_file_is_written_with_input_object() -> None:
    """A pipe is the bug; `-InputObject` is the fix. Assert the call shape."""
    text = script()
    for path, variable in COLLECTION_FILES.items():
        expected = ("ConvertTo-Json -InputObject @(%s) -Depth 12 | Set-Content "
                    "-LiteralPath (Join-Path $root '%s')" % (variable, path))
        assert expected in text, (
            "%s is not written with `ConvertTo-Json -InputObject @(%s)`; a bare pipe "
            "writes no file when the collection is empty" % (path, variable))


def test_no_collection_is_piped_into_converto_json() -> None:
    """Scoped to the collections, because piping a single object is fine.

    `$componentIndex` and `$result` are one `[ordered]@{}` each: a pipe sends exactly one
    object and ConvertTo-Json writes one JSON object, which is what they are. Only a
    variable that can hold zero or many items has the failure this file is about, so the
    check names those rather than flagging every pipe in the script.
    """
    pattern = re.compile(r"(%s)\s*\|\s*ConvertTo-Json"
                         % "|".join(re.escape(v) for v in COLLECTION_FILES.values()))
    offenders = [line.strip() for line in script().splitlines() if pattern.search(line)]
    assert not offenders, (
        "piping a collection into ConvertTo-Json writes nothing when it is empty and a "
        "bare object when it holds one item: %s" % offenders)


def test_the_array_wrapper_is_not_dropped() -> None:
    """`@()` is what makes a one-item collection serialise as an array.

    `ConvertTo-Json -InputObject $relations` alone fixes the empty case and leaves the
    single-item case broken, which is the harder failure to notice: the file exists and
    parses, and only its shape is wrong.
    """
    text = script()
    for variable in COLLECTION_FILES.values():
        bare = "ConvertTo-Json -InputObject %s " % variable
        assert bare not in text, (
            "%s is passed without the @() wrapper, so a one-item collection would "
            "serialise as an object rather than an array" % variable)
