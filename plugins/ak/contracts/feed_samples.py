"""What an import specification declares, against what the file actually contains.

A05's backend links six delimited text files. Every one declares `HDR=NO`, so a
column's meaning is positional, and `DSN=<spec name>` names the specification that
declares what those positions mean. A17 put those specifications in the bundle; A21
proved the second acquisition route reads them too. A17 also named the check neither
of them built - "comparing what the spec declares against what a supplied sample
contains, which is where a sender that has quietly added a column shows up" - and
nothing built it. `input/samples/` was inventoried and hashed; no reader in the kit
opened a sample's bytes. Backlog A23.

Run by hand once, it found something on the first application it saw: `Dpshohin.csv`
carries 29 fields where `DPSHOHIN ﾘﾝｸの定義` declares 28.

**Column order comes from `Start`, and the files prove it.** `MSysIMEXColumns` rows
come back in no useful order - A05's first row is column 20 of 26 - so the positions
are recovered by sorting on `Start`. Three of A05's six files carry a header row whose
names are identical to the declared names *in order*, 26, 29 and 26 of them, which is
independent confirmation that the sort reproduces the producer's real column order. It
is also why the header comparison is worth having at all: where a header exists it is
the sender's own statement of layout, and it can be read against the receiver's.

**Three reports, and why the third one exists.**

  *Fields.* The count the specification declares against the count the file carries.
  This caught `Dpshohin.csv`. It would not catch a sender that renamed a column
  without changing the count.

  *Header.* Where the file carries a header, whether those names are the declared ones,
  in the declared order. This is the half a count check cannot do, which is why it is
  part of the check rather than a refinement of it.

  *StartRow.* Whether `StartRow` agrees with the file having a header. It matters
  because `StartRow` differs *within* this one application - three of A05's feeds skip
  a row and three do not - so a rule assuming one answer would be wrong half the time.
  Both directions are reported: `StartRow=0` against a header row imports the names as
  a record, and `StartRow=1` against a headerless file drops a real one.

Deciding whether a first row is a header needs evidence, and two kinds are available.
Its cells may equal the declared names, which settles it. Failing that, a column the
specification declares numeric holding a non-numeric value cannot be data - which is
how the three A05 headers would still be recognised had the sender renamed every
column. Where neither signal is present the reading is `UNKNOWN` and nothing is
reported, because "no header" and "a header this cannot recognise" are then the same
observation.

**What is calibrated on one application, and what stops it being wrong elsewhere.**
A05 has one value of every declaration that matters here, so three shapes it does not
have are guarded rather than assumed. A link declaring anything but `FMT=Delimited` is
reported and not read: a fixed-width layout has no separators, and counting them would
report one field per record on every feed of such an application. A link declaring
`HDR=YES` has Access reading the header itself, so there the *absence* of a header is
the finding and its presence is not. And a specification whose columns do not carry
distinct `Start` values - a version naming that column differently would give every
column zero - has no order to compare positionally, so the names are compared as a set
and no position is named. The encoding ladder is the kit's own, shared with seven other
readers here; a feed arriving in a Western code page would decode as CP932 rather than
fail, which is why every line of the report names the codec it read the file with.

**What this does not answer.** Not whether the import works. A05's product feed
disagrees three ways - 29 fields in the file, 28 in the specification, 30 columns in
the destination table - and the third number is out of reach from here:
`メインメニュー.取り込み_Click` builds the statement as
`"INSERT INTO " & マスタ名 & " SELECT * FROM 元" & マスタ名`, so the destination never
appears as a literal and no reader can resolve it. Nor does it answer encoding.
`MSysIMEXSpecs.FileType` is 0 for all eight of A05's specifications, so the corpus
carries no evidence of what that field means, and this module reports the encoding
that decoded each file rather than claiming the specification declared one.
"""
from __future__ import annotations

import csv
import io
import json
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Any, Iterable, Iterator

import link_targets

# The DAO type codes that constrain a value to a number, from
# `specifications/dao-field-types.yaml`. Boolean, date, time and timestamp are left
# out deliberately: a date column's cell is a formatted string and "20260101" against
# "出荷日付" would be decided by the date format rather than by the type, which is a
# second question this does not need to answer to recognise a header.
NUMERIC_TYPES = frozenset({2, 3, 4, 5, 6, 7, 16, 19, 20, 21})

