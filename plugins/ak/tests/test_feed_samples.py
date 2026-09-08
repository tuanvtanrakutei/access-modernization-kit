"""An import specification against the sample it describes - and what that cannot say.

A17 predicted this check and did not build it. A21 made it possible by proving both
acquisition routes read the two specification tables, and A23 found something on the
first application it saw: `Dpshohin.csv` carries 29 fields where `DPSHOHIN ﾘﾝｸの定義`
declares 28.

The tests are as much about the limits as the catch. A count check alone would have
found that file and would not find a sender who renames a column without changing the
count, which is why the header comparison is here. And where a first record cannot be
told apart from data, nothing is reported at all - "no header" and "a header this
cannot recognise" are the same observation, and reporting a `StartRow` disagreement on
that basis would be a claim about the sender that the file does not support.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
sys.path.insert(0, str(PACKAGE / "contracts"))

import feed_samples as feeds  # noqa: E402
import check_feed_samples as checker  # noqa: E402

DB = "DATA_4A6C58E8"
SPEC = "DPSHOHIN ﾘﾝｸの定義"
CONNECT = f"Text;DSN={SPEC};FMT=Delimited;HDR=NO;IMEX=2;DATABASE=L:\\品揃支援"

# dbLong and dbText, the two types every one of A05's 176 declared columns uses.
LONG = 4
TEXT = 10


def spec_row(name: str = SPEC, spec_id: str = "28", start_row: int = 0,
             separator: str = ",", quote: str = '"') -> dict:
    return {"SpecID": spec_id, "SpecName": name, "StartRow": str(start_row),
            "FieldSeparator": separator, "TextDelim": quote, "FileType": "0",
            "SpecType": "1"}


def column_row(name: str, start: int, data_type: int = TEXT,
               spec_id: str = "28") -> dict:
    return {"SpecID": spec_id, "FieldName": name, "Start": str(start),
            "DataType": str(data_type), "Width": "10", "SkipColumn": "False"}


def records(specs: list[dict], columns: list[dict], status: str = "read") -> list[dict]:
    return [{"table": "MSysIMEXSpecs", "status": status, "reason": "", "rows": specs},
            {"table": "MSysIMEXColumns", "status": status, "reason": "", "rows": columns}]


def three_columns(start_row: int = 0) -> feeds.Specification:
    """A specification shaped like A05's: an id, a name, a quantity."""
    return feeds.specifications(records(
        [spec_row(start_row=start_row)],
        [column_row("店舗名", start=8, data_type=TEXT),
         column_row("伝票番号", start=0, data_type=LONG),
         column_row("数量", start=40, data_type=LONG)],
    ))[SPEC]


# --- the join, and the order the columns come back in ------------------------

def test_columns_are_ordered_by_start_and_not_by_row_order() -> None:
    """The fact three of A05's six files independently confirm.

    `MSysIMEXColumns` rows arrive in no useful order - A05's first row is column 20 of
    26 - and three of the six files carry a header whose names are the declared names
    *in order*, 26, 29 and 26 of them. That agreement is only reachable by sorting on
    `Start`, and it is what makes the header comparison possible at all.
    """
    assert three_columns().names == ["伝票番号", "店舗名", "数量"]


def test_the_declared_format_travels_with_the_specification() -> None:
    spec = three_columns(start_row=1)
    assert spec.start_row == 1 and spec.delimiter == "," and spec.quote == '"'
    assert spec.spec_id == "28" and spec.file_type == "0"


@pytest.mark.parametrize("status", ["absent", "read_error"])
def test_an_unread_specification_table_contributes_nothing(status: str) -> None:
    """The reason is recorded so it survives, not so it counts."""
    assert feeds.specifications(records([spec_row()], [column_row("a", 0)],
                                        status=status)) == {}


def test_a_specification_with_no_columns_still_appears() -> None:
    """A layout somebody created and never filled in reads differently from one the
    database does not hold, and only one of those two is this."""
    found = feeds.specifications(records([spec_row()], []))
    assert found[SPEC].columns == ()


# --- which file a link points at --------------------------------------------

