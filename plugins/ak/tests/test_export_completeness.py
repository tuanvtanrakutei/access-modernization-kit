"""Whether the exporter wrote the whole object - and the honest limits of asking.

A05's export passed every gate the kit has while carrying 21 of a form's 45 procedures.
The tests here are as much about what this must NOT claim as about what it catches: the
truncated `メインメニュー` balanced, its object count matched the other route's and its
digest was correct, so a test that asserts "this catches an incomplete export" would be
asserting something untrue.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
sys.path.insert(0, str(PACKAGE / "contracts"))

import export_completeness as completeness  # noqa: E402
import check_export_completeness as checker  # noqa: E402

FE = "FRONT_1111"

FORM = """Version =20
Begin Form
    RecordSource ="受注データ"
    Begin Label
        Name ="ラベル1"
    End
    Begin CommandButton
        Name ="btn1"
    End
End
CodeBehindForm
Private Sub btn1_Click()
    DoCmd.OpenForm "商品検索"
End Sub

Public Function 合計() As Long
    合計 = 1
End Function
"""


def test_a_truncated_definition_is_reported() -> None:
    """The one thing decidable from a single file: it stops inside a block."""
    cut = FORM[:FORM.index("Begin CommandButton") + 30]
    shape = completeness.shape_of(cut)
    assert not shape.balanced
    assert "stops inside a control block" in shape.imbalance


def test_a_definition_cut_inside_a_procedure_is_reported() -> None:
    cut = FORM[:FORM.index("DoCmd")]
    assert "stops inside a procedure" in completeness.shape_of(cut).imbalance


def test_a_whole_definition_balances() -> None:
    shape = completeness.shape_of(FORM)
    assert shape.balanced and shape.imbalance == ""
    assert shape.blocks == 3 and shape.procedures == 2


def test_an_api_declaration_is_not_an_unclosed_function() -> None:
    """A `Declare Function` has no body, and counting it makes every module with a
    Win32 declaration look truncated - a check nobody reads is worse than none."""
    text = ('Option Explicit\n'
            'Private Declare Function GetTickCount Lib "kernel32" () As Long\n'
            'Sub A()\nEnd Sub\n')
    shape = completeness.shape_of(text)
    assert shape.procedures == 1 and shape.balanced


def test_a_truncation_that_balances_is_not_caught_and_must_not_pretend_to_be() -> None:
    """This is the A05 case, and it is why the module records rather than checks.

    `メインメニュー` lost 24 of its 45 procedures and still ended on a complete
    `End Sub`. Nothing about the file itself gives it away.
    """
    complete = FORM
    truncated = FORM[:FORM.index("\nPublic Function")] + "\n"
    assert completeness.shape_of(truncated).balanced, "the A05 shape exactly"
    # It is only visible against the other observation.
    assert completeness.disagreements(completeness.shape_of(complete),
                                      completeness.shape_of(truncated))


def test_a_disagreement_is_reported_in_both_directions() -> None:
    """A05's correction arrived as a rise: the first export was the short one.

    A rule watching only for drops would have said nothing at the exact moment the
    evidence turned up.
    """
    small = completeness.shape_of(FORM[:FORM.index("\nPublic Function")] + "\n")
    large = completeness.shape_of(FORM)
    grew = completeness.disagreements(small, large)
    shrank = completeness.disagreements(large, small)
    assert grew and shrank
    assert any("the earlier one is missing content" in line for line in grew)
    assert any("the one now in the bundle is missing content" in line
               for line in shrank)


def test_a_trivial_difference_is_not_reported() -> None:
    """A trailing newline is not a missing procedure."""
    assert completeness.disagreements(completeness.shape_of(FORM),
                                      completeness.shape_of(FORM + "\n")) == []


def _workspace(tmp_path: Path, bundle_text: str, staging_text: str | None) -> Path:
    root = tmp_path / "T01"
    # `input/` is what tells `Workspace` this is the post-2.10.0 layout, and without it
    # every path below resolves under `acquired/` instead.
    (root / "input").mkdir(parents=True)
    inventory = root / ".ak" / "bundles" / "b1" / "ui" / "forms"
    inventory.mkdir(parents=True)
    io.open(inventory.parent.parent / "bundle.json", "w", encoding="utf-8").write("{}")
    io.open(inventory / "inventory.json", "w", encoding="utf-8", newline="\n").write(
        json.dumps([{"kind": "form", "object_name": "メインメニュー",
                     "database_id": FE, "text": bundle_text}], ensure_ascii=False))
    if staging_text is not None:
        staging = root / ".ak" / "staging" / FE / "fresh-01" / "forms"
        staging.mkdir(parents=True)
        io.open(staging / "メインメニュー.txt", "w", encoding="utf-8",
                newline="\n").write(staging_text)
    return root


def run(root: Path, *extra: str) -> tuple[int, str]:
    import contextlib

    sys.argv = ["check_export_completeness.py", "--app-root", str(root), *extra]
    captured = io.StringIO()
    with contextlib.redirect_stdout(captured):
        code = checker.main()
    return code, captured.getvalue()


def test_the_two_routes_are_compared_against_each_other(tmp_path: Path) -> None:
    """The comparison that was available on A05 all along and was never made.

    The frontend was acquired managed for its schema and imported for its definition
    text, so both readings of `メインメニュー` sat in one workspace while the shorter of
    them was published as a finding about dead code.
    """
    short = FORM[:FORM.index("\nPublic Function")] + "\n"
    root = _workspace(tmp_path, bundle_text=short, staging_text=FORM)
    code, output = run(root)
    assert code == 1
    assert "ROUTES" in output
    assert "the one now in the bundle is missing content" in output


def test_agreement_between_the_routes_is_reported_as_nothing(tmp_path: Path) -> None:
    root = _workspace(tmp_path, bundle_text=FORM, staging_text=FORM)
    code, output = run(root)
    assert code == 0
    assert "nothing to report" in output


def test_the_record_gives_the_next_run_something_to_disagree_with(
    tmp_path: Path,
) -> None:
    """The whole design, in one test: the first export cannot be checked, only kept.

    Nothing is wrong on the first run and nothing is claimed to be right. When a
    re-export arrives, the difference is stated without anybody having thought to diff.
    """
    root = _workspace(tmp_path, bundle_text=FORM, staging_text=None)
    code, output = run(root)
    assert code == 0
    assert "nothing recorded before this run" in output
    record = json.loads(
        (root / ".ak" / "extracted" / "object-shapes.json").read_text(encoding="utf-8"))
    assert record["objects"][f"{FE}:form:メインメニュー"]["bundle"]["procedures"] == 2

    # A re-export arrives carrying less than the run before it.
    short = FORM[:FORM.index("\nPublic Function")] + "\n"
    inventory = (root / ".ak" / "bundles" / "b1" / "ui" / "forms" / "inventory.json")
    io.open(inventory, "w", encoding="utf-8", newline="\n").write(
        json.dumps([{"kind": "form", "object_name": "メインメニュー",
                     "database_id": FE, "text": short}], ensure_ascii=False))
    code, output = run(root)
    assert code == 1
    assert "CHANGED" in output and "procedure(s): 2 then, 1 now" in output


def test_dry_run_reports_without_updating_the_record(tmp_path: Path) -> None:
    root = _workspace(tmp_path, bundle_text=FORM, staging_text=None)
    run(root)
    before = (root / ".ak" / "extracted" / "object-shapes.json").read_text(
        encoding="utf-8")
    short = FORM[:FORM.index("\nPublic Function")] + "\n"
    io.open(root / ".ak" / "bundles" / "b1" / "ui" / "forms" / "inventory.json", "w",
            encoding="utf-8", newline="\n").write(
        json.dumps([{"kind": "form", "object_name": "メインメニュー",
                     "database_id": FE, "text": short}], ensure_ascii=False))
    code, output = run(root, "--dry-run")
    assert code == 1 and "CHANGED" in output
    assert (root / ".ak" / "extracted" / "object-shapes.json").read_text(
        encoding="utf-8") == before


def test_an_object_that_stops_being_readable_is_named(tmp_path: Path) -> None:
    """A record that quietly shrinks is the failure mode this is here to prevent."""
    root = _workspace(tmp_path, bundle_text=FORM, staging_text=None)
    run(root)
    io.open(root / ".ak" / "bundles" / "b1" / "ui" / "forms" / "inventory.json", "w",
            encoding="utf-8", newline="\n").write("[]")
    code, output = run(root)
    assert code == 1
    assert "MISSING" in output and "メインメニュー" in output

    # And it keeps saying so. Dropping the recorded shape on the run that reports the
    # disappearance would make the next run compare against nothing and call it clean -
    # the same silence this file exists to break.
    code, output = run(root)
    assert code == 1 and "MISSING" in output


def test_a_binary_print_settings_block_is_an_opener() -> None:
    """Access writes print settings as `PrtMip = Begin` / hex / `End`.

    Counting the closer and not the opener reports an excess of `End` on every object
    that has ever been near a printer. On the first real run over A05 that called
    nearly every form truncated - a check that fires on everything is one nobody reads,
    and it would have buried the twenty-seven objects that are genuinely unbalanced.
    """
    text = ('Begin Form\n'
            '    PrtMip = Begin\n'
            '        0x6c00000000000000\n'
            '    End\n'
            '    Begin Label\n'
            '    End\n'
            'End\n')
    shape = completeness.shape_of(text)
    # `Begin Form`, `PrtMip = Begin`, `Begin Label` - three openers, three closers.
    assert shape.blocks == 3 and shape.block_ends == 3
    assert shape.balanced
