from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"


def run_script(name: str, *args: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / name), *map(str, args)],
        cwd=PACKAGE,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"{name} failed\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    return result


def test_public_package_contract() -> None:
    package = json.loads((PACKAGE / "specifications" / "package.json").read_text(encoding="utf-8"))
    assert package["version"] == "2.1.2"
    assert package["architecture_inspiration"]["dependency"] is False
    assert package["architecture_inspiration"]["vendored_code"] is False
    run_script("validate_structure.py", "--package", str(PACKAGE))


def test_public_yaml_has_unique_keys() -> None:
    class UniqueKeyLoader(yaml.SafeLoader):
        pass

    def construct_mapping(loader: UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False) -> dict:
        mapping: dict = {}
        for key_node, value_node in node.value:
            key = loader.construct_object(key_node, deep=deep)
            assert key not in mapping, f"Duplicate YAML key {key!r} at line {key_node.start_mark.line + 1}"
            mapping[key] = loader.construct_object(value_node, deep=deep)
        return mapping

    UniqueKeyLoader.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        construct_mapping,
    )
    yaml_files = sorted((PACKAGE / ".github").rglob("*.yml"))
    yaml_files += [PACKAGE / "CITATION.cff", PACKAGE / "examples" / "minimal-app" / "manifest.yaml"]
    for path in yaml_files:
        yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)


def test_synthetic_module_aware_pipeline(tmp_path: Path) -> None:
    run_script(
        "init_app.py",
        "--root", str(tmp_path),
        "--app-id", "T21",
        "--name-en", "Synthetic Public Test",
        "--runtime", "generic",
    )
    app = tmp_path / "T21"

    access_file = app / "sources" / "access" / "synthetic.accdb"
    access_file.write_text("synthetic dry-run placeholder", encoding="utf-8")
    (app / "sources" / "vba" / "DemoForm.bas").write_text(
        'Attribute VB_Name = "DemoForm"\nSub Save_Click(): End Sub\n', encoding="utf-8"
    )
    ignored = app / "sources" / "sql" / "ignored.tmp"
    ignored.write_text("ignored", encoding="utf-8")

    compile_commands = app / "sources" / "documents" / "compile_commands.json"
    compile_commands.write_text(
        json.dumps([{
            "directory": "/synthetic/build",
            "file": "/synthetic/demo.cpp",
            "arguments": ["clang++", "--password", "secret-value", "-c", "/synthetic/demo.cpp"],
        }]),
        encoding="utf-8",
    )

    session = app / "extracted" / "access" / "DB1" / "20260715-000000"
    session.mkdir(parents=True)
    (session / "component-index.json").write_text(
        json.dumps({
            "schema_version": "2.1",
            "app_id": "T21",
            "generated_at": "2026-07-15T00:00:00+00:00",
            "components": [{
                "id": "DB1:form:DemoForm",
                "kind": "form",
                "name": "DemoForm",
                "container": "demo",
                "module_hint": "demo",
                "source_paths": ["forms/DemoForm.txt"],
                "depends_on": [],
                "metadata": {},
            }],
        }),
        encoding="utf-8",
    )

    dry_run = run_script(
        "extract_access.py",
        "--database", str(access_file),
        "--database-id", "DB1",
        "--session-id", "DRY-RUN",
        "--output-dir", str(app / "extracted" / "access"),
        "--dry-run",
    )
    assert json.loads(dry_run.stdout)["status"] == "PREFLIGHT_ONLY"

    normalized = app / "extracted" / "build-context" / "compile_commands.normalized.json"
    run_script("parse_compilation_database.py", "--input", str(compile_commands), "--output", str(normalized))
    normalized_text = normalized.read_text(encoding="utf-8")
    assert "secret-value" not in normalized_text
    assert "<REDACTED>" in normalized_text

    run_script("build_component_index.py", "--app-root", str(app))
    run_script(
        "build_module_plan.py",
        "--component-index", str(app / "extracted" / "component-index.json"),
        "--output-dir", str(app / "extracted" / "module-plan"),
    )
    run_script("create_run.py", "--app-root", str(app), "--runtime", "generic", "--run-id", "T21-PUBLIC-SMOKE")
    run = app / "runs" / "T21-PUBLIC-SMOKE"
    run_script("create_tasks.py", "--package", str(PACKAGE), "--run", str(run))

    inventory = json.loads((run / "source-inventory.json").read_text(encoding="utf-8"))
    assert any(item["relative_path"].endswith("ignored.tmp") for item in inventory["ignored"])
    tasks = [json.loads(path.read_text(encoding="utf-8")) for path in (run / "tasks").glob("*.json")]
    assert tasks
    assert any(task["module_targets"] for task in tasks)
