#!/usr/bin/env python3
"""Capture every form and report of an Access database in design view (A90).

A screenshot is the one evidence class Phase 2 degrades without, and the one an
operator often cannot supply: the application needs a mapped drive, a master on a
share, a printer - and does not start on the analyst's machine. Design view needs none
of that. It shows each object as its definition lays it out, with tabs, disabled
buttons and labels, and it runs no event code.

What it is not: a runtime capture. It shows no data, no tab order, and nothing about
which screens anyone opens. A phase that cites it says so.

Safety, in the order it is applied:

- the original is never opened: a copy is made in a temporary directory;
- the copy's `StartupForm` property is deleted before Access opens it, so the
  application's own start-up code does not run;
- each object opens in design view, which runs no event procedure;
- it needs the same authorization as acquisition, `access_snapshot_extract`, because it
  starts an Access host on the application.

    python scripts/capture_design_view.py --app-root <APP_ROOT> \\
        --authorize access_snapshot_extract [--database input/access/<FILE>.mdb]

Writes `<APP_ROOT>/input/screenshots/design-view/` with one PNG per object and a
`capture-log.txt` mapping each file to the object it shows. Windows only.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "scripts"))

import access_runtime  # noqa: E402

AUTHORIZATION = "access_snapshot_extract"
SUFFIXES = {".mdb", ".accdb"}


def frontends(app_root: Path) -> list[Path]:
    """The Access files to capture when none is named: those holding forms or reports
    cannot be told from the file, so every database under input/access/ is offered and
    one with no forms simply yields an empty log."""
    folder = app_root / "input" / "access"
    return sorted(p for p in folder.glob("*") if p.suffix.lower() in SUFFIXES)


def capture(database: Path, out_dir: Path, timeout: int) -> int:
    runtime = access_runtime.inspect_access_runtime()
    host = runtime.get("selected_host") or {}
    if host.get("status") != "READY":
        print(f"No Access host is ready: {host.get('reason') or host.get('status')}", file=sys.stderr)
        return 2
    digest = hashlib.sha256(database.read_bytes()).hexdigest()
    with tempfile.TemporaryDirectory(prefix="ak-design-") as scratch:
        copy = Path(scratch) / f"copy{database.suffix.lower()}"
        shutil.copy2(database, copy)
        completed = subprocess.run(
            [host["path"], "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
             str(PACKAGE / "scripts" / "capture_design_view.ps1"),
             "-Database", str(copy), "-OutDir", str(out_dir)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
    log = out_dir / "capture-log.txt"
    if completed.returncode != 0 or not log.is_file():
        print(completed.stderr.strip() or completed.stdout.strip(), file=sys.stderr)
        return 1
    lines = log.read_text(encoding="utf-8").splitlines()
    log.write_text("\n".join([f"SOURCE\t{database.name}\tsha256 {digest}", *lines]) + "\n",
                   encoding="utf-8")
    ok = sum(1 for line in lines if line.startswith("OK\t"))
    failed = sum(1 for line in lines if line.startswith("FAIL\t"))
    print(f"captured {ok} object(s) from {database.name} into {out_dir}"
          + (f"; {failed} failed, see capture-log.txt" if failed else ""))
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--app-root", required=True)
    parser.add_argument("--database", help="One Access file, relative to the app root. Defaults to every file in input/access/.")
    parser.add_argument("--authorize", action="append", default=[])
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args(argv)
    if AUTHORIZATION not in args.authorize:
        print(f"Refused: capturing starts Access on the application; pass --authorize {AUTHORIZATION}.",
              file=sys.stderr)
        return 2
    app_root = Path(args.app_root).resolve()
    databases = [app_root / args.database] if args.database else frontends(app_root)
    if not databases:
        print("No Access file under input/access/.", file=sys.stderr)
        return 2
    status = 0
    for database in databases:
        out_dir = app_root / "input" / "screenshots" / "design-view"
        if len(databases) > 1:
            out_dir = out_dir / database.stem
        status = max(status, capture(database, out_dir, args.timeout))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
