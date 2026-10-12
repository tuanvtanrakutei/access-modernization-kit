"""The neutral to-be proposed from a legacy screen model (A92)."""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

import to_be  # noqa: E402


def _c(name: str, role: str, section: int = 0, left: int = 0, top: int = 0, width: int = 60, **extra) -> dict:
    return {"name": name, "role": role, "section": section, "left": left, "top": top,
            "width": width, "height": 16, "visible": True, "caption": extra.pop("caption", ""), **extra}


MENU_TEXT = """Begin Form
End
CodeBehindForm
Private Sub cmdList_Click()
    DoCmd.OpenForm "List"
End Sub
Private Sub cmdErrors_Click()
    DoCmd.OpenForm "Errors"
End Sub
"""


def test_a_form_of_buttons_is_a_menu_and_out_of_scope_targets_are_dropped() -> None:
    screen = {"name": "Menu", "id": "F-001", "caption": "Menu", "mode": {"view": "single"},
              "controls": [_c("cmdList", "button", caption="List"),
                           _c("cmdErrors", "button (disabled)", caption="Errors"),
                           _c("txtLast", "display", source="LAST_RUN")]}
    proposal = to_be.propose(screen, MENU_TEXT, {"List": "F-002"}, {"Errors"})
    assert proposal["pattern"] == "menu"
    actions = [a for r in proposal["regions"] if r["kind"] == "actions" for a in r["actions"]]
    assert [a["label"] for a in actions] == ["List"]
    assert actions[0]["does"] == ["open form List (F-002)"]
    status = {m["legacy"]: m["status"] for m in proposal["mapping"]}
    assert status["cmdErrors"] == "out of scope"


def test_a_continuous_form_is_a_table_headed_by_the_labels_above_its_columns() -> None:
    screen = {"name": "Stores", "caption": "Stores", "mode": {"view": "continuous", "edits": True,
                                                              "additions": True, "deletions": False},
              "data": {"rows": [{"CODE": 101, "NAME": "A"}]},
              "controls": [_c("lblCode", "text", section=1, left=0, caption="Code"),
                           _c("lblName", "text", section=1, left=70, caption="Name"),
                           _c("txtCode", "display", left=0, source="CODE"),
                           _c("txtName", "input", left=70, source="NAME"),
                           _c("lnTop", "decoration", section=1),
                           _c("txtSecret", "input", left=140, source="X", visible=False)]}
    proposal = to_be.propose(screen, "", {}, ())
    assert proposal["pattern"] == "editable list"
    table = next(r for r in proposal["regions"] if r["kind"] == "table")
    assert [(c["label"], c["component"], c["editable"]) for c in table["columns"]] == [
        ("Code", "number", False), ("Name", "text", True)]
    assert table["allow_add"] is True and table["allow_delete"] is False
    status = {m["legacy"]: m["status"] for m in proposal["mapping"]}
    assert status["txtSecret"] == "dropped" and status["lnTop"] == "dropped"


def test_a_recorded_out_of_scope_object_is_read_from_the_decision_table() -> None:
    record = "| Object | Kind | In the replacement |\n|---|---|---|\n| Errors (F-005) | form | out of scope |\n"
    assert to_be.out_of_scope_objects([record]) == {"Errors"}


def test_a_menu_keeps_its_tabs_order_and_colours() -> None:
    """Familiar first: an operator finds each button where it was, in its colour."""
    tab = _c("tabMain", "tabs", top=40, pages=[{"name": "p1", "caption": "Food"}, {"name": "p2", "caption": "Veg"}])
    screen = {"name": "Menu", "caption": "Menu", "mode": {"view": "single"}, "controls": [
        _c("cmdImport", "button", top=0, caption="Import", style={"ForeColor": "255"}),
        tab,
        _c("cmdVeg", "button", top=60, caption="Veg list", page="p2"),
        _c("cmdFood", "button", top=60, caption="Food list", page="p1", style={"ForeColor": "32768"}),
        _c("cmdStores", "button", top=200, caption="Stores")]}
    proposal = to_be.propose(screen, "", {}, ())
    kinds = [r["kind"] for r in proposal["regions"]]
    assert kinds == ["actions", "tabs", "actions"]
    tabs = proposal["regions"][1]["tabs"]
    assert [t["title"] for t in tabs] == ["Food", "Veg"]
    assert tabs[0]["actions"][0]["color"] == "#008000"
    assert proposal["regions"][0]["actions"][0]["color"] == "#ff0000"
    assert {m["legacy"]: m["status"] for m in proposal["mapping"]}["tabMain"] == "kept"