# The ladder A05's six files need, in this order. Three arrive CP932 and three UTF-8
# without a BOM, from senders who never agreed with each other. `utf-8-sig` only
# *strips* a BOM - it decodes a BOM-less UTF-8 file just as happily - so the codec a
# file is reported under is `utf-8` unless a BOM was actually there.
ENCODINGS = ("utf-8-sig", "utf-8", "cp932")

DECLARED = "DECLARED"
REORDERED = "REORDERED"
RENAMED = "RENAMED"
DATA = "DATA"
UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Column:
    """One declared column of a specification."""

    name: str
    start: int
    data_type: int
    width: int
    skipped: bool


@dataclass(frozen=True)
class Specification:
    """One `MSysIMEXSpecs` row with its `MSysIMEXColumns` rows, in file order."""

    name: str
    spec_id: str
    start_row: int
    separator: str
    quote: str
    file_type: str
    columns: tuple[Column, ...]

    @property
    def names(self) -> list[str]:
        return [column.name for column in self.columns]

    @property
    def delimiter(self) -> str:
        """The field separator, or empty when it is not one character.

        Access stores this as text and this kit has only ever seen `,`. Anything else
        is reported rather than guessed at, because a wrong delimiter turns every
        following number in this module into fiction. A tab-delimited application is
        the case to expect here: if its `FieldSeparator` arrives as the two characters
        `\\t`, this reports that string rather than parsing the file as one field.
        """
        return self.separator if len(self.separator) == 1 else ""

    @property
    def order_known(self) -> bool:
        """Whether `Start` actually establishes an order for these columns.

        A05's do - 0, 8, 40, 82, 133 - and three of its files confirm it. A version
        that names the column something else, or a specification carrying one column,
        gives every column the same `Start`, and then a positional comparison would
        report every name as moved. Nothing is claimed about order in that case.
        """
        starts = [column.start for column in self.columns]
        return len(starts) < 2 or len(set(starts)) == len(starts)


@dataclass(frozen=True)
class Width:
    """A field count, how many records carry it, and where it first appears."""

    fields: int
    records: int
    first_record: int


@dataclass(frozen=True)
class Header:
    """What the first record of a file is: names, data, or not decidable."""

    verdict: str
    detail: str
    differences: tuple[str, ...] = ()

    @property
    def present(self) -> bool:
        return self.verdict in (DECLARED, REORDERED, RENAMED)


@dataclass(frozen=True)
class Sample:
    """One supplied file, as read through the specification that describes it."""

    codec: str
    bom: bool
    records: int
    widths: tuple[Width, ...]
    header: Header
    problem: str = ""

    @property
    def fields(self) -> int:
        """The field count most of the file's records carry."""
        return self.widths[0].fields if self.widths else 0


@dataclass(frozen=True)
class Feed:
    """A declared import feed, and the file or expression it points at.

    The connect string's own declarations travel with it, because two of them decide
    whether a comparison means anything and A05 has one value of each: `FMT=Delimited`
    (a fixed-width link's fields are not separated at all, so counting separators would
    report one field per record on every one of them) and `HDR=NO` (with `HDR=YES`
    Access reads the header itself, and calling that "the names are imported as a
    record" would be a false finding).
    """

    table: str
    database_id: str
    spec_name: str
    file_name: str
    declared_format: str = ""
    header_declared: str = ""
    origin: str = "link"
    path_expression: str = ""
    operation: str = ""
    direction: str = "inbound"
    declared_in: str = ""

    @property
    def expects_header(self) -> bool:
        return self.header_declared.strip().upper() == "YES"

    @property
    def is_delimited(self) -> bool:
        """Whether the link declares the one format this compares.

        An undeclared format is treated as delimited: every text link this kit has seen
        declares `FMT=`, a specification with a field separator describes a delimited
        file, and refusing to read the file on a missing declaration would turn the
        common case into silence.
        """
        return self.declared_format.strip().lower() in ("", "delimited")


@dataclass(frozen=True)
class Finding:
    """One thing worth a person's attention, and what kind of thing it is."""

    tag: str
    says: str