def test_a_link_is_read_in_either_shape_the_bundle_stores_it_in() -> None:
    """Both shapes sit in one file in A05's bundle.

    The managed route writes linked tables flat; the derived graph nests them under
    `metadata`. A reader of one shape sees half the boundary.
    """
    found = feeds.feeds([
        {"name": "元商品マスタ", "database_id": DB, "connect": CONNECT,
         "source_table_name": "dpshohin.csv"},
        {"name": "元店舗マスタ", "database_id": DB,
         "metadata": {"connect": CONNECT, "source_table_name": "dptenpo.csv"}},
    ])
    assert [feed.file_name for feed in found] == ["dpshohin.csv", "dptenpo.csv"]
    assert {feed.spec_name for feed in found} == {SPEC}


def test_a_link_that_names_no_specification_is_not_a_feed() -> None:
    assert feeds.feeds([{"name": "操作履歴", "connect": ";DATABASE=L:\\x\\data.mdb"}]) == []


def test_the_file_name_loses_any_directory_it_arrived_with() -> None:
    assert feeds.base_name("L:\\品揃支援\\order.txt") == "order.txt"
    assert feeds.base_name("in/order.txt") == "order.txt"
    assert feeds.base_name("") == ""


# --- reading the bytes -------------------------------------------------------

def test_both_encodings_a05_actually_receives_are_read() -> None:
    """Three of the six files are CP932 and three are UTF-8, from senders who never
    agreed with each other."""
    text, codec, bom = feeds.decode("店舗名".encode("cp932"))
    assert (text, codec, bom) == ("店舗名", "cp932", False)
    text, codec, bom = feeds.decode("店舗名".encode("utf-8"))
    assert (text, codec, bom) == ("店舗名", "utf-8", False)


def test_a_utf8_file_without_a_bom_is_not_reported_as_having_one() -> None:
    """`utf-8-sig` decodes a BOM-less file just as happily, so the codec a file is
    reported under has to come from the bytes rather than from which attempt won."""
    assert feeds.decode(b"\xef\xbb\xbfa,b")[1:] == ("utf-8-sig", True)
    assert feeds.decode(b"a,b")[1:] == ("utf-8", False)


def test_a_file_no_encoding_in_the_ladder_reads_is_reported_not_raised() -> None:
    sample = feeds.sample_of(b"\x81\xff\xfe\x00\x81", three_columns())
    assert "decodes this file" in sample.problem
    assert feeds.disagreements(three_columns(), sample)[0].tag == "UNREADABLE"


def test_a_separator_inside_a_quoted_field_is_not_a_field_boundary() -> None:
    sample = feeds.sample_of('1,"安楽亭, 蕨芝店",3\n'.encode("cp932"), three_columns())
    assert sample.fields == 3


def test_the_records_are_streamed_rather_than_collected() -> None:
    """A05's largest sample is 3.5 MB, and a sample is whatever was copied off a share.

    Asserted on the shape rather than on a big file, because the regression to guard
    against is somebody folding this back into a list comprehension - which reads
    better and holds a list of lists for the whole file.
    """
    assert isinstance(feeds.records_of("1,2,3\n", ",", '"'), Iterator)


def test_the_field_count_comes_from_records_and_not_from_lines() -> None:
    """A quoted newline turns one record into two for anything splitting on lines,
    which is the difference between a field count and a guess."""
    sample = feeds.sample_of('1,"蕨芝店\n2号",3\n'.encode("cp932"), three_columns())
    assert sample.records == 1 and sample.fields == 3


# --- what the first record is ------------------------------------------------

def test_a_header_of_the_declared_names_in_order_is_recognised() -> None:
    """A05's `２１商品.CSV`, at 29 columns; the same reading at three."""
    sample = feeds.sample_of("伝票番号,店舗名,数量\n1,蕨芝店,3\n".encode("utf-8"),
                            three_columns(start_row=1))
    assert sample.header.verdict == feeds.DECLARED
    assert sample.header.detail == "the declared names, in order"


def test_a_header_whose_names_were_all_changed_is_still_a_header() -> None:
    """The case a field-count check cannot reach.

    A sender who renames every column without changing their number leaves a header
    that matches nothing declared. It is still recognisable, because a column declared
    numeric cannot hold `伝票No` - and this is the whole reason the header comparison
    is part of the check rather than a refinement of it.
    """
    sample = feeds.sample_of("伝票No,店名,個数\n1,蕨芝店,3\n".encode("utf-8"),
                            three_columns(start_row=1))
    assert sample.header.verdict == feeds.RENAMED
    finding = feeds.disagreements(three_columns(start_row=1), sample)
    assert [item.tag for item in finding] == ["HEADER"]
    assert "position 1: declared `伝票番号`, file `伝票No`" in finding[0].says


