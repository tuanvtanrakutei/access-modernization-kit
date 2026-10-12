"""The runtime capture and the mockup's agreement with it (A93).

Each fidelity case is one the mockup once drew differently from the running application,
measured on a real one: a form whose text boxes are transparent by its default block, a
border written as OldBorderStyle, a special effect over a transparent border, a label's
own effect, and a system colour on a button.
"""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import capture_runtime_view as capture  # noqa: E402
import runtime_fidelity as fidelity  # noqa: E402


def _model(name: str, kind: int, style: dict, role: str = "display", **extra) -> dict:
    return {"name": name, "type": kind, "kind": str(kind), "style": style, "role": role, "visible": True,
            "left": 4, "top": 4, "width": 100, "height": 20, **extra}


def _runtime(name: str, **props) -> dict:
    base = {"name": name, "Visible": "-1", "Enabled": "-1", "Left": "60", "Top": "60", "Width": "1500",
            "Height": "300", "ForeColor": "0", "BackColor": "16777215", "BackStyle": "1", "FontBold": "0",
            "FontSize": "9", "SpecialEffect": "0", "BorderStyle": "1"}
    base.update(props)
    return base


def test_a_transparent_flat_text_box_agrees_with_access() -> None:
    drawn = fidelity.drawn(_model("txt", 109, {"BackStyle": "0", "BorderStyle": "0"}))
    actual = fidelity.actual(_runtime("txt", BackStyle="0", SpecialEffect="0", BorderStyle="0"), 109)
    assert (drawn["transparent"], drawn["border"]) == (actual["transparent"], actual["border"]) == (True, False)


def test_a_sunken_effect_shows_over_a_transparent_border() -> None:
    drawn = fidelity.drawn(_model("txt", 109, {"SpecialEffect": "2", "BorderStyle": "0"}))
    actual = fidelity.actual(_runtime("txt", SpecialEffect="2", BorderStyle="0"), 109)
    assert drawn["border"] is actual["border"] is True


def test_a_label_draws_an_edge_only_for_its_own_effect() -> None:
    assert fidelity.drawn(_model("lbl", 100, {"SpecialEffect": "1"}))["border"] is True
    assert fidelity.drawn(_model("lbl", 100, {}))["border"] is False


def test_a_system_colour_compares_as_written() -> None:
    system = "-2147483630"
    drawn = fidelity.drawn(_model("cmd", 104, {"ForeColor": system}, role="button"))
    actual = fidelity.actual(_runtime("cmd", ForeColor=system), 104)
    assert drawn["fore"] == actual["fore"] == int(system)


def test_compare_counts_agreement_and_names_each_disagreement() -> None:
    screens = [{"name": "List", "id": "F-002", "controls": [
        _model("txtCode", 109, {"BackStyle": "0", "BorderStyle": "0"}),
        _model("txtName", 109, {})]}]
    runtime = {"forms": [
        {"name": "List", "controls": [
            _runtime("txtCode", BackStyle="0", BorderStyle="0"),
            _runtime("txtName", BackStyle="0", BorderStyle="0")]},
        {"name": "Missing", "error": "The OpenForm action was canceled.", "controls": []}]}
    result = fidelity.compare(screens, runtime)
    wrong = {(m["control"], m["property"]) for m in result["disagreements"]}
    assert ("txtName", "transparent") in wrong and ("txtName", "border") in wrong
    assert not any(c == "txtCode" for c, _ in wrong)
    assert result["agreed"] == result["compared"] - len(result["disagreements"])
    lines = fidelity.summary(result)
    assert lines[0].startswith("runtime agreement:")
    assert any("Missing" in line and "not compared" in line for line in lines)


FORM = """Version =17
Begin Form
    DefaultView =2
    RecordSource ="T"
    Begin Section
        Begin
            Begin TextBox
                Name ="txtCode"
                ControlSource ="CODE"
            End
        End
    End
End
CodeBehindForm
Option Compare Database
Private Sub Form_Open(Cancel As Integer)
    DoCmd.Maximize
End Sub
Private Sub cmdPrint_Click()
End Sub
"""


def test_a_request_opens_a_datasheet_as_one_and_names_its_opening_code() -> None:
    forms = [{"name": "Data", "text": FORM, "database_id": "APP"},
             {"name": "Plain", "text": "Begin Form\n    DefaultView =0\nEnd\n", "database_id": "APP"}]
    requests = {r["name"]: r for r in capture.requests_for(forms, {})}
    assert requests["Data"]["view"] == capture.VIEW_DATASHEET
    assert requests["Data"]["has_module"] is True
    assert requests["Data"]["opening"] == ["Form_Open"]
    assert requests["Data"]["controls"] == ["txtCode"]
    assert requests["Plain"]["view"] == capture.VIEW_NORMAL and requests["Plain"]["has_module"] is False


def test_the_capture_log_carries_each_forms_identifier() -> None:
    ids = {"Data": "F-016"}
    assert capture.with_id("OK\tform\tData\tform-009.png", ids) == "OK\tform\tData\tform-009.png\tF-016"
    assert capture.with_id("STRIPPED\tData", ids) == "STRIPPED\tData"
    assert capture.with_id("OK\tform\tOther\tform-010.png", ids) == "OK\tform\tOther\tform-010.png"


def test_capturing_needs_the_snapshot_authorization(tmp_path: Path) -> None:
    assert capture.main(["--app-root", str(tmp_path)]) == 2
