#!/usr/bin/env python3
"""Capture every form as it runs, and read what each control shows at runtime (A93).

A design-view capture shows a list as one row and no data; a runtime mockup drawn from
definitions is only as faithful as the rules that draw it. This runs the application on
copies and opens each form the way an operator would - in the view it opens in - so the
two can be compared: `$ak wireframes --check-runtime` reports how far the mockup agrees.

What it does, in order, all on copies in a temporary folder:

- the frontend and every other Access file under `input/access/` are copied, and a linked
  table whose target has the name of a copy is re-pointed at it, so the application reads
  the supplied data wherever production keeps it (a mapped drive, a share);
- the start-up form is removed, so the application's own start-up code does not run;
- each form opens in its default view (a datasheet as a datasheet), the Access window is
  captured with any pop-up form drawn where it sits, and each control's runtime
  properties are read (visibility, enabled, geometry, colours, back style, border and
  effect, font size and weight, conditional formats);
- with `--code auto` (the default), if this host cannot load the application's VBA - the
  first form with a module is cancelled on opening - every form's code-behind is removed
  on the copy before capturing. The result records which forms lost it and which of their
  opening procedures (`Form_Open`, `Form_Load`, `Form_Activate`, `Form_Current`) went with
  it: a capture of such a form shows what its definition and data show, not what that code
  would have changed. `--code keep` never removes it; `--code strip` always does.

Writes `input/screenshots/runtime/` (one PNG per form, by index, and `capture-log.txt`
mapping each to its form) and `.ak/extracted/runtime-view.json` (properties only, no
row of data). Needs `access_snapshot_extract`. Windows only.

    python scripts/capture_runtime_view.py --app-root <APP_ROOT> \\
        --authorize access_snapshot_extract [--code auto|keep|strip]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "scripts", PACKAGE / "contracts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import access_runtime  # noqa: E402
import collect_mockup_data as mockup  # noqa: E402
import derive_graph_facts as deriver  # noqa: E402
import generate_catalogues as catalogues  # noqa: E402
import wireframe  # noqa: E402

AUTHORIZATION = "access_snapshot_extract"
OUTPUT = Path(".ak") / "extracted" / "runtime-view.json"
SHOTS = Path("input") / "screenshots" / "runtime"
OPENING = re.compile(r"^\s*(?:Private|Public)?\s*Sub\s+(Form_(?:Open|Load|Activate|Current))\s*\(", re.I | re.M)
# DoCmd.OpenForm views: acNormal opens a single or continuous form; a datasheet is acFormDS.
VIEW_NORMAL, VIEW_DATASHEET = 0, 3


def requests_for(forms: list[dict[str, Any]], controls: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """What the capture needs per form: its name, the view it opens in, whether it has a
    module, the opening procedures that module holds, and the controls to read."""
    found = []
    for form in forms:
        text = str(form.get("text") or "")
        name = str(form.get("name") or "")
        code = wireframe.CODE_BEHIND.split(text, 1)[1] if wireframe.CODE_BEHIND.search(text) else ""
        names = [str(c.get("name") or "") for c in controls.get(name, []) if c.get("name")]
        if not names:
            names = list(wireframe.definitions(text))
        found.append({
            "name": name,
            "database": str(form.get("database_id") or ""),
            "view": VIEW_DATASHEET if wireframe.form_mode(text)["view"] == "datasheet" else VIEW_NORMAL,
            "has_module": bool(code.strip()),
            "opening": sorted(set(OPENING.findall(code))),
            "controls": names,
        })
    return found


def with_id(line: str, ids: dict[str, str]) -> str:
    """`OK<tab>form<tab>name<tab>file`, with the form's F- id appended when it has one."""
    cells = line.split("\t")
    if len(cells) >= 4 and cells[0] == "OK" and cells[1] == "form" and ids.get(cells[2]):
        return line + "\t" + ids[cells[2]]
    return line