def _keys(row: dict) -> dict[str, Any]:
    """A row's fields, lowercased.

    These are Access's own column names and are not verified here against a live
    database. Matching them exactly is how a version difference would silently drop
    the layout this exists to read.
    """
    return {str(key).lower(): value for key, value in row.items()}


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def specifications(records: Iterable[dict]) -> dict[str, Specification]:
    """The `SpecID` join, by specification name, with columns in file order.

    Done here rather than in either extractor because here it can be tested, and in
    one place rather than two because two joins of the same two tables disagreeing is
    the defect this kit keeps finding elsewhere. `absent` and `read_error` records
    contribute nothing: their reason is recorded so it survives, not so it counts.
    """
    specs: dict[str, dict[str, Any]] = {}
    columns: dict[str, list[Column]] = {}
    for record in records:
        if record.get("status") != "read":
            continue
        table = str(record.get("table") or "")
        for row in record.get("rows") or []:
            keys = _keys(row)
            spec_id = str(keys.get("specid") or "")
            if not spec_id:
                continue
            if table == "MSysIMEXSpecs":
                if keys.get("specname"):
                    specs[spec_id] = keys
            elif keys.get("fieldname"):
                columns.setdefault(spec_id, []).append(Column(
                    name=str(keys.get("fieldname")),
                    start=_int(keys.get("start")),
                    data_type=_int(keys.get("datatype")),
                    width=_int(keys.get("width")),
                    skipped=str(keys.get("skipcolumn") or "").strip().lower()
                    in ("true", "-1", "yes"),
                ))
    found: dict[str, Specification] = {}
    for spec_id, keys in specs.items():
        ordered = sorted(columns.get(spec_id, []), key=lambda column: column.start)
        found[str(keys.get("specname"))] = Specification(
            name=str(keys.get("specname")),
            spec_id=spec_id,
            start_row=_int(keys.get("startrow")),
            separator=str(keys.get("fieldseparator") or ""),
            quote=str(keys.get("textdelim") or ""),
            file_type=str(keys.get("filetype") or ""),
            columns=tuple(ordered),
        )
    return found


def declared(connect: str, key: str) -> str:
    """One `KEY=value` a connect string declares, if it declares it.

    Values are taken to the next `;` and not split further: A05's specification names
    carry spaces and half-width katakana (`DSN=Order ﾘﾝｸの定義2`), so anything narrower
    would cut them.
    """
    match = re.search(rf"(?i)(?:^|;)\s*{key}\s*=\s*([^;]+)", connect or "")
    return match.group(1).strip() if match else ""


def specification_name(connect: str) -> str:
    """The specification a link's connect string names, if it names one.

    A42. An ODBC connect string also carries `DSN=`, and there it is an ODBC data
    source, not an Access import/export specification. Reading it as one made A06's
    three SQL Server links its only three "file feeds" - `dbo.仕入商品マスタ` reported as
    a file whose layout is declared nowhere, so a FORMAT claim about a database table
    was told to go find a sample of it (EC-02). It also filled the catalogue's
    `Declared columns` cell with `SMSIIS_TargetNeo` **not in the database**, a finding
    about a specification nobody ever declared.

    A text or Excel link names its driver - `Text;DSN=spec;FMT=Delimited;...` - and an
    ODBC link names `ODBC`. So the driver settles it, and the kind is read through the
    one parser that knows what these strings are rather than by matching `DSN=` again
    here.
    """
    if link_targets.parse_connect(connect)["kind"] == "odbc":
        return ""
    return declared(connect, "DSN")


def base_name(value: str) -> str:
    """The file name a link points at, with any directory it came with removed."""
    name = str(value or "").strip().strip('"')
    if not name:
        return ""
    return PureWindowsPath(PurePosixPath(name).name).name


def feeds(rows: Iterable[dict]) -> list[Feed]:
    """Every link that declares a `DSN=`, from bundle rows in either shape.

    A bundle carries linked tables both flat, as the managed route wrote them, and
    nested under `metadata`, as the derived graph does. Both shapes sit in one file in
    A05's bundle, so a reader of one shape sees half the boundary.
    """
    found: list[Feed] = []
    for row in rows:
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        connect = str(row.get("connect") or meta.get("connect") or "")
        spec = specification_name(connect)
        if not spec:
            continue
        source = (row.get("source_table_name") or meta.get("source_table_name")
                  or row.get("path") or row.get("name") or "")
        found.append(Feed(
            table=str(row.get("name") or row.get("path") or ""),
            database_id=str(row.get("database_id") or meta.get("database_id") or ""),
            spec_name=spec,
            file_name=base_name(str(source)),
            declared_format=declared(connect, "FMT"),
            header_declared=declared(connect, "HDR"),
        ))
    return found


