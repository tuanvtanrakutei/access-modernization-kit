#!/usr/bin/env python3
"""Friendly entry point for the SMS Legacy Investigation Kit."""

from __future__ import annotations

import argparse
import json
import os
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
        epilog="For full investigation work, invoke the sms-kit agent skill.",
    )
    parser.add_argument("--version", action="version", version=package_version())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate this shared package without analyzing an app.")

    install = commands.add_parser("install", help="Install this package as an agent-discoverable skill.")
    install.add_argument("--runtime", choices=("codex", "claude", "generic"), required=True)
    install.add_argument("--project", help="Claude project directory; required for --runtime claude.")
    install.add_argument("--destination", help="Skill destination; required for --runtime generic.")
    install.add_argument("--dry-run", action="store_true", help="Print the planned installation without changing files.")

    init = commands.add_parser("init", help="Create an isolated workspace for one legacy app.")
    init.add_argument("--root", required=True, help="Parent directory for app workspaces.")
    init.add_argument("--app-id", required=True, help="App identifier, for example A03.")
    init.add_argument("--name-en", required=True, help="English app name.")
    init.add_argument("--runtime", default="generic", help="Agent runtime label (default: generic).")

    preflight = commands.add_parser("preflight", help="Check capabilities and manifest before any analysis.")
    preflight.add_argument("--app-root", required=True, help="Initialized app workspace directory.")
    preflight.add_argument("--runtime", default="generic", help="Agent runtime label (default: generic).")
    return parser.parse_args()


def install_destination(args: argparse.Namespace) -> Path:
    if args.runtime == "codex":
        return Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".codex" / "skills" / "sms-kit"
    if args.runtime == "claude":
        if not args.project:
            raise ValueError("--project is required for --runtime claude")
        return Path(args.project).expanduser().resolve() / ".claude" / "skills" / "sms-kit"
    if not args.destination:
        raise ValueError("--destination is required for --runtime generic")
    return Path(args.destination).expanduser().resolve()


def install_skill(args: argparse.Namespace) -> int:
    try:
        destination = install_destination(args)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    source = PACKAGE.resolve()
    if args.dry_run:
        print(f"Would install sms-kit for {args.runtime}: {destination} -> {source}")
        return 0
    if destination.exists():
        if destination.resolve() == source:
            print(f"sms-kit is already installed for {args.runtime}: {destination}")
            return 0
        print(f"ERROR: destination already exists and targets a different path: {destination}")
        return 2
    destination.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        result = subprocess.run(
            ["cmd", "/c", f'mklink /J "{destination}" "{source}"'],
            check=False,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stderr or result.stdout, end="")
            return result.returncode
    else:
        destination.symlink_to(source, target_is_directory=True)
    print(f"Installed sms-kit for {args.runtime}: {destination}")
    print("Restart or open a new agent session so it discovers the skill.")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "validate":
        return run("validate_structure.py", "--package", str(PACKAGE))
    if args.command == "install":
        return install_skill(args)
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
