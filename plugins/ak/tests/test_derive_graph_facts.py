"""Where the deriver reads object text from, and why it matters which.

An acquisition that takes its definition text from an operator's export writes that
text into the bundle and leaves the previous staging files untouched. A deriver
reading staging alone therefore re-derives from the older text and reports no
difference - which is how A05's reachability figures came to be computed from a main
menu missing 24 of its 45 procedures, and published as findings about dead code
(`E-17`, `E-18`).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
sys.path.insert(0, str(PACKAGE / "contracts"))

import derive_graph_facts as deriver  # noqa: E402


def _bundle(root: Path, forms: list[dict], queries: list[dict] | None = None) -> Path:
    bundle = root / "bundle"
    (bundle / "ui" / "forms").mkdir(parents=True)
    (bundle / "ui" / "forms" / "inventory.json").write_text(
        json.dumps(forms, ensure_ascii=False), encoding="utf-8")
    if queries is not None:
        (bundle / "code" / "access-sql").mkdir(parents=True)
        (bundle / "code" / "access-sql" / "inventory.json").write_text(
            json.dumps(queries, ensure_ascii=False), encoding="utf-8")
    return bundle


def test_inline_text_is_read(tmp_path: Path) -> None:
    """The imported route stores the whole definition inline, hash-verified."""
    bundle = _bundle(tmp_path, [{
        "kind": "form", "object_name": "メインメニュー",
        "logical_id": "FRONTEND:form:forms/メインメニュー.txt",
        "text": "Private Sub 取り込み_Click()\n    DoCmd.OpenForm \"取込\"\nEnd Sub\n",
    }])
    found = deriver.bundle_texts(bundle)
    assert ("FRONTEND", "form", "メインメニュー") in found
    text, member, row = found[("FRONTEND", "form", "メインメニュー")]
    assert "取り込み_Click" in text
    # Cited as the inventory plus the object name, because that is where the text is.
    assert member.name == "inventory.json" and row == "メインメニュー"


def test_the_database_comes_from_the_logical_id_when_absent(tmp_path: Path) -> None:
    """The imported route leaves `database_id` empty and states it in the id.

    Keyed on an empty database the object would never match the staging key, and the
    text would be silently ignored.
    """
    bundle = _bundle(tmp_path, [{
        "kind": "form", "object_name": "F", "database_id": "",
        "logical_id": "FRONTEND:form:forms/F.txt", "text": "x",
    }])
    assert ("FRONTEND", "form", "F") in deriver.bundle_texts(bundle)


def test_container_kinds_are_normalised(tmp_path: Path) -> None:
    """One inventory holds both spellings when a workspace acquires each way.

    The imported route names its kinds after the container (`vba`, `access_sql`), the
    managed route after the object (`module`, `query`). Left untranslated, an imported
    query is filed under a kind no consumer looks for.
    """
    member = "abc123.txt"
    bundle = _bundle(tmp_path, [], queries=[
        {"kind": "access_sql", "object_name": "q1",
         "logical_id": "FRONTEND:access_sql:queries/q1.sql", "path": member},
        {"kind": "query", "name": "q2", "database_id": "BACKEND", "path": member},
    ])
    (bundle / "code" / "access-sql" / member).write_text("SELECT 1", encoding="utf-8")
    found = deriver.bundle_texts(bundle)
    assert ("FRONTEND", "query", "q1") in found
    assert ("BACKEND", "query", "q2") in found


def test_a_member_that_is_not_there_is_not_invented(tmp_path: Path) -> None:
    bundle = _bundle(tmp_path, [], queries=[
        {"kind": "query", "name": "q", "database_id": "D", "path": "missing.txt"}])
    assert deriver.bundle_texts(bundle) == {}


def test_no_bundle_is_not_an_error(tmp_path: Path) -> None:
    assert deriver.bundle_texts(None) == {}
    assert deriver.bundle_texts(tmp_path / "nope") == {}


def _workspace(tmp_path: Path, staging_text: str, bundle_text: str) -> Path:
    """A workspace holding one form twice: stale in staging, current in the bundle."""
    root = tmp_path / "app"
    ak = root / ".ak"
    (root / "input").mkdir(parents=True)  # marks the new layout

    bundle = ak / "bundles" / "2026-09-04-abcdef12"
    (bundle / "databases").mkdir(parents=True)
    (bundle / "databases" / "tables.json").write_text(
        json.dumps([{"name": "受注データ", "database_id": "FRONTEND"}],
                   ensure_ascii=False), encoding="utf-8")
    (bundle / "bundle.json").write_text("{}", encoding="utf-8")
    (bundle / "ui" / "forms").mkdir(parents=True)
    (bundle / "ui" / "forms" / "inventory.json").write_text(
        json.dumps([{"kind": "form", "object_name": "メインメニュー",
                     "logical_id": "FRONTEND:form:forms/メインメニュー.txt",
                     "text": bundle_text}], ensure_ascii=False), encoding="utf-8")

    session = ak / "staging" / "FRONTEND" / "old-session"
    (session / "forms").mkdir(parents=True)
    (session / "forms" / "メインメニュー.txt").write_text(staging_text, encoding="utf-8")
    (session / "access-extraction.json").write_text(json.dumps({
        "components": [{"kind": "form", "name": "メインメニュー",
                        "source_paths": ["forms/メインメニュー.txt"]}]
    }, ensure_ascii=False), encoding="utf-8")
    return root


def _derive(root: Path) -> dict:
    argv = sys.argv
    sys.argv = ["derive_graph_facts.py", "--app-root", str(root)]
    try:
        assert deriver.main() == 0
    finally:
        sys.argv = argv
    return json.loads(
        (root / ".ak" / "extracted" / "derived-extraction.json").read_text(
            encoding="utf-8"))


def test_bundle_text_wins_over_stale_staging(tmp_path: Path) -> None:
    """The whole point. Staging is refreshed only by the managed route.

    Here staging holds a form that references nothing and the bundle holds the same
    form referencing a table. Reading staging, the deriver finds no edge and reports
    the table as referenced by nothing - which is the shape of E-18.
    """
    root = _workspace(
        tmp_path,
        staging_text="Private Sub Form_Open()\nEnd Sub\n",
        bundle_text='Private Sub Form_Open()\n    x = "受注データ"\nEnd Sub\n')
    derived = _derive(root)
    labels = {node["id"]: node["label"] for node in derived["nodes"]}
    edges = [(labels[e["source"]], labels[e["target"]]) for e in derived["edges"]]
    assert ("メインメニュー", "受注データ") in edges, (
        "the bundle's text names the table; staging's does not")


def test_staging_is_still_read_when_the_bundle_carries_nothing(tmp_path: Path) -> None:
    """The managed route leaves forms in staging, and that route must keep working."""
    root = _workspace(
        tmp_path,
        staging_text='Private Sub Form_Open()\n    x = "受注データ"\nEnd Sub\n',
        bundle_text="")
    # An empty inline text is not text: the row falls back to the staging file.
    derived = _derive(root)
    labels = {node["id"]: node["label"] for node in derived["nodes"]}
    edges = [(labels[e["source"]], labels[e["target"]]) for e in derived["edges"]]
    assert ("メインメニュー", "受注データ") in edges
