"""The output templates must carry the structure the contract promises.

The two derived views were 21 and 23 lines - a heading, a placeholder, and a
gradient - against a reference set whose Boundary Map carries a touchpoint
inventory and a detail panel, and whose E2E Trace shows, per step, which rows
appeared and which went away. The two most-shown deliverables were the two least
specified, and a renderer given a stub produces a stub.

These tests check the structure is present and that the contract and the templates
agree, so the gap cannot silently reopen.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

PACKAGE = Path(__file__).resolve().parents[1]
TEMPLATES = PACKAGE / "templates"


def read(name: str) -> str:
    return (TEMPLATES / name).read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def contract() -> dict:
    return yaml.safe_load((PACKAGE / "specifications" / "output-contract.yaml").read_text(encoding="utf-8"))


# --- boundary map -----------------------------------------------------------

def test_boundary_map_has_every_zone_a_boundary_needs() -> None:
    html = read("boundary-map.html")
    for zone in ("upstream", "inputs", "core", "outputs", "downstream"):
        assert f'class="zone {zone}"' in html, f"boundary map has no {zone} zone"


def test_boundary_map_carries_a_touchpoint_inventory_with_direction_and_evidence() -> None:
    html = read("boundary-map.html")
    assert "{{TOUCHPOINT_ROWS}}" in html
    for header in ("Touchpoint", "Direction", "Mechanism", "Counterparty", "Evidence"):
        assert f">{header}" in html, f"touchpoint table has no {header} column"
    for direction in ("dir-in", "dir-out", "dir-share"):
        assert direction in html, f"no styling for {direction}; direction is not expressible"


def test_boundary_map_nodes_open_a_detail_panel() -> None:
    html = read("boundary-map.html")
    assert 'id="detail"' in html
    assert "function show(" in html
    assert "{{DETAIL_MAP}}" in html


# An empty Inputs column and an unanalysed Inputs column look identical on screen
# and mean opposite things.
def test_boundary_map_tells_the_renderer_never_to_leave_a_zone_silently_empty() -> None:
    html = read("boundary-map.html")
    assert "none established" in html
    assert ".empty" in html, "no style for an explicit empty state"


# --- e2e trace --------------------------------------------------------------

def test_e2e_trace_shows_row_level_change_not_just_step_names() -> None:
    html = read("e2e-trace.html")
    for marker in ("row-new", "row-upd", "row-del", "row-unc"):
        assert marker in html, f"no {marker} styling; the trace cannot show what changed"
    assert "renderTables" in html
    assert "no rows affected" in html, "a step that changed nothing must say so"


def test_e2e_trace_marks_steps_that_happen_outside_the_application() -> None:
    """The reference set described an upstream batch as the application's own work.

    Correcting it needed an errata entry. The template must make the boundary a
    first-class thing a renderer has to fill in, not a nuance it may forget.
    """
    html = read("e2e-trace.html")
    assert "isExternal" in html
    assert "step.external" in html
    assert "Outside" in html


def test_e2e_trace_requires_evidence_per_step() -> None:
    html = read("e2e-trace.html")
    assert "s.evidence" in html
    assert "not traced" in html, "a step with no evidence must be labelled, not rendered as fact"


def test_e2e_trace_has_a_timeline_and_a_detail_pane() -> None:
    html = read("e2e-trace.html")
    assert 'class="timeline"' in html and 'id="content"' in html
    assert "function select(" in html
    assert "{{STEPS_JSON}}" in html


def test_e2e_trace_warns_against_passing_off_illustrative_values_as_measured() -> None:
    html = read("e2e-trace.html")
    assert "illustrative" in html


# --- readme -----------------------------------------------------------------

def test_readme_sends_the_reader_to_the_errata_first() -> None:
    text = read("readme.md")
    assert "errata" in text.lower()
    assert "Start at Phase 6" in text


def test_readme_explains_every_identifier_namespace() -> None:
    text = read("readme.md")
    scheme = yaml.safe_load((PACKAGE / "specifications" / "identifier-scheme.yaml").read_text(encoding="utf-8"))
    for namespace in scheme["namespaces"]:
        # The four risk namespaces are introduced together as `RD/RA/RW/RS-nn`, which
        # reads better than four near-identical rows, so a separator counts too.
        assert re.search(rf"{re.escape(namespace)}[-{{/0-9]", text), (
            f"README does not explain {namespace}"
        )


def test_readme_states_the_rule_that_meaning_needs_a_document_or_an_interview() -> None:
    text = read("readme.md")
    assert "document, an interview" in text
    assert "No volume of schema or code substitutes" in text


def test_readme_states_the_naming_rule() -> None:
    text = read("readme.md")
    assert "production names" in text
    assert "never substitute one for the real name" in text


# --- contract agreement -----------------------------------------------------

def test_every_derived_output_the_contract_declares_has_a_template(contract: dict) -> None:
    templates = {
        "{APP_ID}_BoundaryMap.html": "boundary-map.html",
        "{APP_ID}_E2ETrace.html": "e2e-trace.html",
    }
    for output in contract["derived_outputs"]:
        name = output["name"].replace("_{LANG}", "")
        if name in templates:
            assert (TEMPLATES / templates[name]).is_file(), f"{name} has no template"


def test_readme_is_a_required_control_output(contract: dict) -> None:
    assert "README.md" in contract["required_control_outputs"]


def test_every_phase_declares_a_required_diagram(contract: dict) -> None:
    diagrams = contract["required_diagrams"]
    for phase in (f"phase{n}" for n in range(1, 7)):
        assert diagrams.get(phase), f"{phase} requires no diagram"
    assert diagrams["format"] == "mermaid, rendered inline"


def test_phase6_requires_the_sections_a_synthesis_is_for(contract: dict) -> None:
    sections = contract["phase6_required_sections"]
    # Consolidation, correction and hand-off - the three the template omitted.
    for section in ("Errata", "Recommendations & Migration Roadmap",
                    "Appendix A - Cross-Reference Index", "Appendix B - Glossary"):
        assert section in sections, f"Phase 6 does not require {section}"


def test_phase5_requires_the_landscape_half_it_used_to_omit(contract: dict) -> None:
    sections = contract["phase5_required_sections"]
    for section in ("Organization and Stakeholders", "System Landscape",
                    "Network Architecture", "Inter-System Data Interfaces"):
        assert section in sections, f"Phase 5 does not require {section}"


def test_the_header_every_phase_document_opens_with_is_specified(contract: dict) -> None:
    blocks = {block["block"] for block in contract["required_document_header"]}
    assert blocks == {"naming_convention", "source_coverage"}
