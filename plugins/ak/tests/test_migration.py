from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

from migration import propose_migration  # noqa: E402


def test_migration_proposes_without_rewriting() -> None:
    source = PACKAGE / "references" / "manifest.example.yaml"
    before = source.read_bytes()
    report = propose_migration(source)
    assert source.read_bytes() == before
    assert report["source_version"] == "2.1"
    assert "candidate_classification" in report
    assert isinstance(report["mapped_artifacts"], list)
    assert report["required_bundle_rebuild"] is True
    # The proposal no longer promises a graph rebuild: there is no managed runtime to
    # rebuild, and derivation runs from the bundle the same proposal already requires.
    assert "required_graphify_rebuild" not in report
