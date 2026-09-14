"""What `$ak clean` offers, tested on throwaway workspaces.

The risk here is one-directional. A command that offers too little wastes disk; a
command that offers too much destroys evidence that cannot be re-acquired - the
database may have changed, and on a customer site the kit may never see it again.
So most of what follows asserts a *refusal*: the cited session survives, the last
session survives, the newest export survives, the supplied file survives without
the flag that names it.

The first test is the case that decided the design. On the real A05 workspace the
newest staging session for the frontend holds four files, because that acquisition
declared `skip_object_export`, while the session the register cites 30 times is
three weeks older and holds 170 definition texts. Any rule phrased as "keep the
newest" deletes the evidence and keeps the husk.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
sys.path.insert(0, str(PACKAGE / "contracts"))

import clean_workspace as clean  # noqa: E402
from workspace import Workspace  # noqa: E402

MANIFEST = """version: '2.2'
app:
  id: A05
artifacts:
- id: FRONTEND
  source_ref:
    type: local_path
    value: input/access/frontend.mdb
"""


def write(path: Path, text: str = "x") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


@pytest.fixture
def space(tmp_path: Path) -> Workspace:
    """A current-layout workspace with one artifact and one published register."""
    write(tmp_path / "manifest.yaml", MANIFEST)
    write(tmp_path / "input" / "access" / "frontend.mdb")
    write(tmp_path / "output" / "registers" / "A05_Evidence.json", json.dumps({
        "items": [{"id": "E-1", "source": ".ak/staging/FRONTEND/fresh-01/forms/menu.txt"}],
    }))
    return Workspace(tmp_path)


def offered(space: Workspace) -> dict[str, dict]:
    return {item["path"]: item for item in clean.survey(space)}


# --- staging sessions --------------------------------------------------------


def test_the_cited_session_survives_a_newer_uncited_one(space: Workspace) -> None:
    old = write(space.root / ".ak/staging/FRONTEND/fresh-01/forms/menu.txt", "definition")
    new = write(space.root / ".ak/staging/FRONTEND/acquire-ff/schema/tables.txt", "names")
    new.parent.parent.touch()  # newer by mtime than the cited session

    found = offered(space)
    assert ".ak/staging/FRONTEND/acquire-ff" in found
    assert ".ak/staging/FRONTEND/fresh-01" not in found
    assert old.is_file()


def test_a_databases_last_session_is_never_offered(space: Workspace) -> None:
    write(space.root / ".ak/staging/BACKEND/acquire-01/schema/tables.txt")
    assert ".ak/staging/BACKEND/acquire-01" not in offered(space)


def test_with_nothing_cited_the_newest_session_is_kept(space: Workspace) -> None:
    first = write(space.root / ".ak/staging/BACKEND/acquire-01/schema/tables.txt")
    second = write(space.root / ".ak/staging/BACKEND/acquire-02/schema/tables.txt")
    second.parent.parent.touch()

    found = offered(space)
    assert ".ak/staging/BACKEND/acquire-01" in found
    assert ".ak/staging/BACKEND/acquire-02" not in found
    assert second.is_file() and first.is_file()  # survey removes nothing


# --- kit directories in a place nothing resolves -----------------------------


def test_a_staging_outside_ak_is_offered(space: Workspace) -> None:
    write(space.root / ".ak/staging/FRONTEND/fresh-01/forms/menu.txt")
    write(space.root / "staging/FRONTEND/acquire-99/forms/menu.txt")
    assert "staging" in offered(space)


def test_it_is_not_offered_when_ak_has_no_counterpart(space: Workspace) -> None:
    """A half-migrated workspace, where the top-level directory is still the live one."""
    write(space.root / "staging/FRONTEND/acquire-99/forms/menu.txt")
    assert "staging" not in offered(space)


def test_a_legacy_workspace_keeps_its_own_layout(tmp_path: Path) -> None:
    write(tmp_path / "manifest.yaml", MANIFEST.replace("input/", "sources/"))
    write(tmp_path / "sources/access/frontend.mdb")
    write(tmp_path / "acquired/staging/FRONTEND/fresh-01/forms/menu.txt")
    write(tmp_path / "runs/A05-P1/tasks.json", "{}")

    found = offered(Workspace(tmp_path))
    assert "runs" not in found
    assert "acquired/staging" not in found


# --- export packages ---------------------------------------------------------


def test_a_superseded_export_package_is_offered_and_the_newest_is_not(space: Workspace) -> None:
    for name in ("FRONTEND-2026-09-01", "FRONTEND-2026-09-04", "FRONTEND-2026-09-08"):
        write(space.root / "input/exports" / name / "forms" / "menu.txt")
    write(space.root / "manifest.yaml", MANIFEST + """- id: FRONTEND_EXPORT
  source_ref:
    type: local_path
    value: input/exports/FRONTEND-2026-09-04
