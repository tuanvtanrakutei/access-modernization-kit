"""The errata register has a page a person can read, and the page cannot fall behind it (A81).

Phase documents cite `E-nn` as soon as a correction is made (A67), and the register was meant
to be rendered at the head of Phase 6. A project that had not reached Phase 6 had entries cited
across four published phases and nowhere to read them but a JSON file. `$ak errata` renders the
register as `{APP}_Errata.md`; the phase gate fails a page that no longer matches it.

Each test is one way that goes wrong.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import build_errata  # noqa: E402
import errata_render as er  # noqa: E402
import validate_phase_conformance as checker  # noqa: E402

CONTRACT = PACKAGE / "specifications" / "errata-contract.yaml"


def errata(ident: str, severity: str = "MEDIUM", **extra: object) -> dict:
    return {
        "id": ident, "severity": severity, "phase": 3, "cause": "EVIDENCE_MISREAD",
        "original": "The import overwrites the quantities staff typed.",
        "corrected": "The import adds to the ordered quantity and never writes the prepared one.",
        "affected": ["A99_Phase1_DataUnderstanding_{EN,VI}.md RD-05"],
        "source": "A99-P3-CODE-001", "created_at": "2026-01-01T00:00:00+00:00", **extra,
    }


def workspace(tmp_path: Path, entries: list[dict] | None) -> Path:
    root = tmp_path / "A99"
    out = root / "output"
    out.mkdir(parents=True)
    (root / "input").mkdir()
    if entries is not None:
        (out / "A99_Errata.json").write_text(
            json.dumps({"app_id": "A99", "entries": entries}, ensure_ascii=False), encoding="utf-8")
    return root


def run(monkeypatch: pytest.MonkeyPatch, root: Path, *args: str) -> int:
    monkeypatch.setattr(sys, "argv", ["build_errata.py", "--app-root", str(root), *args])
    return build_errata.main()


def test_every_cause_the_contract_defines_has_a_meaning_to_print() -> None:
    causes = er.load_causes(CONTRACT)
    assert {"EVIDENCE_ABSENT", "EVIDENCE_MISREAD", "INFERRED_AS_FACT", "DESCRIBED_NOT_COUNTED",
            "SCOPE_WRONG", "STALE"} <= set(causes)
    assert all(causes.values())


def test_entries_read_in_id_order_and_the_glance_puts_the_worst_first() -> None:
    entries = [errata("E-10", "LOW"), errata("E-2", "HIGH"), errata("E-1", "MEDIUM")]
    text = er.render(entries, "A99", er.load_causes(CONTRACT))
    # E-10 after E-2: numeric order, not string order.
    assert text.index("### E-1\n") < text.index("### E-2\n") < text.index("### E-10\n")
    glance = text[text.index("## At a glance"):text.index("## Entries")]
    assert glance.index("[E-2]") < glance.index("[E-1]") < glance.index("[E-10]")
    assert "3 correction(s): 1 HIGH, 1 MEDIUM, 1 LOW" in glance
    # Only the causes used are explained.
    assert "`EVIDENCE_MISREAD`" in glance and "`STALE`" not in glance


def test_the_page_carries_what_a_reader_needs_to_audit_the_correction() -> None:
    text = er.render([errata("E-01", superseded_evidence_ids=["A99-P1-INTERVIEW-001"],
                             note="An operator sees the row appear.")], "A99")
    for part in ("**Was said.** The import overwrites", "**Is true.** The import adds",
                 "- A99_Phase1_DataUnderstanding_{EN,VI}.md RD-05", "`A99-P3-CODE-001`",
                 "`A99-P1-INTERVIEW-001`", "**Note.** An operator"):
        assert part in text


def test_the_same_register_gives_the_same_bytes() -> None:
    entries = [errata("E-02"), errata("E-01", "HIGH")]
    assert er.render(entries, "A99") == er.render(list(reversed(entries)), "A99")
    assert "2026" not in er.render(entries, "A99").split("## Entries")[0]


def test_an_empty_register_says_nothing_was_corrected() -> None:
    text = er.render([], "A99")
    assert "No claim published by any phase has been superseded." in text
    assert "## Entries" not in text


def test_a_pipe_in_a_cause_does_not_break_the_glance_table() -> None:
    text = er.render([errata("E-01", cause="A|B")], "A99")
    assert "A\\|B" in text


def test_an_entry_that_cannot_be_audited_is_named() -> None:
    entries = [errata("E-01", affected=[], source=""), errata("E-01"), errata("E-02", cause="GUESS"),
               errata("X-03")]
    found = er.problems(entries, er.load_causes(CONTRACT))
    assert "E-01 has no affected, source" in found
    assert "E-01 appears more than once" in found
    assert any("E-02 names cause GUESS" in p for p in found)
    assert "X-03 is not an E-nn identifier" in found


def test_the_command_writes_the_page_once_and_then_leaves_it(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    root = workspace(tmp_path, [errata("E-01")])
    assert run(monkeypatch, root) == 0
    page = root / "output" / "A99_Errata.md"
    assert page.read_text(encoding="utf-8").startswith(er.GENERATED)
    assert "\r\n" not in page.read_bytes().decode("utf-8")
    assert run(monkeypatch, root) == 0
    assert "unchanged" in capsys.readouterr().out


def test_a_dry_run_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = workspace(tmp_path, [errata("E-01")])
    assert run(monkeypatch, root, "--dry-run") == 0
    assert not (root / "output" / "A99_Errata.md").exists()


def test_no_register_means_no_page(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """An absent register and an empty one read differently; only the empty one gets a page."""
    root = workspace(tmp_path, None)
    assert run(monkeypatch, root) == 0
    assert not (root / "output" / "A99_Errata.md").exists()


def test_a_page_a_person_wrote_is_not_overwritten(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = workspace(tmp_path, [errata("E-01")])
    page = root / "output" / "A99_Errata.md"
    page.write_text("# Our errata\n", encoding="utf-8")
    assert run(monkeypatch, root) == 2
    assert page.read_text(encoding="utf-8") == "# Our errata\n"
    assert run(monkeypatch, root, "--replace-handwritten") == 0
    assert page.read_text(encoding="utf-8").startswith(er.GENERATED)


def test_an_unauditable_entry_fails_the_command_and_still_renders(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = workspace(tmp_path, [errata("E-01", source="")])
    assert run(monkeypatch, root) == 1
    assert (root / "output" / "A99_Errata.md").is_file()


def test_the_gate_holds_the_page_to_its_register(
        tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = workspace(tmp_path, [errata("E-01")])
    out = root / "output"
    assert checker._errata_page(out) == ("missing", "A99_Errata.md")
    assert run(monkeypatch, root) == 0
    assert checker._errata_page(out) == ("current", "A99_Errata.md")
    register = json.loads((out / "A99_Errata.json").read_text(encoding="utf-8"))
    register["entries"].append(errata("E-02"))
    (out / "A99_Errata.json").write_text(json.dumps(register), encoding="utf-8")
    assert checker._errata_page(out) == ("stale", "A99_Errata.md")


def test_the_gate_asks_for_no_page_without_a_register(tmp_path: Path) -> None:
    assert checker._errata_page(workspace(tmp_path, None) / "output") is None
