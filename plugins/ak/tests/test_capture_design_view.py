"""The design-view capture refuses without authorization and never names an original."""
from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

import capture_design_view as capture  # noqa: E402


def test_it_refuses_without_the_acquisition_authorization(tmp_path: Path, capsys) -> None:
    (tmp_path / "input" / "access").mkdir(parents=True)
    (tmp_path / "input" / "access" / "app.mdb").write_bytes(b"x")
    assert capture.main(["--app-root", str(tmp_path)]) == 2
    assert "access_snapshot_extract" in capsys.readouterr().err


def test_every_access_file_under_input_access_is_offered(tmp_path: Path) -> None:
    folder = tmp_path / "input" / "access"
    folder.mkdir(parents=True)
    for name in ("front.mdb", "back.accdb", "notes.txt"):
        (folder / name).write_bytes(b"x")
    assert [p.name for p in capture.frontends(tmp_path)] == ["back.accdb", "front.mdb"]
