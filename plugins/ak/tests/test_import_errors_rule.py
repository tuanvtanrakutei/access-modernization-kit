"""The exclusion that destroyed its own evidence, and the condition it needed.

Both acquisition routes drop a table whose fields are exactly Text/Text/Long as an
Access ImportErrors table. The rule is deliberate and the reason is good: a long-lived
application accumulates hundreds of them, one A05 frontend carried 210 against 21 real
tables, and identifying them by *table* name fails because that name is localized and
this corpus has a legitimate table matching the Japanese word for "error".

Shape alone is not enough either, and A05's backend is the proof. Measured there on
2026-09-08, all four of its Text/Text/Long tables:

    Sheet1$_インポート エラー      エラー(Text) / フィールド(Text) / 行(Long)
    商品情報_エクスポート エラー   エラー(Text) / フィールド(Text) / 行(Long)
    集計分類マスタ                集計分類コード(Text) / 集計分類名(Text) / 配送分類コード(Long)
    雑貨Ⅱ集計分類マスタ           集計分類コード(Text) / 集計分類名(Text) / 配送分類コード(Long)

The last two are business masters, referenced 56 and 18 times across the corpus, and
both routes dropped them recording nothing but their names - so nobody could tell
`エラー / フィールド / 行` from `集計分類コード / 集計分類名 / 配送分類コード`, and the
exclusion could only be trusted. Backlog A22.

The field names are Access's own and a person never types them, which is what makes
them safe to key on where the table name is not. These tests run the real PowerShell
rule against those four shapes, and hold the two routes' lists against each other,
because two routes drifting apart is exactly what A21 was.
"""
from __future__ import annotations

import base64
import json
import re
import shutil
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

PS1 = PACKAGE / "scripts" / "extract_access.ps1"
BAS = PACKAGE / "tools" / "ExportAccessObjects.bas"

TEXT, LONG = 10, 4

# Access's own field names for an errors table, and the two business masters that
# share their shape. Written as real strings here and sent across the pipe as code
# points, because a console code page decides what survives otherwise.
JA_ERRORS = ("エラー", "フィールド", "行")
EN_ERRORS = ("Error", "Field", "Row")
HALF_WIDTH_ERRORS = ("ｴﾗｰ", "ﾌｨｰﾙﾄﾞ", "行")
MASTER = ("集計分類コード", "集計分類名", "配送分類コード")

HARNESS = """
$ErrorActionPreference = 'Stop'
$c = Get-Content -Raw -LiteralPath '{script}'
foreach ($pattern in @(
    '(?ms)^\\$importErrorsFieldNames = @\\(.*?^\\)',
    '(?ms)^function Normalize-AccessName.*?^\\}}',
    '(?ms)^function Test-ImportErrorsShape.*?^\\}}',
    '(?ms)^function Test-ImportErrorsNaming.*?^\\}}')) {{
  $m = [regex]::Match($c, $pattern)
  if (-not $m.Success) {{ throw "not found in the script: $pattern" }}
  Invoke-Expression $m.Value
}}

$cases = {cases}
$out = @()
foreach ($case in $cases) {{
  $fields = @()
  for ($i = 0; $i -lt $case.codes.Count; $i++) {{
    $name = -join (@($case.codes[$i]) | ForEach-Object {{ [char]$_ }})
    $fields += [ordered]@{{ name = $name; type = $case.types[$i] }}
  }}
  $out += [ordered]@{{
    label = $case.label
    shape = [bool](Test-ImportErrorsShape $fields)
    naming = [bool](Test-ImportErrorsNaming $fields)
  }}
}}
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$json = ConvertTo-Json @($out) -Depth 6 -Compress
[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($json))
"""


def _case(label: str, names: tuple[str, ...], types: tuple[int, ...]) -> str:
    codes = ", ".join("@(" + ", ".join(str(ord(char)) for char in name) + ")"
                      for name in names)
    return (f"@{{ label = '{label}'; codes = @({codes}); "
            f"types = @({', '.join(str(t) for t in types)}) }}")


