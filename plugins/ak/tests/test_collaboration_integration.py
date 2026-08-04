from __future__ import annotations

import json
from pathlib import Path

from collaboration import (
    find_collaboration_conflicts,
    integration_order,
    load_work_package,
    project_task,
)
from contract_impact import validate_contract_impact
from review import validate_review_receipt


PACKAGE = Path(__file__).resolve().parents[1]
FIXTURE = PACKAGE / "fixtures" / "collaboration" / "two-contributor"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def packages() -> list[dict]:
    return [
        load_work_package(path)
        for path in sorted(
            (FIXTURE / "collaboration" / "work-packages").glob(
                "*/work-package.json"
            )
        )
    ]


def test_two_contributors_share_authority_and_keep_disjoint_scopes() -> None:
    values = packages()
    assert len(values) == 2
    assert find_collaboration_conflicts(values) == []
    for package in values:
        receipt = load(
            FIXTURE
            / "collaboration"
            / "reviews"
            / f"RR-{package['package_id']}.json"
        )
        validate_review_receipt(package, receipt)
        task = load(
            FIXTURE / "run" / "candidate-tasks" / f"{package['package_id']}.json"
        )
        projected = project_task(package, task)
        assert projected["work_package_id"] == package["package_id"]


def test_dependency_order_is_deterministic() -> None:
    expected = load(FIXTURE / "expected-integration-order.json")
    assert integration_order(packages()) == expected == ["WP_SYN_SQL", "WP_SYN_UI"]


def test_contract_impact_fixture_is_bound_to_a_real_package() -> None:
    package = load_work_package(FIXTURE / "contract-fixture" / "work-package.json")
    impact = load(FIXTURE / "contract-fixture" / "contract-impact.json")
    validate_contract_impact(package, impact, impact["changed_paths"])


def test_fixture_contains_no_prohibited_binary_or_secret() -> None:
    prohibited = {
        ".mdb", ".accdb", ".adp", ".mde", ".accde", ".bak", ".mdf", ".ldf", ".dsn"
    }
    files = [path for path in FIXTURE.rglob("*") if path.is_file()]
    assert not [path for path in files if path.suffix.lower() in prohibited]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    assert "password=" not in text.lower()
    assert "D:\\" not in text