def test_the_declared_names_in_a_different_order_are_reported() -> None:
    """Which is a layout change, not a naming difference: the positions moved."""
    sample = feeds.sample_of("数量,店舗名,伝票番号\n3,蕨芝店,1\n".encode("utf-8"),
                            three_columns(start_row=1))
    assert sample.header.verdict == feeds.REORDERED
    assert [item.tag for item in feeds.disagreements(three_columns(start_row=1),
                                                     sample)] == ["HEADER"]


def test_a_headerless_file_reads_as_data() -> None:
    """A05's `order.txt`, `Dptenpo.csv` and `Dpshohin.csv`, all `StartRow=0`."""
    sample = feeds.sample_of("1,蕨芝店,3\n2,美女木店,4\n".encode("cp932"),
                             three_columns())
    assert sample.header.verdict == feeds.DATA
    assert feeds.disagreements(three_columns(), sample) == []


def test_a_first_record_that_cannot_be_told_apart_claims_nothing() -> None:
    """An all-text specification gives no signal, so neither does this.

    Reporting `StartRow` against a guess would be a claim about the sender that the
    file does not support.
    """
    spec = feeds.specifications(records(
        [spec_row(start_row=1)],
        [column_row("店舗名", 0, TEXT), column_row("略称", 8, TEXT)]))[SPEC]
    sample = feeds.sample_of("蕨芝店,蕨\n美女木店,美女木\n".encode("cp932"), spec)
    assert sample.header.verdict == feeds.UNKNOWN
    assert feeds.disagreements(spec, sample) == []


# --- the three reports -------------------------------------------------------

def test_an_extra_column_in_the_file_is_reported() -> None:
    """`Dpshohin.csv`: spec 28, file 29. The first thing this ever found."""
    sample = feeds.sample_of("1,蕨芝店,3,酒\n2,美女木店,4,酒\n".encode("cp932"),
                             three_columns())
    finding = feeds.disagreements(three_columns(), sample)
    assert [item.tag for item in finding] == ["FIELDS"]
    assert "declares 3 column(s), the file carries 4" in finding[0].says


def test_startrow_0_against_a_header_imports_the_names_as_a_record() -> None:
    sample = feeds.sample_of("伝票番号,店舗名,数量\n1,蕨芝店,3\n".encode("utf-8"),
                            three_columns(start_row=0))
    tags = [item.tag for item in feeds.disagreements(three_columns(), sample)]
    assert tags == ["STARTROW"]


def test_startrow_1_against_a_headerless_file_drops_a_record() -> None:
    """The direction that loses data silently, and the reason the check is per feed:
    `StartRow` differs *within* this one application, so a rule assuming one answer
    would be wrong half the time."""
    spec = three_columns(start_row=1)
    sample = feeds.sample_of("1,蕨芝店,3\n2,美女木店,4\n".encode("cp932"), spec)
    finding = feeds.disagreements(spec, sample)
    assert [item.tag for item in finding] == ["STARTROW"]
    assert "1 record(s) of data are dropped" in finding[0].says


def test_a_header_and_a_startrow_that_agree_report_nothing() -> None:
    """A05's `２１受注.CSV`, `２１商品.CSV` and `幸松受注.CSV`."""
    spec = three_columns(start_row=1)
    sample = feeds.sample_of("伝票番号,店舗名,数量\n1,蕨芝店,3\n".encode("utf-8"), spec)
    assert feeds.disagreements(spec, sample) == []


def test_records_that_disagree_about_field_count_are_reported() -> None:
    sample = feeds.sample_of("1,蕨芝店,3\n2,美女木店,4,酒\n1,蕨,3\n".encode("cp932"),
                             three_columns())
    tags = [item.tag for item in feeds.disagreements(three_columns(), sample)]
    assert "RAGGED" in tags
    says = [item.says for item in feeds.disagreements(three_columns(), sample)
            if item.tag == "RAGGED"][0]
    assert "4 field(s) in 1 record(s), first at record 2" in says