def test_an_instruction_naming_a_folder_on_the_pc_becomes_an_upload() -> None:
    """A technical gap: a browser application cannot read the operator's disk."""
    screen = {"name": "Menu", "caption": "Menu", "mode": {"view": "single"}, "controls": [
        _c("cmdImport", "button", caption="Import"),
        _c("lblA", "text", left=70, width=40, caption="Before importing, copy to "),
        _c("lblB", "text", left=110, width=80, caption="C:" + chr(165) + "data" + chr(165)),
        _c("lblC", "text", left=70, top=16, width=120, caption=" first."),
        _c("lblFar", "text", top=300, caption="Last run")]}
    proposal = to_be.propose(screen, "", {}, ())
    upload = next(r for r in proposal["regions"] if r["kind"] == "upload")
    assert upload["note"] == "Before importing, copy to C:" + chr(165) + "data" + chr(165) + " first."
    status = {m["legacy"]: m["status"] for m in proposal["mapping"]}
    assert status["lblA"] == status["lblB"] == status["lblC"] == "changed"
    assert status["lblFar"] == "kept"


def test_a_list_is_paged_as_a_web_list_and_the_mapping_says_what_the_legacy_one_did() -> None:
    screen = {"name": "Stores", "caption": "Stores", "mode": {"view": "continuous"},
              "window": {"height": 420, "maximized": False}, "form": {},
              "sections": [{"code": 1, "height": 20}, {"code": 0, "height": 25}],
              "data": {"rows": [], "total": 54},
              "controls": [_c("txtCode", "display", source="CODE")]}
    proposal = to_be.propose(screen, "", {}, ())
    page = next(r for r in proposal["regions"] if r["kind"] == "table")["pagination"]
    # A current-day pager, not the legacy navigator: the legacy rows only explain the change.
    assert (page["page_size"], page["sizes"], page["legacy_rows"], page["total"]) == (20, [20, 50, 100], 15, 54)
    assert any(m["role"] == "navigation" and m["status"] == "changed" for m in proposal["mapping"])


def test_a_list_page_is_paged_even_when_the_sample_is_short() -> None:
    """Today's three rows say nothing about tomorrow's; the pager is the list page's."""
    screen = {"name": "Shops", "caption": "Shops", "mode": {"view": "continuous"}, "form": {},
              "sections": [{"code": 0, "height": 20}], "data": {"rows": [], "total": 3},
              "controls": [_c("txtCode", "display", source="CODE")]}
    proposal = to_be.propose(screen, "", {}, ())
    page = next(r for r in proposal["regions"] if r["kind"] == "table")["pagination"]
    assert (page["page_size"], page["total"]) == (20, 3)
    assert any(m["role"] == "navigation" for m in proposal["mapping"])


def test_a_heading_over_two_columns_stays_the_legacy_heading() -> None:
    screen = {"name": "Lines", "caption": "Lines", "mode": {"view": "continuous"},
              "data": {"rows": [], "total": 1},
              "controls": [_c("lblItem", "text", section=1, left=0, width=130, caption="Item"),
                           _c("txtCode", "display", left=0, source="CODE"),
                           _c("txtName", "display", left=0, top=20, source="NAME")]}
    proposal = to_be.propose(screen, "", {}, ())
    columns = next(r for r in proposal["regions"] if r["kind"] == "table")["columns"]
    assert [(c["label"], c.get("shared_heading")) for c in columns] == [("Item", True), ("Item", True)]
    rows = {m["legacy"]: m["to_be"] for m in proposal["mapping"]}
    assert "field CODE" in rows["txtCode"] and "field NAME" in rows["txtName"]


def test_a_caption_above_an_embedded_list_goes_with_that_list() -> None:
    sub = {"SourceObject": "Form.Shops"}
    screen = {"name": "Orders", "caption": "Orders", "mode": {"view": "single"}, "controls": [
        _c("lblShops", "text", left=0, top=0, width=100, caption="Shops"),
        _c("lblLines", "text", left=200, top=0, width=100, caption="Lines"),
        _c("subShops", "embedded list", left=0, top=20, width=180, style=sub),
        _c("subLines", "embedded list", left=200, top=20, width=300, style={"SourceObject": "Form.Lines"})]}
    proposal = to_be.propose(screen, "", {}, ())
    items = next(r for r in proposal["regions"] if r["kind"] == "embedded")["items"]
    assert {i["form"]: i["caption"]["text"] for i in items} == {"Shops": "Shops", "Lines": "Lines"}
    assert not any(r["kind"] == "text" for r in proposal["regions"])
