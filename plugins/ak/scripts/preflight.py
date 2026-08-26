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
    parser.add_argument(
        "--verify-access-activation", action="store_true",
        help="Actually activate and release Access.Application, so a READY status predicts whether extraction can run. Off by default because it starts Access.",
    )
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
    # yaml_parsed records whether the manifest was really parsed or only pattern-matched.
    # Without it a missing PyYAML silently downgraded every answer below to a text scan
    # and reported the guesses as facts, with nothing anywhere saying a package was
    # absent - the same class of defect as a failure that erases its own evidence.
    # access_host is deliberately separate from access. Only the Access Application
    # tier can require elevation; the DAO tier activates in-process and never does. An
    # Access-only project that skips object export needs no host at all, and warning it
    # about administrator rights trains operators to elevate runs that never needed it.
    needs = {"graphify": False, "xlsx": False, "pdf": False, "html": False, "pptx": False, "live_sql": False, "access": False, "access_host": False, "adp": False, "compdb": False, "yaml_parsed": False}
    if not path or not path.is_file():
        return needs
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    try:
        import yaml  # type: ignore[import-not-found]
        data = yaml.safe_load(text) or {}
        needs["yaml_parsed"] = True
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
        # A V2.2 manifest declares its inputs as `artifacts`, not under `sources`, so
        # reading only the V2.1 shape reported every capability as unneeded - including
        # Access itself on an Access-only project.
        artifacts = data.get("artifacts") or []
        access_artifacts = [
            item for item in artifacts
            if isinstance(item, dict) and item.get("kind") == "access_database"
        ]
        needs["live_sql"] = bool(sql_live.get("enabled")) or any(
            isinstance(item, dict) and str(item.get("kind", "")).startswith("sql_server")
            for item in artifacts
        )
        needs["access"] = bool(access_sources) or bool(access_artifacts)
        # A V2.1 manifest has no per-artifact runtime, so it is assumed to start a host.
        needs["access_host"] = bool(access_sources) or any(
            not (item.get("runtime") or {}).get("skip_object_export") for item in access_artifacts
        )
        needs["adp"] = any(
            isinstance(item, dict) and item.get("format") == "adp"
            for item in list(access_sources) + access_artifacts
        )
        needs["compdb"] = bool(build.get("compilation_databases") or build.get("compile_flags"))
    except (ImportError, AttributeError, TypeError, ValueError):
        needs["graphify"] = "graphify:" in text
        needs["xlsx"] = ".xlsx" in text
        needs["pdf"] = ".pdf" in text
        template_match = re.search(r"(?m)^\s*presentation_template:\s*([^#\r\n]*)", text)
        template_value = template_match.group(1).strip().strip('"\'') if template_match else ""
        needs["html"] = "e2e_html: true" in text or "boundary_html: true" in text
        needs["pptx"] = "presentation_pptx: true" in text or bool(template_value)
        # The V2.2 shape has to be recognized here too. This branch only ever matched
        # V2.1 keys, so without PyYAML a V2.2 Access-only project reported access:false
        # - the same defect already fixed in the parsed branch above, left standing in
        # the fallback where it is harder to notice.
        needs["live_sql"] = bool(re.search(r"(?m)^\s{6}enabled:\s*true\s*$", text)) or bool(
            re.search(r"(?m)^\s*-?\s*kind:\s*[\"']?sql_server", text)
        )
        needs["access"] = bool(re.search(r"(?m)^\s*access_databases:\s*$", text)) or bool(
            re.search(r"(?m)^\s*-?\s*kind:\s*[\"']?access_database", text)
        )
        needs["adp"] = bool(re.search(r"(?m)^\s*format:\s*[\"']?adp", text))
        # Without a parser the per-artifact pairing cannot be established, so a host is
        # assumed unless the text carries no enabled skip_object_export at all. Erring
        # toward "a host may start" keeps the elevation warning rather than losing it.
        needs["access_host"] = needs["access"] and not bool(
            re.search(r"(?m)^\s*skip_object_export:\s*true\s*$", text)
        )
        needs["compdb"] = "compile_commands.json" in text
    return needs


