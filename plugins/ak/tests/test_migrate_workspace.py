"""The layout move, tested on throwaway workspaces before it touches a real one.

The ordering constraint is the whole risk here. `Workspace.is_legacy` is decided by
the absence of `input/`, so the instant `input/` exists the workspace reads as
current - and every accessor starts answering from `input/`, including for content
still sitting in `sources/`. A migration that creates `input/` early does not fail;
it silently makes the sources invisible.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))
sys.path.insert(0, str(PACKAGE / "contracts"))

import migrate_workspace as migrate  # noqa: E402
from workspace import Workspace  # noqa: E402

MANIFEST = """version: '2.2'
app:
  id: A05
artifacts:
- id: DATA
  source_ref:
    type: local_path
    value: sources/access/base.mdb
graphify:
  enabled: true
  mode: standard
  extras:
  - pdf
outputs:
  languages:
  - EN
"""

GITIGNORE = """runs/
graphify-out/
outputs/drafts/
sources/access/*.mdb
!extracted/**
!outputs/*.md
"""


def build(root: Path) -> Path:
    for directory in ("sources/access", "sources/documents", "sources/reports-out",
                      "acquired/staging", "extracted", "decisions", "shared-docs"):
        (root / directory).mkdir(parents=True)
    (root / "sources/access/base.mdb").write_text("db", encoding="utf-8")
    (root / "sources/reports-out/sample.csv").write_text("a,b", encoding="utf-8")
    (root / "extracted/component-index.json").write_text("{}", encoding="utf-8")
    bundle = root / "acquired" / "bundle-abc123"
    bundle.mkdir()
    (bundle / "bundle.json").write_text("{}", encoding="utf-8")
    outputs = root / "runs" / "A05-P1" / "outputs"
    outputs.mkdir(parents=True)
    (outputs / "A05_Phase1_DataUnderstanding_EN.md").write_text("# one", encoding="utf-8")
    (outputs / "A05_Evidence.json").write_text("{}", encoding="utf-8")
    (root / "runs" / "A05-P1" / "run-state.json").write_text("{}", encoding="utf-8")
    (root / "manifest.yaml").write_text(MANIFEST, encoding="utf-8")
    (root / ".gitignore").write_text(GITIGNORE, encoding="utf-8")
    (root / ".graphifyignore").write_text("x\n", encoding="utf-8")
    return root


@pytest.fixture()
def legacy(tmp_path: Path) -> Path:
    return build(tmp_path / "A05")


def test_planning_changes_nothing(legacy: Path) -> None:
    before = sorted(p.relative_to(legacy).as_posix() for p in legacy.rglob("*"))
    migrate.plan(legacy)
    assert sorted(p.relative_to(legacy).as_posix() for p in legacy.rglob("*")) == before


def test_the_move_puts_the_documents_at_the_top(legacy: Path) -> None:
    migrate.apply(legacy, migrate.plan(legacy))
    published = sorted(p.name for p in (legacy / "output").iterdir())
    assert published == ["A05_Evidence.json", "A05_Phase1_DataUnderstanding_EN.md"]


def test_the_run_keeps_its_working_state(legacy: Path) -> None:
    """Only the rendered documents move. Losing the evidence trail would be silent."""
    migrate.apply(legacy, migrate.plan(legacy))
    assert (legacy / ".ak" / "runs" / "A05-P1" / "run-state.json").is_file()


def test_sources_move_and_reports_out_is_renamed(legacy: Path) -> None:
    migrate.apply(legacy, migrate.plan(legacy))
    assert (legacy / "input" / "access" / "base.mdb").is_file()
    assert (legacy / "input" / "report-samples" / "sample.csv").is_file()
    assert not (legacy / "sources").exists()


def test_a_flat_bundle_directory_is_folded_under_bundles(legacy: Path) -> None:
    migrate.apply(legacy, migrate.plan(legacy))
    assert (legacy / ".ak" / "bundles" / "bundle-abc123" / "bundle.json").is_file()


def test_the_workspace_reads_as_current_afterwards(legacy: Path) -> None:
    migrate.apply(legacy, migrate.plan(legacy))
    workspace = Workspace(legacy)
    assert not workspace.is_legacy
    assert workspace.output_dir() == legacy / "output"
    assert workspace.input_dir("access") == legacy / "input" / "access"
    assert workspace.extracted() == legacy / ".ak" / "extracted"


def test_every_accessor_resolves_to_something_that_exists(legacy: Path) -> None:
    """The failure this guards is a move that leaves an accessor pointing at nothing."""
    migrate.apply(legacy, migrate.plan(legacy))
    workspace = Workspace(legacy)
    assert workspace.input_dir("access").is_dir()
    assert workspace.staging_root().is_dir()
    assert workspace.extracted().is_dir()
    assert workspace.run_dir("A05-P1").is_dir()
    assert workspace.output_dir().is_dir()


def test_the_manifest_stops_pointing_at_sources(legacy: Path) -> None:
    migrate.apply(legacy, migrate.plan(legacy))
    text = (legacy / "manifest.yaml").read_text(encoding="utf-8")
    assert "value: input/access/base.mdb" in text
    assert "sources/" not in text


def test_the_graphify_block_goes_and_the_rest_of_the_manifest_stays(legacy: Path) -> None:
    """The schema no longer accepts it, so a manifest carrying it does not validate."""
    migrate.apply(legacy, migrate.plan(legacy))
    text = (legacy / "manifest.yaml").read_text(encoding="utf-8")
    assert "graphify" not in text
    assert "extras" not in text
    assert "outputs:" in text and "- EN" in text
    assert "version: '2.2'" in text


def test_the_migrated_manifest_still_parses(legacy: Path) -> None:
    import yaml

    migrate.apply(legacy, migrate.plan(legacy))
    data = yaml.safe_load((legacy / "manifest.yaml").read_text(encoding="utf-8"))
    assert data["artifacts"][0]["source_ref"]["value"] == "input/access/base.mdb"
    assert "graphify" not in data
    assert data["outputs"]["languages"] == ["EN"]


def test_the_raw_databases_stay_ignored(legacy: Path) -> None:
    """A rewrite that missed this line would put production data in the next commit."""
    migrate.apply(legacy, migrate.plan(legacy))
    text = (legacy / ".gitignore").read_text(encoding="utf-8")
    assert "input/access/*.mdb" in text
    assert "sources/access/*.mdb" not in text
    assert ".ak/" in text and "graphify-out" not in text


def test_the_dead_graphify_policy_file_is_removed(legacy: Path) -> None:
    migrate.apply(legacy, migrate.plan(legacy))
    assert not (legacy / ".graphifyignore").exists()


def test_migrating_twice_is_refused_rather_than_repeated(legacy: Path) -> None:
    migrate.apply(legacy, migrate.plan(legacy))
    second = migrate.plan(legacy)
    assert second["blockers"], "a migrated workspace must not be migrated again"
    assert not second["moves"]


def test_a_workspace_with_no_runs_still_migrates(tmp_path: Path) -> None:
    root = tmp_path / "B01"
    (root / "sources" / "access").mkdir(parents=True)
    (root / "sources" / "access" / "x.mdb").write_text("db", encoding="utf-8")
    migrate.apply(root, migrate.plan(root))
    assert (root / "input" / "access" / "x.mdb").is_file()
    assert not (root / "output").exists()


# --- the half the first version of this script forgot ------------------------
#
# It moved a real workspace and left 66 of 67 evidence items citing paths that no
# longer resolved. Every other check still passed: they all read the register against
# the documents, and none against the filesystem.


def test_cited_paths_are_repointed(legacy: Path) -> None:
    outputs = legacy / "runs" / "A05-P1" / "outputs"
    (outputs / "A05_Evidence.json").write_text(
        '{"items": ['
        '{"id": "X-001", "source_path": "acquired/staging/DB/fresh-01/vba/AutoExec.txt"},'
        '{"id": "X-002", "source_path": "acquired/bundle-abc123/interfaces/linked.json"},'
        '{"id": "X-003", "source_path": "extracted/ui-facts/a.json"},'
        '{"id": "X-004", "source_path": "sources/reports-out/sample.csv"},'
        '{"id": "X-005", "source_path": "acquired/staging"}]}',
        encoding="utf-8",
    )
    migrate.apply(legacy, migrate.plan(legacy))
    import json

    items = json.loads((legacy / "output" / "A05_Evidence.json").read_text(encoding="utf-8"))
    paths = {item["id"]: item["source_path"] for item in items["items"]}
    assert paths["X-001"] == ".ak/staging/DB/fresh-01/vba/AutoExec.txt"
    assert paths["X-002"] == ".ak/bundles/bundle-abc123/interfaces/linked.json"
    assert paths["X-003"] == ".ak/extracted/ui-facts/a.json"
    assert paths["X-004"] == "input/report-samples/sample.csv"
    assert paths["X-005"] == ".ak/staging"


def test_every_repointed_path_actually_exists(legacy: Path) -> None:
    """The point of the rewrite, asserted against the filesystem rather than a string."""
    outputs = legacy / "runs" / "A05-P1" / "outputs"
    (outputs / "A05_Evidence.json").write_text(
        '{"items": ['
        '{"id": "X-001", "source_path": "acquired/bundle-abc123/bundle.json"},'
        '{"id": "X-002", "source_path": "extracted/component-index.json"},'
        '{"id": "X-003", "source_path": "sources/access/base.mdb"},'
        '{"id": "X-004", "source_path": "sources/reports-out/sample.csv"}]}',
        encoding="utf-8",
    )
    migrate.apply(legacy, migrate.plan(legacy))
    import json

    items = json.loads((legacy / "output" / "A05_Evidence.json").read_text(encoding="utf-8"))
    for item in items["items"]:
        assert (legacy / item["source_path"]).exists(), f"{item['id']} -> {item['source_path']}"


def test_a_document_citing_a_path_in_prose_is_repointed_too(legacy: Path) -> None:
    outputs = legacy / "runs" / "A05-P1" / "outputs"
    (outputs / "A05_Phase1_DataUnderstanding_EN.md").write_text(
        "Read from `acquired/staging/DB/fresh-01/schema/tables.json`.\n", encoding="utf-8"
    )
    migrate.apply(legacy, migrate.plan(legacy))
    text = (legacy / "output" / "A05_Phase1_DataUnderstanding_EN.md").read_text(encoding="utf-8")
    assert ".ak/staging/DB/fresh-01/schema/tables.json" in text
    assert "acquired/" not in text


def test_the_rewrite_is_idempotent(legacy: Path) -> None:
    """It must be safe to run on a workspace someone already migrated by hand."""
    migrate.apply(legacy, migrate.plan(legacy))
    before = (legacy / "output" / "A05_Evidence.json").read_text(encoding="utf-8")
    assert migrate.rewrite_published_citations(legacy) == []
    assert (legacy / "output" / "A05_Evidence.json").read_text(encoding="utf-8") == before


def test_a_longer_prefix_is_not_eaten_by_a_shorter_one() -> None:
    assert migrate.rewrite_citation("acquired/bundles/b1/x") == ".ak/bundles/b1/x"
    assert migrate.rewrite_citation("acquired/bundle-abc/x") == ".ak/bundles/bundle-abc/x"
    assert migrate.rewrite_citation("acquired/staging/x") == ".ak/staging/x"
    assert migrate.rewrite_citation("acquired/staging") == ".ak/staging"