def verdicts(cases: dict[str, tuple[tuple[str, ...], tuple[int, ...]]]) -> dict:
    """Run the real rule from `extract_access.ps1` against each set of fields.

    The functions are invoked out of the shipped script rather than reimplemented,
    which is the only version of this test worth having: the defect this replaces was
    a rule that read correctly and matched nothing, and it survived a reading.
    """
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        pytest.skip("PowerShell not available on this platform")
    rendered = "@(" + ", ".join(
        _case(label, names, types) for label, (names, types) in cases.items()) + ")"
    command = HARNESS.format(script=PS1.as_posix(), cases=rendered)
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
        check=False, capture_output=True)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    parsed = json.loads(base64.b64decode(result.stdout.strip()).decode("utf-8"))
    return {row["label"]: row for row in parsed}


# --- the rule, run ----------------------------------------------------------

def test_the_four_shapes_a05_actually_has() -> None:
    """One run, both halves of the decision, on the tables that motivated it."""
    answers = verdicts({
        "ja_errors": (JA_ERRORS, (TEXT, TEXT, LONG)),
        "en_errors": (EN_ERRORS, (TEXT, TEXT, LONG)),
        "master": (MASTER, (TEXT, TEXT, LONG)),
    })
    # All three are the shape. That is the whole problem with the shape.
    assert all(answers[label]["shape"] for label in answers)
    assert answers["ja_errors"]["naming"], "Access's Japanese errors table"
    assert answers["en_errors"]["naming"], "Access's English errors table"
    assert not answers["master"]["naming"], (
        "集計分類マスタ is a business master referenced 56 times; excluding it is the "
        "defect A22 records")


def test_a_half_width_spelling_is_the_same_name() -> None:
    """What NFKC is for: `ｴﾗｰ` and `エラー` are the one name they are on screen."""
    assert unicodedata.normalize("NFKC", "ﾌｨｰﾙﾄﾞ") == "フィールド", "the premise"
    answers = verdicts({"half": (HALF_WIDTH_ERRORS, (TEXT, TEXT, LONG))})
    assert answers["half"]["shape"] and answers["half"]["naming"]


@pytest.mark.parametrize("types", [(TEXT, TEXT, TEXT), (TEXT, LONG, LONG), (TEXT, TEXT)])
def test_a_table_of_another_shape_is_never_this_rule(types: tuple[int, ...]) -> None:
    """The shape test stays exactly as narrow as it was."""
    answers = verdicts({"other": (JA_ERRORS[:len(types)], types)})
    assert not answers["other"]["shape"]


def test_the_naming_alone_does_not_exclude_a_table_of_another_shape() -> None:
    """Both conditions, and in that order: a three-column master called Error/Field/Row
    would be excluded, a five-column one would not, and neither is decided by the name
    of the table."""
    answers = verdicts({"wide": (EN_ERRORS, (TEXT, TEXT, TEXT))})
    assert not answers["wide"]["shape"]


# --- the two routes, held against each other --------------------------------

def _array_groups(block: str) -> list[str]:
    """Each top-level `@(...)` in a PowerShell array literal, by paren depth.

    Scanned rather than matched: the Japanese names are `-join ([char]0x30A8, ...)`
    expressions, and a regex ending at the first `)` reads only the English triple -
    which is how the first version of this test passed while agreeing about half the
    list.
    """
    groups: list[str] = []
    depth, start, index = 0, None, 0
    while index < len(block):
        if block.startswith("@(", index):
            if depth == 0:
                start = index + 2
            depth += 1
            index += 2
            continue
        char = block[index]
        if depth and char == "(":
            depth += 1
        elif depth and char == ")":
            depth -= 1
            if depth == 0 and start is not None:
                groups.append(block[start:index])
                start = None
        index += 1
    return groups


NAME_IN_PS1 = re.compile(r"'([^']*)'|-join \(([^)]*)\)")


def ps1_triples() -> list[tuple[str, ...]]:
    """The field-name list as the PowerShell route declares it."""
    # The body of the outer array, so the scan below sees the triples as top level.
    block = re.search(r"(?ms)^\$importErrorsFieldNames = @\((.*?)^\)",
                      PS1.read_text(encoding="utf-8"))
    assert block, "the PowerShell route no longer declares a field-name list"
    found: list[tuple[str, ...]] = []
    for group in _array_groups(block.group(1)):
        names = [quoted if quoted else
                 "".join(chr(int(code, 16))
                         for code in re.findall(r"0x([0-9A-Fa-f]+)", codes))
                 for quoted, codes in NAME_IN_PS1.findall(group)]
        if len(names) == 3:
            found.append(tuple(names))
    return found


