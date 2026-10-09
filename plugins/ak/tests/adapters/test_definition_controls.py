from __future__ import annotations

from pathlib import Path

from adapters import definition_controls
from adapters.managed_access.adapter import ManagedAccessAdapter, _inline_definitions

# A trimmed SaveAsText definition: a tab with two pages, a disabled button on one, a
# hidden text box, a combo box with a value list, and code behind the form.
DEFINITION = """Version =20
Begin Form
    RecordSource ="T_ORDER"
    Caption ="Menu"
    Begin
        Begin Label
            BackStyle =0
        End
    End
    Begin Section
        Height =4000
        Begin
            Begin CommandButton
                Left =300
                Top =200
                Width =1200
                Height =300
                Name ="cmdImport"
                Caption ="Import"
                OnClick ="[Event Procedure]"
            End
            Begin Tab
                Name ="tabMain"
                Begin
                    Begin Page
                        Name ="pageA"
                        Caption ="A"
                        Begin
                            Begin CommandButton
                                Enabled = NotDefault
                                Name ="cmdErrors"
                                Caption ="Errors"
                            End
                        End
                    End
                    Begin Page
                        Name ="pageB"
                        Caption ="B"
                    End
                End
            End
            Begin TextBox
                Visible = NotDefault
                Name ="txtHidden"
                ControlSource ="LAST_RUN"
            End
            Begin ComboBox
                Name ="cboCourse"
                RowSource ="Mon;Tue"
            End
        End
    End
End
CodeBehindForm
Private Sub cmdImport_Click()
End Sub
"""


def test_every_named_control_is_read_with_its_type_parent_and_state() -> None:
    controls = {c["name"]: c for c in definition_controls.controls(DEFINITION)}

    assert list(controls) == ["cmdImport", "tabMain", "pageA", "cmdErrors", "pageB",
                              "txtHidden", "cboCourse"]
    assert controls["cmdImport"]["type"] == 104
    assert controls["cmdImport"]["caption"] == "Import"
    assert controls["cmdImport"]["on_click"] == "[Event Procedure]"
    assert controls["cmdImport"]["left"] == 300
    assert controls["tabMain"]["type"] == 123
    assert controls["pageA"]["parent"] == "tabMain"
    assert controls["cmdErrors"]["parent"] == "pageA"
    assert controls["cmdErrors"]["enabled"] is False
    assert controls["txtHidden"]["visible"] is False
    assert controls["txtHidden"]["control_source"] == "LAST_RUN"
    assert controls["cboCourse"]["row_source"] == "Mon;Tue"
    assert all(c["section"] == 0 for c in controls.values())


def test_the_managed_route_carries_definition_text_and_controls(tmp_path: Path) -> None:
    """A90. The managed route recorded only a path to each form's definition, so the
    bundle held names: no definition text and no control inventory."""
    (tmp_path / "forms").mkdir()
    (tmp_path / "forms" / "Menu.txt").write_text(DEFINITION, encoding="utf-8-sig")
    data = {
        "schema_version": "2.1", "database_id": "APP", "session_id": "s1",
        "source": {"path": "x", "format": "mdb", "sha256": "a" * 64},
        "snapshot": {"path": "s", "sha256": "a" * 64}, "status": "EXTRACTED",
        "runtime": {}, "project_context": {}, "warnings": [],
        "components": [{"kind": "form", "name": "Menu", "metadata": {},
                        "source_paths": ["forms/Menu.txt"]}],
    }
    _inline_definitions(data, tmp_path)
    adapter = ManagedAccessAdapter()
    contribution = adapter.normalize(adapter.result_from_extraction("SYN", data))

    form = contribution["ui"]["forms"][0]
    assert "cmdImport_Click" in form["text"]
    entry = contribution["ui"]["controls"][0]
    assert (entry["database_id"], entry["object"], entry["kind"]) == ("APP", "Menu", "form")
    assert len(entry["controls"]) == 7
    assert "ui_definition_text" in contribution["provenance"]["capabilities"]
