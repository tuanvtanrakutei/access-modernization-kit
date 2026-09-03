"""The references page, and the two things it must not get wrong.

It exists because the published set cited evidence ids and evidence ids cited paths,
and nothing named the sources as documents - no date, no author, no digest. A reader
holding a spreadsheet had no way to know whether it was the copy that was read.

Two ways it could mislead: reporting a file as uncited when it is cited through
something derived from it, and omitting a supplied file altogether.
"""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
sys.path.insert(0, str(PACKAGE / "contracts"))

import build_references as references  # noqa: E402


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    root = tmp_path / "T01"
    for name in ("documents", "screenshots", "access", "decisions"):
        (root / "input" / name).mkdir(parents=True)
    io.open(root / "input" / "documents" / "function-list.xlsx", "w",
            encoding="utf-8").write("x")
    io.open(root / "input" / "documents" / "unread.docx", "w", encoding="utf-8").write("y")
    io.open(root / "input" / "screenshots" / "menu.png", "w", encoding="utf-8").write("z")
    io.open(root / "input" / "access" / "app.mdb", "w", encoding="utf-8").write("db")
    io.open(root / "input" / "decisions" / "glossary.yaml", "w",
            encoding="utf-8").write("tables: {}")
    output = root / "output" / "registers"
    output.mkdir(parents=True)
    io.open(output / "T01_Evidence.json", "w", encoding="utf-8").write(json.dumps({
        "items": [
            {"id": "T01-P5-DOC-001",
             "source_path": "input/documents/function-list.xlsx"},
            {"id": "T01-P1-SCHEMA-001",
             "source_path": ".ak/staging/DB/fresh-01/schema/tables.json"},
        ]
    }))
    io.open(root / "manifest.yaml", "w", encoding="utf-8").write(
        "version: '2.2'\napp:\n  id: T01\n")
    return root


def run(root: Path, *extra: str) -> str:
    result = subprocess.run(
        [sys.executable, str(PACKAGE / "scripts" / "build_references.py"),
         "--app-root", str(root), *extra],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout


def page(root: Path) -> str:
    run(root)
    return (root / "output" / "T01_References.md").read_text(encoding="utf-8")


def test_every_supplied_file_appears(workspace: Path) -> None:
    text = page(workspace)
    for name in ("function-list.xlsx", "unread.docx", "menu.png", "app.mdb",
                 "glossary.yaml"):
        assert name in text, name


def test_each_file_carries_a_digest_and_a_date(workspace: Path) -> None:
    """The digest is the point: it says which copy was read."""
    text = page(workspace)
    import re

    assert re.search(r"`[0-9a-f]{16}…`", text), "a truncated SHA-256 must be shown"
    assert re.search(r"\| \d{4}-\d{2}-\d{2} \|", text), "a modification date must be shown"


def test_a_cited_document_reads_as_cited(workspace: Path) -> None:
    text = page(workspace)
    row = next(line for line in text.splitlines() if "function-list.xlsx" in line)
    assert "| yes |" in row


def test_an_uncited_document_is_named_rather_than_hidden(workspace: Path) -> None:
    text = page(workspace)
    row = next(line for line in text.splitlines() if "unread.docx" in line)
    assert "not yet" in row
    # Two: the unread document and the screenshot. Both are evidence classes a
    # document cites by path, and neither is cited by the fixture's register.
    assert "2 supplied file(s) are not cited" in text


def test_an_access_database_is_not_reported_as_uncited(workspace: Path) -> None:
    """It is cited through the definition text extracted from it, not by path."""
    text = page(workspace)
    row = next(line for line in text.splitlines() if "app.mdb" in line)
    assert "via extraction" in row
    assert "not yet" not in row


def test_a_decisions_file_is_not_reported_as_uncited(workspace: Path) -> None:
    text = page(workspace)
    row = next(line for line in text.splitlines() if "glossary.yaml" in line)
    assert "| n/a |" in row


def test_an_empty_workspace_says_nothing_was_supplied(tmp_path: Path) -> None:
    root = tmp_path / "T02"
    (root / "input").mkdir(parents=True)
    (root / "output").mkdir(parents=True)
    io.open(root / "manifest.yaml", "w", encoding="utf-8").write(
        "version: '2.2'\napp:\n  id: T02\n")
    run(root)
    text = (root / "output" / "T02_References.md").read_text(encoding="utf-8")
    assert "**Nothing.**" in text
    assert "absent by necessity rather than by omission" in text


def test_the_contract_versions_are_listed(workspace: Path) -> None:
    """A conformance result means nothing without the contract version behind it."""
    text = page(workspace)
    assert "evidence-classes.yaml" in text
    assert "ja-en-terms.yaml" in text


def test_dry_run_writes_nothing(workspace: Path) -> None:
    run(workspace, "--dry-run")
    assert not (workspace / "output" / "T01_References.md").exists()


def test_regenerating_is_stable_apart_from_the_date(workspace: Path) -> None:
    first = page(workspace)
    second = page(workspace)
    assert first == second