def bas_triples() -> list[tuple[str, ...]]:
    """The same list as the VBA route declares it, ChrW code points resolved."""
    text = BAS.read_text(encoding="utf-8")
    body = re.search(r"(?ms)^Private Function HasImportErrorsFieldNames.*?^End Function",
                     text)
    assert body, "the VBA route no longer declares a field-name list"
    parts: dict[str, str] = {}
    for name, expression in re.findall(r"^\s*(ja\w+) = (.+)$", body.group(0), re.MULTILINE):
        parts[name] = "".join(chr(int(code, 16)) for code in
                              re.findall(r"ChrW\(&H([0-9A-Fa-f]+)&?\)", expression))
    found: list[tuple[str, ...]] = []
    for call in re.findall(r"FieldNamesAre\(td, (.+?)\)\s*Then", body.group(0)):
        names = []
        for argument in [item.strip() for item in call.split(",")]:
            if argument.startswith('"'):
                names.append(argument.strip('"'))
            else:
                names.append(parts.get(argument, argument))
        if len(names) == 3:
            found.append(tuple(names))
    return found


def test_both_routes_declare_the_same_field_names() -> None:
    """A17 landed in one route and not the other and cost a whole boundary's layout.

    There is no shared file two languages can both read here, so the list is written
    twice and this is what keeps them one list. A locale added to either route alone
    fails here rather than in an operator's export six weeks later.
    """
    assert ps1_triples(), "could not parse the PowerShell list"
    assert bas_triples(), "could not parse the VBA list"
    assert sorted(ps1_triples()) == sorted(bas_triples())
    assert EN_ERRORS in ps1_triples() and JA_ERRORS in ps1_triples()


def test_both_routes_record_the_field_names_of_what_they_exclude() -> None:
    """The half of A22 that holds whatever happens to the rule.

    One line per excluded table, carrying its three field names, so a person can see
    in one line whether the rule was right. `export-manifest.txt` listed the name and
    `extract_access.ps1` did not even do that - it incremented a counter.
    """
    ps1 = PS1.read_text(encoding="utf-8")
    excluded = next(line for line in ps1.splitlines() if "$script:excludedByShape.Add" in line)
    assert "Format-FieldShape $fields" in excluded and "{0}" in excluded

    bas = BAS.read_text(encoding="utf-8")
    assert 'excludedNames = excludedNames & ": " & FieldShapeText(td)' in bas
    assert "keptShapeNames = keptShapeNames" in bas and "FieldShapeText(td)" in bas


def test_both_routes_name_a_table_kept_despite_the_shape() -> None:
    """Otherwise the second condition is invisible: after it the excluded list holds
    only genuine error tables, and nothing shows how close a real master came."""
    assert "$script:keptDespiteShape.Add" in PS1.read_text(encoding="utf-8")
    assert "KEPT tables with the ImportErrors shape" in BAS.read_text(encoding="utf-8")


# --- the type names, against the specification ------------------------------

def documented_types() -> dict[int, str]:
    yaml = pytest.importorskip("yaml")
    types = yaml.safe_load(
        (PACKAGE / "specifications" / "dao-field-types.yaml").read_text(
            encoding="utf-8"))["types"]
    return {int(code): str(entry["dao_constant"]).removeprefix("db")
            for code, entry in types.items()}


def test_the_powershell_route_names_the_types_the_specification_documents() -> None:
    """`type = 10` in an exclusion line tells a reviewer nothing.

    Held against `dao-field-types.yaml` in both directions, because a wrong name here
    is a reviewer reading an exclusion wrongly, which is the whole point of the line.
    """
    block = re.search(r"(?ms)^\$daoTypeNames = @\{(.*?)^\}",
                      PS1.read_text(encoding="utf-8"))
    assert block, "the PowerShell route no longer maps type codes to names"
    mapped = {int(code): name for code, name in
              re.findall(r"(\d+) = '([A-Za-z]+)'", block.group(1))}
    assert mapped == documented_types()


def test_the_vba_route_names_the_same_types() -> None:
    body = re.search(r"(?ms)^Private Function DaoTypeName.*?^End Function",
                     BAS.read_text(encoding="utf-8"))
    assert body, "the VBA route no longer maps type codes to names"
    mapped = {int(code): name for code, name in
              re.findall(r'Case (\d+): DaoTypeName = "([A-Za-z]+)"', body.group(0))}
    assert mapped == documented_types()
