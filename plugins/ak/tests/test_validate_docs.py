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
