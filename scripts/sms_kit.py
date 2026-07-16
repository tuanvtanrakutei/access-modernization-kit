#!/usr/bin/env python3
"""Friendly entry point for the SMS Legacy Investigation Kit."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"


def package_version() -> str:
    return json.loads((PACKAGE / "specifications" / "package.json").read_text(encoding="utf-8"))["version"]


def run(script: str, *args: str) -> int:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], check=False).returncode


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="For full investigation work, invoke the sms-legacy-investigation-kit agent skill.",
    )
    parser.add_argument("--version", action="version", version=package_version())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate this shared package without analyzing an app.")

    init = commands.add_parser("init", help="Create an isolated workspace for one legacy app.")
    init.add_argument("--root", required=True, help="Parent directory for app workspaces.")
    init.add_argument("--app-id", required=True, help="App identifier, for example A03.")
    init.add_argument("--name-en", required=True, help="English app name.")
    init.add_argument("--runtime", default="generic", help="Agent runtime label (default: generic).")

    preflight = commands.add_parser("preflight", help="Check capabilities and manifest before any analysis.")
    preflight.add_argument("--app-root", required=True, help="Initialized app workspace directory.")
    preflight.add_argument("--runtime", default="generic", help="Agent runtime label (default: generic).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "validate":
        return run("validate_structure.py", "--package", str(PACKAGE))
    if args.command == "init":
        return run(
            "init_app.py",
            "--root", args.root,
            "--app-id", args.app_id,
            "--name-en", args.name_en,
            "--runtime", args.runtime,
        )
    app_root = Path(args.app_root).expanduser().resolve()
    manifest = app_root / "manifest.yaml"
    if not manifest.is_file():
        print(f"ERROR: manifest not found: {manifest}")
        return 2
    return run(
        "preflight.py",
        "--package", str(PACKAGE),
        "--runtime", args.runtime,
        "--manifest", str(manifest),
    )


if __name__ == "__main__":
    raise SystemExit(main())