def _vba_code_lines(text: str) -> Iterator[str]:
    pending = ""
    for raw in text.splitlines():
        line = []
        quoted = False
        for char in raw:
            if char == '"':
                quoted = not quoted
            if char == "'" and not quoted:
                break
            line.append(char)
        current = "".join(line).rstrip()
        if current.endswith("_"):
            pending += current[:-1] + " "
            continue
        yield pending + current
        pending = ""
    if pending.strip():
        yield pending


def _vba_arguments(text: str) -> list[str]:
    arguments: list[str] = []
    start = 0
    quoted = False
    depth = 0
    for index, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        elif not quoted and char == "(":
            depth += 1
        elif not quoted and char == ")":
            depth = max(0, depth - 1)
        elif not quoted and char == "," and depth == 0:
            arguments.append(text[start:index].strip())
            start = index + 1
    arguments.append(text[start:].strip())
    return arguments


def _vba_literal(value: str) -> str:
    value = value.strip()
    if len(value) < 2 or value[0] != '"' or value[-1] != '"':
        return ""
    return value[1:-1].replace('""', '"')


# Which way the data moves, from the transfer type the call names. `acLink` reads
# `inbound` because the rows arrive from the file; it is kept distinct from `acImport`
# in `transfer_type`, because an attachment that stays live is not a copy taken once.
_DIRECTIONS = (("acimport", "inbound"), ("acexport", "outbound"), ("aclink", "inbound"))



# `DoCmd.OutputTo ObjectType, [ObjectName], [OutputFormat], [OutputFile], ...`
_OUTPUT_TO = re.compile(r"(?i)(?:DoCmd\.)?OutputTo\b")
# `acFormatXLS` -> `XLS`, which is what an operator calls the file.
_OUTPUT_FORMAT = re.compile(r"(?i)^acFormat(.+)$")


def _output_to_feeds(records: Iterable[dict]) -> list[Feed]:
    """Every `DoCmd.OutputTo` call: Access's third way of writing a file.

    A64. The scan knew `TransferText` and `TransferSpreadsheet` and Access has three
    verbs, so A06's `電算データ作成画面` wrote an Excel file that appeared in no boundary
    list, and `共通関数` held a generic exporter whose every argument is a variable.

    Always outbound - there is no direction argument, and that is the whole difference
    from the transfer verbs. The file argument is optional, so a call is kept without
    one: Access prompts for the destination at run time, and a boundary whose
    destination is chosen by whoever runs it is a finding, not a row to drop.
    """
    found: list[Feed] = []
    for record in records:
        text = str(record.get("text") or "")
        declared_in = str(record.get("name") or record.get("object_name") or "")
        constants = _constants(text)
        for line in _vba_code_lines(text):
            for match in _OUTPUT_TO.finditer(line):
                arguments_text = line[match.end():].strip()
                if arguments_text.startswith("(") and arguments_text.endswith(")"):
                    arguments_text = arguments_text[1:-1].strip()
                arguments = _vba_arguments(arguments_text)
                if len(arguments) < 2:
                    # `OutputTo` with only a type exports the active object. Nothing
                    # names what leaves, so there is no boundary to record.
                    continue
                object_name = _vba_literal(arguments[1]) or arguments[1]
                if not object_name:
                    continue
                declared_format = ""
                if len(arguments) > 2:
                    fmt = _OUTPUT_FORMAT.match(arguments[2].strip())
                    declared_format = fmt.group(1) if fmt else arguments[2].strip()
                path_expression = arguments[3].strip() if len(arguments) > 3 else ""
                resolved, is_literal = _resolve_path(path_expression, constants)
                found.append(Feed(
                    table=object_name,
                    database_id=str(record.get("database_id") or ""),
                    spec_name="",
                    file_name=base_name(resolved) if is_literal else "",
                    declared_format=declared_format,
                    header_declared="",
                    origin="code",
                    path_expression=resolved or path_expression,
                    operation=f"OutputTo {arguments[0].strip()}".strip(),
                    direction="outbound",
                    declared_in=declared_in,
                ))
    return found


