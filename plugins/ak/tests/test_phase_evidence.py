from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
import yaml

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(PACKAGE / "contracts"))
sys.path.insert(0, str(PACKAGE / "scripts"))

import evidence_requirements  # noqa: E402
import evidence_classes
import phase_evidence  # noqa: E402
from classification import Classification  # noqa: E402

PROFILES = PACKAGE / "profiles"
SPLIT = Classification("split_file", "mdb", "full", ("access_file",))


# Readiness said which capability was missing and never what to do about it, so
# "missing:any:trigger_effect_output_trace" was a true statement nobody could act on.
def test_every_capability_a_phase_can_require_names_a_way_to_supply_it() -> None:
    required: set[str] = set()
    for baseline in evidence_requirements.phase_readiness_contract.BASELINE.values():
        required |= set(baseline.get("all", set()))
        required |= set(baseline.get("any", set()))
    for profile in ("topology.yaml", "backend.yaml", "frontend.yaml", "source-availability.yaml"):
        data = yaml.safe_load((PROFILES / profile).read_text(encoding="utf-8")) or {}
        for rule in data.get("rules", []) or []:
            require = rule.get("require", {}) or {}
            required |= set(require.get("all", []) or [])
            required |= set(require.get("any", []) or [])
    undocumented = sorted(required - set(evidence_requirements.SUPPLY))
    assert undocumented == [], f"no supply route documented for: {undocumented}"


def test_requirements_separates_what_is_present_from_what_is_missing() -> None:
    present = {"field_inventory", "key_index_inventory", "boundary_inventory",
               "access_schema_inventory", "backend_authority_declared"}
    report = evidence_requirements.requirements(1, SPLIT, PROFILES, present)
    assert report["status"] == "READY"
    assert {item["capability"] for item in report["satisfied"]} >= {"field_inventory", "boundary_inventory"}
    assert report["missing"] == []

    blocked = evidence_requirements.requirements(4, SPLIT, PROFILES, present)
    assert blocked["status"] == "BLOCKED"
    gap = blocked["missing"][0]
    assert "trigger_effect_output_trace" in gap.get("alternatives", [gap["capability"]])
    # A63 added the analysis route. The two that were here described supplying
    # samples and running the application, and neither could ever produce this
    # capability - so the assertion was protecting an unreachable remedy.
    assert {item["route"] for item in gap["supply"]} == {"files", "analysis", "runtime"}


def _workspace(tmp_path: Path, capabilities: dict[str, list[str]] | None = None) -> Path:
    app = tmp_path / "A99"
    (app / "acquired" / "bundle-abc").mkdir(parents=True)
    (app / "manifest.yaml").write_text(yaml.safe_dump({
        "version": "2.2",
        "app": {"id": "A99", "name_en": "Evidence Test"},
        "project": {"classification": {
            "topology": "split_file", "frontend_format": "mdb",
            "source_availability": "full", "backend_kinds": ["access_file"],
        }},
        "artifacts": [],
    }, sort_keys=False), encoding="utf-8")
    bundle = app / "acquired" / "bundle-abc"
    (bundle / "bundle.json").write_text(json.dumps({"bundle_id": "bundle-abc"}), encoding="utf-8")
    provenance: dict = {"schema_version": "2.7.3", "bundle_id": "bundle-abc", "sources": []}
    if capabilities is not None:
        provenance["capabilities"] = capabilities
    (bundle / "provenance.json").write_text(json.dumps(provenance), encoding="utf-8")
    return app


# The point of persisting capabilities: a later phase must not ask again for evidence
# an earlier one already supplied, and must be able to say where it came from.
def test_evidence_already_supplied_is_not_requested_again(tmp_path: Path) -> None:
    app = _workspace(tmp_path, {
        "field_inventory": ["managed_access"],
        "key_index_inventory": ["managed_access"],
        "boundary_inventory": ["managed_access"],
        "access_schema_inventory": ["imported_sources"],
        "backend_authority_declared": ["manifest"],
    })
    report = phase_evidence.phase_report(app, 1)
    # Every capability the phase asks for is satisfied and nothing is re-requested -
    # which is what this test is for. The status is LIMITED rather than READY because
    # all five capabilities are structural, and structural evidence cannot say what a
    # table is for. This assertion used to read READY, and it was protecting the
    # defect the 2.9.0 audit was opened to fix.
    assert report["missing"] == []
    assert report["status"] == "LIMITED"
    assert any("DOCUMENT" in reason for reason in report["reasons"])
    by_name = {item["capability"]: item["supplied_by"] for item in report["satisfied"]}
    assert by_name["field_inventory"] == "managed_access"
    assert by_name["access_schema_inventory"] == "imported_sources"


