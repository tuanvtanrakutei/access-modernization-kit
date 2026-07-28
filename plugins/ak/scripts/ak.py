#!/usr/bin/env python3
"""Friendly entry point for the Access Modernization Kit."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"
CONTRACTS = PACKAGE / "contracts"
sys.path.insert(0, str(CONTRACTS))


def package_version() -> str:
    return json.loads((PACKAGE / "specifications" / "package.json").read_text(encoding="utf-8"))["version"]


def run(script: str, *args: str) -> int:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], check=False).returncode


def configure_acquire_parser(commands: argparse._SubParsersAction) -> None:
    acquire = commands.add_parser("acquire", help="Route declared artifacts through acquisition adapters.")
    acquire_commands = acquire.add_subparsers(dest="acquire_action", required=True)
    acquire_plan = acquire_commands.add_parser("plan")
    acquire_plan.add_argument("--manifest", required=True)
    acquire_run = acquire_commands.add_parser("run")
    acquire_run.add_argument("--manifest", required=True)
    acquire_run.add_argument("--output-root", required=True)
    acquire_run.add_argument("--authorize", action="append", default=[])
    acquire_run.add_argument("--acquisition-id", default="acquire")


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

    profile = commands.add_parser("profile", help="Detect or validate a composable project classification.")
    profile_commands = profile.add_subparsers(dest="profile_action", required=True)
    profile_validate = profile_commands.add_parser("validate")
    profile_validate.add_argument("--topology", required=True)
    profile_validate.add_argument("--frontend", required=True)
    profile_validate.add_argument("--source-availability", required=True)
    profile_validate.add_argument("--backend", action="append", required=True)
    profile_validate.add_argument("--profile")
    profile_detect = profile_commands.add_parser("detect")
    profile_detect.add_argument("--manifest", required=True)

    manifest = commands.add_parser("manifest", help="Read or migrate manifest contracts.")
    manifest_commands = manifest.add_subparsers(dest="manifest_action", required=True)
    manifest_migrate = manifest_commands.add_parser("migrate")
    manifest_migrate.add_argument("--manifest", required=True)
    manifest_migrate.add_argument("--output")

    bundle = commands.add_parser("bundle", help="Validate or approve a canonical extraction bundle.")
    bundle_commands = bundle.add_subparsers(dest="bundle_action", required=True)
    bundle_validate = bundle_commands.add_parser("validate")
    bundle_validate.add_argument("--bundle-dir", required=True)
    bundle_approve = bundle_commands.add_parser("approve")
    bundle_approve.add_argument("--bundle-dir", required=True)
    bundle_approve.add_argument("--approval-id", required=True)
    bundle_approve.add_argument("--approver", required=True)
    bundle_approve.add_argument("--approved-at")
    bundle_approve.add_argument("--distribution-policy", choices=("local_only", "shared_path", "artifact_store", "git_allowed"), default="artifact_store")
    bundle_approve.add_argument("--output", required=True)
    configure_acquire_parser(commands)
    return parser.parse_args()


def print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True))


def classification_result(classification: object, profile: str | None = None) -> dict[str, object]:
    from classification import reconcile_alias, resolve_classification

    if profile:
        reconcile_alias(profile, classification)
    resolved = resolve_classification(classification, PACKAGE / "profiles")
    return {
        "classification": classification.as_dict(),
        "profile": profile,
        "rule_ids": list(resolved.rule_ids),
        "rule_versions": resolved.rule_versions,
    }


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
    if args.command == "profile":
        from classification import Classification
        from manifest_v22 import load_manifest
        from migration import propose_migration

        if args.profile_action == "validate":
            classification = Classification(args.topology, args.frontend, args.source_availability, tuple(args.backend))
            print_json(classification_result(classification, args.profile))
            return 0
        manifest_data = load_manifest(Path(args.manifest).expanduser().resolve())
        if manifest_data.classification is None:
            print_json({"status": "LIMITED", "migration": propose_migration(Path(args.manifest))})
        else:
            print_json(classification_result(manifest_data.classification, manifest_data.profile))
        return 0
    if args.command == "manifest":
        from migration import propose_migration

        report = propose_migration(Path(args.manifest).expanduser().resolve())
        if args.output:
            Path(args.output).expanduser().resolve().write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        print_json(report)
        return 0
    if args.command == "acquire":
        package_path = str(PACKAGE)
        if package_path not in sys.path:
            sys.path.insert(0, package_path)
        from acquisition_orchestrator import plan_acquisition, run_acquisition

        manifest_path = Path(args.manifest).expanduser().resolve()
        if args.acquire_action == "plan":
            print_json(plan_acquisition(manifest_path))
            return 0
        result = run_acquisition(
            manifest_path, Path(args.output_root).expanduser().resolve(),
            tuple(args.authorize), args.acquisition_id,
        )
        print_json(result)
        return 0
    if args.command == "bundle":
        import hashlib
        from bundle import make_approval, validate_bundle

        bundle_dir = Path(args.bundle_dir).expanduser().resolve()
        data = validate_bundle(bundle_dir)
        if args.bundle_action == "validate":
            print_json({"status": "VALID", "bundle_id": data["bundle_id"]})
            return 0
        output = Path(args.output).expanduser().resolve()
        try:
            output.relative_to(bundle_dir)
        except ValueError:
            pass
        else:
            print("ERROR: bundle approval must remain outside the immutable bundle")
            return 2
        checksum_source = bundle_dir / "checksums.sha256"
        if not checksum_source.is_file():
            checksum_source = bundle_dir / "bundle.json"
        approval = make_approval(
            args.approval_id, data["bundle_id"], hashlib.sha256(checksum_source.read_bytes()).hexdigest(),
            data["schema_version"], package_version(), args.approver,
            args.approved_at or datetime.now(timezone.utc).isoformat(), args.distribution_policy,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(approval, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print_json(approval)
        return 0
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
