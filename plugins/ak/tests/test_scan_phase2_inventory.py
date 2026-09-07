"""The registry seeder, run against the document the kit actually ships.

`LEGACY_EVIDENCE.md` 6.2 records the last defect in this script: it matched a phase
document by `startswith("phase2")`, which only ever matches this plugin's own template
filename and never a real run's `{APP_ID}_Phase2_ScreenAnalysis_{LANG}.md`. It was
caught by renaming a self-test fixture to the real convention.

The same shape was still here, one layer in. Section 1 of the shipped template opens
with a totals table under `### 1.1` and carries the object rows under `### 1.2`;
`NEXT_HEADING_RE` breaks on `#` and `##` only, so both tables sit in one extracted
block, and the seeder read the first line of that block as the header of everything.
Against the kit's own template - the document a first run supplies - it exited 2 with
"inventory table missing required column(s): ['object']".

There were no tests for this script at all. These run it as a process, against the
template, the way bootstrap-project does.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
SCANNER = PACKAGE / "modernize" / "scripts" / "scan_phase2_inventory.py"
TEMPLATE = PACKAGE / "templates" / "phase2-screen-analysis.md"

# The filename the real output contract declares, not the template's own name.
PUBLISHED_NAME = "A05_Phase2_ScreenAnalysis_EN.md"
ENTRY_TABLE_HEADER = (
    "| ID | Object | Type | Business purpose | Entry path | Evidence |\n"
    "|---|---|---|---|---|---|\n"
)


def make_run(tmp_path: Path, extra_rows: str = "", gate: str = "PUBLISHED") -> Path:
    run = tmp_path / "run"
    run.mkdir()
    (run / "run-state.json").write_text(
        json.dumps({"phase_gates": {"phase2": gate}}), encoding="utf-8")
    document = TEMPLATE.read_text(encoding="utf-8")
    if extra_rows:
        assert ENTRY_TABLE_HEADER in document, (
            "the template's entry-point table header changed; this fixture inserts "
            "rows under it and has to be updated with it")
        document = document.replace(
            ENTRY_TABLE_HEADER, ENTRY_TABLE_HEADER + extra_rows, 1)
    (run / PUBLISHED_NAME).write_text(document, encoding="utf-8")
    return run


def scan(run: Path) -> tuple[int, dict | None, str]:
    out = run / "proposal.json"
    result = subprocess.run(
        [sys.executable, str(SCANNER), "--ak-run-dir", str(run), "--out", str(out)],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    payload = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else None
    return result.returncode, payload, result.stdout + result.stderr


def test_the_shipped_template_is_readable(tmp_path: Path) -> None:
    """Exit 2 means "could not run". The kit's own template must not produce it."""
    code, payload, output = scan(make_run(tmp_path))
    assert code == 0, output
    assert payload is not None and payload["row_count"] == 0, payload
    # An empty table is not a missing one: the template ships the shape, not the rows.
    assert "missing required column" not in output


def test_the_totals_table_is_not_mistaken_for_the_inventory(tmp_path: Path) -> None:
    """Section 1's first table counts forms and reports; it has no `Object` column.

    Selecting by position picks it. Selecting by the columns the seeder needs does not,
    and this asserts the difference rather than the fix's shape - a later refactor is
    free to find the table another way.
    """
    code, payload, output = scan(make_run(
        tmp_path,
        "| F-01 | 受注一覧 | Form | Lists the day's orders | Main menu | E-01 |\n",
    ))
    assert code == 0, output
    assert payload["row_count"] == 1, payload
    assert payload["rows"][0]["screen"] == "受注一覧"


def test_a_japanese_name_falls_back_to_the_row_id_and_ascii_does_not(
    tmp_path: Path,
) -> None:
    """Both paths through `screen_key`, on one document.

    The fallback keys off the inventory's own ID, which is unique per row, so two
    Japanese screens cannot collide. An ASCII name is slugified instead, splitting
    word boundaries because legacy Access names routinely have no separator.
    """
    code, payload, output = scan(make_run(
        tmp_path,
        "| F-01 | 受注一覧 | Form | Lists the day's orders | Main menu | E-01 |\n"
        "| F-02 | OrderEntryForm | Form | Captures one order | F-01 button | E-02 |\n",
    ))
    assert code == 0, output
    keys = {row["screen"]: row["screen_key"] for row in payload["rows"]}
    assert keys == {"受注一覧": "screen_F01", "OrderEntryForm": "order_entry_form"}
    assert len(set(keys.values())) == 2


def test_an_unpublished_gate_stops_before_reading_anything(tmp_path: Path) -> None:
    """Exit 1 is "nothing safe to seed from yet", which is not a failure to run."""
    code, _payload, output = scan(make_run(tmp_path, gate="PENDING"))
    assert code == 1, output
    assert "PUBLISHED" in output
