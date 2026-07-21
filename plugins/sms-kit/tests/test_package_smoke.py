from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml


PACKAGE = Path(__file__).resolve().parents[1]
REPOSITORY = PACKAGE.parents[1]
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
    import re

    package = json.loads((PACKAGE / "specifications" / "package.json").read_text(encoding="utf-8"))
    version = package["version"]
    assert re.fullmatch(r"\d+\.\d+\.\d+", version), version
    assert package["architecture_inspiration"]["dependency"] is False
    assert package["architecture_inspiration"]["vendored_code"] is False

    # package.json is the single source of truth; every manifest bump_version.py
    # touches must stay in lock-step so one release command is sufficient.
    for manifest in (".codex-plugin/plugin.json", ".claude-plugin/plugin.json"):
        assert json.loads((PACKAGE / manifest).read_text(encoding="utf-8"))["version"] == version
    marketplace = json.loads((REPOSITORY / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
    assert marketplace["metadata"]["version"] == version
    assert all(entry["version"] == version for entry in marketplace["plugins"])

    run_script("validate_structure.py", "--package", str(PACKAGE), "--repository-root", str(REPOSITORY))


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
    yaml_files = sorted((REPOSITORY / ".github").rglob("*.yml"))
    yaml_files += [REPOSITORY / "CITATION.cff", PACKAGE / "examples" / "minimal-app" / "manifest.yaml"]
    for path in yaml_files:
        yaml.load(path.read_text(encoding="utf-8"), Loader=UniqueKeyLoader)


def test_friendly_cli_entrypoint(tmp_path: Path) -> None:
    run_script("sms_kit.py", "validate")
    run_script(
        "sms_kit.py", "install",
        "--runtime", "generic",
        "--destination", str(tmp_path / "sms-kit"),
        "--dry-run",
    )
    run_script(
        "sms_kit.py", "install",
        "--runtime", "claude",
        "--project", str(tmp_path / "claude-project"),
        "--dry-run",
    )
    claude_project = tmp_path / "claude-project"
    run_script("sms_kit.py", "install", "--runtime", "claude", "--project", str(claude_project))
    assert (claude_project / ".claude" / "sms-kit-runtime").resolve() == PACKAGE.resolve()
    assert (claude_project / ".claude" / "skills" / "sms-kit").resolve() == (PACKAGE / "skills" / "sms-kit").resolve()
    run_script(
        "sms_kit.py", "init",
        "--root", str(tmp_path),
        "--app-id", "T22",
        "--name-en", "Friendly CLI Test",
    )
    app = tmp_path / "T22"
    assert (app / "manifest.yaml").is_file()
    run_script("sms_kit.py", "preflight", "--app-root", str(app))


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


def test_access_runtime_probe_reports_json() -> None:
    result = run_script("access_runtime.py")
    report = json.loads(result.stdout)
    for key in ("platform", "python_process_bitness", "registry", "powershell_candidates", "selected_host", "activation", "status"):
        assert key in report, f"access runtime report missing {key}"
    assert report["activation"]["status"] in {"NOT_REQUESTED", "READY", "NOT_INSTALLED", "REGISTERED_BUT_ACTIVATION_FAILED", "INSTALLED_BUT_BITNESS_MISMATCH", "NOT_FOUND"}
    assert report["selected_host"]["status"] in {"READY", "NOT_INSTALLED", "INSTALLED_BUT_BITNESS_MISMATCH", "NOT_FOUND"}


def test_extract_access_reports_runtime_block(tmp_path: Path) -> None:
    database = tmp_path / "runtime.accdb"
    database.write_text("synthetic dry-run placeholder", encoding="utf-8")

    discovered = run_script(
        "extract_access.py",
        "--database", str(database),
        "--database-id", "DBR",
        "--session-id", "DRY-RUNTIME",
        "--output-dir", str(tmp_path / "extracted"),
        "--dry-run",
    )
    plan = json.loads(discovered.stdout)
    assert plan["status"] == "PREFLIGHT_ONLY"
    runtime = plan["runtime"]
    assert runtime["runtime_check"] == "COMPLETED"
    assert runtime["runtime_tested"] is False
    assert "host" in runtime and "status" in runtime["host"]

    skipped = run_script(
        "extract_access.py",
        "--database", str(database),
        "--database-id", "DBR",
        "--session-id", "DRY-SKIP",
        "--output-dir", str(tmp_path / "extracted"),
        "--dry-run",
        "--skip-runtime-check",
    )
    skipped_runtime = json.loads(skipped.stdout)["runtime"]
    assert skipped_runtime["runtime_check"] == "SKIPPED"
    assert skipped_runtime["runtime_tested"] is False


def test_preflight_input_preconditions(tmp_path: Path) -> None:
    run_script(
        "init_app.py",
        "--root", str(tmp_path),
        "--app-id", "T24",
        "--name-en", "Preconditions Test",
        "--runtime", "generic",
    )
    app = tmp_path / "T24"
    manifest = app / "manifest.yaml"

    empty = json.loads(run_script("preflight.py", "--package", str(PACKAGE), "--manifest", str(manifest)).stdout)
    precond = empty["input_preconditions"]
    assert precond["mode"] == "none"
    assert set(precond["recommended_missing"]) == {"sources/vba", "sources/sql"}

    (app / "sources" / "vba" / "Form1.bas").write_text('Attribute VB_Name = "Form1"\n', encoding="utf-8")
    (app / "sources" / "sql" / "schema.sql").write_text("CREATE TABLE t(id int);\n", encoding="utf-8")
    exported = json.loads(run_script("preflight.py", "--package", str(PACKAGE), "--manifest", str(manifest)).stdout)
    assert exported["input_preconditions"]["mode"] == "export"
    assert exported["input_preconditions"]["recommended_missing"] == []

    access_db = app / "sources" / "access" / "T24.accdb"
    access_db.write_text("synthetic placeholder", encoding="utf-8")
    extract = json.loads(run_script("preflight.py", "--package", str(PACKAGE), "--manifest", str(manifest)).stdout)
    # VBA/SQL exports already present, so an unextracted Access binary makes it mixed.
    assert extract["input_preconditions"]["mode"] == "mixed"
    assert "runtime_status" in extract["input_preconditions"]


def test_extract_ps1_declares_unique_safe_names() -> None:
    # Regression guard (runs everywhere): the safe-name function must derive a
    # deterministic hash from the original name so distinct non-ASCII objects do
    # not sanitize to the same filename and overwrite each other on disk.
    ps1 = (SCRIPTS / "extract_access.ps1").read_text(encoding="utf-8")
    assert "function Get-SafeName" in ps1
    assert "ComputeHash" in ps1


def test_extract_ps1_safe_names_are_unique_on_collide() -> None:
    import re
    import shutil

    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        import pytest

        pytest.skip("PowerShell not available on this platform")

    script = (SCRIPTS / "extract_access.ps1").as_posix()
    command = (
        "$ErrorActionPreference='Stop';"
        f"$c = Get-Content -Raw -LiteralPath '{script}';"
        "$m = [regex]::Match($c, '(?ms)^function Get-SafeName\\(.*?^\\}');"
        "if (-not $m.Success) { throw 'Get-SafeName not found' };"
        "Invoke-Expression $m.Value;"
        "$names = @('***','///','@@@','Form1','');"
        "($names | ForEach-Object { Get-SafeName $_ }) -join [char]10"
    )
    result = subprocess.run(
        [powershell, "-NoProfile", "-NonInteractive", "-Command", command],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    safe = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    assert len(safe) == 5, safe
    assert len(set(safe)) == 5, f"safe names collide: {safe}"
    for name in safe:
        assert re.fullmatch(r"[A-Za-z0-9_.-]+", name), name


def test_adopt_existing_workspace_preserves_files(tmp_path: Path) -> None:
    app = tmp_path / "T23"
    original = app / "docs" / "scope.md"
    original.parent.mkdir(parents=True)
    original.write_text("preserve", encoding="utf-8")

    refused = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "sms_kit.py"),
            "init",
            "--app-root", str(app),
            "--app-id", "T23",
            "--name-en", "Adopted Existing App",
        ],
        cwd=PACKAGE,
        check=False,
        capture_output=True,
        text=True,
    )
    assert refused.returncode != 0
    assert not (app / "manifest.yaml").exists()

    run_script(
        "sms_kit.py",
        "init",
        "--app-root", str(app),
        "--app-id", "T23",
        "--name-en", "Adopted Existing App",
        "--adopt-existing",
    )
    assert original.read_text(encoding="utf-8") == "preserve"
    assert (app / "manifest.yaml").is_file()
