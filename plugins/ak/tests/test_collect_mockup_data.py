"""The runtime mockup's data collection: what it asks the database, and when it refuses."""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

import collect_mockup_data as collect  # noqa: E402

FORM = (
    'Begin Form\n'
    '    RecordSource ="SELECT A.X, A.Y FROM A GROUP BY A.X, A"\n'
    '        ".Y;"\n'
    '    Begin Section\n'
    '        Begin\n'
    '            Begin ComboBox\n'
    '                Name ="cboStore"\n'
    '                RowSource ="SELECT CODE, NAME FROM STORE;"\n'
    '            End\n'
    '            Begin ComboBox\n'
    '                Name ="cboCourse"\n'
    '                RowSourceType ="Value List"\n'
    '                RowSource ="A;B"\n'
    '            End\n'
    '        End\n'
    '    End\n'
    'End\n'
)


def test_each_form_and_each_table_row_source_is_requested_once() -> None:
    requests = collect.requests_for([{"database_id": "APP", "name": "List", "text": FORM}])
    assert requests == [
        {"key": "APP::form::List", "database": "APP",
         "source": "SELECT A.X, A.Y FROM A GROUP BY A.X, A.Y;"},
        {"key": "APP::rows::List::cboStore", "database": "APP",
         "source": "SELECT CODE, NAME FROM STORE;"},
    ]


def test_it_refuses_without_the_acquisition_authorization(tmp_path: Path, capsys) -> None:
    assert collect.main(["--app-root", str(tmp_path)]) == 2
    assert "access_snapshot_extract" in capsys.readouterr().err