def windows_access_capabilities(verify_activation: bool = False) -> dict[str, object]:
    """Report Access automation capability, delegating to the shared runtime probe.

    The richer discovery in access_runtime.py adds bitness-matched PowerShell
    host selection on top of the registry checks. Backward-compatible keys are
    preserved so existing report consumers keep working; a lightweight
    registry-only fallback runs if the shared module cannot be imported.

    Discovery alone is not predictive: a registered, bitness-matched Access can still
    fail to activate (an elevation-flagged install returns 0x800702E4), so a READY
    status here was reported for a runtime extraction could not actually use.
    ``activation_verified`` states plainly whether a real activation was attempted.
    """
    try:
        from access_runtime import inspect_access_runtime
    except ImportError:
        return _legacy_windows_access_capabilities()
    report = inspect_access_runtime(smoke_test=verify_activation)
    views = report.get("registry", {}).get("views", {})
    activation = report.get("activation", {})
    return {
        "windows": report["platform"] == "Windows",
        "process_bitness": report["python_process_bitness"],
        "access_com_registered": any(view.get("access", {}).get("registered") for view in views.values()),
        "ace_provider_registered": any(
            provider.get("registered") for view in views.values() for provider in view.get("ace_providers", {}).values()
        ),
        "selected_host": report["selected_host"],
        # Which Access will actually open the database. A bare ProgId resolves per
        # machine, so on a host carrying more than one Office an operator could not
        # see which install a run was about to use - the registry knew, and nothing
        # reported it. Naming the executable and its version makes an unintended
        # engine visible before the run rather than after.
        "registered_access": [
            {
                "view": view_name,
                "executable": entry.get("executable"),
                "version": entry.get("version"),
            }
            for view_name, view in views.items()
            for entry in [view.get("access", {})]
            if entry.get("registered")
        ],
        "runtime_status": report["status"],
        "runasadmin_detected": report["runasadmin_detected"],
        "activation_verified": bool(activation.get("tested")),
        "activation": activation,
        "appcompat_flags": report.get("appcompat_flags", []),
    }


def _legacy_windows_access_capabilities() -> dict[str, bool | str]:
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


def managed_graphify_capabilities() -> dict[str, object]:
    """Inspect the isolated Graphify runtime without installing anything."""
    try:
        from graphify_runtime import load_spec, runtime_report

        return runtime_report(load_spec())
    except (ImportError, OSError, ValueError) as exc:
        return {"status": "NOT_AVAILABLE", "error": str(exc), "install_policy": "auto_managed"}


def manifest_source_paths(manifest: Path | None) -> dict[str, list[str]]:
    """Read declared source locations without assuming a fixed workspace layout."""
    defaults = {
        "vba": ["sources/vba"],
        "sql": ["sources/sql"],
        "documents": ["sources/documents"],
        "japanese_documents": ["shared-docs"],
        # Export packages: a directory or .zip carrying forms, reports, macros, modules
        # and query SQL together, declared through their own producer manifest. There is
        # no conventional default location for these - they are always declared.
        "source_packages": [],
    }
    if not manifest or not manifest.is_file():
        return defaults
    try:
        import yaml  # type: ignore[import-not-found]

        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        if str(data.get("version")) == "2.2":
            values: dict[str, list[str]] = {
                "vba": [], "sql": [], "documents": [], "japanese_documents": [],
                "source_packages": [],
            }
            for artifact in data.get("artifacts", []) or []:
                if not isinstance(artifact, dict):
                    continue
                source_ref = artifact.get("source_ref", {}) or {}
                value = source_ref.get("value")
                if not isinstance(value, str) or not value.strip():
                    continue
                kind = str(artifact.get("kind", ""))
                fmt = str(artifact.get("format", ""))
                if kind == "source_export" and fmt == "vba":
                    values["vba"].append(value)
                # Only a single-file export declares format: vba. A directory or zip
                # package - the shape the imported adapter requires, and the shape
                # scripts/build_import_manifest.py produces - was recognized as neither
                # VBA nor SQL, so an application whose forms, reports and modules all
                # arrived that way was reported as having no exported sources at all,
                # and a hybrid project was labelled pure extract mode.
                elif kind == "source_export":
                    values["source_packages"].append(value)
                elif kind.startswith("sql_server"):
                    values["sql"].append(value)
                elif kind == "document":
                    values["documents"].append(value)
            return values
        sources = data.get("sources", {})
        sql_server = sources.get("sql_server", {}) or {}
        japanese = sources.get("japanese_documents", {}) or {}
        values = {
            "vba": sources.get("vba_exports", []),
            "sql": sql_server.get("exported_paths", []),
            "documents": sources.get("app_documents", []),
            "japanese_documents": list(japanese.values()) if isinstance(japanese, dict) else [],
        }
        return {
            key: [str(item) for item in value if isinstance(item, str) and item.strip()]
            for key, value in values.items()
        }
    except (ImportError, OSError, AttributeError, TypeError, ValueError):
        return defaults


