"""The two tables that declare a text link's columns, and why they are read at all.

A05 links six delimited text files, every one declaring `FMT=Delimited;HDR=NO;IMEX=2`
and `DSN=<spec name>`. `HDR=NO` means there is no header row, so a column's meaning is
positional and the specification named by `DSN=` is the only declaration of what those
positions mean. It lives in `MSysIMEXSpecs` and `MSysIMEXColumns`, inside the database.

The extractor skipped both by name, alongside the `MSys*` tables DAO genuinely cannot
read. That cost the layout of the entire inbound boundary: all six linked tables came
back `read_error` - "could not find the object 'order.txt'" - with `columns: 0`, because
the share was not mounted at acquisition and Access cannot enumerate a text link's
columns without reading the file. The one copy of that layout which did not depend on
the file being reachable was the one being skipped, and Phase 3 was published as
inference on that basis. Backlog A17.

These tables read only when a link declares a DSN. Reading them always would put
Access's own bookkeeping in every bundle; reading them never cost a boundary.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

import generate_catalogues as catalogues  # noqa: E402

SCRIPT = PACKAGE / "scripts" / "extract_access.ps1"


def spec_records(rows_specs: list[dict], rows_columns: list[dict],
                 status: str = "read") -> list[dict]:
    return [
        {"table": "MSysIMEXSpecs", "status": status, "reason": "", "rows": rows_specs},
        {"table": "MSysIMEXColumns", "status": status, "reason": "", "rows": rows_columns},
    ]


# --- the join, done where it can be tested ----------------------------------

def test_columns_join_their_specification_by_id() -> None:
    """The extractor emits rows without interpreting them; the join belongs here."""
    joined = catalogues.imex_columns(spec_records(
        [{"SpecID": "1", "SpecName": "order_spec"},
         {"SpecID": "2", "SpecName": "shipping_spec"}],
        [{"SpecID": "1", "FieldName": "商品コード"},
         {"SpecID": "1", "FieldName": "数量"},
         {"SpecID": "2", "FieldName": "伝票番号"}],
    ))
    assert joined == {"order_spec": ["商品コード", "数量"], "shipping_spec": ["伝票番号"]}


def test_a_specification_with_no_columns_still_appears() -> None:
    """An empty specification is a finding, not an absence.

    It means the link names a layout somebody created and never filled in, which reads
    very differently from naming one the database does not hold.
    """
    joined = catalogues.imex_columns(spec_records(
        [{"SpecID": "9", "SpecName": "empty_spec"}], []))
    assert joined == {"empty_spec": []}


def test_field_names_are_matched_case_insensitively() -> None:
    """These are Access's column names and are not verified here against a live
    database. Matching them exactly is how a version difference would silently drop
    the layout this exists to capture.
    """
    joined = catalogues.imex_columns([
        {"table": "MSysIMEXSpecs", "status": "read",
         "rows": [{"specid": "1", "specname": "order_spec"}]},
        {"table": "MSysIMEXColumns", "status": "read",
         "rows": [{"SPECID": "1", "FIELDNAME": "商品コード"}]},
    ])
    assert joined == {"order_spec": ["商品コード"]}


@pytest.mark.parametrize("status", ["absent", "read_error"])
def test_an_unread_table_contributes_nothing(status: str) -> None:
    """`absent` and `read_error` are recorded so the reason survives, not so they count.

    A database with no saved specification has no such table, and a link that names one
    then has no declared layout anywhere - which the catalogue has to be able to say.
    """
    assert catalogues.imex_columns(spec_records(
        [{"SpecID": "1", "SpecName": "order_spec"}],
        [{"SpecID": "1", "FieldName": "商品コード"}],
        status=status,
    )) == {}


# --- what the catalogue says about a link -----------------------------------

DSN_CONNECT = "Text;FMT=Delimited;HDR=NO;IMEX=2;DSN=order_spec;DATABASE=L:/in"


def test_a_link_naming_a_specification_shows_its_column_count() -> None:
    layout = catalogues.declared_layout(DSN_CONNECT, {"order_spec": ["a", "b", "c"]})
    assert "`order_spec`" in layout and "3 column(s)" in layout


def test_a_link_naming_a_specification_the_database_lacks_says_so() -> None:
    """The layout of a headerless file is then declared nowhere.

    A sample is the only remaining route, which is EC-02, and the cell has to say that
    rather than read the same as a link that never named a specification.
    """
    layout = catalogues.declared_layout(DSN_CONNECT, {})
    assert "not in the database" in layout


def test_a_link_with_no_dsn_claims_nothing() -> None:
    assert catalogues.declared_layout("Text;DATABASE=L:/in", {"order_spec": ["a"]}) == ""
    assert catalogues.declared_layout("", {}) == ""


# --- the extractor itself, without Access -----------------------------------

MOCK = """
$ErrorActionPreference = 'Stop'
$c = Get-Content -Raw -LiteralPath '{script}'
$m = [regex]::Match($c, '(?ms)^function Read-ImexSpecifications\\(.*?^\\}}')
if (-not $m.Success) {{ throw 'Read-ImexSpecifications not found' }}
Invoke-Expression $m.Value

