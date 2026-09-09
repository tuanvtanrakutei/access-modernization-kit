from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import init_app

PACKAGE = Path(__file__).resolve().parents[1]


def run_init(app_root: Path, app_id: str, *extra: str) -> str:
    result = subprocess.run(
        [sys.executable, str(PACKAGE / "scripts" / "init_app.py"),
         "--app-root", str(app_root), "--app-id", app_id,
         "--name-en", "Test App", *extra],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout


def _sources(root: Path) -> Path:
    """A source tree in the shape this kit's own extractor produces."""
    (root / "access").mkdir(parents=True)
    (root / "forms").mkdir()
    (root / "queries").mkdir()
    (root / "schema").mkdir()
    return root


# Two Access databases are a split application, not a monolith with two frontends.
# The wrong role is the costly part: nothing then declares an authoritative backend,
# so Phase 1 can never leave BLOCKED however complete the extraction is.
def test_two_access_databases_are_classified_as_a_split_application(tmp_path: Path) -> None:
    app_root = tmp_path / "A05"
    sources = _sources(app_root / "sources")
    (sources / "access" / "frontend.mdb").write_bytes(b"x")
    (sources / "access" / "data.mdb").write_bytes(b"x")

    classification, artifacts = init_app.discover_sources(app_root)

    assert classification["topology"] == "split_file"
    assert classification["backend_kinds"] == ["access_file"]
    databases = [item for item in artifacts if item["kind"] == "access_database"]
    assert len(databases) == 2
    # Which file is authoritative cannot be read off the filesystem, so the role is
    # left explicitly unknown for a human rather than guessed from a filename.
    assert {item["role"] for item in databases} == {"unknown"}


def test_a_single_access_database_stays_a_monolith(tmp_path: Path) -> None:
    app_root = tmp_path / "A05"
    sources = _sources(app_root / "sources")
    (sources / "access" / "only.mdb").write_bytes(b"x")

    classification, artifacts = init_app.discover_sources(app_root)

    assert classification["topology"] == "monolith"
    assert classification["backend_kinds"] == ["embedded_access"]
    assert [item["role"] for item in artifacts if item["kind"] == "access_database"] == ["frontend"]


# A Japanese name - the norm in this kit's target systems - lost every character to
# the id sanitize, so distinct objects collapsed onto one base and were separated by
# an arrival-order counter that changed whenever the file order did.
def test_non_ascii_names_get_stable_distinct_ids(tmp_path: Path) -> None:
    app_root = tmp_path / "A05"
    sources = _sources(app_root / "sources")
    (sources / "forms" / "共通ルーチン.txt").write_text("Version =20", encoding="utf-8")
    (sources / "forms" / "印刷設定.txt").write_text("Version =20", encoding="utf-8")

    _, first = init_app.discover_sources(app_root)
    _, second = init_app.discover_sources(app_root)

    ids = [item["id"] for item in first]
    assert len(set(ids)) == 2, ids
    assert not any(item["id"] == "ART" for item in first)
    # Derived from the name, so a second pass produces the same ids.
    assert ids == [item["id"] for item in second]


# extract_access.ps1 writes object definitions as .txt under forms/, reports/,
# macros/ and vba/. Classifying by extension alone dropped all of it into the
# catch-all sample bucket, so the package did not recognize its own output.
def test_the_kits_own_export_layout_is_recognized(tmp_path: Path) -> None:
    app_root = tmp_path / "A05"
    sources = _sources(app_root / "sources")
    (sources / "forms" / "OrderEntry.txt").write_text("Version =20", encoding="utf-8")
    (sources / "schema" / "tables.txt").write_text("{}", encoding="utf-8")
    (sources / "queries" / "qOrders.sql").write_text("SELECT 1;", encoding="utf-8")

    classification, artifacts = init_app.discover_sources(app_root)

    by_id = {item["id"]: item for item in artifacts}
    assert by_id["ORDERENTRY"]["format"] == "form"
    assert by_id["ORDERENTRY"]["kind"] == "source_export"
    assert by_id["TABLES"]["format"] == "table_schema"
    # Query SQL exported out of an Access database is not evidence of a SQL Server
    # backend; only .sql outside a queries/ folder implies a server.
    assert classification["backend_kinds"] == ["embedded_access"]


def test_sql_outside_a_queries_folder_still_implies_a_server(tmp_path: Path) -> None:
    app_root = tmp_path / "A05"
    sources = _sources(app_root / "sources")
    (sources / "sql").mkdir()
    (sources / "sql" / "schema.sql").write_text("CREATE TABLE t (id int);", encoding="utf-8")

    classification, _ = init_app.discover_sources(app_root)

    assert classification["backend_kinds"] == ["sql_server"]


# A generated manifest declared a graph runtime, its version and its refresh policy.
# None of it survives: derivation needs no runtime, no version pin and no policy, so a
# manifest that still carried the block would be describing machinery that is gone.
def test_generated_v22_manifest_declares_no_graph_runtime() -> None:
    import yaml

    text = init_app.manifest_v22_text(
        "A05", "Product Assortment Support",
        {"topology": "monolith", "frontend_format": "mdb", "source_availability": "full", "backend_kinds": ["embedded_access"]},
        [],
    )
    data = yaml.safe_load(text)
    assert "graphify" not in data
    assert set(data) == {"version", "app", "project", "artifacts"}


# --- the guide to input/ ------------------------------------------------------
#
# It belongs to the kit, not to a project: it explains what each evidence class can
# establish, which is the same in every workspace. What a particular project still
# needs is the evidence request in output/, regenerated as the run learns - so the
# two must not merge, and this guide must name no project.


def test_init_writes_the_input_guide(tmp_path: Path) -> None:
    root = tmp_path / "T01"
    run_init(root, "T01")
    guide = root / "input" / "README.md"
    assert guide.is_file(), "init must write input/README.md"
    text = guide.read_text(encoding="utf-8")
    assert "DOCUMENT" in text and "SCREENSHOT" in text and "SAMPLE_DATA" in text
    assert "ExportAccessObjects" in text


def test_the_guide_names_no_project(tmp_path: Path) -> None:
    """A shared template carrying one project's counts is a template nobody trusts."""
    text = (PACKAGE / "templates" / "input.README.md").read_text(encoding="utf-8")
    for leaked in ("A05", "品揃支援", "受注データ", "L:"):
        assert leaked not in text, f"the shared guide must not name {leaked!r}"


def test_adopting_a_workspace_does_not_overwrite_an_edited_guide(tmp_path: Path) -> None:
    """`init` refuses a workspace that already holds kit-owned files, so the case
    that matters is adopting a directory somebody laid out by hand and annotated."""
    root = tmp_path / "T02"
    (root / "input").mkdir(parents=True)
    guide = root / "input" / "README.md"
    guide.write_text("notes I wrote myself\n", encoding="utf-8")
    run_init(root, "T02", "--adopt-existing")
    assert guide.read_text(encoding="utf-8") == "notes I wrote myself\n"


def test_migrating_an_older_workspace_adds_the_guide(tmp_path: Path) -> None:
    """A workspace created before the guide existed should gain one on migration."""
    import migrate_workspace as migrate

    root = tmp_path / "T03"
    (root / "sources" / "access").mkdir(parents=True)
    (root / "sources" / "access" / "x.mdb").write_text("db", encoding="utf-8")
    migrate.apply(root, migrate.plan(root))
    assert (root / "input" / "README.md").is_file()


def test_the_workspace_gitignore_covers_what_init_actually_creates(tmp_path: Path) -> None:
    """The template drifted a whole layout behind the workspace it is written into.

    2.10.0 renamed `sources/` to `input/` and moved `runs/`, `snapshots/` and
    `staging/` under `.ak/`, and `templates/app.gitignore` kept only the older names.
    Nothing failed, which is why it survived: a rule that matches no path is
    indistinguishable from a rule that matches nothing worth ignoring. The cost showed
    up on a real project - two production Access databases sitting untracked but not
    ignored inside an application repository shared with another developer, one
    `git add .` away from being pushed.

    This asserts the semantics rather than the text, because the defect was that the
    text looked entirely reasonable.
    """
    if not shutil.which("git"):
        pytest.skip("git is not on PATH; this test asserts real ignore semantics")
    app_root = tmp_path / "A99"
    run_init(app_root, "A99")

    (app_root / "input" / "access" / "app.mdb").write_bytes(b"not a real database")
    (app_root / "input" / "access" / "DATA.MDB").write_bytes(b"not a real database")
    snapshot = app_root / ".ak" / "snapshots" / "acquire-1"
    snapshot.mkdir(parents=True, exist_ok=True)
    (snapshot / "copy.mdb").write_bytes(b"not a real database")
    bundle = app_root / ".ak" / "bundles" / "2026-01-01-abcdef12"
    bundle.mkdir(parents=True, exist_ok=True)
    (bundle / "bundle.json").write_text("{}", encoding="utf-8")

    subprocess.run(["git", "init", "--quiet"], cwd=app_root, check=True,
                   capture_output=True, text=True)
    listed = subprocess.run(
        ["git", "status", "--porcelain", "--untracked-files=all"],
        cwd=app_root, check=True, capture_output=True, text=True, encoding="utf-8",
        errors="replace").stdout

    databases = [line for line in listed.splitlines() if line.lower().endswith(".mdb")]
    assert databases == [], databases
    # The sealed bundle is the evidence a later phase cites. Ignoring the raw
    # databases must not take it with them.
    assert any("bundle.json" in line for line in listed.splitlines()), listed


def test_init_writes_the_interview_guide_without_claiming_interview_evidence(
    tmp_path: Path,
) -> None:
    """Two changes that only work together, so they are asserted together.

    `input/interviews/` is the one evidence class no command in this kit produces, and
    the schema requires a name and a date *inside* the file - which a bare directory
    cannot tell anybody. So `init` writes a guide there. That is only safe because
    `evidence_classes._has_files` skips the kit's own guides: writing this file
    without that rule would report INTERVIEW evidence present on every freshly
    initialized project, and Phases 5 and 6 would read better than they are.
    """
    import sys

    sys.path.insert(0, str(PACKAGE / "contracts"))
    import evidence_classes

    app_root = tmp_path / "A99"
    run_init(app_root, "A99")

    guide = app_root / "input" / "interviews" / "README.md"
    assert guide.is_file(), "init must write input/interviews/README.md"
    text = guide.read_text(encoding="utf-8")
    assert "recorded_on" in text, "the guide must name what the schema requires"
    assert "EC-01" in text, "and why the class carries the weight it does"

    assert "INTERVIEW" not in evidence_classes.observe(set(), app_root)