def test_an_empty_file_is_reported_as_empty_and_not_as_a_layout_change() -> None:
    sample = feeds.sample_of(b"", three_columns())
    assert [item.tag for item in feeds.disagreements(three_columns(), sample)] == ["EMPTY"]


@pytest.mark.parametrize("separator", ["", "\\t"])
def test_a_separator_that_is_not_one_character_is_reported_not_guessed(
    separator: str,
) -> None:
    """A wrong delimiter turns every number this module reports into fiction.

    Both cases are the same defect from opposite ends: a row an Access version stores
    the field under a different name, so nothing is read, and a tab stored as the two
    characters `\\t`. Defaulting either to `,` would report one field per record as a
    layout finding about the sender.
    """
    spec = feeds.specifications(records([spec_row(separator=separator)],
                                        [column_row("a", 0)]))[SPEC]
    sample = feeds.sample_of(b"1,2\n", spec)
    assert "not one character" in sample.problem
    assert feeds.disagreements(spec, sample)[0].tag == "UNREADABLE"


# --- the shapes A05 does not have -------------------------------------------
#
# Every declaration that matters here has exactly one value across A05's six feeds, so
# these are the cases a check calibrated on this one application would get wrong. They
# are tests rather than a note because the failure mode is a false finding on somebody
# else's application, which is worse than no check.

def test_a_fixed_width_link_is_reported_and_not_read_as_delimited() -> None:
    """Counting separators in a file that has none reports one field per record.

    On an application whose links are fixed-width that is every feed, and a check that
    fires on everything is one nobody reads twice.
    """
    feed = feeds.feeds([{"name": "元受注データ", "connect":
                         f"Text;DSN={SPEC};FMT=Fixed;HDR=NO;IMEX=2"}])[0]
    assert not feed.is_delimited
    sample = feeds.sample_of("1  蕨芝店   3\n".encode("cp932"), three_columns())
    finding = feeds.disagreements(three_columns(), sample, feed)
    assert [item.tag for item in finding] == ["FORMAT"]
    assert "Start and Width" in finding[0].says


def test_a_delimited_link_and_a_link_declaring_no_format_are_both_read() -> None:
    """A05 declares `FMT=Delimited`; refusing to read a link that declares nothing
    would turn the common case into silence."""
    for connect in (f"Text;DSN={SPEC};FMT=Delimited;HDR=NO", f"Text;DSN={SPEC};HDR=NO"):
        feed = feeds.feeds([{"name": "元商品マスタ", "connect": connect}])[0]
        assert feed.is_delimited and feeds.format_problem(feed) is None


def test_hdr_yes_makes_a_header_expected_rather_than_a_finding() -> None:
    """With `HDR=YES` Access reads the header itself.

    A05's six all declare `HDR=NO`, so the `StartRow=0` finding is right there and
    would be a false claim about any application declaring the other value.
    """
    feed = feeds.feeds([{"name": "元商品マスタ", "connect":
                         f"Text;DSN={SPEC};FMT=Delimited;HDR=YES"}])[0]
    assert feed.expects_header
    sample = feeds.sample_of("伝票番号,店舗名,数量\n1,蕨芝店,3\n".encode("utf-8"),
                             three_columns(start_row=0))
    assert feeds.disagreements(three_columns(start_row=0), sample, feed) == []


def test_hdr_yes_against_a_file_with_no_header_is_the_finding() -> None:
    feed = feeds.feeds([{"name": "元商品マスタ", "connect":
                         f"Text;DSN={SPEC};FMT=Delimited;HDR=YES"}])[0]
    sample = feeds.sample_of("1,蕨芝店,3\n2,美女木店,4\n".encode("cp932"),
                             three_columns())
    finding = feeds.disagreements(three_columns(), sample, feed)
    assert [item.tag for item in finding] == ["HEADER"]
    assert "read as the column names" in finding[0].says