function New-Field($name, $value) {{
  [pscustomobject]@{{ Name = $name; Value = $value }}
}}
function New-Recordset($rows) {{
  $state = [pscustomobject]@{{ Index = 0; Rows = $rows }}
  $rs = [pscustomobject]@{{ State = $state }}
  $rs | Add-Member ScriptProperty EOF {{ $this.State.Index -ge $this.State.Rows.Count }}
  $rs | Add-Member ScriptProperty Fields {{
    $row = $this.State.Rows[$this.State.Index]
    @($row.Keys | ForEach-Object {{ New-Field $_ $row[$_] }})
  }}
  $rs | Add-Member ScriptMethod MoveNext {{ $this.State.Index++ }}
  $rs | Add-Member ScriptMethod Close {{ }}
  $rs
}}

$specRows = @([ordered]@{{ SpecID = 1; SpecName = 'order_spec' }})
$columnRows = @(
  [ordered]@{{ SpecID = 1; FieldName = '商品コード'; Start = 1; Width = 7 }},
  [ordered]@{{ SpecID = 1; FieldName = '数量'; Start = 8; Width = 5 }}
)
$database = [pscustomobject]@{{ Missing = '{missing}' }}
$database | Add-Member ScriptMethod OpenRecordset {{
  param($sql)
  if ($sql -match 'MSysIMEXSpecs') {{
    if ($this.Missing -eq 'specs') {{ throw 'no such table' }}
    return New-Recordset $specRows
  }}
  if ($this.Missing -eq 'columns') {{ throw 'no such table' }}
  return New-Recordset $columnRows
}}

$collector = [System.Collections.ArrayList]::new()
Read-ImexSpecifications $database $collector
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$json = $collector | ConvertTo-Json -Depth 8 -Compress
[Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($json))
"""


def run_reader(missing: str = "") -> list[dict]:
    """Run the real `Read-ImexSpecifications` against a mock DAO database.

    There is no Access here, and the function's whole job is talking to DAO - so the
    Database is mocked and the function is not. Base64 across the pipe for the reason
    `test_package_smoke.py` uses it: the names are Japanese and a console code page
    decides whether they survive.
    """
    import base64

    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        pytest.skip("PowerShell not available on this platform")
    command = MOCK.format(script=SCRIPT.as_posix(), missing=missing)
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
        check=False, capture_output=True)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    return json.loads(base64.b64decode(result.stdout.strip()).decode("utf-8"))


def test_the_reader_returns_every_field_of_every_row() -> None:
    """Not a chosen subset. A rename in Access's own schema would drop the layout."""
    records = run_reader()
    assert [record["table"] for record in records] == ["MSysIMEXSpecs", "MSysIMEXColumns"]
    assert all(record["status"] == "read" for record in records)

    columns = next(r for r in records if r["table"] == "MSysIMEXColumns")
    assert [row["FieldName"] for row in columns["rows"]] == ["商品コード", "数量"]
    # Start and Width came along without being asked for by name, which is the point.
    assert columns["rows"][0]["Start"] == "1" and columns["rows"][0]["Width"] == "7"


