#!/usr/bin/env python3
"""Provision and inspect the kit-managed Graphify runtime.

The runtime is intentionally outside both the plugin cache and every app
workspace.  This keeps plugin installation declarative while preventing a
Graphify upgrade from mutating the user's system Python environment.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
SPEC_PATH = PACKAGE / "specifications" / "graphify-runtime.json"


def load_spec() -> dict[str, object]:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def cache_root() -> Path:
    override = os.environ.get("AK_GRAPHIFY_RUNTIME_ROOT")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    else:
        base = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    return base / "access-modernization-kit" / "graphify"


def runtime_root(version: str) -> Path:
    return cache_root() / version


def runtime_paths(root: Path) -> tuple[Path, Path]:
    if os.name == "nt":
        return root / "Scripts" / "python.exe", root / "Scripts" / "graphify.exe"
    return root / "bin" / "python", root / "bin" / "graphify"


def installed_version(python: Path) -> str | None:
    if not python.is_file():
        return None
    result = subprocess.run(
        [str(python), "-c", "import importlib.metadata; print(importlib.metadata.version('graphifyy'))"],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def runtime_report(spec: dict[str, object]) -> dict[str, object]:
    wanted = str(spec["version"])
    root = runtime_root(wanted)
    python, executable = runtime_paths(root)
    actual = installed_version(python)
    return {
        "status": "READY" if actual == wanted and executable.is_file() else "NOT_INSTALLED",
        "install_policy": "auto_managed",
        "requested_version": wanted,
        "installed_version": actual,
        "runtime_root": str(root),
        "python_executable": str(python),
        "graphify_executable": str(executable),
        "global_graphify": shutil.which("graphify"),
        "isolated_from_system_python": True,
    }


def run_checked(command: list[str]) -> None:
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(f"Command failed with exit code {result.returncode}: {' '.join(command)}; {detail}")


def ensure_runtime(spec: dict[str, object], runtime: str, register_skill: bool, dry_run: bool) -> dict[str, object]:
    report = runtime_report(spec)
    wanted = str(spec["version"])
    root = Path(str(report["runtime_root"]))
    python = Path(str(report["python_executable"]))
    executable = Path(str(report["graphify_executable"]))
    package_specs = [str(value) for value in spec.get("packages", [])]
    if report["status"] != "READY":
        uv = shutil.which("uv")
        if uv:
            commands = [
                [uv, "venv", str(root), "--python", sys.executable],
                [uv, "pip", "install", "--python", str(python), *package_specs],
            ]
            installer = "uv"
        else:
            commands = [
                [sys.executable, "-m", "venv", str(root)],
                [str(python), "-m", "pip", "install", *package_specs],
            ]
            installer = "venv+pip"
        if dry_run:
            report.update({"status": "INSTALL_PLANNED", "installer": installer, "commands": commands})
            return report
        root.parent.mkdir(parents=True, exist_ok=True)
        for command in commands:
            run_checked(command)

    actual = installed_version(python)
    if actual != wanted or not executable.is_file():
        raise RuntimeError(f"Managed Graphify verification failed: requested={wanted!r}, installed={actual!r}")

    registration = "NOT_REQUESTED"
    if register_skill and runtime in {"codex", "claude"}:
        command = [str(executable), "install", "--platform", runtime]
        if dry_run:
            registration = "PLANNED"
        else:
            run_checked(command)
            registration = "COMPLETED"
    elif register_skill:
        registration = "UNSUPPORTED_FOR_GENERIC_RUNTIME"

    report = runtime_report(spec)
    report.update({
        "installer": "managed",
        "skill_registration": registration,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    })
    if not dry_run:
        (root / "ak-runtime.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("status", "ensure"))
    parser.add_argument("--runtime", choices=("codex", "claude", "generic"), default="generic")
    parser.add_argument("--register-skill", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = load_spec()
    try:
        report = runtime_report(spec) if args.action == "status" else ensure_runtime(
            spec, args.runtime, args.register_skill, args.dry_run
        )
    except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
        report = {"status": "BLOCKED", "error": str(exc), "requested_version": spec.get("version")}
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    print(rendered)
    if args.output:
        Path(args.output).expanduser().resolve().write_text(rendered + "\n", encoding="utf-8")
    return 0 if report["status"] in {"READY", "INSTALL_PLANNED"} else 3


if __name__ == "__main__":
    raise SystemExit(main())
