#!/usr/bin/env python3
"""Safely snapshot an Access database and invoke the optional Windows extractor."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from access_runtime import inspect_access_runtime


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True)
    parser.add_argument("--database-id", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--session-id", help="Immutable extraction session id; default is a UTC timestamp")
    parser.add_argument("--password-env", help="Environment variable name containing an Access password; the password is never passed on the command line")
    parser.add_argument("--execute", action="store_true", help="Create a snapshot and run Access COM automation")
    parser.add_argument("--dry-run", action="store_true", help="Report the plan without copying or opening the database")
    parser.add_argument("--powershell", help="Override the PowerShell host used to drive the Access COM adapter")
    parser.add_argument("--allow-run-as-invoker", action="store_true", help="Set __COMPAT_LAYER=RunAsInvoker for the PowerShell host. Note this does not reach an out-of-process COM server: a RUNASADMIN-flagged Access still fails with 0x800702E4")
    parser.add_argument("--skip-runtime-check", action="store_true", help="Skip Access runtime discovery and use the default PowerShell host (restores pre-2.3 behavior)")
    parser.add_argument("--snapshot-dir", help="Directory the snapshot copy is placed in. Defaults to a folder private to this extraction. A split Access application whose frontend opens its backend as a sibling needs both snapshots in one directory, which only the caller knows how to arrange.")
    parser.add_argument("--timeout", type=int, default=1800, help="Seconds to wait for the Access adapter before treating the run as hung (default: 1800)")
    parser.add_argument("--access-progid", default="Access.Application", help="COM ProgId for the Access host; version-qualify it (Access.Application.11) to pin one install")
    parser.add_argument("--dao-progid", default="DAO.DBEngine.36", help="COM ProgId for the DAO engine that reads schema without starting Access")
    parser.add_argument("--access-path", help="Declare the Access executable this run expects; a mismatch with the registered COM server is reported instead of silently using another install")
    parser.add_argument("--skip-object-export", action="store_true", help="Run only the DAO tier: full schema and object inventory, no exported definition text")
    parser.add_argument("--skip-object-inventory", action="store_true", help="Do not register forms, reports, macros or modules; use when an imported export of the same database supplies them")
    parser.add_argument("--visible-host", action="store_true", help="Show the Access host so an operator can dismiss dialogs a broken VBA reference raises. Marks the run attended")
    return parser.parse_args()


def terminate_recorded_hosts(output: Path) -> list[int]:
    """Kill only the Access processes this run started, listed by the adapter.

    A hung host keeps the snapshot locked, which makes the next run fail on a
    directory it cannot remove. Killing by recorded PID never touches an Access
    instance the operator opened themselves.
    """
    record = output / "access-host.json"
    if not record.is_file():
        return []
    try:
        pids = [int(pid) for pid in json.loads(record.read_text(encoding="utf-8-sig")).get("pids", [])]
    except (ValueError, OSError):
        return []
    killed: list[int] = []
    for pid in pids:
        try:
            subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], check=False, capture_output=True)
            killed.append(pid)
        except OSError:
            continue
    return killed


def build_runtime_block(args: argparse.Namespace) -> tuple[dict, dict | None]:
    """Return the extraction ``runtime`` block and the selected PowerShell host.

    Discovery is read-only. A COM activation smoke test runs only for a real
    ``--execute`` extraction so a dry-run never opens Access.
    """
    if args.skip_runtime_check:
        return {"adapter": "scripts/extract_access.ps1", "runtime_tested": False, "runtime_check": "SKIPPED"}, None
    report = inspect_access_runtime(
        override=args.powershell,
        smoke_test=bool(args.execute and not args.dry_run),
        allow_run_as_invoker=args.allow_run_as_invoker,
    )
    host = report["selected_host"]
    activation = report["activation"]
    runtime = {
        "adapter": "scripts/extract_access.ps1",
        "runtime_check": "COMPLETED",
        "runtime_tested": bool(activation.get("tested") and report["status"] == "READY"),
        "status": report["status"],
        "process_bitness": report["python_process_bitness"],
        "host": {"path": host.get("path"), "bitness": host.get("bitness"), "status": host.get("status"), "reason": host.get("reason")},
        "runasadmin_detected": report["runasadmin_detected"],
        "activation": activation,
    }
    # A declared runtime is checked against the one COM would actually activate.
    # Windows resolves a bare ProgId per machine, so on a host carrying more than one
    # Office the caller could silently get an install they did not mean.
    registered = [
        entry.get("executable") for view in report.get("registry", {}).get("views", {}).values()
        for entry in [view.get("access", {})] if entry.get("executable")
    ]
    runtime["declared_runtime"] = {
        "requested_path": args.access_path,
        "requested_prog_id": args.access_progid,
        "registered_paths": registered,
        "matches": None if not args.access_path else any(
            Path(str(found)).resolve() == Path(args.access_path).expanduser().resolve()
            for found in registered
        ),
    }
    return runtime, host


def main() -> int:
    args = parse_args()
    source = Path(args.database).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Access database not found: {source}")
    fmt = source.suffix.lower().lstrip(".")
    if fmt not in {"mdb", "accdb", "adp"}:
        raise SystemExit("Supported Access formats are .mdb, .accdb, and .adp")
    if args.password_env and not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.password_env):
        raise SystemExit("--password-env must be a valid environment variable name")
    if args.password_env and args.execute and args.password_env not in os.environ:
        raise SystemExit(f"Password environment variable is not set: {args.password_env}")
    session_id = args.session_id or datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", session_id):
        raise SystemExit("--session-id may contain only letters, digits, underscores, and hyphens")
    output = Path(args.output_dir).expanduser().resolve() / args.database_id / session_id
    # A frontend that resolves its backend as a sibling - CurrentProject.Path plus a
    # file name, the ordinary Access split pattern - cannot open it from a snapshot
    # directory holding one database. The caller may point every database of one
    # application at a shared directory so that layout survives.
    snapshot_root = (
        Path(args.snapshot_dir).expanduser().resolve() if args.snapshot_dir
        else output / "snapshot"
    )
    snapshot = snapshot_root / source.name
    runtime, host = build_runtime_block(args)
    plan = {
        "schema_version": "2.1", "database_id": args.database_id, "session_id": session_id,
        "source": {"path": str(source), "format": fmt, "sha256": sha256(source)},
        "snapshot": {"path": str(snapshot), "sha256": sha256(source)},
        "status": "PREFLIGHT_ONLY", "runtime": runtime,
        "project_context": {}, "components": [],
        "warnings": ["The original database will never be opened; execution uses a copied snapshot.", "ADP extraction requires a compatible legacy Access runtime." if fmt == "adp" else "Access/ACE automation is required for executable extraction."],
    }
    # A declared runtime that does not match the one COM will activate used to be
    # recorded as matches: false inside the receipt and read by nobody, so the run
    # proceeded against an install the operator had explicitly said it was not. The
    # declaration only means something if violating it stops the run.
    declared = runtime.get("declared_runtime", {})
    if declared.get("requested_path") and declared.get("matches") is False:
        registered = ", ".join(str(item) for item in declared.get("registered_paths") or []) or "none registered"
        plan["status"] = "BLOCKED"
        plan["warnings"].append(
            f"Declared Access runtime {declared['requested_path']} is not the registered COM server "
            f"({registered}). Register the declared install, correct runtime.access_path, or remove "
            "the declaration to accept whichever install Windows resolves."
        )
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 3
    if runtime.get("runasadmin_detected"):
        plan["warnings"].append("The registered Access executable has a RunAsAdmin compatibility flag; use --allow-run-as-invoker if COM activation prompts for elevation.")
    if args.dry_run or not args.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    if not args.skip_runtime_check and runtime.get("status") != "READY":
        # Fail before copying a snapshot when the runtime cannot actually be
        # activated, and explain the most likely remedy.
        plan["status"] = "BLOCKED"
        effective = runtime.get("status")
        activation = runtime.get("activation", {})
        if effective == "REGISTERED_BUT_ACTIVATION_FAILED":
            # --allow-run-as-invoker was advised here for years and cannot work:
            # __COMPAT_LAYER is set on the PowerShell host, while the Access COM server
            # is launched by the service and does not inherit the parent environment.
            # Verified against a RUNASADMIN-flagged Access 2003: run_as_invoker true,
            # activation still 0x800702E4.
            plan["warnings"].append(
                "Access is registered but COM activation failed. If the executable carries a RUNASADMIN "
                "compatibility flag, remove RUNASADMIN from its AppCompatFlags\\Layers value or run from an "
                "elevated (Administrator) terminal - --allow-run-as-invoker cannot help, because the COM server "
                "is launched out of process and does not inherit __COMPAT_LAYER. To read schema and the object "
                "inventory without any Access host, pass --skip-object-export; to skip runtime discovery entirely, "
                "pass --skip-runtime-check."
            )
        elif effective in {"INSTALLED_BUT_BITNESS_MISMATCH", "NOT_FOUND"}:
            plan["warnings"].append(
                f"No matching PowerShell host for the registered Access runtime ({host.get('reason') if host else effective}). "
                "Pass --powershell to point at a matching-bitness host, or --skip-runtime-check to bypass discovery."
            )
        else:
            plan["warnings"].append(
                "Access automation is not available on this host (Access/ACE is not registered). "
                "Export the VBA and SQL on a compatible machine and use export mode instead."
            )
        message = activation.get("message")
        if message:
            plan["warnings"].append(f"Activation detail: {str(message)[:500]}")
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 3
    if output.exists() and any(output.iterdir()):
        raise SystemExit(f"Refusing to overwrite immutable extraction session: {output}")
    output.mkdir(parents=True, exist_ok=True)
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, snapshot)
    if sha256(snapshot) != plan["source"]["sha256"]:
        raise SystemExit("Snapshot hash differs from source; extraction aborted")
    script = Path(__file__).resolve().with_name("extract_access.ps1")
    powershell = (host.get("path") if host and host.get("path") else None) or args.powershell or "powershell"
    command = [powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script), "-Snapshot", str(snapshot), "-DatabaseId", args.database_id, "-SessionId", session_id, "-OutputDir", str(output)]
    if args.password_env:
        command += ["-PasswordEnvironment", args.password_env]
    command += ["-AccessProgId", args.access_progid, "-DaoProgId", args.dao_progid]
    if args.skip_object_export:
        command.append("-SkipObjectExport")
    if args.skip_object_inventory:
        command.append("-SkipObjectInventory")
    if args.visible_host:
        command.append("-VisibleHost")
    env = os.environ.copy()
    if args.allow_run_as_invoker:
        env["__COMPAT_LAYER"] = "RunAsInvoker"
    try:
        completed = subprocess.run(command, check=False, env=env, timeout=args.timeout)
    except subprocess.TimeoutExpired:
        # Without this the run waited forever. A real application's startup VBA can
        # drop into the debugger's break mode, and because the host is hidden there
        # is nothing to click and no output to read.
        killed = terminate_recorded_hosts(output)
        plan["status"] = "BLOCKED"
        plan["warnings"].append(
            f"Access adapter did not finish within {args.timeout}s and was treated as hung. "
            "Startup VBA or a modal dialog can stall a hidden Access host; raise --timeout "
            "if the database is genuinely large."
        )
        if killed:
            plan["warnings"].append(f"Terminated the Access host started by this run: {killed}.")
        result_path = output / "access-extraction.json"
        if not result_path.is_file():
            result_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 4
    if completed.returncode != 0:
        plan["status"] = "BLOCKED"
        plan["warnings"].append(f"Access automation adapter exited with code {completed.returncode}")
        # Only write the thin plan when the adapter produced nothing. It records
        # the collected warnings and component index, and overwriting that with
        # this stub erased the only account of what actually went wrong.
        result_path = output / "access-extraction.json"
        if not result_path.is_file():
            result_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return completed.returncode
    print(f"Access extraction completed from snapshot: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