def test_a_specification_that_states_no_order_is_compared_as_a_set() -> None:
    """`Start` is how the order is recovered, and a version difference loses it.

    Every column then reads as position zero, and a positional comparison would report
    all of them as moved - on a file whose header is in fact the declared names.
    """
    spec = feeds.specifications(records(
        [spec_row(start_row=1)],
        [{"SpecID": "28", "FieldName": name, "DataType": str(kind)}
         for name, kind in (("伝票番号", LONG), ("店舗名", TEXT), ("数量", LONG))]))[SPEC]
    assert not spec.order_known
    sample = feeds.sample_of("伝票番号,店舗名,数量\n1,蕨芝店,3\n".encode("utf-8"), spec)
    assert sample.header.verdict == feeds.DECLARED
    assert "does not state what order" in sample.header.detail
    assert feeds.disagreements(spec, sample) == []


def test_an_unordered_specification_names_no_positions() -> None:
    """A position this cannot place is a position it must not name."""
    spec = feeds.specifications(records(
        [spec_row(start_row=1)],
        [{"SpecID": "28", "FieldName": name, "DataType": str(kind)}
         for name, kind in (("伝票番号", LONG), ("店舗名", TEXT), ("数量", LONG))]))[SPEC]
    sample = feeds.sample_of("伝票No,店名,個数\n1,蕨芝店,3\n".encode("utf-8"), spec)
    assert sample.header.verdict == feeds.RENAMED
    assert sample.header.differences == ()
    assert "position" not in feeds.disagreements(spec, sample)[0].says


# --- the encoding the specification does not declare -------------------------

def test_feeds_that_disagree_about_encoding_are_reported_once() -> None:
    """A05's do: three CP932 and three UTF-8, every specification declaring
    `FileType=0`. An importer written against either half breaks the other."""
    spec = three_columns()
    cp932 = feeds.sample_of("1,蕨芝店,3\n".encode("cp932"), spec)
    utf8 = feeds.sample_of("1,美女木店,4\n".encode("utf-8"), spec)
    note = feeds.encoding_spread([(spec, cp932), (spec, utf8)])
    assert "cp932 (1)" in note and "utf-8 (1)" in note
    assert "FileType=0" in note and "not established" in note


def test_feeds_that_share_an_encoding_say_nothing() -> None:
    spec = three_columns()
    sample = feeds.sample_of("1,蕨芝店,3\n".encode("cp932"), spec)
    assert feeds.encoding_spread([(spec, sample), (spec, sample)]) == ""


def test_the_numeric_types_are_the_ones_the_kit_documents() -> None:
    """A typo in a type code would silently stop recognising headers.

    Checked against `specifications/dao-field-types.yaml` in both directions, because
    a code missing from the set is a header this stops finding and a code wrongly in it
    is a header it invents.
    """
    yaml = pytest.importorskip("yaml")
    types = yaml.safe_load(
        (PACKAGE / "specifications" / "dao-field-types.yaml").read_text(
            encoding="utf-8"))["types"]
    documented = {code for code, entry in types.items()
                  if str(entry["access_type"]).startswith("Number")
                  or entry["access_type"] == "Currency"}
    assert feeds.NUMERIC_TYPES == documented


# --- the command -------------------------------------------------------------

def workspace(tmp_path: Path, *, files: dict[str, bytes],
              links: list[dict] | None = None,
              specs: list[dict] | None = None) -> Path:
    root = tmp_path / "A05"
    # `input/` is what tells `Workspace` this is the post-2.10.0 layout.
    samples = root / "input" / "samples"
    samples.mkdir(parents=True)
    for name, raw in files.items():
        (samples / name).write_bytes(raw)
    interfaces = root / ".ak" / "bundles" / "b1" / "interfaces"
    interfaces.mkdir(parents=True)
    io.open(interfaces.parent / "bundle.json", "w", encoding="utf-8").write("{}")
    write = lambda path, data: io.open(  # noqa: E731
        path, "w", encoding="utf-8", newline="\n").write(
            json.dumps(data, ensure_ascii=False))
    write(interfaces / "linked-tables.json", links if links is not None else [
        {"name": "元商品マスタ", "database_id": DB, "connect": CONNECT,
         "source_table_name": "dpshohin.csv"}])
    write(interfaces / "imex-specs.json", records(
        [spec_row()], specs if specs is not None else [
            column_row("店舗名", 8, TEXT), column_row("伝票番号", 0, LONG),
            column_row("数量", 40, LONG)]))
    return root