def scan_app_sources(app_root: Path, declared: dict[str, list[str]]) -> dict[str, object]:
    def nonempty(rel: str) -> bool:
        candidate = app_root / rel
        if candidate.is_file():
            return True
        return candidate.is_dir() and any(item.is_file() for item in candidate.rglob("*"))

    def existing(paths: list[str]) -> list[str]:
        return [path for path in paths if nonempty(path)]

    access_dir = app_root / "sources" / "access"
    access_db = access_dir.is_dir() and any(
        item.is_file() and item.suffix.lower() in {".mdb", ".accdb", ".adp"} for item in access_dir.rglob("*")
    )
    extracted = app_root / "extracted" / "access"
    # A published acquisition bundle is stronger evidence that extraction already
    # happened than the legacy extracted/access path, which current acquisition does
    # not write - it stages under acquired/. Without this an app with a valid bundle
    # still reported extracted_access false and was told to run extraction again.
    acquired = app_root / "acquired"
    bundled = acquired.is_dir() and any(
        item.is_dir() and item.name.startswith("bundle-") for item in acquired.iterdir()
    )
    vba_present = existing(declared["vba"])
    sql_present = existing(declared["sql"])
    document_present = existing(declared["documents"])
    japanese_present = existing(declared["japanese_documents"])
    package_present = existing(declared.get("source_packages", []))
    return {
        "vba": bool(vba_present),
        "sql": bool(sql_present),
        "source_packages": bool(package_present),
        "access_db": access_db,
        "screenshots": nonempty("sources/screenshots"),
        "reports": nonempty("sources/reports"),
        "documents": bool(document_present),
        "samples": nonempty("sources/samples"),
        "shared_docs": bool(japanese_present),
        "extracted_access": (extracted.is_dir() and any(item.is_file() for item in extracted.rglob("*"))) or bundled,
        "acquisition_bundle": bundled,
        "declared_paths": declared,
        "present_paths": {
            "vba": vba_present,
            "sql": sql_present,
            "documents": document_present,
            "japanese_documents": japanese_present,
            "source_packages": package_present,
        },
    }