# `Const NAME = "literal"`, module level or inside a procedure.
_CONST = re.compile(r'(?i)^\s*(?:Public\s+|Private\s+)?Const\s+([^\s=]+)\s*=\s*"([^"]*)"\s*$')


def _constants(text: str) -> dict[str, str]:
    """String constants a definition declares, keeping only names assigned once.

    A06 declares each import path twice - a live block and a commented-out test block
    beneath it - and `_vba_code_lines` has already dropped the commented one. A name
    that is still assigned twice after that resolves to nothing: picking the last
    would be picking by file order.
    """
    seen: dict[str, str] = {}
    twice: set[str] = set()
    for line in _vba_code_lines(text):
        match = _CONST.match(line)
        if not match:
            continue
        name = match.group(1).strip()
        if name in seen and seen[name] != match.group(2):
            twice.add(name)
        seen[name] = match.group(2)
    return {name: value for name, value in seen.items() if name not in twice}


def _resolve_path(expression: str, constants: dict[str, str]) -> tuple[str, bool]:
    """Substitute constants into a `&` chain. Returns the text and whether it is literal.

    Literal means every part resolved, so the result is a real path a sample can be
    matched against. A part that is a call or an unknown name keeps its own text, and
    the caller must not treat the result as a file name - `Format(Me.受注日,
    "yyyymmdd")` is knowable at run time and not before.
    """
    raw = (expression or "").strip()
    if not raw:
        return "", False
    rendered: list[str] = []
    resolved: list[str] = []
    literal = True
    for part in _vba_split_concat(raw):
        if len(part) >= 2 and part[0] == '"' and part[-1] == '"':
            value = _vba_literal(part)
            resolved.append(value)
            rendered.append(f'"{value}"')
        elif part in constants:
            resolved.append(constants[part])
            rendered.append(f'"{constants[part]}"')
        else:
            rendered.append(part)
            literal = False
    if literal:
        return "".join(resolved), True
    return " & ".join(rendered), False


def _vba_split_concat(text: str) -> list[str]:
    """Split on `&` at depth zero, outside string literals."""
    parts: list[str] = []
    depth = quoted = 0
    start = 0
    for index, char in enumerate(text):
        if char == '"':
            quoted = 1 - quoted
        elif not quoted and char == "(":
            depth += 1
        elif not quoted and char == ")":
            depth = max(0, depth - 1)
        elif not quoted and char == "&" and depth == 0:
            parts.append(text[start:index])
            start = index + 1
    parts.append(text[start:])
    return [part for part in (piece.strip() for piece in parts) if part]

def code_feeds(records: Iterable[dict]) -> list[Feed]:
    """Find every `TransferText` and `TransferSpreadsheet` call in definition text.

    A46. A feed the code declares is a feed, and until this existed the inventory began
    at a link's connect string - so A06's four live CSV inputs, each named in a
    `TransferText` call and each with its layout saved in the database, appeared in no
    document at all.

    Both directions, because the section that prints these says *inbound and outbound*
    and a heading that over-promises is the same defect one level up: A06 writes three
    CSVs from code and holds a saved specification called `商品マスタ ｴｸｽﾎﾟｰﾄ定義`,
    none of which a caller filtering on `acImport` would ever see.

    A call is retained even when its file path is a variable or its specification is
    absent. Those are boundaries the code proves, and the unresolved path is reported as
    itself rather than becoming a file name nobody can find. No sample comparison is
    attempted without a literal specification and file name.
    """
    found: list[Feed] = []
    found += _output_to_feeds(records)
    call_pattern = re.compile(r"(?i)(?:DoCmd\.)?(TransferText|TransferSpreadsheet)\b")
    for record in records:
        text = str(record.get("text") or "")
        declared_in = str(record.get("name") or record.get("object_name") or "")
        # A65. A path assembled from constants declared in this same definition is a
        # path, not an unknown. Five of A06's eleven sample findings were answerable
        # from the file they were reported against.
        constants = _constants(text)
        for line in _vba_code_lines(text):
            for match in call_pattern.finditer(line):
                arguments_text = line[match.end():].strip()
                if arguments_text.startswith("(") and arguments_text.endswith(")"):
                    arguments_text = arguments_text[1:-1].strip()
                arguments = _vba_arguments(arguments_text)
                if len(arguments) < 4:
                    continue
                transfer_type = arguments[0].strip()
                folded = transfer_type.casefold()
                direction = next((way for prefix, way in _DIRECTIONS
                                  if folded.startswith(prefix)), "")
                if not direction:
                    # A transfer type held in a variable, or omitted so that Access
                    # applies its default. Which way it moves is not readable here, and
                    # guessing would put a file in the wrong half of the boundary.
                    continue
                is_text = match.group(1).casefold() == "transfertext"
                spec_name = _vba_literal(arguments[1]) if is_text else ""
                table_value = _vba_literal(arguments[2]) or arguments[2]
                path_value, path_is_literal = _resolve_path(arguments[3], constants)
                if not path_is_literal:
                    path_value = ""
                header = ""
                if len(arguments) > 4:
                    header_value = arguments[4].strip().casefold()
                    if header_value in {"true", "-1"}:
                        header = "YES"
                    elif header_value in {"false", "0"}:
                        header = "NO"
                declared_format = (
                    "Delimited" if "delim" in folded else transfer_type
                ) if is_text else "Spreadsheet"
                found.append(Feed(
                    table=table_value,
                    database_id=str(record.get("database_id") or ""),
                    spec_name=spec_name,
                    file_name=base_name(path_value),
                    declared_format=declared_format,
                    header_declared=header,
                    origin="code",
                    path_expression=_resolve_path(arguments[3], constants)[0]
                    or arguments[3],
                    operation=f"{match.group(1)} {transfer_type}".strip(),
                    direction=direction,
                    declared_in=declared_in,
                ))
    return found