def test_a_missing_capability_comes_with_a_runnable_command(tmp_path: Path) -> None:
    app = _workspace(tmp_path, {})
    report = phase_evidence.phase_report(app, 1)
    assert report["status"] == "BLOCKED"
    routes = {item["route"]: item for gap in report["missing"] for item in gap["supply"]}
    assert "acquire run" in " ".join(routes["runtime"]["commands"])
    files = " ".join(routes["files"]["commands"])
    assert "ExportAccessObjects.bas" in files
    assert "import-sources" in files
    # The command has to name this workspace, not a placeholder path.
    assert str(app) in files


# A bundle written before capabilities were recorded still says which phases it
# reached, so its evidence is treated as supplied rather than demanded again.
def test_an_older_bundle_falls_back_to_its_readiness_verdict(tmp_path: Path) -> None:
    app = _workspace(tmp_path, None)
    bundle = app / "acquired" / "bundle-abc"
    (bundle / "phase-readiness.json").write_text(json.dumps({
        "phase1": {"status": "READY", "reasons": [], "rule_ids": []},
    }), encoding="utf-8")
    report = phase_evidence.phase_report(app, 1)
    supplied = {item["capability"]: item["supplied_by"] for item in report["satisfied"]}
    assert "field_inventory" in supplied
    assert "capabilities not recorded" in supplied["field_inventory"]


def test_a_waiver_is_reported_alongside_the_phase_it_unblocked(tmp_path: Path) -> None:
    app = _workspace(tmp_path, {})
    report = phase_evidence.phase_report(app, 4, ("trigger_effect_output_trace",), "no sample files exist")
    assert report["waived"] == [
        {"capability": "trigger_effect_output_trace", "reason": "no sample files exist"}
    ]
    # A waiver clears the capability it names. It does not clear the evidence classes
    # Phase 4 needs, and an empty workspace has none of them - so the phase stays
    # BLOCKED, and the report says which class rather than which capability. A waiver
    # that could wave away a missing class would be a way to declare the analysis
    # possible without the evidence to do it.
    assert report["status"] == "BLOCKED"
    blocking = [entry["class"] for entry in report["evidence"]["blocking"]]
    assert blocking == ["CODE", "UI_DEFINITION"]


# The derivation exists because Graphify's AST pass yields file-level nodes and no
# edges for a query corpus, while the relationships are stated literally in the text.
def test_derived_node_ids_survive_japanese_names() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "derive_graph_facts", PACKAGE / "scripts" / "derive_graph_facts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    # The skill's own id rule normalizes to [a-z0-9_], which erases every character of
    # these three names and merges them into one node.
    names = ["受注データ", "商品マスタ", "店舗マスタ"]
    ids = {module.node_id("table_a05", name) for name in names}
    assert len(ids) == 3, "distinct Japanese names must not collapse onto one id"
    # Deterministic: the same name yields the same id on a later run.
    assert module.node_id("table_a05", names[0]) == module.node_id("table_a05", names[0])
    # Still shaped as Graphify expects, with the digest appended rather than replacing.
    for identifier in ids:
        assert identifier.replace("_", "").isalnum()