@pytest.mark.parametrize("missing", ["specs", "columns"])
def test_a_missing_specification_table_is_recorded_not_raised(missing: str) -> None:
    """A database with no saved specification has no such table.

    That is not a failure to extract - it means no link declared a DSN, or the spec was
    deleted after the link was made, which is itself worth recording because the link
    then has no declared layout anywhere.
    """
    records = run_reader(missing=missing)
    absent = [r for r in records if r["status"] == "absent"]
    assert len(absent) == 1
    assert absent[0]["reason"]
    assert absent[0]["rows"] == []
    # And the reader carried on to the other table rather than stopping.
    assert len(records) == 2


def test_the_reader_runs_only_for_a_link_that_declares_a_dsn() -> None:
    """Reading these always would put Access bookkeeping in every bundle.

    Asserted against the script text because the condition sits inside `Read-JetLayer`,
    which needs a real DAO Database to call. The regex is checked separately, below.
    """
    text = SCRIPT.read_text(encoding="utf-8")
    assert "Read-ImexSpecifications $Database $imexSpecs" in text
    assert "needsSpecs" in text
    guard = next(line for line in text.splitlines() if "$needsSpecs = " in line)
    assert "DSN" in guard and "connect" in guard


def test_the_dsn_guard_matches_a_real_connect_string_and_not_a_bare_link() -> None:
    """`Redact-Connection` leaves `DSN=` intact - it redacts credentials, not
    specification names - so the collected connect strings are enough to decide.
    """
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        pytest.skip("PowerShell not available on this platform")
    text = SCRIPT.read_text(encoding="utf-8")
    guard = next(line for line in text.splitlines() if "$needsSpecs = " in line)
    pattern = guard.split("-match", 1)[1].strip().rstrip("})").strip()
    command = (
        "$ErrorActionPreference='Stop';"
        f"$p = {pattern};"
        "$yes = 'Text;FMT=Delimited;HDR=NO;IMEX=2;DSN=order_spec;DATABASE=L:/in';"
        "$no = 'Text;DATABASE=L:/in';"
        "'{0},{1}' -f ($yes -match $p), ($no -match $p)"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
        check=False, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "True,False", result.stdout


# --- the two routes have to agree, and one of them cannot be run here ---------

BAS = PACKAGE / "tools" / "ExportAccessObjects.bas"


def test_the_exporter_reads_the_specifications_on_the_same_condition() -> None:
    """`evidence-layout.yaml` requires both routes to write the same containers.

    A17 fixed the runtime route. The exporter reads the same tables' `Connect`
    strings into `schema/tables.json`, so leaving it out produced the links without
    the layout they point at - which is the failure that file's opening note names.
    """
    text = BAS.read_text(encoding="utf-8")
    assert "LinkDeclaresDsn" in text
    assert "ExportImexSpecifications" in text
    assert "imex-specs.json" in text
    gate = next(line for line in text.splitlines() if "LinkDeclaresDsn = InStr" in line)
    assert ";DSN=" in gate
    # Spaces stripped first, because `; DSN =` is legal and the runtime route's regex
    # allows whitespace. The routes must agree on *when* they read, not only on what.
    assert 'Replace(c, " ", "")' in gate


def test_both_routes_emit_the_same_record_keys() -> None:
    """A consumer joins these without knowing which route wrote the file.

    `generate_catalogues.imex_columns` reads `table`, `status` and `rows`, and is the
    only consumer - so a key spelled differently by one route is a silent miss, which
    is the defect class this kit spends most of its time finding.
    """
    ps1 = SCRIPT.read_text(encoding="utf-8")
    bas = BAS.read_text(encoding="utf-8")
    for key in ("table", "status", "reason", "rows"):
        assert f'"{key}"' in ps1 or f"{key} =" in ps1, key
        assert f'Q & "{key}" & Q' in bas, f"the exporter does not emit {key!r}"
    for status in ("read", "absent"):
        assert f"'{status}'" in ps1 or f'"{status}"' in ps1, status
        assert f'Q & "{status}" & Q' in bas, status


def test_the_exporter_cannot_tell_a_missing_table_from_an_unreadable_one() -> None:
    """Recorded, not fixed. The runtime route has three statuses and this one has two.

    `read_error` means the table exists and the read failed; `absent` means there is
    no such table. One `On Error` around `OpenRecordset` cannot separate them, and the
    reason string carries the real message either way - so a consumer that needs the
    distinction has it in `reason` and not in `status`.

    Adding a third status would mean more VBA that no test in this repository can
    execute, on a path that has never fired. Named here so the difference is on the
    record rather than found later. Backlog A21.
    """
    ps1 = SCRIPT.read_text(encoding="utf-8")
    bas = BAS.read_text(encoding="utf-8")
    assert "'read_error'" in ps1
    assert 'Q & "read_error" & Q' not in bas


def test_the_quote_constant_is_one_quote() -> None:
    """The trap that produced the last defect in this file, in a new place.

    A double quote inside a VBA literal is written as two, so a constant holding one
    quote is four characters. Three would be an unterminated literal Access shows in
    red; five would put two quotes in every JSON key.
    """
    text = BAS.read_text(encoding="utf-8")
    line = next(l for l in text.splitlines() if l.startswith("Private Const Q "))
    assert line.endswith('= """"'), line


# --- the imported route has to read what the exporter writes ------------------

def test_the_importer_expands_the_exporter_file_into_the_interfaces_section() -> None:
    """Otherwise the exporter writes a file nothing reads, which is A15's defect.

    `_route_schema_tables` exists because `schema/tables.json` was written by the
    exporter and unread for long enough that the constraint "an export cannot reach
    Phase 1" looked like a property of exports rather than of a consumer. This is the
    same file one directory along.
    """
    sys.path.insert(0, str(PACKAGE))
    from adapters.base import empty_sections
    from adapters.imported_sources.adapter import _route_record

    sections = empty_sections()
    payload = [
        {"table": "MSysIMEXSpecs", "status": "read", "reason": "",
         "rows": [{"SpecID": "1", "SpecName": "order_spec"}]},
        {"table": "MSysIMEXColumns", "status": "read", "reason": "",
         "rows": [{"SpecID": "1", "FieldName": "商品コード"}]},
    ]
    _route_record(sections, {
        "kind": "metadata", "logical_id": "FRONT_1111:schema/imex-specs.json",
        "path": "FRONT_1111/schema/imex-specs.json",
        "text": json.dumps(payload, ensure_ascii=False),
    })
    carried = sections["interfaces"]["imex_specs"]
    assert [entry["table"] for entry in carried] == ["MSysIMEXSpecs", "MSysIMEXColumns"]
    assert all(entry["database_id"] == "FRONT_1111" for entry in carried)
    # And the catalogue's join reads what the importer produced, unchanged.
    assert catalogues.imex_columns(carried) == {"order_spec": ["商品コード"]}


def test_a_malformed_exporter_file_is_left_alone_rather_than_half_read() -> None:
    """A metadata record that is not this file must fall through to its own handler."""
    sys.path.insert(0, str(PACKAGE))
    from adapters.base import empty_sections
    from adapters.imported_sources.adapter import _route_imex_specs

    sections = empty_sections()
    assert not _route_imex_specs(sections, {
        "kind": "metadata", "logical_id": "FRONT_1111:schema/tables.json",
        "path": "FRONT_1111/schema/tables.json", "text": "[]"})
    assert not _route_imex_specs(sections, {
        "kind": "metadata", "logical_id": "FRONT_1111:schema/imex-specs.json",
        "path": "FRONT_1111/schema/imex-specs.json", "text": "{not json"})
    assert sections["interfaces"]["imex_specs"] == []
