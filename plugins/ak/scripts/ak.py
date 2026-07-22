#!/usr/bin/env python3
"""Friendly entry point for the Access Modernization Kit."""

from __future__ import annotations

import argparse
import base64
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
        epilog="For full investigation work, invoke the ak agent skill.",
    )
    parser.add_argument("--version", action="version", version=package_version())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate this shared package without analyzing an app.")

    install = commands.add_parser("install", help="Install the skill for a non-Codex runtime.")
    install.add_argument("--runtime", choices=("codex", "claude", "generic"), required=True)
    install.add_argument("--project", help="Claude project directory; required for --runtime claude.")
    install.add_argument("--destination", help="Skill destination; required for --runtime generic.")
    install.add_argument("--dry-run", action="store_true", help="Print the planned installation without changing files.")

    init = commands.add_parser("init", help="Create or safely adopt one legacy app workspace.")
    init_location = init.add_mutually_exclusive_group(required=True)
    init_location.add_argument("--root", help="Parent directory for a new app workspace.")
    init_location.add_argument("--app-root", help="Existing or new app workspace directory.")
    init.add_argument("--app-id", required=True, help="App identifier, for example A03.")
    init.add_argument("--name-en", required=True, help="English app name.")
    init.add_argument("--adopt-existing", action="store_true", help="Safely add kit files to a non-empty --app-root.")
    init.add_argument("--runtime", default="generic", help="Agent runtime label (default: generic).")

    preflight = commands.add_parser("preflight", help="Check capabilities and manifest before any analysis.")
    preflight.add_argument("--app-root", required=True, help="Initialized app workspace directory.")
    preflight.add_argument("--runtime", default="generic", help="Agent runtime label (default: generic).")

    graphify = commands.add_parser("graphify", help="Prepare or validate the mandatory Graphify phase gate.")
    graphify.add_argument("action", choices=("prepare", "check", "finalize"))
    graphify.add_argument("--app-root", required=True)
    graphify.add_argument("--phase", required=True, type=int, choices=range(1, 7))
    graphify.add_argument("--runtime", choices=("codex", "claude", "generic"), default="generic")
    graphify.add_argument("--no-install-missing", action="store_true")
    graphify.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def install_destination(args: argparse.Namespace) -> Path:
    if args.runtime == "codex":
        return Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".codex" / "skills" / "ak"
    if args.runtime == "claude":
        if not args.project:
            raise ValueError("--project is required for --runtime claude")
        return Path(args.project).expanduser().resolve() / ".claude" / "skills" / "ak"
    if not args.destination:
        raise ValueError("--destination is required for --runtime generic")
    return Path(args.destination).expanduser().resolve()


def create_directory_link(link: Path, target: Path) -> int:
    if os.name != "nt":
        link.symlink_to(target, target_is_directory=True)
        return 0
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    command = f"New-Item -ItemType Junction -Path {quote(link)} -Target {quote(target)} | Out-Null"
    encoded = base64.b64encode(command.encode("utf-16le")).decode("ascii")
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand", encoded],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stderr or result.stdout, end="")
    return result.returncode


def install_skill(args: argparse.Namespace) -> int:
    if args.runtime == "codex":
        print("ak is installed for Codex through `codex plugin add ak@access-modernization-kit`.")
        print("Do not create a manual .codex/skills link.")
        return 0
    try:
        destination = install_destination(args)
    except ValueError as exc:
        print(f"ERROR: {exc}")
        return 2
    source = PACKAGE.resolve()
    if args.runtime == "claude":
        runtime_root = destination.parents[1] / "ak-runtime"
        skill_source = runtime_root / "skills" / "ak"
        if args.dry_run:
            print(f"Would install package runtime for Claude: {runtime_root} -> {source}")
            print(f"Would install Claude skill: {destination} -> {skill_source}")
            return 0
        for link, target in ((runtime_root, source), (destination, skill_source)):
            if link.exists():
                if link.resolve() == target.resolve():
                    continue
                print(f"ERROR: destination already exists and targets a different path: {link}")
                return 2
            link.parent.mkdir(parents=True, exist_ok=True)
            if create_directory_link(link, target) != 0:
                return 1
        print(f"Installed ak for Claude: {destination}")
        print("Restart or open a new Claude session so it discovers the skill.")
        return 0
    source = PACKAGE / "skills" / "ak"
    if args.dry_run:
        print(f"Would install ak for {args.runtime}: {destination} -> {source}")
        return 0
    if destination.exists():
        if destination.resolve() == source:
            print(f"ak is already installed for {args.runtime}: {destination}")
            return 0
        print(f"ERROR: destination already exists and targets a different path: {destination}")
        return 2
    destination.parent.mkdir(parents=True, exist_ok=True)
    if create_directory_link(destination, source) != 0:
        return 1
    print(f"Installed ak for {args.runtime}: {destination}")
    print("Restart or open a new agent session so it discovers the skill.")
    return 0


def main() -> int:
    args = parse_args()
    if args.command == "validate":
        return run("validate_structure.py", "--package", str(PACKAGE))
    if args.command == "install":
        return install_skill(args)
    if args.command == "init":
        init_args = [
            "--app-id", args.app_id,
            "--name-en", args.name_en,
            "--runtime", args.runtime,
        ]
        if args.root:
            init_args.extend(["--root", args.root])
        else:
            init_args.extend(["--app-root", args.app_root])
        if args.adopt_existing:
            init_args.append("--adopt-existing")
        return run("init_app.py", *init_args)
    if args.command == "graphify":
        graphify_args = [
            args.action,
            "--app-root", args.app_root,
            "--phase", str(args.phase),
            "--runtime", args.runtime,
        ]
        if args.no_install_missing:
            graphify_args.append("--no-install-missing")
        if args.dry_run:
            graphify_args.append("--dry-run")
        return run("graphify_phase_gate.py", *graphify_args)
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
