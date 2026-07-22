#!/usr/bin/env python3
"""Validate V2.2 plugin package contracts and an optional app manifest without analysis."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


REQUIRED_FILES = (
    "requirements-dev.txt", ".codex-plugin/plugin.json", "skills/ak/SKILL.md", "skills/ak/agents/openai.yaml", "adapters/adapter-map.json",
    "specifications/package.json", "specifications/runtime-capabilities.yaml", "specifications/language-support.yaml",
    "specifications/senior-system-analyst-instruction.md", "specifications/evidence-policy.yaml", "specifications/output-contract.yaml",
    "specifications/input-preconditions.md",
    "schemas/manifest.schema.json", "schemas/evidence.schema.json", "schemas/traceability-row.schema.json", "schemas/task.schema.json",
    "schemas/handoff.schema.json", "schemas/conflict.schema.json", "schemas/run-state.schema.json", "schemas/source-inventory.schema.json",
    "schemas/access-extraction.schema.json", "schemas/component-index.schema.json", "schemas/module-tree.schema.json",
    "schemas/processing-order.schema.json", "schemas/compilation-database.schema.json",
    "orchestration/roles.json", "orchestration/waves.json", "orchestration/merge-policy.json", "orchestration/conflict-policy.json", "orchestration/runtime-adapters.json",
    "references/manifest.example.yaml", "references/agent-compatibility.md", "references/presentation-guidance.md", "references/orchestration-guide.md",
    "references/capability-matrix.md", "references/access-extraction-guide.md", "references/module-and-build-context.md",
    "templates/phase1-data-understanding.md", "templates/phase2-screen-analysis.md", "templates/phase3-logic-processing.md",
    "templates/phase4-workflow-reconstruction.md", "templates/phase5-document-integration.md", "templates/phase6-synthesis.md",
    "templates/question-list.md", "templates/qa-report.md", "templates/traceability-matrix.csv", "templates/e2e-trace.html",
    "templates/recommended-optional-evidence.md",
    "templates/boundary-map.html", "templates/presentation-storyboard.md", "templates/task-envelope.json", "templates/agent-handoff.json",
    "templates/conflict-record.json", "templates/worker-prompt.md", "templates/app.gitignore", "templates/app.graphifyignore", "templates/app.investigationignore",
    "scripts/init_app.py", "scripts/preflight.py", "scripts/create_run.py", "scripts/create_tasks.py", "scripts/extract_access.py",
    "scripts/extract_access.ps1", "scripts/access_runtime.py", "scripts/parse_compilation_database.py", "scripts/build_component_index.py", "scripts/build_module_plan.py", "scripts/validate_handoffs.py",
    "scripts/merge_evidence.py", "scripts/advance_run.py", "scripts/ak.py", "scripts/validate_structure.py",
    "tools/ExportAccessObjects.bas",
    "tests/test_package_smoke.py", "examples/minimal-app/README.md", "examples/minimal-app/manifest.yaml",
    "examples/minimal-app/.investigationignore", "examples/minimal-app/sources/vba/DemoOrderForm.bas", "examples/minimal-app/sources/sql/demo_orders.sql",
)
JSON_FILES = tuple(path for path in REQUIRED_FILES if path.endswith(".json"))
REPOSITORY_FILES = (
    ".gitignore", ".graphifyignore", ".gitattributes", "README.md", "LICENSE", "NOTICE", "CHANGELOG.md", "CONTRIBUTING.md", "SECURITY.md",
    "CODE_OF_CONDUCT.md", "THIRD_PARTY_NOTICES.md", "CITATION.cff", ".agents/plugins/marketplace.json",
    "docs/first-access-mdb-investigation.md",
    ".github/workflows/validate.yml", ".github/dependabot.yml", ".github/pull_request_template.md",
    ".github/ISSUE_TEMPLATE/bug_report.yml", ".github/ISSUE_TEMPLATE/feature_request.yml",
)
PHASE_HEADINGS = tuple(f"Phase {number} — {title}" for number, title in enumerate((
    "Data Understanding", "Screen & Form Analysis", "Logic & Processing", "Workflow Reconstruction", "Document Integration", "Synthesis"
), 1))
MANIFEST_TOKENS = (
    'version: "2.1"', "app:", "id:", "scope:", "legacy_only:", "sources:", "access_databases:", "vba_exports:", "sql_server:",
    "japanese_documents:", "analysis:", "source_policy:", "ignore_file:", "build_context:", "compilation_databases:", "execute_commands: false",
    "module_planning:", 'strategy: "hierarchical_leaf_first"', "shared_context:", "outputs:", "languages:", "derived:", "presentation_pptx:",
    "graphify:", 'input_policy: "extracted_text_and_supported_sources"', "multi_agent:", "coordinator_only_merge:", "independent_qa:", "phase_publication_sequential:",
)
IGNORED_SCAN_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "graphify-out",
    "node_modules",
    "venv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", required=True)
    parser.add_argument("--repository-root", help="Repository root containing public metadata and CI files.")
    parser.add_argument("--manifest")
    return parser.parse_args()


def load_json(path: Path, errors: list[str]) -> object | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Invalid JSON {path}: {exc}")
        return None


def validate_manifest_yaml(path: Path, schema_path: Path, errors: list[str], warnings: list[str]) -> None:
    try:
        import jsonschema  # type: ignore[import-not-found]
        import yaml  # type: ignore[import-not-found]
    except ImportError:
        warnings.append("PyYAML/jsonschema unavailable; manifest received token-level validation only")
        return
    try:
        jsonschema.validate(yaml.safe_load(path.read_text(encoding="utf-8")), json.loads(schema_path.read_text(encoding="utf-8")))
    except Exception as exc:  # noqa: BLE001
        errors.append(f"Manifest schema validation failed for {path}: {exc}")


def validate_orchestration(root: Path, json_data: dict[str, object], errors: list[str]) -> None:
    roles_data = json_data.get("orchestration/roles.json")
    waves_data = json_data.get("orchestration/waves.json")
    adapters = json_data.get("orchestration/runtime-adapters.json")
    merge = json_data.get("orchestration/merge-policy.json")
    if not isinstance(roles_data, dict) or not isinstance(waves_data, dict):
        return
    roles = roles_data.get("roles", [])
    waves = waves_data.get("waves", [])
    role_ids = [role.get("id") for role in roles if isinstance(role, dict)]
    wave_ids = [wave.get("id") for wave in waves if isinstance(wave, dict)]
    if len(role_ids) != len(set(role_ids)):
        errors.append("orchestration/roles.json contains duplicate role ids")
    if len(wave_ids) != len(set(wave_ids)):
        errors.append("orchestration/waves.json contains duplicate wave ids")
    coordinators = [role for role in roles if isinstance(role, dict) and role.get("id") == "coordinator"]
    if len(coordinators) != 1 or coordinators[0].get("may_merge") is not True:
        errors.append("Exactly one coordinator with may_merge=true is required")
    coverage: set[int] = set()
    for role in roles:
        if not isinstance(role, dict):
            continue
        coverage.update(role.get("phases", []))
        if role.get("id") != "coordinator" and role.get("may_merge") is True:
            errors.append(f"Non-coordinator role may not merge: {role.get('id')}")
        if "handoffs" not in role.get("allowed_writes", []):
            errors.append(f"Role cannot return required handoff: {role.get('id')}")
    if coverage != set(range(1, 7)):
        errors.append(f"Role phase coverage must be exactly 1-6, got {sorted(coverage)}")
    required_roles = {"access_extractor", "build_context_analyzer", "module_decomposer"}
    if not required_roles.issubset(set(role_ids)):
        errors.append(f"Missing V2.1 preprocessing roles: {sorted(required_roles - set(role_ids))}")
    seen: set[str] = set()
    for wave in waves:
        if not isinstance(wave, dict):
            continue
        wave_id = wave.get("id")
        unknown = sorted(set(wave.get("roles", [])) - set(role_ids))
        forward = sorted(set(wave.get("depends_on", [])) - seen)
        if unknown:
            errors.append(f"Wave {wave_id} references unknown roles: {unknown}")
        if forward:
            errors.append(f"Wave {wave_id} has missing/forward dependencies: {forward}")
        maximum = wave.get("max_parallel")
        if not isinstance(maximum, int) or maximum < 1 or maximum > len(wave.get("roles", [])):
            errors.append(f"Wave {wave_id} has invalid max_parallel")
        seen.add(str(wave_id))
    try:
        if not wave_ids.index("wave0_context_extraction") < wave_ids.index("wave0_module_decomposition") < wave_ids.index("wave1_source_extraction"):
            errors.append("Context extraction and module planning must precede source-analysis fanout")
        if not wave_ids.index("gate4_publish_phase6") < wave_ids.index("wave4_independent_qa") < wave_ids.index("wave5_derived_rendering"):
            errors.append("Independent QA must run after Phase 6 publication and before rendering")
    except ValueError:
        errors.append("Required V2.1 preprocessing, Phase 6, QA, or rendering wave is missing")
    if isinstance(adapters, dict) and set(adapters.get("required_operations", [])) != {"spawn", "message", "wait", "inspect", "interrupt"}:
        errors.append("Runtime adapter must define spawn/message/wait/inspect/interrupt")
    if isinstance(merge, dict) and merge.get("coordinator_only_merge") is not True:
        errors.append("Merge policy must enforce coordinator_only authority")


def main() -> int:
    args = parse_args()
    root = Path(args.package).expanduser().resolve()
    repository_root = Path(args.repository_root).expanduser().resolve() if args.repository_root else root.parents[1]
    errors: list[str] = []
    warnings: list[str] = []
    for relative in REQUIRED_FILES:
        path = root / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"Missing or empty required file: {relative}")
    for relative in REPOSITORY_FILES:
        path = repository_root / relative
        if not path.is_file() or path.stat().st_size == 0:
            errors.append(f"Missing or empty repository file: {relative}")

    skill_path = root / "skills/ak/SKILL.md"
    if skill_path.is_file():
        skill = skill_path.read_text(encoding="utf-8")
        if not skill.startswith("---\nname: ak\n") or "description:" not in skill.split("---", 2)[1]:
            errors.append("SKILL.md frontmatter is missing or incorrect")
        if len(skill.splitlines()) > 500:
            errors.append("SKILL.md exceeds 500 lines")
        for phrase in ("multi-agent", "coordinator", "independent QA", "scripts/create_run.py", "Access extraction", "leaf-first", "CodeWiki is not a dependency", "$ak help", "$ak init <APP_ID>", "$ak render <APP_ID> [LANGUAGE]"):
            if phrase not in skill:
                errors.append(f"SKILL.md missing V2.1 term: {phrase}")
        if "TODO" in skill:
            errors.append("SKILL.md still contains TODO placeholders")

    package_data = load_json(root / "specifications/package.json", errors)
    expected_version: str | None = None
    if isinstance(package_data, dict):
        expected_version = package_data.get("version")
        if not isinstance(expected_version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", expected_version):
            errors.append("Package version must be semantic (X.Y.Z)")
            expected_version = None
        if package_data.get("contract_version") != "2.1":
            errors.append("Contract version must be 2.1")
        inspiration = package_data.get("architecture_inspiration", {})
        if not isinstance(inspiration, dict) or inspiration.get("dependency") is not False or inspiration.get("vendored_code") is not False:
            errors.append("CodeWiki reference must remain non-dependency and non-vendored")

    publication_checks = {
        "README.md": ("Access Modernization Kit", "codex plugin add", "$ak init <APP_ID>"),
        "docs/first-access-mdb-investigation.md": ("local Access MDB workspace", "--adopt-existing", "Graphify", "Phase 1"),
        "LICENSE": ("Apache License", "Version 2.0, January 2004"),
        "NOTICE": ("Copyright 2026 Vo Ta Tuan", "vo-ta-tuan@anrakutei.vn"),
        "SECURITY.md": ("vo-ta-tuan@anrakutei.vn", "Do not open a public GitHub issue"),
        ".github/workflows/validate.yml": ("pytest", "plugins/ak"),
    }
    for relative, tokens in publication_checks.items():
        path = repository_root / relative
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        for token in tokens:
            if token not in content:
                errors.append(f"Publication file {relative} missing required token: {token}")
    workflow_path = repository_root / ".github/workflows/validate.yml"
    if workflow_path.is_file():
        workflow = workflow_path.read_text(encoding="utf-8")
        for action in ("actions/checkout", "actions/setup-python"):
            if not re.search(rf"(?m)^\s*uses:\s*{re.escape(action)}@v\d+\s*$", workflow):
                errors.append(f"Validate workflow must use a supported major version of {action}")
    ignore_path = repository_root / ".gitignore"
    if ignore_path.is_file():
        ignore_text = ignore_path.read_text(encoding="utf-8")
        for token in ("*.mdb", "*.accdb", "*.adp", ".env", "*.dsn", "graphify-out/"):
            if token not in ignore_text:
                errors.append(f".gitignore missing public-safety rule: {token}")

    contract_path = root / "specifications/senior-system-analyst-instruction.md"
    if contract_path.is_file():
        contract = contract_path.read_text(encoding="utf-8")
        for heading in PHASE_HEADINGS:
            if heading not in contract:
                errors.append(f"Canonical instruction missing: {heading}")
        for phrase in ("Focus on business meaning, not code syntax.", "Cross-check forms, SQL, and documents.", "Clearly state assumptions when logic is unclear."):
            if phrase not in contract:
                errors.append(f"Canonical instruction missing note: {phrase}")

    json_data: dict[str, object] = {"specifications/package.json": package_data}
    for relative in JSON_FILES:
        if relative == "specifications/package.json":
            continue
        path = root / relative
        if path.is_file():
            json_data[relative] = load_json(path, errors)
    validate_orchestration(root, json_data, errors)

    plugin_manifest = load_json(root / ".codex-plugin/plugin.json", errors)
    if isinstance(plugin_manifest, dict):
        if plugin_manifest.get("name") != "ak" or plugin_manifest.get("version") != expected_version:
            errors.append(f"Plugin manifest must identify ak version {expected_version}")
        if plugin_manifest.get("skills") != "./skills/":
            errors.append("Plugin manifest must expose ./skills/")
    marketplace = load_json(repository_root / ".agents/plugins/marketplace.json", errors)
    if isinstance(marketplace, dict):
        if marketplace.get("name") != "access-modernization-kit":
            errors.append("Marketplace name must be access-modernization-kit")
        entries = marketplace.get("plugins")
        if not isinstance(entries, list) or not any(isinstance(entry, dict) and entry.get("name") == "ak" and entry.get("source", {}).get("path") == "./plugins/ak" for entry in entries):
            errors.append("Marketplace must expose plugins/ak")

    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else root / "references/manifest.example.yaml"
    if not manifest_path.is_file():
        errors.append(f"Manifest not found: {manifest_path}")
    else:
        manifest = manifest_path.read_text(encoding="utf-8")
        for token in MANIFEST_TOKENS:
            if token not in manifest:
                errors.append(f"Manifest missing V2.1 token: {token}")
        match = re.search(r"(?m)^\s*id:\s*[\"']?([A-Za-z0-9_-]+)", manifest)
        if not match or not re.fullmatch(r"[A-Z][A-Z0-9_-]{1,15}", match.group(1)):
            errors.append("Manifest app.id is missing or invalid")
        if 'current_implementation: "excluded"' not in manifest:
            warnings.append("Manifest does not use the default legacy-only implementation exclusion")
        validate_manifest_yaml(manifest_path, root / "schemas/manifest.schema.json", errors, warnings)
    example_manifest = root / "examples/minimal-app/manifest.yaml"
    if example_manifest.is_file():
        validate_manifest_yaml(example_manifest, root / "schemas/manifest.schema.json", errors, warnings)

    forbidden = ("D:\\Anrakutei\\a01_docs", "C:\\Users\\USER")
    checked_suffixes = {".md", ".yaml", ".json", ".py", ".ps1", ".html", ".csv"}
    for path in root.rglob("*"):
        relative_parts = path.relative_to(root).parts
        if (
            not path.is_file()
            or any(part in IGNORED_SCAN_DIRS for part in relative_parts)
            or path.suffix.lower() not in checked_suffixes
        ):
            continue
        relative = path.relative_to(root).as_posix()
        content = path.read_text(encoding="utf-8", errors="replace")
        for value in forbidden:
            if value in content:
                errors.append(f"Machine-specific path found in {relative}: {value}")
        if "\ufffd" in content or chr(0x7AA6) in content:
            errors.append(f"Encoding corruption marker found in {relative}")

    for warning in warnings:
        print(f"WARN: {warning}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        print(f"Validation failed: {len(errors)} error(s), {len(warnings)} warning(s)")
        return 1
    print(f"Validation passed: {len(REQUIRED_FILES)} plugin files and {len(REPOSITORY_FILES)} repository files, {len(warnings)} warning(s)")
    print("No app corpus was analyzed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
