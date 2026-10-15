"""The registry seeder reading a five-phase workspace that has no run-state.json.

The first project bootstrapped from a phase-by-phase workspace stopped at Step 3 with
"run-state.json not found", and its registry was typed by hand from the Phase 2 prose.
Everything the registry needs was already in the workspace's registers; these tests build
a small workspace of that shape and read it back.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "modernize" / "scripts"))

import scan_phase2_inventory as scanner  # noqa: E402
import workspace_inventory  # noqa: E402

TEMPLATE_REGISTRY = PACKAGE / "modernize" / "templates" / "Screens_Registry.md"

FORMS = ["Menu", "Orders", "OrderLines", "OldOrders", "Errors", "Stores"]
REPORTS = ["OrderList", "ErrorList", "Orphan"]


def make_workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "output" / "registers").mkdir(parents=True)
    (ws / ".ak" / "extracted").mkdir(parents=True)
    (ws / "input" / "target-intent").mkdir(parents=True)
    (ws / "manifest.yaml").write_text("app:\n  id: A99\n", encoding="utf-8")
    (ws / "output" / "A99_Phase2_ScreenAnalysis_EN.md").write_text(
        "# A99\n\n## 1. Screen, Form, and Report Inventory\n\n### 1.3 Entry points\n\n"
        "| ID | Object | Type | Business purpose | Entry path | Evidence |\n"
        "|---|---|---|---|---|---|\n| F-001 | `Menu` | form | menu | startup | E1 |\n\n## 2. Next\n",
        encoding="utf-8")
    ids = ["Menu", "Orders", "OrderLines", "OldOrders", "Errors", "Stores",
           "OrderList", "ErrorList", "Orphan"]
    (ws / "output" / "registers" / "A99_Identifiers.json").write_text(json.dumps({"entries": [
        {"id": f"F-{i:03d}", "namespace": "F-", "title": name} for i, name in enumerate(ids, 1)
    ]}), encoding="utf-8")
    nodes = [{"id": f"form_{n.lower()}", "label": n} for n in FORMS]
    nodes += [{"id": f"report_{n.lower()}", "label": n} for n in REPORTS]

    def edge(src, dst):
        return {"source": src, "target": dst, "relation": "references"}

    edges = [edge("form_menu", "form_orders"), edge("form_menu", "form_errors"),
             edge("form_menu", "form_stores"), edge("form_orders", "form_orderlines"),
             edge("form_orderlines", "report_orderlist"), edge("form_errors", "report_errorlist")]
    (ws / ".ak" / "extracted" / "derived-extraction.json").write_text(
        json.dumps({"nodes": nodes, "edges": edges}), encoding="utf-8")
    (ws / "output" / "registers" / "A99_ScreenModel.json").write_text(json.dumps({"screens": [
        {"id": "F-002", "name": "Orders", "controls": [
            {"name": "sub", "kind": "subform", "style": {"SourceObject": "Form.OrderLines"}}]},
    ]}), encoding="utf-8")
    (ws / "input" / "target-intent" / "scope.md").write_text(
        "| Object | Kind | In the replacement |\n|---|---|---|\n"
        "| Errors (F-005) | form | out of scope |\n| ErrorList (F-008) | report | out of scope |\n",
        encoding="utf-8")
    return ws


@pytest.fixture
def conforming(monkeypatch):
    monkeypatch.setattr(workspace_inventory, "conformance_gate", lambda root, doc: ("CONFORMS", ""))


def test_a_workspace_sorts_its_objects_into_active_future_and_excluded(tmp_path, conforming):
    found = workspace_inventory.inventory(str(make_workspace(tmp_path)))

    assert [r["object"] for r in found["active"]] == ["Menu", "Orders", "Stores"]
    assert [r["object"] for r in found["future"]] == ["OldOrders", "Orphan"]
    assert sorted(r["object"] for r in found["excluded"]) == ["ErrorList", "Errors"]
    orders = found["active"][1]
    assert orders["embeds"] == ["F-003 OrderLines"]
    assert orders["prints"] == ["F-007 OrderList"]
    assert found["entry_points"] == ["Menu"]


def test_a_workspace_whose_phase2_does_not_conform_is_not_seeded(tmp_path, monkeypatch):
    ws = make_workspace(tmp_path)
    monkeypatch.setattr(workspace_inventory, "conformance_gate", lambda root, doc: ("FAILS", "diagram_present"))
    monkeypatch.setattr(sys, "argv", ["scan", "--ak-run-dir", str(ws), "--out", str(tmp_path / "p.json")])

    assert scanner.main() == 1
    assert not (tmp_path / "p.json").exists()


def test_the_seeder_writes_the_registry_with_modules_the_config_names(tmp_path, monkeypatch, conforming):
    ws = make_workspace(tmp_path)
    config = tmp_path / "PROJECT_CONFIG.md"
    config.write_text(
        "| `FE_ROUTE_BASE` | `/a99` | x |\n\n### Modules\n\n| module | url prefix | owns |\n|---|---|---|\n"
        "| `orders` | `orders/` | WF-003 imports; Menu, Orders (F-002) |\n"
        "| `master` | `master/` | Stores |\n\n### Shared Backend Components\n", encoding="utf-8")
    registry = tmp_path / "Screens_Registry.md"
    registry.write_text(TEMPLATE_REGISTRY.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "scan", "--ak-run-dir", str(ws), "--screen-key-case", "kebab-case",
        "--project-config", str(config), "--out", str(tmp_path / "p.json"),
        "--write-registry", str(registry)])

    assert scanner.main() == 0
    text = registry.read_text(encoding="utf-8")
    assert "| 1 | `Menu` | `menu` | `menu` | `orders` | `orders/` | `/a99/menu` | `not_started` | `not_started` |" in text
    assert "| 3 | `Stores` | `stores` | `stores` | `master` | `master/` |" in text
    assert "| 1 | `OldOrders` | `old-orders` | `UNASSIGNED` |" in text
    assert "{{SCREEN_1}}" not in text
    proposal = json.loads((tmp_path / "p.json").read_text(encoding="utf-8"))
    assert [r["object"] for r in proposal["excluded"]] == ["Errors", "ErrorList"]


def test_an_id_inside_a_longer_token_does_not_name_a_module():
    modules = [("orders", "orders/", "WF-002 and WF-003")]

    assert scanner.named_module(["Orders", "F-002"], modules) is None
    assert scanner.named_module(["Orders", "F-002"], [("orders", "orders/", "screens F-002, F-004")]) == ("orders", "orders/")


def test_the_writer_refuses_a_registry_someone_has_edited(tmp_path, monkeypatch, conforming):
    ws = make_workspace(tmp_path)
    registry = tmp_path / "Screens_Registry.md"
    edited = TEMPLATE_REGISTRY.read_text(encoding="utf-8").replace("`{{SCREEN_1}}`", "`Hand typed`")
    registry.write_text(edited, encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["scan", "--ak-run-dir", str(ws), "--out", str(tmp_path / "p.json"),
                                      "--write-registry", str(registry)])

    assert scanner.main() == 2
    assert registry.read_text(encoding="utf-8") == edited