def _listed(value: Any) -> list[Any]:
    """PowerShell 5.1 writes a one-element array as the element itself."""
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def capture(app_root: Path, code: str, timeout: int) -> int:
    bundle = deriver.newest_bundle(app_root)
    if bundle is None:
        print("No acquisition bundle; run `$ak acquire` first.", file=sys.stderr)
        return 2
    inventory = json.loads((bundle / "ui" / "forms" / "inventory.json").read_text(encoding="utf-8"))
    forms = [row for row in inventory if isinstance(row, dict) and row.get("text")
             and str(row.get("kind") or "form") == "form"]
    if not forms:
        print("No form in the bundle carries definition text; nothing to capture.", file=sys.stderr)
        return 2
    controls_file = bundle / "ui" / "controls.json"
    rows = json.loads(controls_file.read_text(encoding="utf-8")) if controls_file.is_file() else []
    controls = {str(r.get("object") or ""): r.get("controls") or [] for r in rows if isinstance(r, dict)}
    host = access_runtime.inspect_access_runtime().get("selected_host") or {}
    if host.get("status") != "READY":
        print(f"No Access host is ready: {host.get('reason') or host.get('status')}", file=sys.stderr)
        return 2
    wanted = requests_for(forms, controls)
    files = mockup.access_files(app_root)
    out_dir = app_root / SHOTS
    out_dir.mkdir(parents=True, exist_ok=True)
    captured: list[dict[str, Any]] = []
    stripped_any = False
    log_lines: list[str] = []
    sources: dict[str, str] = {}
    for database in sorted({r["database"] for r in wanted}):
        front = mockup.database_file(app_root, database, files)
        if front is None:
            print(f"No supplied file for database {database or '(unnamed)'}; skipped.", file=sys.stderr)
            continue
        mine = [r for r in wanted if r["database"] == database]
        with tempfile.TemporaryDirectory(prefix="ak-runtime-") as scratch:
            root = Path(scratch)
            copies = []
            for path in files:
                folder = root / ("front" if path == front else f"back{len(copies)}")
                folder.mkdir()
                copies.append(Path(shutil.copy2(path, folder / path.name)))
                sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            front_copy = next(c for c in copies if c.parent.name == "front")
            request_file = root / "requests.json"
            request_file.write_text(json.dumps(mine, ensure_ascii=False), encoding="utf-8")
            out_file = root / "out.json"
            completed = subprocess.run(
                [host["path"], "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(PACKAGE / "scripts" / "capture_runtime_view.ps1"),
                 "-Database", str(front_copy), "-Backends", ";".join(str(c) for c in copies if c != front_copy),
                 "-Requests", str(request_file), "-OutDir", str(out_dir), "-Out", str(out_file), "-Code", code],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
            )
            if completed.returncode != 0 or not out_file.is_file():
                print(completed.stderr.strip() or completed.stdout.strip(), file=sys.stderr)
                return 1
            payload = json.loads(out_file.read_text(encoding="utf-8-sig"))
            log_lines += [f"SOURCE\t{front.name}\tsha256 {sources[front.name]}",
                          *(out_dir / "capture-log.txt").read_text(encoding="utf-8-sig").splitlines()]
            stripped = bool(payload.get("stripped"))
            stripped_any = stripped_any or stripped
            by_name = {r["name"]: r for r in mine}
            for entry in _listed(payload.get("forms")):
                request = by_name.get(entry.get("name"), {})
                entry["controls"] = _listed(entry.get("controls"))
                entry["code_removed"] = stripped and bool(request.get("has_module"))
                entry["opening_removed"] = request.get("opening", []) if entry["code_removed"] else []
                captured.append(entry)
    # A reader looks a capture up by its F- id: append it where the phase register has one.
    ids = catalogues.screen_indices(app_root / "output") if (app_root / "output").is_dir() else {}
    log_lines = [with_id(line, ids) for line in log_lines]
    (out_dir / "capture-log.txt").write_text("\n".join(log_lines) + "\n", encoding="utf-8")
    record = {
        "schema_version": "1.0",
        "evidence_class": "SCREENSHOT",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "bundle": bundle.name,
        "source_sha256": sources,
        "code_removed": stripped_any,
        "forms": captured,
    }
    target = app_root / OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    ok = [f for f in captured if not f.get("error")]
    failed = [f["name"] for f in captured if f.get("error")]
    changed = [f["name"] for f in captured if f.get("opening_removed")]
    print(f"captured {len(ok)} of {len(captured)} form(s) into {out_dir}; properties in {target}")
    if stripped_any:
        print("  this host cannot load the application's VBA: code-behind was removed on the copy"
              + (f"; opening code that may change what is shown went with it on: {', '.join(changed)}" if changed else ""))
    if failed:
        print(f"  {len(failed)} could not be opened: {', '.join(failed)}; see capture-log.txt")
    return 0 if not failed else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--app-root", required=True)
    parser.add_argument("--authorize", action="append", default=[])
    parser.add_argument("--code", choices=("auto", "keep", "strip"), default="auto",
                        help="Remove the forms' code-behind on the copy: when VBA does not load (auto), never, or always.")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args(argv)
    if AUTHORIZATION not in args.authorize:
        print(f"Refused: capturing runs the application; pass --authorize {AUTHORIZATION}.", file=sys.stderr)
        return 2
    return capture(Path(args.app_root).resolve(), args.code, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