def test_distilled_ui_facts_keep_relationships_and_drop_geometry() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "derive_graph_facts", PACKAGE / "scripts" / "derive_graph_facts.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    definition = '\n'.join([
        'Version =20',
        'Begin Report',
        '    RecordSource ="SELECT * FROM 店舗マスタ"',
        '    Begin Section',
        '        Name ="ページヘッダー"',
        '        Begin TextBox',
        '            Top =1410',
        '            ControlSource ="店舗コード"',
        '        End',
        '        Begin OLEUnbound',
        '            OLEClass ="Microsoft ﾊﾞｰｺｰﾄﾞ ｺﾝﾄﾛｰﾙ"',
        '            Class ="BARCODE.BarCodeCtrl.1"',
        '        End',
        '    End',
        'End',
        'Private Sub Report_Open(Cancel As Integer)',
        'End Sub',
    ])
    fact = module.distil_object(definition, "report")
    assert fact["record_source"] == "SELECT * FROM 店舗マスタ"
    assert fact["control_sources"] == ["店舗コード"]
    # OLEClass is the localized caption, not a ProgID; matching it reported a caption
    # as an embedded control.
    assert fact["activex_classes"] == ["BARCODE.BarCodeCtrl.1"]
    assert fact["event_procedures"] == ["Report_Open"]
    # Geometry is what the corpus renounces, and it must not survive distillation.
    assert "1410" not in json.dumps(fact, ensure_ascii=False)


# --- A63: the capability that gated phase 4 and nothing could produce ---------
#
# `missing:any:trigger_effect_output_trace` was permanent. No adapter names it,
# `_declaration_capabilities` yields only `backend_authority_declared`, and the manifest
# has no field for it - so the remedy printed beside it changed nothing when followed.
# A06 supplied one SAMPLE_DATA and fourteen OUTPUT_SAMPLE and stayed BLOCKED.

HEADER = ("run_id,app_id,task_id,workflow_id,step,user_action,screen,vba_event,"
          "processing,data_target,output,evidence_ids\n")


def _trace_workspace(tmp_path, *, samples=True, outputs=True, matrix_rows=()):
    root = tmp_path / "W"
    (root / "output").mkdir(parents=True)
    if samples:
        (root / "input" / "samples").mkdir(parents=True)
        (root / "input" / "samples" / "20260820.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    if outputs:
        (root / "input" / "report-samples").mkdir(parents=True)
        (root / "input" / "report-samples" / "r.csv").write_text("x\n1\n", encoding="utf-8")
    if matrix_rows:
        (root / "output" / "W_TraceabilityMatrix.csv").write_text(
            HEADER + "".join(matrix_rows), encoding="utf-8")
    return root


def test_samples_alone_do_not_establish_the_trace(tmp_path) -> None:
    """The half A06 had. Samples are outputs; nothing in them says which action made
    one, and that is two thirds of what the capability is named for."""
    root = _trace_workspace(tmp_path)
    assert not evidence_classes.trace_capability(
        root, evidence_classes.supplied_inventory(root))


def test_a_matrix_alone_does_not_establish_it_either(tmp_path) -> None:
    root = _trace_workspace(tmp_path, samples=False, outputs=False,
                      matrix_rows=(",,,,,click,F1,Click,import,受注情報,out.csv,E1\n",))
    assert not evidence_classes.trace_capability(
        root, evidence_classes.supplied_inventory(root))


def test_samples_and_a_matrix_row_establish_it(tmp_path) -> None:
    root = _trace_workspace(tmp_path,
                      matrix_rows=(",,,,,click,F1,Click,import,受注情報,out.csv,E1\n",))
    assert evidence_classes.trace_capability(
        root, evidence_classes.supplied_inventory(root))


def test_a_header_with_no_rows_is_not_evidence(tmp_path) -> None:
    root = _trace_workspace(tmp_path)
    (root / "output" / "W_TraceabilityMatrix.csv").write_text(HEADER, encoding="utf-8")
    assert evidence_classes.trace_matrix_rows(root) == 0


def test_a_row_missing_its_target_or_output_does_not_count(tmp_path) -> None:
    """Both columns, because a step that names neither where it wrote nor what it
    produced is a step nobody can trace."""
    root = _trace_workspace(tmp_path, matrix_rows=(
        ",,,,,click,F1,Click,import,受注情報,,E1\n",      # no output
        ",,,,,click,F2,Click,export,,out.csv,E2\n",      # no data target
    ))
    assert evidence_classes.trace_matrix_rows(root) == 0


def test_workflow_id_is_not_required_so_the_gate_is_not_circular(tmp_path) -> None:
    """Phase 4 assigns workflow_id and step. Requiring them would block phase 4 on a
    matrix only phase 4 can complete."""
    root = _trace_workspace(tmp_path,
                      matrix_rows=(",,,,,click,F1,Click,import,受注情報,out.csv,E1\n",))
    assert evidence_classes.trace_matrix_rows(root) == 1
