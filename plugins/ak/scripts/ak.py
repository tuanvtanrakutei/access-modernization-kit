#!/usr/bin/env python3
"""Friendly entry point for the Access Modernization Kit."""

from __future__ import annotations

import argparse
import base64
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
SCRIPTS = PACKAGE / "scripts"
CONTRACTS = PACKAGE / "contracts"
sys.path.insert(0, str(CONTRACTS))


def _workspace(app_root: Path):
    """The layout resolver: one place knows a pre-2.10.0 workspace names things
    differently, so every caller asks instead of assuming."""
    from workspace import Workspace

    return Workspace(app_root)



def package_version() -> str:
    return json.loads((PACKAGE / "specifications" / "package.json").read_text(encoding="utf-8"))["version"]


def run(script: str, *args: str) -> int:
    return subprocess.run([sys.executable, str(SCRIPTS / script), *args], check=False).returncode


def configure_acquire_parser(commands: argparse._SubParsersAction) -> None:
    acquire = commands.add_parser("acquire", help="Route declared artifacts through acquisition adapters.")
    acquire.add_argument("app_or_action", nargs="?", help="App workspace, ID, or action ('plan' or 'run').")
    acquire.add_argument("target", nargs="?", help="Target app workspace or directory when action is specified.")
    acquire.add_argument("--manifest", help="Path to manifest.yaml")
    acquire.add_argument("--output-root", help="Output directory for acquisition bundle")
    acquire.add_argument("--authorize", action="append", default=[])
    acquire.add_argument("--acquisition-id", default=None)
    acquire.add_argument(
        "--keep-snapshots", action="store_true",
        help="Keep the disposable database copies after a clean run. They are removed by "
             "default: nothing reads them once extraction has written its receipt, and on a "
             "real application they doubled the workspace.",
    )
    # The question an operator actually has is not "which mode is this" but "can this
    # evidence carry the phases I came here for". Naming them makes acquisition answer
    # it instead of leaving a blocked phase to be discovered in a file afterwards.
    acquire.add_argument(
        "--require-phases", default="",
        help="Comma-separated phases this acquisition must reach, for example 1,2,3. "
             "Reported by 'plan'; 'run' fails if the acquired evidence leaves one blocked.",
    )

