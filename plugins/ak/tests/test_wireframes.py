"""Every form is drawn from its definition, and nothing on the drawing is guessed (A79).

The PPTX that rendered Phase 6 was retired with it (A78). What a developer rebuilding a
screen lacks is a picture of it; the bundle holds every control's geometry and every
section's height, so the picture is generated. Each test is one way the drawing would
lie about the form.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import build_wireframes  # noqa: E402
import wireframe  # noqa: E402

FORM_TEXT = """Version =17
Begin Form
    Width =4500
    Caption ="Order entry"
    RecordSource ="SELECT * FROM T_ORDER"
    Begin
        Begin Label
            Width =1701
            Height =390
        End
    End
    Begin FormHeader
        Height =600
        Begin
            Begin Label
                Height =300
            End
        End
    End
    Begin Section
        Height =3000
        Begin
            Begin TextBox
                Height =315
            End
        End
    End
    Begin FormFooter
        Height =0
    End
End
"""


def ctl(name: str, code: int, section: int = 0, left: int = 150, top: int = 150,
        width: int = 1500, height: int = 300, **extra: object) -> dict:
    return {"name": name, "type": code, "section": str(section), "left": left, "top": top,
            "width": width, "height": height, "caption": "", "attached_label": "",
            "on_click": "", "tooltip": "", "visible": True, "parent": "F", **extra}


def test_the_layout_reads_form_properties_and_section_heights_at_their_own_depth() -> None:
    """A control's `Height` sits deeper than its section's; reading it would size the section."""
    shape = wireframe.layout(FORM_TEXT)
    assert shape["width"] == 300
    assert shape["caption"] == "Order entry"
    assert shape["record_source"] == "SELECT * FROM T_ORDER"
    assert shape["sections"] == {1: 40, 0: 200, 2: 0}


def test_a_control_height_written_before_the_section_height_is_not_taken_for_it() -> None:
    text = ("Begin Form\n    Width =1500\n    Begin Section\n        Begin\n"
            "            Begin TextBox\n                Height =9000\n            End\n"
            "        End\n        Height =1500\n    End\nEnd\n")
    assert wireframe.layout(text)["sections"] == {0: 100}


def test_twips_become_pixels_at_fifteen_to_one() -> None:
    assert wireframe.pixels(1500) == 100
    assert wireframe.pixels("15") == 1
    assert wireframe.pixels(None) == 0
    assert wireframe.pixels(-30) == 0


def test_sections_appear_in_the_order_a_screen_shows_them() -> None:
    form = {"name": "F", "kind": "form", "text": FORM_TEXT}
    s = wireframe.screen(form, [ctl("b", 104, 2), ctl("a", 109, 0), ctl("h", 100, 1)], "F-001", None)
    assert [sec["label"] for sec in s["sections"]] == ["Form header", "Detail", "Form footer"]
    assert [c["name"] for c in s["controls"]] == ["h", "a", "b"]


def test_a_section_with_no_declared_height_is_sized_to_its_controls_and_says_so() -> None:
    form = {"name": "F", "kind": "form", "text": "Begin Form\n    Width =1500\nEnd\n"}
    s = wireframe.screen(form, [ctl("a", 109, 0, top=1500, height=300)], "", None)
    detail, = s["sections"]
    assert detail["height"] == 120 and detail["height_declared"] is False


def test_a_control_past_its_section_is_flagged_not_clipped_silently() -> None:
    form = {"name": "F", "kind": "form", "text": FORM_TEXT}
    s = wireframe.screen(form, [ctl("far", 109, 0, top=6000)], "", None)
    detail = next(sec for sec in s["sections"] if sec["code"] == 0)
    assert detail["overflow"] is True


def test_the_page_header_is_marked_as_printed_only() -> None:
    form = {"name": "F", "kind": "form", "text": FORM_TEXT}
    s = wireframe.screen(form, [ctl("p", 100, 3)], "", None)
    page = next(sec for sec in s["sections"] if sec["code"] == 3)
    assert page["print_only"] is True


def test_every_control_type_is_named_and_119_is_not_a_toggle() -> None:
    """119 is an ActiveX custom control; reading it as a toggle hides a dependency."""
    assert wireframe.CONTROL_TYPES[119].startswith("custom control")
    assert wireframe.CONTROL_TYPES[122] == "toggle button"
    assert wireframe.control(ctl("x", 999))["kind"] == "type 999"


def test_a_hidden_control_is_drawn_and_counted_not_dropped() -> None:
    form = {"name": "F", "kind": "form", "text": FORM_TEXT}
    s = wireframe.screen(form, [ctl("ghost", 104, visible=False), ctl("seen", 104)], "", None)
    assert s["hidden"] == 1
    assert {c["name"] for c in s["controls"]} == {"ghost", "seen"}


def test_open_decisions_are_those_naming_the_form_directly() -> None:
    queue = {"items": [
        {"id": "Q1", "title": "by F-", "blocks": [{"id": "F-001", "title": "F"}]},
        {"id": "Q2", "title": "by object", "blocks": [{"object": "F"}]},
        {"id": "Q3", "title": "by workflow only", "blocks": [{"id": "WF-001"}]},
        {"id": "Q4", "title": "another form", "blocks": [{"id": "F-002"}]},
    ]}
    found = wireframe.decisions_for(queue, "F", "F-001")
    assert [d["id"] for d in found] == ["Q1", "Q2"]
    assert wireframe.decisions_for(None, "F", "F-001") == []


def test_reports_are_not_drawn_and_forms_sort_by_identifier() -> None:
    forms = [{"name": "Z", "kind": "form", "text": ""}, {"name": "A", "kind": "form", "text": ""},
             {"name": "R", "kind": "report", "text": ""}]
    screens = wireframe.build(forms, {}, {"Z": "F-001"}, None)
    assert [s["name"] for s in screens] == ["Z", "A"]


@pytest.mark.parametrize("name", ["</script><b>", "<!-- x", "a<b"])
def test_a_name_holding_markup_cannot_end_the_data_block(name: str) -> None:
    form = {"name": name, "kind": "form", "text": ""}
    text = build_wireframes.page("A99", wireframe.build([form], {}, {}, None))
    data = text.split('<script id="data" type="application/json">', 1)[1].split("</script>", 1)[0]
    assert "<" not in data
    assert json.loads(data)[0]["name"] == name


# --- the command ------------------------------------------------------------

def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "A99"
    bundle = root / ".ak" / "bundles" / "B1"
    (bundle / "ui" / "forms").mkdir(parents=True)
    (root / "input").mkdir()
    (root / "output").mkdir()
    (bundle / "bundle.json").write_text("{}", encoding="utf-8")
    (bundle / "ui" / "forms" / "inventory.json").write_text(json.dumps(
        [{"name": "F", "kind": "form", "text": FORM_TEXT}]), encoding="utf-8")
    (bundle / "ui" / "controls.json").write_text(json.dumps(
        [{"object": "F", "kind": "form", "controls": [ctl("a", 109), ctl("b", 104, visible=False)]}]),
        encoding="utf-8")
    (root / "output" / "A99_Identifiers.json").write_text(json.dumps(
        {"app_id": "A99", "entries": [{"id": "F-001", "namespace": "F-", "title": "F"}]}),
        encoding="utf-8")
    return root


def run(monkeypatch: pytest.MonkeyPatch, root: Path, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["build_wireframes.py", "--app-root", str(root),
                                      "--app-id", "A99", *args])
    return build_wireframes.main()


def test_the_command_writes_one_page_and_then_leaves_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = workspace(tmp_path)
    assert run(monkeypatch, root) == 0
    page = root / "output" / "A99_Wireframes.html"
    text = page.read_text(encoding="utf-8")
    assert build_wireframes.GENERATED in text and "{{" not in text
    assert '"id":"F-001"' in text and '"hidden":1' in text
    assert run(monkeypatch, root) == 0
    assert "unchanged" in capsys.readouterr().out


def test_a_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = workspace(tmp_path)
    assert run(monkeypatch, root, "--dry-run") == 0
    assert not (root / "output" / "A99_Wireframes.html").exists()


def test_a_page_a_person_wrote_is_not_overwritten(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = workspace(tmp_path)
    page = root / "output" / "A99_Wireframes.html"
    page.write_text("<p>ours</p>", encoding="utf-8")
    assert run(monkeypatch, root) == 2
    assert page.read_text(encoding="utf-8") == "<p>ours</p>"
    assert run(monkeypatch, root, "--replace-handwritten") == 0


def test_no_bundle_means_no_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "A99"
    (root / "input").mkdir(parents=True)
    (root / "output").mkdir()
    assert run(monkeypatch, root) == 2
    assert not (root / "output" / "A99_Wireframes.html").exists()
