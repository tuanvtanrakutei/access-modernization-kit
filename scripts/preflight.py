#!/usr/bin/env python3
"""Check runtime capabilities without installing packages or analyzing an app."""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import sys
import platform
from pathlib import Path


MODULES = {
    "yaml": "PyYAML for full YAML validation",
    "jsonschema": "JSON Schema validation",
    "pyodbc": "Live SQL Server access",
    "openpyxl": "Local XLSX fallback",
    "pypdf": "Local PDF text fallback",
    "playwright": "Local browser automation",
}
EXECUTABLES = {
    "graphify": "Persistent knowledge graph",
    "node": "Presentation or browser runtimes",
    "tesseract": "OCR for scanned Japanese sources",
    "powershell": "Access extraction adapter and Windows capability inspection",
    "clang": "Optional AST enrichment for supported compiled languages",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", default=".", help="Package root")
    parser.add_argument("--runtime", choices=("codex", "claude", "generic"), default="generic")
    parser.add_argument("--manifest", help="Optional app manifest")
    parser.add_argument("--output", help="Optional JSON report path")
    parser.add_argument("--skip-skill-scan", action="store_true")
    return parser.parse_args()


def discover_skills() -> list[str]:
    roots = [
        Path.home() / ".codex" / "skills",
        Path.home() / ".agents" / "skills",
        Path.home() / ".codex" / "plugins" / "cache",
    ]
    names: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("SKILL.md"):
            try:
                head = path.read_text(encoding="utf-8", errors="ignore")[:1000]
            except OSError:
                continue
            for line in head.splitlines():
                if line.startswith("name:"):
                    names.add(line.split(":", 1)[1].strip().strip('"\''))
                    break
    return sorted(names)


def manifest_needs(path: Path | None) -> dict[str, bool]:
    needs = {"graphify": False, "xlsx": False, "pdf": False, "html": False, "pptx": False, "live_sql": False, "access": False, "adp": False, "compdb": False}
    if not path or not path.is_file():
        return needs
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    try:
        import yaml  # type: ignore[import-not-found]
        data = yaml.safe_load(text) or {}
        sources = data.get("sources", {})
        access_sources = sources.get("access_databases", []) or []
        sql_live = sources.get("sql_server", {}).get("live", {})
        analysis = data.get("analysis", {})
        build = analysis.get("build_context", {})
        derived = data.get("outputs", {}).get("derived", {})
        needs["graphify"] = bool(data.get("graphify", {}).get("enabled"))
        needs["xlsx"] = ".xlsx" in text
        needs["pdf"] = ".pdf" in text
        needs["html"] = bool(derived.get("e2e_html") or derived.get("boundary_html"))
        needs["pptx"] = bool(derived.get("presentation_pptx") or data.get("outputs", {}).get("presentation_template"))
        needs["live_sql"] = bool(sql_live.get("enabled"))
        needs["access"] = bool(access_sources)
        needs["adp"] = any(isinstance(item, dict) and item.get("format") == "adp" for item in access_sources)
        needs["compdb"] = bool(build.get("compilation_databases") or build.get("compile_flags"))
    except (ImportError, AttributeError, TypeError, ValueError):
        needs["graphify"] = "graphify:" in text
        needs["xlsx"] = ".xlsx" in text
        needs["pdf"] = ".pdf" in text
        template_match = re.search(r"(?m)^\s*presentation_template:\s*([^#\r\n]*)", text)
        template_value = template_match.group(1).strip().strip('"\'') if template_match else ""
        needs["html"] = "e2e_html: true" in text or "boundary_html: true" in text
        needs["pptx"] = "presentation_pptx: true" in text or bool(template_value)
        needs["live_sql"] = bool(re.search(r"(?m)^\s{6}enabled:\s*true\s*$", text))
        needs["access"] = bool(re.search(r"(?m)^\s*access_databases:\s*$", text))
        needs["adp"] = bool(re.search(r"(?m)^\s*format:\s*[\"']?adp", text))
        needs["compdb"] = "compile_commands.json" in text
    return needs


def windows_access_capabilities() -> dict[str, bool | str]:
    result: dict[str, bool | str] = {"windows": platform.system() == "Windows", "access_com_registered": False, "ace_provider_registered": False, "process_bitness": f"{8 * __import__('struct').calcsize('P')}-bit"}
    if not result["windows"]:
        return result
    try:
        import winreg  # type: ignore[import-not-found]
        for hive, key in (
            (winreg.HKEY_CLASSES_ROOT, r"Access.Application\CLSID"),
            (winreg.HKEY_CLASSES_ROOT, r"Microsoft.ACE.OLEDB.12.0\CLSID"),
            (winreg.HKEY_CLASSES_ROOT, r"Microsoft.ACE.OLEDB.16.0\CLSID"),
        ):
            try:
                with winreg.OpenKey(hive, key):
                    if key.startswith("Access.Application"):
                        result["access_com_registered"] = True
                    else:
                        result["ace_provider_registered"] = True
            except OSError:
                pass
    except ImportError:
        pass
    return result


def main() -> int:
    args = parse_args()
    package = Path(args.package).expanduser().resolve()
    manifest = Path(args.manifest).expanduser().resolve() if args.manifest else None
    needs = manifest_needs(manifest)
    package_version_path = package / "specifications/package.json"

    required = {
        "python_3_10_plus": sys.version_info >= (3, 10),
        "package_version": package_version_path.is_file(),
        "roles_contract": (package / "orchestration/roles.json").is_file(),
        "waves_contract": (package / "orchestration/waves.json").is_file(),
        "runtime_adapter": (package / "orchestration/runtime-adapters.json").is_file(),
    }
    modules = {name: importlib.util.find_spec(name) is not None for name in MODULES}
    executables = {name: shutil.which(name) is not None for name in EXECUTABLES}
    access = windows_access_capabilities()
    skills = [] if args.skip_skill_scan else discover_skills()

    recommendations: list[str] = []
    if needs["graphify"] and not executables["graphify"]:
        recommendations.append("Install/enable Graphify before graph generation; Phase 1-6 can still run.")
    if needs["xlsx"] and not any("spreadsheet" in name.lower() for name in skills) and not modules["openpyxl"]:
        recommendations.append("Enable a spreadsheet skill/runtime or install openpyxl for XLSX fallback.")
    if needs["pdf"] and not modules["pypdf"]:
        recommendations.append("Use a runtime PDF reader; install pypdf only if a local fallback is needed.")
    if needs["pptx"] and not any("presentation" in name.lower() for name in skills):
        recommendations.append("Enable a presentation skill/runtime before requesting PPTX output.")
    if needs["html"] and not any("playwright" in name.lower() for name in skills) and not modules["playwright"]:
        recommendations.append("Enable a browser automation skill/runtime before HTML visual QA.")
    if needs["live_sql"] and not modules["pyodbc"]:
        recommendations.append("Install pyodbc and Microsoft ODBC Driver only after live SQL access is authorized.")
    if needs["access"] and not access["access_com_registered"]:
        recommendations.append("Access automation is not registered; keep existing exports or run snapshot extraction on a compatible Windows host with Microsoft Access/ACE.")
    if needs["adp"]:
        recommendations.append("ADP extraction requires a compatible legacy Access environment; do not assume modern Access can open the project.")
    if needs["compdb"]:
        recommendations.append("Use parse_compilation_database.py for read-only normalization; Clang is optional and commands must never be executed.")
    if args.runtime == "generic":
        recommendations.append("Map spawn/message/wait/inspect/interrupt operations before multi-agent execution.")

    report = {
        "runtime": args.runtime,
        "python": sys.version.split()[0],
        "required": required,
        "modules": modules,
        "executables": executables,
        "access": access,
        "discovered_skills": skills,
        "manifest_needs": needs,
        "recommendations": recommendations,
        "status": "PASS" if all(required.values()) else "FAIL",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).expanduser().resolve().write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
