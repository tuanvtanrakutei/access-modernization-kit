#!/usr/bin/env python3
"""Read the rows each screen shows, for the runtime mockup (A91).

A wireframe drawn from definitions alone is a page of empty boxes, and a design-view
capture is one row of a list. What makes a mockup recognisable to the people who use the
screen is its data: the list filled, the drop-down holding its choices, the subform showing
the records of the selected parent. This reads that data from the application itself.

For every form in the newest bundle it reads the first rows of the form's record source,
and for every combo and list box whose row source is a table or query, the first rows of
that. It runs on copies, never the originals: the frontend and every other declared Access
database are copied to a temporary folder, and a linked table whose target file has the
name of one of those copies is re-pointed at it, so a join through a link resolves.

Writes `.ak/extracted/mockup-data.json`, DATA_STATE evidence: what the database held when
the copy was taken, with each source file's SHA-256. A source that cannot be read - a
query calling a VBA function, a link with no supplied target - is recorded with its error,
and the page falls back to values made up from the field's type, marked as such.

    python scripts/collect_mockup_data.py --app-root <APP_ROOT> \\
        --authorize access_snapshot_extract [--rows 20]

The file holds customer data. It stays in the workspace and is never part of the kit.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "scripts", PACKAGE / "contracts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import access_runtime  # noqa: E402
import derive_graph_facts as deriver  # noqa: E402
import wireframe  # noqa: E402

AUTHORIZATION = "access_snapshot_extract"
SUFFIXES = {".mdb", ".accdb"}
OUTPUT = Path(".ak") / "extracted" / "mockup-data.json"


def requests_for(forms: list[dict]) -> list[dict[str, str]]:
    """One request per form record source and per table/query row source."""
    found: list[dict[str, str]] = []
    for form in forms:
        text = str(form.get("text") or "")
        database, name = str(form.get("database_id") or ""), str(form.get("name") or "")
        source = wireframe.layout(text)["record_source"].strip()
        if source:
            found.append({"key": f"{database}::form::{name}", "database": database, "source": source})
        for control, definition in wireframe.definitions(text).items():
            props = definition.get("props") or {}
            if definition.get("block") not in ("ComboBox", "ListBox"):
                continue
            row_source = str(props.get("RowSource") or "").strip()
            kind = str(props.get("RowSourceType") or "Table/Query")
            if row_source and kind == "Table/Query":
                found.append({"key": f"{database}::rows::{name}::{control}",
                              "database": database, "source": row_source})
    return found


def access_files(app_root: Path) -> list[Path]:
    return sorted(p for p in (app_root / "input" / "access").glob("*") if p.suffix.lower() in SUFFIXES)


def database_file(app_root: Path, database_id: str, files: list[Path]) -> Path | None:
    """The supplied file behind a bundle database id, read from the manifest."""
    manifest = app_root / "manifest.yaml"
    try:
        import yaml
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    except (OSError, ImportError, ValueError):
        data = {}
    for artifact in data.get("artifacts") or []:
        if isinstance(artifact, dict) and artifact.get("id") == database_id:
            value = str((artifact.get("source_ref") or {}).get("value") or "")
            candidate = (app_root / value).resolve()
            if candidate.is_file():
                return candidate
    return files[0] if len(files) == 1 else None


def collect(app_root: Path, rows: int, timeout: int) -> int:
    bundle = deriver.newest_bundle(app_root)
    if bundle is None:
        print("No acquisition bundle; run `$ak acquire` first.", file=sys.stderr)
        return 2
    inventory = json.loads((bundle / "ui" / "forms" / "inventory.json").read_text(encoding="utf-8"))
    forms = [row for row in inventory if isinstance(row, dict) and row.get("text")]
    wanted = requests_for(forms)
    if not wanted:
        print("No form in the bundle carries definition text; nothing to read.", file=sys.stderr)
        return 2
    host = access_runtime.inspect_access_runtime().get("selected_host") or {}
    if host.get("status") != "READY":
        print(f"No Access host is ready: {host.get('reason') or host.get('status')}", file=sys.stderr)
        return 2
    files = access_files(app_root)
    results: dict[str, dict] = {}
    relinked: list[str] = []
    sources: dict[str, str] = {}
    for database in sorted({r["database"] for r in wanted}):
        front = database_file(app_root, database, files)
        if front is None:
            for r in wanted:
                if r["database"] == database:
                    results[r["key"]] = {"columns": [], "rows": [], "error": "no supplied file for this database"}
            continue
        with tempfile.TemporaryDirectory(prefix="ak-mockup-") as scratch:
            root = Path(scratch)
            copies: list[Path] = []
            for path in files:
                folder = root / ("front" if path == front else f"back{len(copies)}")
                folder.mkdir()
                copies.append(Path(shutil.copy2(path, folder / path.name)))
                sources[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            front_copy = next(c for c in copies if c.parent.name == "front")
            backends = ";".join(str(c) for c in copies if c != front_copy)
            request_file = root / "requests.json"
            request_file.write_text(json.dumps([r for r in wanted if r["database"] == database],
                                               ensure_ascii=False), encoding="utf-8")
            out_file = root / "out.json"
            completed = subprocess.run(
                [host["path"], "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                 str(PACKAGE / "scripts" / "collect_mockup_data.ps1"),
                 "-Database", str(front_copy), "-Backends", backends,
                 "-Requests", str(request_file), "-Out", str(out_file), "-Rows", str(rows)],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
            )
            if completed.returncode != 0 or not out_file.is_file():
                print(completed.stderr.strip() or completed.stdout.strip(), file=sys.stderr)
                return 1
            payload = json.loads(out_file.read_text(encoding="utf-8-sig"))
            # PowerShell 5.1 writes a one-element array as the element itself, so a source
            # with one row or one column arrives unwrapped.
            for key, entry in (payload.get("results") or {}).items():
                for field in ("rows", "columns"):
                    value = entry.get(field)
                    if value is None:
                        entry[field] = []
                    elif not isinstance(value, list):
                        entry[field] = [value]
                results[key] = entry
            linked = payload.get("relinked") or []
            relinked += linked if isinstance(linked, list) else [linked]
    record = {
        "schema_version": "1.0",
        "evidence_class": "DATA_STATE",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "rows_per_source": rows,
        "bundle": bundle.name,
        "source_sha256": sources,
        "relinked": sorted(set(relinked)),
        "results": results,
    }
    target = app_root / OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failed = sorted(k for k, v in results.items() if v.get("error"))
    print(f"read {len(results) - len(failed)} of {len(results)} source(s) into {target}"
          + (f"; {len(failed)} could not be read: {', '.join(failed)}" if failed else ""))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--app-root", required=True)
    parser.add_argument("--authorize", action="append", default=[])
    parser.add_argument("--rows", type=int, default=20)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args(argv)
    if AUTHORIZATION not in args.authorize:
        print(f"Refused: reading rows opens the application's database; pass --authorize {AUTHORIZATION}.",
              file=sys.stderr)
        return 2
    return collect(Path(args.app_root).resolve(), args.rows, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