# Where a definition's text lives in a bundle, by the section that holds its inventory.
# VBA is written out as a file and named by `path`; a form or report carries its text
# inline. Both shapes are read here so that no caller has to know which is which.
_DEFINITION_SECTIONS = (("code", "vba"), ("ui", "forms"), ("ui", "reports"),
                        ("ui", "macros"))


def code_feeds_of_bundle(bundle) -> list[Feed]:
    """Every code-declared feed in a sealed bundle, for any reader that wants them.

    A33's rule, applied before it could be broken: the catalogue and `$ak samples` both
    need this, and the first version of A46 gave each its own copy. The copies had
    already drifted - one decoded VBA as UTF-8 only and raised on a CP932 module, which
    is the ordinary encoding of a Japanese application's exported code. A reader that
    lists a feed and a reader that crashes on it are two answers to one question.
    """
    records: list[dict] = []
    for section, folder in _DEFINITION_SECTIONS:
        for record in _inventory(bundle / section / folder / "inventory.json"):
            text = record.get("text")
            if text is None and record.get("path"):
                text = read_definition(bundle / section / folder / str(record["path"]))
            if text is not None:
                records.append({**record, "text": text})
    return code_feeds(records)


def _inventory(path) -> list[dict]:
    """The rows of one bundle inventory, or none when the section is absent."""
    raw = read_definition(path)
    if raw is None:
        return []
    try:
        data = json.loads(raw)
    except ValueError:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value
    return []


def read_definition(path) -> str | None:
    """A definition file's text, or None when nothing could read it.

    The same codec order the rest of the kit uses. `None` rather than `""` so that a
    file which exists and cannot be decoded is distinguishable from one that is empty -
    silently reading an undecodable module as blank is how a declared feed disappears.
    """
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
        except OSError:
            return None
    return None


def decode(raw: bytes) -> tuple[str, str, bool]:
    """The file's text, the codec that read it, and whether it carried a BOM.

    Returns an empty codec when nothing in the ladder decodes the bytes, which is a
    reportable state rather than an error: a file this cannot read is a file whose
    format claim has no evidence, and pretending it decoded would be worse.
    """
    bom = raw.startswith(b"\xef\xbb\xbf")
    for codec in ENCODINGS:
        try:
            text = raw.decode(codec)
        except UnicodeDecodeError:
            continue
        return text, ("utf-8" if codec == "utf-8-sig" and not bom else codec), bom
    return "", "", bom


def numeric_like(value: str) -> bool:
    """Whether a cell could be the number a numeric column declares.

    Deliberately permissive - an empty cell passes, and so does a thousands separator
    inside a quoted field - because this decides whether a row is a *header*, and the
    cost of being wrong in that direction is a false claim about the sender.
    """
    text = str(value).strip().replace(",", "")
    if not text:
        return True
    try:
        float(text)
    except ValueError:
        return False
    return True