def input_preconditions(manifest: Path | None, needs: dict[str, bool], access: dict[str, object]) -> tuple[dict[str, object], list[str]]:
    """Detect the input mode and report missing inputs as warnings, never failures."""
    if not manifest or not (manifest.parent / "sources").is_dir():
        return {"mode": "unknown", "reason": "no app workspace beside the manifest"}, []
    app_root = manifest.parent
    declared = manifest_source_paths(manifest)
    present = scan_app_sources(app_root, declared)
    warnings: list[str] = []
    has_export = (
        present["vba"] or present["sql"] or present["extracted_access"]
        or present["source_packages"]
    )
    has_binary = bool(present["access_db"] or needs.get("access"))
    needs_extraction = has_binary and not present["extracted_access"]
    # The mode describes which inputs the operator provided, and nothing else. It used
    # to be derived from whether extraction was still pending, so an application holding
    # both a database and export packages reported "mixed" before acquisition and
    # "export" afterwards - the same inputs described two different ways depending on
    # work already done. What remains to be done is `needs_extraction`, reported
    # separately below.
    declared_export = has_export or bool(
        declared["vba"] or declared["sql"] or declared.get("source_packages")
    )
    if has_binary and declared_export:
        mode = "mixed"
    elif has_binary:
        mode = "extract"
    elif has_export:
        mode = "export"
    else:
        mode = "none"

    recommended_missing: list[str] = []
    if not present["extracted_access"]:
        if declared["vba"] and not present["vba"]:
            recommended_missing.extend(declared["vba"])
        if declared["sql"] and not present["sql"]:
            recommended_missing.extend(declared["sql"])

    if mode == "none":
        warnings.append("No app sources detected; add exported VBA/SQL (export mode) or an Access database (extract mode) before running the six phases.")
    else:
        for relative in recommended_missing:
            warnings.append(f"No files in {relative}; affected phases will run but must record missing coverage as an assumption/open question.")
    if not present["shared_docs"]:
        warnings.append("No shared Japanese documents in shared-docs/; Phase 5 document integration will be limited.")

    block: dict[str, object] = {
        "app_root": str(app_root),
        "mode": mode,
        "needs_extraction": needs_extraction,
        "present": present,
        "recommended_missing": recommended_missing,
    }
    if needs_extraction:
        runtime_status = access.get("runtime_status")
        block["runtime_status"] = runtime_status
        block["selected_host"] = access.get("selected_host")
        if runtime_status != "READY":
            warnings.append("Access database present but no READY runtime host; run scripts/access_runtime.py --smoke-test, or export VBA/SQL on a compatible host and use export mode.")
    return block, warnings


