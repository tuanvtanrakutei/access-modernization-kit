from __future__ import annotations

import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
MODERNIZE_SCRIPTS = PACKAGE / "modernize" / "scripts"
sys.path.insert(0, str(MODERNIZE_SCRIPTS))

import validate_docs  # noqa: E402


def test_instance_placeholder_examples_and_report_are_ignored(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    report = docs / "validate-docs-report.md"
    (docs / "MASTER_WORKFLOW.md").write_text(
        "Example {{PLACEHOLDER}} and unresolved {{REAL_PROJECT_KEY}}.\n",
        encoding="utf-8",
    )
    report.write_text("Old finding for {{STALE_REPORT_KEY}}.\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_placeholders_in_instance(findings, str(docs), {str(report)})

    assert findings.rows == [
        (
            "MEDIUM",
            "unresolved-placeholder",
            "MASTER_WORKFLOW.md:1",
            "{{REAL_PROJECT_KEY}} was never substituted",
        )
    ]


def test_plugin_templates_resolve_document_references(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    plugin = tmp_path / "plugin"
    docs.mkdir()
    (plugin / "templates").mkdir(parents=True)
    (docs / "FRONTEND_CODING.md").write_text(
        "Use `templates/FRONTEND_API_PATTERNS_TEMPLATE.md` and "
        "`templates/FRONTEND_UI_PATTERNS_TEMPLATE.md`.\n",
        encoding="utf-8",
    )
    for name in ("FRONTEND_API_PATTERNS_TEMPLATE.md", "FRONTEND_UI_PATTERNS_TEMPLATE.md"):
        (plugin / "templates" / name).write_text("template\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_dangling_doc_refs(findings, str(docs), [str(plugin)])

    assert findings.rows == []


def test_issue_citations_scan_code_but_not_markdown(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    source = tmp_path / "source"
    docs.mkdir()
    source.mkdir()
    issues = docs / "Known_Issues.md"
    issues.write_text(
        "| # | Date | Type | Title | Affects | Status | Owner | Decision / Next step |\n"
        "|---|---|---|---|---|---|---|---|\n"
        "| 1 | 2026-08-10 | process | Existing | all | open | — | — |\n",
        encoding="utf-8",
    )
    (source / "Known_Issues_Archive.md").write_text("Example Known_Issues.md #12.\n", encoding="utf-8")
    (source / "validate-docs-report.md").write_text("Old finding Known_Issues.md #13.\n", encoding="utf-8")
    (source / "service.py").write_text("# Known_Issues.md #14\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_issues(findings, str(docs), str(issues), str(source))

    assert findings.rows == [
        (
            "HIGH",
            "dangling-issue-ref",
            "service.py",
            "code cites Known_Issues.md #14 but no such row exists",
        )
    ]


# --- A69: the plugin's own documents against the plugin's own template --------
#
# `FRONTEND_CODING.md` section 15.2 says to run every frontend command through
# `{{PACKAGE_MANAGER}}`, and `templates/PROJECT_CONFIG.md` declared no such row. Every
# project bootstrapped from that template inherited a rule it could not follow, and the
# check that finds it only ran once somebody pointed it at a real project. The two files
# ship together, so they can be checked together here.


def test_the_plugin_docs_only_consume_keys_its_own_template_declares() -> None:
    plugin = PACKAGE / "modernize"
    findings = validate_docs.Findings()
    validate_docs.check_config(
        findings,
        str(plugin / "docs"),
        str(plugin),
        str(plugin / "templates" / "PROJECT_CONFIG.md"),
    )
    missing = [row for row in findings.rows if row[1] == "missing-config-key"]
    assert not missing, missing


# --- A71: a citation qualified by another subsystem is not a broken one -------
#
# A06's backend inherits `auth_client` and `format_bulk_validation_errors` from A01, and
# the comments that explain why they exist cite A01's issue rows. Scanned as if they were
# A06's, they read as two dangling references, and three more came from walking into
# `.claude`, a symlink to the plugin whose own test fixtures cite issue numbers.


def test_a_citation_qualified_by_another_subsystem_is_not_dangling(tmp_path: Path) -> None:
    docs = tmp_path / "docs"
    source = tmp_path / "src"
    docs.mkdir()
    source.mkdir()
    (docs / "Known_Issues.md").write_text("# log\n", encoding="utf-8")
    (source / "conftest.py").write_text(
        "# Inherited from A01 - see A01 Known_Issues.md #41.\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_issues(findings, str(docs), str(docs / "Known_Issues.md"),
                               str(source))

    assert [r for r in findings.rows if r[1] == "dangling-issue-ref"] == []


def test_an_unqualified_citation_with_no_row_is_still_dangling(tmp_path: Path) -> None:
    """The check has to keep working - this is the defect it was written for."""
    docs = tmp_path / "docs"
    source = tmp_path / "src"
    docs.mkdir()
    source.mkdir()
    (docs / "Known_Issues.md").write_text("# log\n", encoding="utf-8")
    (source / "svc.py").write_text("# See Known_Issues.md #41.\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_issues(findings, str(docs), str(docs / "Known_Issues.md"),
                               str(source))

    rows = [r for r in findings.rows if r[1] == "dangling-issue-ref"]
    assert len(rows) == 1 and "#41" in rows[0][3]


def test_the_scan_does_not_walk_into_dot_claude(tmp_path: Path) -> None:
    """`.claude/ak-runtime` is a symlink to the plugin on a real project, and the
    plugin's own tests cite issue numbers that are fixtures."""
    docs = tmp_path / "docs"
    source = tmp_path / "src"
    docs.mkdir()
    (source / ".claude" / "tests").mkdir(parents=True)
    (source / ".claude" / "tests" / "test_x.py").write_text(
        "# See Known_Issues.md #12.\n", encoding="utf-8")
    (docs / "Known_Issues.md").write_text("# log\n", encoding="utf-8")

    findings = validate_docs.Findings()
    validate_docs.check_issues(findings, str(docs), str(docs / "Known_Issues.md"),
                               str(source))

    assert [r for r in findings.rows if r[1] == "dangling-issue-ref"] == []