def configure_collaboration_parser(commands: argparse._SubParsersAction) -> None:
    collaboration = commands.add_parser(
        "collaboration", help="Validate deterministic collaboration contracts."
    )
    groups = collaboration.add_subparsers(dest="collaboration_group", required=True)

    package = groups.add_parser("package")
    package_commands = package.add_subparsers(dest="collaboration_action", required=True)
    package_validate = package_commands.add_parser("validate")
    package_validate.add_argument("--package", required=True)
    package_conflicts = package_commands.add_parser("conflicts")
    package_conflicts.add_argument("--root", required=True)
    package_project = package_commands.add_parser("project")
    package_project.add_argument("--package", required=True)
    package_project.add_argument("--receipt", required=True)
    package_project.add_argument("--run", required=True)

    handoff = groups.add_parser("handoff")
    handoff_validate = handoff.add_subparsers(
        dest="collaboration_action", required=True
    ).add_parser("validate")
    handoff_validate.add_argument("--run", required=True)
    handoff_validate.add_argument("--work-package-root", required=True)

    review = groups.add_parser("review")
    review_validate = review.add_subparsers(
        dest="collaboration_action", required=True
    ).add_parser("validate")
    review_validate.add_argument("--package", required=True)
    review_validate.add_argument("--receipt", required=True)

    impact = groups.add_parser("impact")
    impact_validate = impact.add_subparsers(
        dest="collaboration_action", required=True
    ).add_parser("validate")
    impact_validate.add_argument("--package", required=True)
    impact_validate.add_argument("--impact", required=True)
    impact_validate.add_argument("--changed-paths", required=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="For full investigation work, invoke the ak agent skill.",
    )
    parser.add_argument("--version", action="version", version=package_version())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate", help="Validate this shared package without analyzing an app.")

    citations = commands.add_parser(
        "citations",
        help="Check that every evidence id a phase document cites exists.",
    )
    citations.add_argument("--outputs", required=True, help="Directory holding the phase documents and evidence register.")
    citations.add_argument("--json", action="store_true", help="Emit a machine-readable report.")

    conformance = commands.add_parser(
        "conformance",
        help="Check a published phase document carries what the phase contract promises.",
    )
    conformance.add_argument("--outputs", required=True, help="Directory holding the phase documents.")
    conformance.add_argument("--strict", action="store_true", help="Fail on evidence apparatus as well as content.")
    conformance.add_argument("--group", choices=("content", "apparatus", "all"), default="all")
    conformance.add_argument("--json", action="store_true", help="Emit a machine-readable report.")

    clean = commands.add_parser(
        "clean", help="Report, and optionally remove, what a workspace no longer needs.",
    )
    clean.add_argument("--app-root", required=True)
    clean.add_argument("--delete", action="store_true", help="Actually remove; without it the command only reports.")
    clean.add_argument("--json", action="store_true")

    references = commands.add_parser(
        "references",
        help="List every source this analysis read, with the digest that says which copy.",
    )
    references.add_argument("--app-root", required=True)
    references.add_argument("--app-id")
    references.add_argument("--dry-run", action="store_true")

    bilingual = commands.add_parser(
        "bilingual",
        help="Print the English name beside every production name in the narratives.",
    )
    bilingual.add_argument("--app-root", required=True)
    bilingual.add_argument("--dry-run", action="store_true")

    glossary = commands.add_parser(
        "glossary",
        help="Propose an English name for every production name, for a person to accept.",
    )
    glossary.add_argument("--app-root", required=True)
    glossary.add_argument("--dry-run", action="store_true")

    meanings = commands.add_parser(
        "meanings",
        help="List every table and column still needing a business meaning, blank, "
             "for a person to fill.",
    )
    meanings.add_argument("--app-root", required=True)
    meanings.add_argument(
        "--top", type=int,
        help="Only add the N highest-priority subjects per section.",
    )
    meanings.add_argument("--dry-run", action="store_true")

    completeness = commands.add_parser(
        "completeness",
        help="Record each object's definition-text shape and compare it with the last "
             "record and the other acquisition route.",
    )
    completeness.add_argument("--app-root", required=True)
    completeness.add_argument(
        "--dry-run", action="store_true", help="Report without updating the record.",
    )

    samples = commands.add_parser(
        "samples",
        help="Compare each supplied sample with the import specification its link "
             "names: field count, header names, and StartRow.",
    )
    samples.add_argument("--app-root", required=True)

    interviews = commands.add_parser(
        "interviews",
        help="Read the Q&A register and the pages it indexes, and report where they "
             "disagree: a question marked answered whose page holds no answer, one "
             "still open, one the register does not list.",
    )
    interviews.add_argument("--app-root", required=True)
    interviews.add_argument("--dry-run", action="store_true", help="Report without writing the record.")

    catalogues = commands.add_parser(
        "catalogues",
        help="Generate the exhaustive per-entity catalogues from the acquisition bundle.",
    )
    catalogues.add_argument("--app-root", required=True)
    catalogues.add_argument("--app-id", help="Defaults to the manifest's app id.")
    catalogues.add_argument(
        "--dry-run", action="store_true", help="Report the sizes without writing.",
    )

    migrate = commands.add_parser(
        "migrate-workspace",
        help="Move a workspace laid out before 2.10.0 into input/, output/ and .ak/.",
    )
    migrate.add_argument("--workspace", required=True)
    migrate.add_argument(
        "--apply", action="store_true",
        help="Perform the move; without it the command only prints what it would do.",
    )
    migrate.add_argument("--json", action="store_true")

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
    init.add_argument("--source", help="Path to source directory or ZIP archive to auto-import and scan.")
    init.add_argument("--runtime", default="generic", help="Agent runtime label (default: generic).")

    import_sources = commands.add_parser(
        "import-sources",
        help="Write the producer manifest an already-exported source tree needs to be imported.",
    )
    import_sources.add_argument("--source", required=True, help="Export directory that becomes the import package.")
    import_sources.add_argument("--producer-id", required=True, help="What produced the export.")
    import_sources.add_argument("--producer-version", required=True, help="Version of that producer.")
    import_sources.add_argument("--logical-id-prefix", required=True, help="Prefix for each file's logical id, normally the artifact id.")
    import_sources.add_argument(
        "--source-database",
        help="The .mdb/.accdb this export was produced from. Recorded so a run can detect an export gone stale.",
    )
    import_sources.add_argument("--allow-unclassified", action="store_true", help="Declare files in unrecognized directories as metadata instead of failing.")
    import_sources.add_argument("--dry-run", action="store_true", help="Report the plan without writing the manifest.")

    preflight = commands.add_parser("preflight", help="Check capabilities and manifest before any analysis.")
    preflight.add_argument("--app-root", required=True, help="Initialized app workspace directory.")
    preflight.add_argument("--runtime", default="generic", help="Agent runtime label (default: generic).")
    preflight.add_argument(
        "--verify-access-activation", action="store_true",
        help="Actually activate and release Access so a READY status predicts whether extraction can run.",
    )

    derive = commands.add_parser(
        "derive", help="Derive the relationships the sealed bundle states literally. Runs once, before the first phase.",
    )
    derive.add_argument("--app-root", required=True)
    derive.add_argument("--dry-run", action="store_true", help="Report counts without writing.")

    documents = commands.add_parser(
        "documents", help="Normalize XLSX/DOCX/PPTX/PDF and legacy-encoded text into citable UTF-8 with provenance.",
    )
    documents.add_argument("--app-root", required=True)
    documents.add_argument("--dry-run", action="store_true", help="Report planned sources without writing.")
    documents.add_argument("--output", help="Also write the audit to this path.")

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
    phase = commands.add_parser("phase", help="Report what evidence a phase still needs, and how to supply it.")
    phase_commands = phase.add_subparsers(dest="phase_action", required=True)
    phase_req = phase_commands.add_parser("requirements")
    phase_req.add_argument("--app-root", required=True)
    phase_req.add_argument("--phase", type=int, choices=range(1, 7), required=True)
    phase_req.add_argument(
        "--waive", action="append", default=[],
        help="Proceed without a capability. Requires --reason and is recorded in the receipt.",
    )
    phase_req.add_argument("--reason", help="Why the waived evidence cannot be supplied.")
    configure_acquire_parser(commands)
    configure_collaboration_parser(commands)
    return parser.parse_args()


