from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

from staging import acceptance_state, classify_incoming  # noqa: E402


def test_extension_alone_never_accepts(tmp_path: Path) -> None:
    candidate = tmp_path / "fake.mdb"
    candidate.write_bytes(b"not-access")
    decision = classify_incoming(
        candidate, declared_kind="access_database", signature_ok=False, staging_root=tmp_path
    )
    assert decision.destination == "quarantine"
    assert decision.reason == "SIGNATURE_MISMATCH"


def test_path_escape_quarantines(tmp_path: Path) -> None:
    decision = classify_incoming(
        Path("../../outside.txt"), declared_kind="text_or_csv", signature_ok=True, staging_root=tmp_path
    )
    assert decision.destination == "quarantine"
    assert decision.reason == "PATH_ESCAPE"


def test_missing_provenance_quarantines(tmp_path: Path) -> None:
    candidate = tmp_path / "input.csv"
    candidate.write_text("header", encoding="utf-8")
    decision = classify_incoming(
        candidate, declared_kind="text_or_csv", signature_ok=True,
        staging_root=tmp_path, provenance_ok=False,
    )
    assert decision.reason == "PROVENANCE_MISSING"


def test_acceptance_states_are_rule_based() -> None:
    assert acceptance_state(True, False, [], False) == "VALID"
    assert acceptance_state(True, True, [], False) == "PARTIAL"
    assert acceptance_state(False, True, ["conflict"], False) == "INVALID"
    assert acceptance_state(False, False, [], True) == "BLOCKED"
