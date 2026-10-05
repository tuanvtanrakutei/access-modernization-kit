"""`$ak glossary` rewrites the name sections and leaves the person's own sections alone.

The file is shared: the kit proposes names, a person accepts them and adds vocabulary
under `terms:`. The command rewrote the whole file from the name sections, so the next
run deleted every term a person had declared, with the comments saying why.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import build_glossary  # noqa: E402

GLOSSARY = """\
# header written by the kit

tables:
  "受注データ": {en: "order_data", status: "accepted", provenance: "analysis", covered: 1.0}

# Place names this project uses. Proper nouns: romanised, never translated.
terms:
  # Declared after an interview with the warehouse team.
  "本町": {en: "honmachi", status: "accepted", source: "User declaration, 2026-10-05"}
  "西口": {en: "nishiguchi", status: "accepted", source: "User declaration, 2026-10-05"}

notes:
  reviewed_by: "the decider"
"""


def workspace(tmp_path: Path, glossary: str | None = GLOSSARY) -> Path:
    (tmp_path / "input" / "decisions").mkdir(parents=True)
    bundle = tmp_path / ".ak" / "bundles" / "2026-10-05-00000000"
    (bundle / "databases").mkdir(parents=True)
    (bundle / "bundle.json").write_text("{}", encoding="utf-8")
    (bundle / "databases" / "tables.json").write_text(
        json.dumps([{"name": "受注データ"}, {"name": "本町出荷データ"}]), encoding="utf-8")
    if glossary is not None:
        (tmp_path / "input" / "decisions" / "glossary.yaml").write_text(glossary, encoding="utf-8")
    return tmp_path


def run(root: Path, *extra: str) -> int:
    argv = sys.argv
    sys.argv = ["build_glossary.py", "--app-root", str(root), *extra]
    try:
        return build_glossary.main()
    finally:
        sys.argv = argv


def test_a_terms_section_survives_a_rewrite(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    assert run(root) == 0
    text = (root / "input" / "decisions" / "glossary.yaml").read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    assert data["terms"]["本町"]["en"] == "honmachi"
    assert data["terms"]["西口"]["status"] == "accepted"
    assert data["notes"] == {"reviewed_by": "the decider"}
    assert "# Place names this project uses." in text
    assert "# Declared after an interview with the warehouse team." in text


def test_the_declared_terms_still_compose_the_new_names(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    run(root)
    data = yaml.safe_load(
        (root / "input" / "decisions" / "glossary.yaml").read_text(encoding="utf-8"))
    assert data["tables"]["本町出荷データ"]["en"].startswith("honmachi_")
    assert data["tables"]["受注データ"]["status"] == "accepted"


def test_a_second_run_changes_nothing(tmp_path: Path) -> None:
    root = workspace(tmp_path)
    run(root)
    path = root / "input" / "decisions" / "glossary.yaml"
    first = path.read_bytes()
    run(root)
    assert path.read_bytes() == first


def test_a_term_that_is_also_a_name_does_not_replace_the_name(tmp_path: Path) -> None:
    """Reading `terms:` as names let a term overwrite the name of the same spelling."""
    glossary = GLOSSARY.replace('"西口"', '"受注データ"')
    root = workspace(tmp_path, glossary)
    run(root)
    data = yaml.safe_load(
        (root / "input" / "decisions" / "glossary.yaml").read_text(encoding="utf-8"))
    assert data["tables"]["受注データ"] == {
        "en": "order_data", "status": "accepted", "provenance": "analysis", "covered": 1.0}


def test_a_first_run_has_nothing_of_its_own_to_keep(tmp_path: Path) -> None:
    root = workspace(tmp_path, glossary=None)
    assert run(root) == 0
    data = yaml.safe_load(
        (root / "input" / "decisions" / "glossary.yaml").read_text(encoding="utf-8"))
    assert set(data) == {"tables"}


def test_a_new_name_spelt_like_an_accepted_term_takes_that_decision(tmp_path: Path) -> None:
    """A column called `本町` after `本町: honmachi` was accepted needs no second decision."""
    root = workspace(tmp_path)
    tables = root / ".ak" / "bundles" / "2026-10-05-00000000" / "databases" / "tables.json"
    tables.write_text(json.dumps([{"name": "受注データ"}, {"name": "本町"}]), encoding="utf-8")
    run(root)
    data = yaml.safe_load(
        (root / "input" / "decisions" / "glossary.yaml").read_text(encoding="utf-8"))
    assert data["tables"]["本町"]["en"] == "honmachi"
    assert data["tables"]["本町"]["status"] == "accepted"