""")

    found = offered(space)
    assert "input/exports/FRONTEND-2026-09-01" in found
    assert found["input/exports/FRONTEND-2026-09-01"]["guard"] == "input"
    assert "input/exports/FRONTEND-2026-09-04" not in found  # cited by the manifest
    assert "input/exports/FRONTEND-2026-09-08" not in found  # newest for its artifact


def test_nothing_is_offered_when_no_package_is_cited(space: Workspace) -> None:
    """Exported but not yet acquired - every package is still someone's next step."""
    for name in ("FRONTEND-2026-09-01", "FRONTEND-2026-09-08"):
        write(space.root / "input/exports" / name / "forms" / "menu.txt")
    assert not [path for path in offered(space) if path.startswith("input/exports")]


# --- supplied files ----------------------------------------------------------


def test_a_lock_file_beside_a_declared_database_is_offered(space: Workspace) -> None:
    write(space.root / "input/access/frontend.ldb")
    found = offered(space)
    assert "input/access/frontend.ldb" in found
    assert found["input/access/frontend.ldb"]["kind"] == "file"
    assert "input/access/frontend.mdb" not in found


def test_an_undeclared_database_is_left_alone_when_nothing_is_declared(tmp_path: Path) -> None:
    write(tmp_path / "manifest.yaml", "version: '2.2'\napp:\n  id: A05\n")
    write(tmp_path / "input/access/one.mdb")
    write(tmp_path / "input/access/two.mdb")
    assert not offered(Workspace(tmp_path))


# --- removal -----------------------------------------------------------------


def test_input_entries_need_their_own_flag(space: Workspace) -> None:
    write(space.root / "input/access/frontend.ldb")
    write(space.root / ".ak/snapshots/acquire-01/frontend.mdb")
    found = clean.survey(space)

    removed = clean.remove(space.root, found, include_input=False)
    assert removed == [".ak/snapshots"]
    assert (space.root / "input/access/frontend.ldb").is_file()

    assert clean.remove(space.root, clean.survey(space), include_input=True) == [
        "input/access/frontend.ldb",
    ]
    assert not (space.root / "input/access/frontend.ldb").exists()


def test_a_protected_path_is_refused(space: Workspace) -> None:
    entry = {"path": ".ak/staging", "guard": "kit"}
    with pytest.raises(PermissionError):
        clean.remove(space.root, [entry], include_input=False)
    assert (space.root / "input").is_dir()

    with pytest.raises(PermissionError):
        clean.remove(space.root, [{"path": "..", "guard": "kit"}], include_input=False)


# --- reading a citation ------------------------------------------------------


@pytest.mark.parametrize("text, expected", [
    (r'"D:\Anrakutei\fresh\A05\.ak\staging\FRONTEND\fresh-01\forms\menu.txt"',
     ".ak/staging/FRONTEND/fresh-01/forms/menu.txt"),
    ("see input/exports/FRONTEND-2026-09-04/forms/menu.txt, line 12",
     "input/exports/FRONTEND-2026-09-04/forms/menu.txt"),
    ("[the export](input/exports/FRONTEND-2026-09-04)",
     "input/exports/FRONTEND-2026-09-04"),
    ("input/access/品揃支援（windows11専用）.mdb",
     "input/access/品揃支援（windows11専用）.mdb"),
])
def test_a_citation_reduces_to_one_workspace_relative_key(text: str, expected: str) -> None:
    assert expected in clean.paths_in(text)


def test_a_longer_name_is_not_mistaken_for_a_root(space: Workspace) -> None:
    assert clean.paths_in("no-input/exports/FRONTEND-2026-09-01") == set()
