"""Part 0's output had grown three answers to one question and no rule to choose.

Measured on a real application before this: `sources/` held 587 MB of original
databases, `acquired/staging/_snapshots/` held 615 MB of copies of the same two
files, and the evidence those 1.2 GB existed to produce was about 3 MB of text. The
canonical bundle sat in a directory named by a 64-character SHA-256, and the
distilled screen facts were named by a hash with the object's name only inside the
file.

These tests hold the repaired layout: evidence moves left to right and each step has
one home - snapshots are disposable, staging is what was read out, a bundle is what
was sealed, `extracted/` is what was derived from a bundle.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(PACKAGE / "contracts"))

import bundle as bundle_contract  # noqa: E402
from adapters.base import AcquisitionPlan  # noqa: E402
from adapters.managed_access.adapter import _reclaim_snapshots, _snapshot_dir  # noqa: E402


def _derive_module():
    spec = importlib.util.spec_from_file_location(
        "derive_graph_facts", PACKAGE / "scripts" / "derive_graph_facts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DIGEST = "fcf525d9e67a0fb3e242f8eff100d18ab6afe7963cb3f7e8710a5573a69116c5"
BUNDLE_ID = f"bundle-{DIGEST}"


def make_bundle(root: Path, name: str) -> Path:
    path = root / name
    path.mkdir(parents=True, exist_ok=True)
    (path / "bundle.json").write_text(json.dumps({"bundle_id": BUNDLE_ID}), encoding="utf-8")
    return path


def plan(tmp_path: Path, keep: bool = False) -> AcquisitionPlan:
    return AcquisitionPlan(
        adapter_id="managed_access", adapter_version="1.0.0", planned_artifacts=(),
        acquisition_id="acq-1",
        runtime_output_root=str(tmp_path / "acquired" / "staging"),
        snapshot_root=str(tmp_path / "acquired" / "snapshots"),
        keep_snapshots=keep,
    )


def seed_snapshot(tmp_path: Path, size: int = 4096) -> Path:
    directory = _snapshot_dir(plan(tmp_path))
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "app.mdb").write_bytes(b"x" * size)
    return directory


# --- bundle directory -------------------------------------------------------

def test_the_bundle_directory_is_readable_and_the_id_stays_a_content_address() -> None:
    name = bundle_contract.bundle_dir_name(BUNDLE_ID, date(2026, 8, 26))
    assert name == "2026-08-26-fcf525d9"
    # 71 characters of path per bundle was the cost of using the address as the name.
    assert len(name) < 25


def test_bundle_directories_sort_by_recency_under_their_own_names() -> None:
    older = bundle_contract.bundle_dir_name(BUNDLE_ID, date(2026, 8, 1))
    newer = bundle_contract.bundle_dir_name(BUNDLE_ID, date(2026, 8, 26))
    assert sorted([newer, older]) == [older, newer]


def test_both_layouts_are_found_so_upgrading_does_not_strand_a_workspace(tmp_path: Path) -> None:
    acquired = tmp_path / "acquired"
    make_bundle(acquired / "bundles", "2026-08-26-fcf525d9")
    make_bundle(acquired, BUNDLE_ID)
    found = {path.name for path in bundle_contract.find_bundles(acquired)}
    assert found == {"2026-08-26-fcf525d9", BUNDLE_ID}


def test_a_directory_without_a_bundle_json_is_not_a_bundle(tmp_path: Path) -> None:
    acquired = tmp_path / "acquired"
    (acquired / "bundles" / "2026-08-26-deadbeef").mkdir(parents=True)
    assert bundle_contract.find_bundles(acquired) == []


# --- snapshots --------------------------------------------------------------

def test_snapshots_live_beside_staging_not_inside_it(tmp_path: Path) -> None:
    """They wore a leading underscore to stay out of the database-id namespace.

    A workaround that had become structure, and it also made "delete after a clean
    run" look like deleting part of the evidence.
    """
    directory = _snapshot_dir(plan(tmp_path))
    assert directory == tmp_path / "acquired" / "snapshots" / "acq-1"
    assert "staging" not in directory.parts


def test_a_clean_run_reclaims_the_snapshots(tmp_path: Path) -> None:
    directory = seed_snapshot(tmp_path)
    reclaimed = _reclaim_snapshots(plan(tmp_path), "VALID")
    assert reclaimed == 4096
    assert not directory.exists()


def test_a_run_that_did_not_fully_succeed_keeps_them(tmp_path: Path) -> None:
    """A PARTIAL or BLOCKED run is the one somebody will investigate."""
    for status in ("PARTIAL", "BLOCKED"):
        directory = seed_snapshot(tmp_path)
        assert _reclaim_snapshots(plan(tmp_path), status) == 0
        assert directory.exists()


def test_keep_snapshots_wins_over_a_clean_run(tmp_path: Path) -> None:
    directory = seed_snapshot(tmp_path)
    assert _reclaim_snapshots(plan(tmp_path, keep=True), "VALID") == 0
    assert directory.exists()


def test_reclaiming_is_safe_when_there_is_nothing_there(tmp_path: Path) -> None:
    assert _reclaim_snapshots(plan(tmp_path), "VALID") == 0


def test_a_plan_without_a_snapshot_root_still_writes_inside_the_workspace(tmp_path: Path) -> None:
    """Older callers and hand-built test plans must not land at the filesystem root."""
    legacy = AcquisitionPlan(
        adapter_id="managed_access", adapter_version="1.0.0", planned_artifacts=(),
        acquisition_id="acq-1", runtime_output_root=str(tmp_path / "acquired" / "staging"),
    )
    assert _snapshot_dir(legacy).is_relative_to(tmp_path)


# --- distilled screen facts -------------------------------------------------

def test_a_japanese_object_name_survives_into_its_filename() -> None:
    """The sanitiser this kit already had to fix once, arriving in newer code.

    `re.sub(r"[^A-Za-z0-9_.-]+", "_", name)` turns 各種アイス個数表 into nothing and
    leaves a filename that is a database id and a hash - in a kit whose whole target
    population is Japanese.
    """
    derive = _derive_module()
    assert derive.fact_filename("DATA_1", "各種アイス個数表") == "DATA_1-各種アイス個数表.md"


def test_an_altered_name_always_carries_a_digest_so_it_cannot_silently_collide() -> None:
    derive = _derive_module()
    first = derive.fact_filename("DB", "a/b")
    second = derive.fact_filename("DB", "a:b")
    assert first != second
    assert first.startswith("DB-a_b-") and second.startswith("DB-a_b-")


def test_a_name_needing_no_change_gets_no_digest() -> None:
    derive = _derive_module()
    assert derive.fact_filename("DB", "Order Entry-1.0") == "DB-Order Entry-1.0.md"


def test_every_forbidden_character_is_replaced() -> None:
    derive = _derive_module()
    name = "".join(sorted({'<', '>', ':', '"', '/', '|', '?', '*', chr(92)}))
    produced = derive.fact_filename("DB", name)
    assert not (set(produced) & {'<', '>', '|', '?', '*', chr(92)})
    assert produced.count(":") == 0


def test_a_very_long_name_is_shortened_and_digested() -> None:
    derive = _derive_module()
    produced = derive.fact_filename("DB", "あ" * 300)
    assert len(produced.encode("utf-8")) < 255


# --- reclaiming an existing workspace ---------------------------------------

def _clean_module():
    spec = importlib.util.spec_from_file_location(
        "clean_workspace", PACKAGE / "scripts" / "clean_workspace.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _workspace(tmp_path: Path) -> Path:
    for relative in ("sources/access", "acquired/staging/DB1/acq-1",
                     "acquired/staging/_snapshots", "acquired/bundles/2026-08-26-abcd1234",
                     "graphify-out/corpus", "runs/R1", "decisions"):
        (tmp_path / relative).mkdir(parents=True, exist_ok=True)
    (tmp_path / "sources/access/app.mdb").write_bytes(b"o" * 100)
    (tmp_path / "acquired/staging/DB1/acq-1/forms.txt").write_text("evidence", encoding="utf-8")
    (tmp_path / "acquired/staging/_snapshots/app.mdb").write_bytes(b"c" * 2048)
    (tmp_path / "graphify-out/corpus/x.md").write_text("x", encoding="utf-8")
    return tmp_path


def test_clean_reports_before_it_removes_anything(tmp_path: Path) -> None:
    """The point of the command is that a person sees what is about to go."""
    clean = _clean_module()
    workspace = _workspace(tmp_path)
    found = {entry["path"] for entry in clean.survey(workspace)}
    assert found == {"acquired/staging/_snapshots", "graphify-out"}
    # Surveying changes nothing.
    assert (workspace / "acquired/staging/_snapshots/app.mdb").is_file()


def test_clean_never_touches_the_evidence_or_the_inputs(tmp_path: Path) -> None:
    clean = _clean_module()
    workspace = _workspace(tmp_path)
    sys.argv = ["clean_workspace.py", "--app-root", str(workspace), "--delete"]
    assert clean.main() == 0
    assert (workspace / "sources/access/app.mdb").is_file()
    assert (workspace / "acquired/staging/DB1/acq-1/forms.txt").is_file()
    assert (workspace / "acquired/bundles/2026-08-26-abcd1234").is_dir()
    assert (workspace / "runs/R1").is_dir()
    assert not (workspace / "acquired/staging/_snapshots").exists()
    assert not (workspace / "graphify-out").exists()


def test_every_reclaimable_entry_states_what_would_be_lost() -> None:
    """A delete an operator cannot evaluate is one they will decline or regret."""
    clean = _clean_module()
    for _, what, losing in clean.RECLAIMABLE:
        assert what and losing


def test_the_protected_paths_cover_everything_that_is_not_regenerable() -> None:
    clean = _clean_module()
    assert set(clean.PROTECTED) >= {"sources", "acquired/staging", "acquired/bundles", "runs"}


def test_a_reclaimable_entry_can_never_name_a_protected_path(tmp_path: Path) -> None:
    """The guard exists so a future entry cannot quietly eat the evidence."""
    clean = _clean_module()
    workspace = _workspace(tmp_path)
    for relative in clean.PROTECTED:
        assert clean._is_protected(workspace, workspace / relative)
    assert clean._is_protected(workspace, workspace)
    assert not clean._is_protected(workspace, workspace / "graphify-out")


# --- the resolver: one place knows both layouts -----------------------------

def _space(root: Path):
    from workspace import Workspace

    return Workspace(root)


def _new_layout(tmp_path: Path) -> Path:
    (tmp_path / "input" / "access").mkdir(parents=True)
    return tmp_path


def _old_layout(tmp_path: Path) -> Path:
    (tmp_path / "sources" / "access").mkdir(parents=True)
    return tmp_path


def test_a_new_workspace_puts_what_a_person_reads_at_the_top(tmp_path: Path) -> None:
    """The six documents used to sit two levels down in runs/<run-id>/outputs/.

    An operator met seven directories, four of which they never open, and had to
    know a run id to find the thing they came for.
    """
    space = _space(_new_layout(tmp_path))
    assert space.output_dir() == tmp_path / "output"
    assert space.input_dir("access") == tmp_path / "input" / "access"


def test_the_kit_owned_areas_are_all_under_one_directory(tmp_path: Path) -> None:
    space = _space(_new_layout(tmp_path))
    for name in ("snapshots", "staging", "bundles", "extracted", "runs"):
        assert space.owned(name).parent == tmp_path / ".ak"


def test_a_pre_2_10_workspace_answers_unchanged(tmp_path: Path) -> None:
    """Upgrading the kit must never strand a run in progress."""
    space = _space(_old_layout(tmp_path))
    assert space.is_legacy
    assert space.input_dir("access") == tmp_path / "sources" / "access"
    assert space.input_dir("shared-docs") == tmp_path / "shared-docs"
    assert space.input_dir("decisions") == tmp_path / "decisions"
    assert space.staging_root() == tmp_path / "acquired" / "staging"
    assert space.extracted("ui-facts") == tmp_path / "extracted" / "ui-facts"


def test_a_legacy_output_dir_finds_the_newest_run(tmp_path: Path) -> None:
    root = _old_layout(tmp_path)
    for run_id in ("R1", "R2"):
        (root / "runs" / run_id / "outputs").mkdir(parents=True)
        (root / "runs" / run_id / "outputs" / "x.md").write_text(run_id, encoding="utf-8")
    assert _space(root).output_dir().parent.name in {"R1", "R2"}
    assert _space(root).output_dir(run_id="R1") == root / "runs" / "R1" / "outputs"


def test_a_half_migrated_workspace_reads_as_new(tmp_path: Path) -> None:
    """The safe direction: a stale sources/ left behind cannot shadow input/."""
    (tmp_path / "input").mkdir()
    (tmp_path / "sources").mkdir()
    assert not _space(tmp_path).is_legacy
    assert _space(tmp_path).input_dir("access") == tmp_path / "input" / "access"


def test_bundles_are_found_in_every_layout_this_kit_has_written(tmp_path: Path) -> None:
    from workspace import find_bundle_dirs

    make_bundle(tmp_path / ".ak" / "bundles", "2026-08-28-aaaaaaaa")
    make_bundle(tmp_path / "acquired" / "bundles", "2026-08-26-bbbbbbbb")
    make_bundle(tmp_path / "acquired", BUNDLE_ID)
    (tmp_path / "input").mkdir()
    found = {path.name for path in find_bundle_dirs(_space(tmp_path))}
    assert "2026-08-28-aaaaaaaa" in found


def test_the_input_root_is_where_an_operator_actually_puts_things(tmp_path: Path) -> None:
    assert _space(_new_layout(tmp_path)).input_root().name == "input"
    assert _space(_old_layout(tmp_path / "old")).input_root().name == "sources"


# --- a form and a report may share a name -----------------------------------

def test_a_form_and_a_report_sharing_a_name_are_two_objects() -> None:
    """Access permits it, and the A05 frontend does it four times.

    Keyed on (database, name) alone the second silently replaced the first. Five
    objects never entered the derived corpus, and - worse - four of them were print
    launchers whose `DoCmd.OpenReport` calls were therefore never counted. The
    published reachability figure said 57 objects were referenced by nothing; the
    real number was 37. A collapse in the analysis became a finding about the
    application.
    """
    derive = _derive_module()
    form = derive.fact_filename("FE", "酒アイテム別確認表", "form")
    report = derive.fact_filename("FE", "酒アイテム別確認表", "report")
    assert form != report
    assert "form" in form and "report" in report


def test_the_kind_is_optional_so_older_callers_still_work() -> None:
    derive = _derive_module()
    assert derive.fact_filename("FE", "x") == "FE-x.md"
    assert derive.fact_filename("FE", "x", "form") == "FE-form-x.md"