def main() -> int:
    args = parse_args()
    package = Path(args.package).expanduser().resolve()
    manifest = Path(args.manifest).expanduser().resolve() if args.manifest else None
    needs = manifest_needs(manifest)
    package_version_path = package / "specifications/package.json"

    required = {
        "python_3_10_plus": sys.version_info >= (3, 10),
        # Nothing installs these: neither plugin manifest declares a dependency and
        # there is no install hook. `init` is stdlib-only and works without them, so a
        # PASS here used to promise a working workspace right up to `acquire`, which
        # imports both at module level and dies with ModuleNotFoundError. Required, so
        # the failure lands at preflight where it can be explained.
        "python_package_pyyaml": importlib.util.find_spec("yaml") is not None,
        "python_package_jsonschema": importlib.util.find_spec("jsonschema") is not None,
        "package_version": package_version_path.is_file(),
        "roles_contract": (package / "orchestration/roles.json").is_file(),
        "waves_contract": (package / "orchestration/waves.json").is_file(),
        "runtime_adapter": (package / "orchestration/runtime-adapters.json").is_file(),
    }
    modules = {name: importlib.util.find_spec(name) is not None for name in MODULES}
    executables = {name: shutil.which(name) is not None for name in EXECUTABLES}
    access = windows_access_capabilities(verify_activation=args.verify_access_activation)
    graphify_runtime = managed_graphify_capabilities()
    skills = [] if args.skip_skill_scan else discover_skills()

    recommendations: list[str] = []
    if not modules["yaml"] or not modules["jsonschema"]:
        missing = [
            name for name, present in (("PyYAML", modules["yaml"]), ("jsonschema", modules["jsonschema"]))
            if not present
        ]
        recommendations.append(
            f"Required Python package(s) not installed: {', '.join(missing)}. "
            "Installing this package as a plugin does not install them. Run "
            "`pip install -r plugins/ak/requirements.txt`. Until then `init` still works, "
            "but `acquire` and everything after it cannot run."
        )
    if manifest and not needs["yaml_parsed"]:
        recommendations.append(
            "The manifest was pattern-matched rather than parsed, so the capability needs "
            "below are guesses. Install PyYAML for an accurate read."
        )
    if needs["graphify"] and graphify_runtime.get("status") != "READY":
        recommendations.append(
            "The isolated Graphify runtime is not installed yet. The first Phase/run gate must bootstrap the pinned managed runtime, normalize a binary-free corpus, build or refresh the graph, and complete a phase query before analysis starts."
        )
    if needs["xlsx"] and not needs["graphify"] and not any("spreadsheet" in name.lower() for name in skills) and not modules["openpyxl"]:
        recommendations.append("Enable a spreadsheet skill/runtime or install openpyxl for XLSX fallback.")
    if needs["pdf"] and not needs["graphify"] and not modules["pypdf"]:
        recommendations.append("Use a runtime PDF reader; install pypdf only if a local fallback is needed.")
    if needs["pptx"] and not any("presentation" in name.lower() for name in skills):
        recommendations.append("Enable a presentation skill/runtime before requesting PPTX output.")
    if needs["html"] and not any("playwright" in name.lower() for name in skills) and not modules["playwright"]:
        recommendations.append("Enable a browser automation skill/runtime before HTML visual QA.")
    if needs["live_sql"] and not modules["pyodbc"]:
        recommendations.append("Install pyodbc and Microsoft ODBC Driver only after live SQL access is authorized.")
    if needs["access"] and not access["access_com_registered"]:
        recommendations.append("Access automation is not registered; keep existing exports or run snapshot extraction on a compatible Windows host with Microsoft Access/ACE.")
    if needs["access"] and not needs["access_host"]:
        recommendations.append(
            "Every managed artifact declares runtime.skip_object_export, so acquisition runs through the DAO tier only: "
            "no Access host is started, and no administrator rights or COM activation are required. Object definition text "
            "will not be exported; supply it as an imported export package if Phase 2 and Phase 3 need the definitions."
        )
    if needs["access_host"] and access["access_com_registered"] and not access.get("activation_verified"):
        recommendations.append(
            "Access is registered but no activation was attempted, so this status does not predict whether extraction can run. "
            "Re-run with --verify-access-activation, or use the DAO-only tier (runtime.skip_object_export) which needs no Access host."
        )
    # An elevation-flagged Access cannot be worked around from inside the process:
    # __COMPAT_LAYER=RunAsInvoker is set on the PowerShell host, while the COM server
    # is launched by the service and does not inherit it. Name the remedy that works.
    if needs["access_host"] and access.get("runasadmin_detected"):
        flags = ", ".join(
            f"{flag.get('hive')}:{flag.get('value')}" for flag in access.get("appcompat_flags", []) or []
        )
        recommendations.append(
            "The registered Access executable carries a RUNASADMIN compatibility flag, so COM activation fails with 0x800702E4. "
            "--allow-run-as-invoker cannot fix this: it sets __COMPAT_LAYER on the PowerShell host, but the COM server is launched "
            "by the service and does not inherit it. Remove RUNASADMIN from the AppCompatFlags\\Layers value for that executable, "
            f"or run from an elevated terminal. Detected: {flags or 'no value read'}"
        )
    if needs["adp"]:
        recommendations.append("ADP extraction requires a compatible legacy Access environment; do not assume modern Access can open the project.")
    if needs["compdb"]:
        recommendations.append("Use parse_compilation_database.py for read-only normalization; Clang is optional and commands must never be executed.")
    if args.runtime == "generic":
        recommendations.append("Map spawn/message/wait/inspect/interrupt operations before multi-agent execution.")

    preconditions, precondition_warnings = input_preconditions(manifest, needs, access)
    recommendations.extend(precondition_warnings)

    report = {
        "runtime": args.runtime,
        "python": sys.version.split()[0],
        "required": required,
        "modules": modules,
        "executables": executables,
        "graphify_runtime": graphify_runtime,
        "access": access,
        "discovered_skills": skills,
        "manifest_needs": needs,
        "input_preconditions": preconditions,
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