def run(root: Path) -> tuple[int, str]:
    sys.argv = ["check_feed_samples.py", "--app-root", str(root)]
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        code = checker.main()
    return code, captured.getvalue()


def test_the_command_names_the_file_the_declaration_disagrees_with(
    tmp_path: Path,
) -> None:
    """The A05 run, at test scale: an extra column in the file nobody declared."""
    root = workspace(tmp_path, files={
        "Dpshohin.csv": "1,蕨芝店,3,酒\n2,美女木店,4,酒\n".encode("cp932")})
    code, output = run(root)
    assert code == 1
    assert "FIELDS" in output and "元商品マスタ (dpshohin.csv)" in output
    # The name on the share is capitalised and the link is not. Matching case would
    # report every one of A05's six feeds as a missing sample.
    assert "NO SAMPLE" not in output


def test_the_command_reports_a_feed_whose_specification_is_not_in_the_bundle(
    tmp_path: Path,
) -> None:
    """A17's case: the layout of a headerless file is then declared nowhere."""
    root = workspace(tmp_path, files={"dpshohin.csv": b"1,2,3\n"},
                     links=[{"name": "元受注データ", "database_id": DB,
                             "connect": "Text;DSN=Order ﾘﾝｸの定義2;HDR=NO",
                             "source_table_name": "order.txt"}])
    code, output = run(root)
    assert code == 1
    assert "NO SPEC" in output and "Order ﾘﾝｸの定義2" in output


def test_the_command_reports_a_declared_feed_with_no_sample(tmp_path: Path) -> None:
    root = workspace(tmp_path, files={})
    code, output = run(root)
    assert code == 1
    assert "NO SAMPLE" in output and "EC-02" in output


def test_the_command_reports_a_sample_no_link_names(tmp_path: Path) -> None:
    """An operator supplying a file nothing imports is worth one line: either the
    link is missing or the file is."""
    root = workspace(tmp_path, files={
        "dpshohin.csv": "1,蕨芝店,3\n".encode("cp932"),
        "unknown.csv": b"1,2\n"})
    code, output = run(root)
    assert code == 1
    assert "UNCLAIMED" in output and "unknown.csv" in output


def test_two_files_of_one_name_are_reported_rather_than_one_of_them_chosen(
    tmp_path: Path,
) -> None:
    """An operator collecting from several senders puts each in a folder.

    Both may hold an `order.txt`, the link names only the file, and comparing the
    declaration against whichever one sorted first could report agreement about a file
    the application never reads.
    """
    root = workspace(tmp_path, files={"dpshohin.csv": "1,蕨芝店,3\n".encode("cp932")})
    nested = root / "input" / "samples" / "sender-b"
    nested.mkdir()
    (nested / "dpshohin.csv").write_bytes("9,美女木店,4,酒\n".encode("cp932"))
    code, output = run(root)
    assert code == 1
    assert "AMBIGUOUS" in output and "sender-b/dpshohin.csv" in output
    # And no comparison is published against either of them.
    assert "FIELDS" not in output and "spec 3" not in output


def test_a_bundle_whose_links_name_no_specification_is_not_a_failure(
    tmp_path: Path,
) -> None:
    """A05's frontend is exactly this, and it is correct: its two linked tables both
    point at the backend `.mdb` and neither declares a DSN."""
    root = workspace(tmp_path, files={}, links=[
        {"name": "操作履歴", "database_id": "WINDOWS11_45D0FDDD",
         "connect": ";DATABASE=L:\\新品揃支援\\XP\\品揃支援data.mdb"}])
    code, output = run(root)
    assert code == 0
    assert "nothing to compare" in output


def test_an_agreeing_feed_reports_nothing(tmp_path: Path) -> None:
    root = workspace(tmp_path, files={
        "dpshohin.csv": "1,蕨芝店,3\n2,美女木店,4\n".encode("cp932")})
    code, output = run(root)
    assert code == 0
    assert "every declared layout agrees" in output


def test_no_bundle_is_a_second_exit_code_and_not_a_clean_report(
    tmp_path: Path,
) -> None:
    (tmp_path / "A05" / "input").mkdir(parents=True)
    code, output = run(tmp_path / "A05")
    assert code == 2 and "run `$ak acquire` first" in output