def print_json(value: object) -> None:
    # Two separate problems. A console codepage such as cp932 cannot encode every
    # character a real report carries, and an encode error here threw away the whole
    # result after the work was done. And when stdout is redirected, the locale
    # encoding would write a JSON file that is not UTF-8 and has lost characters to
    # replacement. Emitting UTF-8 keeps redirected reports machine-readable and
    # lossless; a legacy console renders non-ASCII as mojibake either way.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass
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
        return Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".codex" / "skills" / "investigate"
    if args.runtime == "claude":
        if not args.project:
            raise ValueError("--project is required for --runtime claude")
        return Path(args.project).expanduser().resolve() / ".claude" / "skills" / "investigate"
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
        skill_source = runtime_root / "skills" / "investigate"
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
    source = PACKAGE / "skills" / "investigate"
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
    if args.command == "citations":
        citation_args = ["--outputs", args.outputs]
        if args.json:
            citation_args.append("--json")
        return run("validate_evidence_citations.py", *citation_args)
    if args.command == "conformance":
        conformance_args = ["--outputs", args.outputs, "--group", args.group]
        if args.strict:
            conformance_args.append("--strict")
        if args.json:
            conformance_args.append("--json")
        return run("validate_phase_conformance.py", *conformance_args)
    if args.command == "references":
        reference_args = ["--app-root", args.app_root]
        if args.app_id:
            reference_args += ["--app-id", args.app_id]
        if args.dry_run:
            reference_args.append("--dry-run")
        return run("build_references.py", *reference_args)

    if args.command == "bilingual":
        bilingual_args = ["--app-root", args.app_root]
        if args.dry_run:
            bilingual_args.append("--dry-run")
        return run("annotate_bilingual.py", *bilingual_args)

    if args.command == "glossary":
        glossary_args = ["--app-root", args.app_root]
        if args.dry_run:
            glossary_args.append("--dry-run")
        return run("build_glossary.py", *glossary_args)

    if args.command == "meanings":
        meaning_args = ["--app-root", args.app_root]
        if args.top:
            meaning_args += ["--top", str(args.top)]
        if args.dry_run:
            meaning_args.append("--dry-run")
        return run("build_meanings.py", *meaning_args)

    if args.command == "completeness":
        completeness_args = ["--app-root", args.app_root]
        if args.dry_run:
            completeness_args.append("--dry-run")
        return run("check_export_completeness.py", *completeness_args)

    if args.command == "samples":
        return run("check_feed_samples.py", "--app-root", args.app_root)

    if args.command == "interviews":
        interview_args = ["--app-root", args.app_root]
        if args.dry_run:
            interview_args.append("--dry-run")
        return run("check_interview_register.py", *interview_args)

    if args.command == "catalogues":
        catalogue_args = ["--app-root", args.app_root]
        if args.app_id:
            catalogue_args += ["--app-id", args.app_id]
        if args.dry_run:
            catalogue_args.append("--dry-run")
        return run("generate_catalogues.py", *catalogue_args)

    if args.command == "migrate-workspace":
        migrate_args = ["--workspace", args.workspace]
        if args.apply:
            migrate_args.append("--apply")
        if args.json:
            migrate_args.append("--json")
        return run("migrate_workspace.py", *migrate_args)

    if args.command == "clean":
        clean_args = ["--app-root", args.app_root]
        if args.delete:
            clean_args.append("--delete")
        if args.json:
            clean_args.append("--json")
        return run("clean_workspace.py", *clean_args)
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
        if getattr(args, "source", None):
            init_args.extend(["--source", args.source])
        return run("init_app.py", *init_args)
    if args.command == "derive":
        derive_args = ["--app-root", args.app_root]
        if args.dry_run:
            derive_args.append("--dry-run")
        return run("derive_graph_facts.py", *derive_args)
    if args.command == "documents":
        document_args = ["--app-root", args.app_root]
        if args.dry_run:
            document_args.append("--dry-run")
        if args.output:
            document_args.extend(["--output", args.output])
        return run("normalize_documents.py", *document_args)
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
    if args.command == "import-sources":
        import_args = [
            "--source", args.source,
            "--producer-id", args.producer_id,
            "--producer-version", args.producer_version,
            "--logical-id-prefix", args.logical_id_prefix,
        ]
        if args.source_database:
            import_args += ["--source-database", args.source_database]
        if args.allow_unclassified:
            import_args.append("--allow-unclassified")
        if args.dry_run:
            import_args.append("--dry-run")
        return run("build_import_manifest.py", *import_args)
    if args.command == "manifest":
        from migration import propose_migration

        report = propose_migration(Path(args.manifest).expanduser().resolve())
        if args.output:
            Path(args.output).expanduser().resolve().write_text(
                json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        print_json(report)
        return 0
    if args.command == "phase":
        package_path = str(PACKAGE)
        if package_path not in sys.path:
            sys.path.insert(0, package_path)
        from phase_evidence import phase_report

        if args.waive and not args.reason:
            print("ERROR: --waive requires --reason; an undocumented waiver is worse than a blocked phase")
            return 2
        report = phase_report(
            Path(args.app_root).expanduser().resolve(), args.phase,
            tuple(args.waive), args.reason,
        )
        print_json(report)
        return 0 if report["status"] != "BLOCKED" else 2

    if args.command == "acquire":
        package_path = str(PACKAGE)
        if package_path not in sys.path:
            sys.path.insert(0, package_path)
        from acquisition_orchestrator import plan_acquisition, run_acquisition

        app_or_action = getattr(args, "app_or_action", None)
        target = getattr(args, "target", None)
        action = None
        app = None

        if app_or_action in ("plan", "run"):
            action = app_or_action
            app = target
        elif target in ("plan", "run"):
            action = target
            app = app_or_action
        else:
            app = app_or_action or target

        manifest_arg = getattr(args, "manifest", None)
        if manifest_arg:
            manifest_path = Path(manifest_arg).expanduser().resolve()
        elif app:
            app_path = Path(app).expanduser().resolve()
            if (app_path / "manifest.yaml").is_file():
                manifest_path = app_path / "manifest.yaml"
            elif app_path.is_file():
                manifest_path = app_path
            else:
                manifest_path = app_path / "manifest.yaml"
        else:
            manifest_path = Path.cwd() / "manifest.yaml"

        if not manifest_path.is_file():
            print(f"ERROR: manifest not found: {manifest_path}")
            return 2

        output_root = (
            Path(args.output_root).expanduser().resolve()
            if getattr(args, "output_root", None)
            else _workspace(manifest_path.parent).acquired_root()
        )
        acquisition_id = getattr(args, "acquisition_id", None) or f"acquire-{uuid.uuid4().hex}"
        authorize = tuple(getattr(args, "authorize", []) or [])
        required_phases = tuple(
            item if item.startswith("phase") else f"phase{item}"
            for item in (
                part.strip() for part in str(getattr(args, "require_phases", "") or "").split(",")
            )
            if item
        )

        if action == "plan":
            plan = plan_acquisition(manifest_path)
            if required_phases:
                plan["required_phases"] = {
                    "requested": list(required_phases),
                    "reachable": sorted(
                        phase for phase in required_phases
                        if plan["phase_outlook"]["if_content_present"].get(phase) != "BLOCKED"
                    ),
                    "unreachable": sorted(
                        phase for phase in required_phases
                        if plan["phase_outlook"]["if_content_present"].get(phase) == "BLOCKED"
                    ),
                }
            print_json(plan)
            return 0 if not plan.get("required_phases", {}).get("unreachable") else 2
        elif action == "run":
            result = run_acquisition(
                manifest_path, output_root, authorize, acquisition_id, required_phases,
                keep_snapshots=args.keep_snapshots,
            )
            print_json(result)
            return 0 if result.get("bundle_id") else 2

        plan = plan_acquisition(manifest_path)
        result = run_acquisition(
            manifest_path, output_root, authorize, acquisition_id, required_phases,
            keep_snapshots=args.keep_snapshots,
        )
        result["plan"] = plan
        print_json(result)
        return 0 if result.get("bundle_id") else 2
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
    if args.command == "collaboration":
        from collaboration import CollaborationError
        from collaboration_cli import (
            project_package,
            scan_conflicts,
            validate_handoff,
            validate_impact,
            validate_package,
            validate_review,
        )

        try:
            if args.collaboration_group == "package":
                if args.collaboration_action == "validate":
                    result = validate_package(Path(args.package))
                elif args.collaboration_action == "conflicts":
                    result = scan_conflicts(Path(args.root))
                else:
                    result = project_package(
                        Path(args.package), Path(args.receipt), Path(args.run)
                    )
            elif args.collaboration_group == "handoff":
                result = validate_handoff(
                    Path(args.run), Path(args.work_package_root)
                )
            elif args.collaboration_group == "review":
                result = validate_review(Path(args.package), Path(args.receipt))
            else:
                result = validate_impact(
                    Path(args.package), Path(args.impact), Path(args.changed_paths)
                )
        except CollaborationError as exc:
            print_json(
                {"status": "ERROR", "code": exc.code, "message": str(exc.detail)}
            )
            return 2
        print_json(result)
        return 2 if result.get("status") == "CONFLICT" else 0
    app_root = Path(args.app_root).expanduser().resolve()
    manifest = app_root / "manifest.yaml"
    if not manifest.is_file():
        print(f"ERROR: manifest not found: {manifest}")
        return 2
    preflight_args = [
        "--package", str(PACKAGE),
        "--runtime", args.runtime,
        "--manifest", str(manifest),
    ]
    if args.verify_access_activation:
        preflight_args.append("--verify-access-activation")
    return run("preflight.py", *preflight_args)


if __name__ == "__main__":
    raise SystemExit(main())