def records_of(text: str, delimiter: str, quote: str) -> Iterator[list[str]]:
    """The file's records, honouring the text delimiter the specification declares.

    Splitting on the separator instead would break every quoted field containing one,
    and a quoted newline would turn one record into two - which is the difference
    between a field count and a guess.

    Yielded rather than collected. A05's largest sample is 3.5 MB and 15,305 records,
    but a "sample" is whatever an operator copied off a share, and holding a list of
    lists for one of those is the multiplier that turns a large file into a failure
    instead of a slow answer.
    """
    stream = io.StringIO(text, newline="")
    if quote:
        reader = csv.reader(stream, delimiter=delimiter, quotechar=quote)
    else:
        reader = csv.reader(stream, delimiter=delimiter, quoting=csv.QUOTE_NONE)
    for row in reader:
        if row:
            yield row


def header_reading(spec: Specification, row: list[str]) -> Header:
    """What the first record of the file is.

    `DECLARED` is every declared name at its own position; a file with an extra column
    can still carry the declared names in order, and saying so beside the field-count
    finding reads far better than calling it a renamed header.
    """
    names = [name.strip() for name in spec.names]
    cells = [cell.strip() for cell in row]
    if not names or not cells:
        return Header(UNKNOWN, "no declared columns to compare with")

    same_set = (set(cell for cell in cells if cell)
                == set(name for name in names if name))
    if not spec.order_known:
        # `Start` establishes no order for these columns, so a positional reading would
        # report every name as moved. The names can still be compared as a set.
        if same_set:
            return Header(DECLARED, "the declared names; the specification does not "
                                    "state what order they are in")
        return _renamed_or_data(spec, names, cells, positional=False)

    overlap = min(len(cells), len(names))
    matched = [index for index in range(overlap) if cells[index] == names[index]]
    if overlap and len(matched) == overlap:
        detail = "the declared names, in order"
        if len(cells) != len(names):
            detail += f" for the first {overlap} of {len(names)}"
        return Header(DECLARED, detail)

    if same_set:
        return Header(REORDERED, "the declared names, in a different order")

    return _renamed_or_data(spec, names, cells, positional=True)


def _renamed_or_data(spec: Specification, names: list[str], cells: list[str],
                     positional: bool) -> Header:
    """A first record that is not the declared names: a header, data, or unreadable.

    Two signals, and one of them survives a sender renaming every column: a column the
    specification declares numeric cannot hold text in a data record. `positional` is
    false when `Start` established no order, and then the differences are not listed -
    a position this cannot place is a position it must not name.
    """
    overlap = min(len(cells), len(names))
    matched = [index for index in range(overlap)
               if positional and cells[index] == names[index]]
    numeric = [index for index, column in enumerate(spec.columns)
               if column.data_type in NUMERIC_TYPES and index < len(cells)]
    non_numeric = [index for index in numeric if not numeric_like(cells[index])]

    differences = tuple(
        f"position {index + 1}: declared `{names[index]}`, file `{cells[index]}`"
        for index in range(overlap) if positional and cells[index] != names[index]
    )
    if matched or non_numeric:
        why = (f"{len(non_numeric)} column(s) declared numeric hold text"
               if non_numeric else f"{len(matched)} name(s) are the declared ones")
        return Header(RENAMED, f"a header row whose names differ ({why})", differences)
    if numeric:
        return Header(DATA, "no header row")
    return Header(UNKNOWN, "cannot tell whether the first record is a header")


def sample_of(raw: bytes, spec: Specification) -> Sample:
    """Read one supplied file through one specification."""
    text, codec, bom = decode(raw)
    if not codec:
        return Sample(codec="", bom=bom, records=0, widths=(),
                      header=Header(UNKNOWN, "the file did not decode"),
                      problem="no encoding in the ladder "
                              f"({', '.join(ENCODINGS)}) decodes this file")
    delimiter = spec.delimiter
    if not delimiter:
        return Sample(codec=codec, bom=bom, records=0, widths=(),
                      header=Header(UNKNOWN, "the file was not parsed"),
                      problem="the specification's field separator is not one "
                              f"character: {spec.separator!r}")
    counted: Counter[int] = Counter()
    first_at: dict[int, int] = {}
    first_row: list[str] = []
    total = 0
    for row in records_of(text, delimiter, spec.quote):
        total += 1
        if total == 1:
            first_row = row
        counted[len(row)] += 1
        first_at.setdefault(len(row), total)
    widths = tuple(sorted(
        (Width(fields, records, first_at[fields]) for fields, records in counted.items()),
        key=lambda width: (-width.records, width.fields),
    ))
    return Sample(codec=codec, bom=bom, records=total, widths=widths,
                  header=header_reading(spec, first_row))


