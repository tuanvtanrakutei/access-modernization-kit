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
    parser.add_argument("--allow-run-as-invoker", action="store_true", help="Set __COMPAT_LAYER=RunAsInvoker so an elevated Access install activates without a UAC prompt")
    parser.add_argument("--skip-runtime-check", action="store_true", help="Skip Access runtime discovery and use the default PowerShell host (restores pre-2.3 behavior)")
    return parser.parse_args()


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
    snapshot = output / "snapshot" / source.name
    runtime, host = build_runtime_block(args)
    plan = {
        "schema_version": "2.1", "database_id": args.database_id, "session_id": session_id,
        "source": {"path": str(source), "format": fmt, "sha256": sha256(source)},
        "snapshot": {"path": str(snapshot), "sha256": sha256(source)},
        "status": "PREFLIGHT_ONLY", "runtime": runtime,
        "project_context": {}, "components": [],
        "warnings": ["The original database will never be opened; execution uses a copied snapshot.", "ADP extraction requires a compatible legacy Access runtime." if fmt == "adp" else "Access/ACE automation is required for executable extraction."],
    }
    if runtime.get("runasadmin_detected"):
        plan["warnings"].append("The registered Access executable has a RunAsAdmin compatibility flag; use --allow-run-as-invoker if COM activation prompts for elevation.")
    if args.dry_run or not args.execute:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    if host is not None and host.get("status") != "READY":
        plan["status"] = "BLOCKED"
        plan["warnings"].append(f"Access runtime is not ready: {host.get('reason', 'no compatible host found')}")
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
    env = os.environ.copy()
    if args.allow_run_as_invoker:
        env["__COMPAT_LAYER"] = "RunAsInvoker"
    completed = subprocess.run(command, check=False, env=env)
    if completed.returncode != 0:
        plan["status"] = "BLOCKED"
        plan["warnings"].append(f"Access automation adapter exited with code {completed.returncode}")
        (output / "access-extraction.json").write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return completed.returncode
    print(f"Access extraction completed from snapshot: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