def format_problem(feed: Feed | None) -> Finding | None:
    """The declaration that has to be read before the file is.

    A fixed-width link's fields are not separated at all, so parsing one on a field
    separator reports a single field per record - on every feed of such an application,
    which is a check nobody would read a second time. Its layout is in the `Start` and
    `Width` of the same specification rows and nothing here reads them that way yet.
    """
    if feed is None or feed.is_delimited:
        return None
    return Finding("FORMAT", f"the feed declares FMT={feed.declared_format}, and this "
                   "compares delimited files only - a fixed-width layout is declared "
                   "by Start and Width, which nothing here reads yet")


def disagreements(spec: Specification, sample: Sample,
                  feed: Feed | None = None) -> list[Finding]:
    """Everything this pair says that does not agree, in the order to read it.

    `feed` carries the link's own declarations and changes what may be concluded. A05
    has one value of each - `FMT=Delimited` and `HDR=NO` - so it exercises neither
    branch, and an application with the other value would be reported wrongly by a
    check calibrated on this one.
    """
    found: list[Finding] = []
    unreadable = format_problem(feed)
    if unreadable is not None:
        return [unreadable]
    if sample.problem:
        return [Finding("UNREADABLE", sample.problem)]
    if not sample.records:
        return [Finding("EMPTY", "the file carries no records")]

    declared = len(spec.columns)
    if sample.fields != declared:
        found.append(Finding("FIELDS", f"the specification declares {declared} "
                                       f"column(s), the file carries {sample.fields}"))
    if len(sample.widths) > 1:
        spread = "; ".join(
            f"{width.fields} field(s) in {width.records} record(s), first at record "
            f"{width.first_record}" for width in sample.widths)
        found.append(Finding("RAGGED", f"records disagree about field count: {spread}"))

    header = sample.header
    if header.verdict in (REORDERED, RENAMED):
        says = header.detail
        if header.differences:
            says += " - " + "; ".join(header.differences[:3])
        found.append(Finding("HEADER", says))

    # With `HDR=YES` Access reads the header itself, so a header row is what the link
    # asked for and its absence is the finding rather than its presence.
    if feed is not None and feed.expects_header:
        if header.verdict == DATA:
            found.append(Finding("HEADER", "the link declares HDR=YES and the file "
                                 "carries no header row, so its first record of data "
                                 "is read as the column names"))
        return found

    if spec.start_row == 0 and header.present:
        found.append(Finding("STARTROW", "StartRow=0 and the file carries a header "
                                         "row, so the names are imported as a record"))
    skipped = spec.start_row - (1 if header.present else 0)
    if skipped > 0 and header.verdict != UNKNOWN:
        found.append(Finding("STARTROW", f"StartRow={spec.start_row} against "
                             f"{'a header row' if header.present else 'no header row'}, "
                             f"so {skipped} record(s) of data are dropped"))
    return found


def encoding_spread(samples: Iterable[tuple[Specification, Sample]]) -> str:
    """One line when an application's feeds do not share an encoding.

    A05's do not: three CP932 and three UTF-8, from senders who never agreed with each
    other, while all eight specifications declare the same `FileType`. An importer
    written against either half breaks the other, so this is worth saying once at the
    application level rather than per feed.
    """
    codecs = Counter(sample.codec for _, sample in samples if sample.codec)
    if len(codecs) < 2:
        return ""
    declared = sorted({spec.file_type for spec, sample in samples if sample.codec})
    spread = ", ".join(f"{codec} ({count})" for codec, count in sorted(codecs.items()))
    note = (f"every specification declares FileType={declared[0]}"
            if len(declared) == 1 else f"FileType is one of {', '.join(declared)}")
    return (f"the feeds do not share one encoding: {spread}. Meanwhile {note}, and what "
            "that field says about encoding is not established here - so an importer "
            "has to detect the encoding rather than assume the application's.")
