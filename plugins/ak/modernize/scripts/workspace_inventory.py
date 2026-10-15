"""Screen inventory read from a five-phase workspace that has no run-state.json.

A workspace built phase by phase (`$ak init`, the extraction verbs, documents written and
checked with `$ak conformance`) never writes `run-state.json`; only `$ak run` does. The
registry seeder used to require that file and stopped on every such workspace, so a
project's first registry was typed by hand from Phase 2 - the step bootstrap exists to
automate.

Everything here is already in the workspace, written by the kit:

  phase 2 gate   `$ak conformance` on the Phase 2 document: no FAIL check reads CONFORMS.
                 It stands in for `phase_gates.phase2 == PUBLISHED`; both mean the kit's
                 own checks passed the document.
  screens        the `F-` identifiers of the register (`{APP}_Identifiers.json`), with
                 their production names. A title ending ` (report)` is the report of a
                 form with the same name.
  who opens what `.ak/extracted/derived-extraction.json`: an edge from a form to a form or
                 report is a reference in its code or definition.
  embedded       `{APP}_ScreenModel.json`: a subform control's SourceObject. An embedded
                 form is part of its parent's screen, not a screen of its own.
  entry points   the Phase 2 `Entry points` table; without one, a form nothing references
                 that references other forms.
  scope          `input/target-intent/*.md` rows marking an object `out of scope`, read the
                 way the wireframe builder reads them.

A form reached from an entry point is a screen to build. A form nothing reaches goes to
Future Scope: the legacy application cannot open it, so whether it is wanted is a question,
not a task. A report is printed by the form that opens it and travels with that row.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import deque
from pathlib import Path

ENTRY_HEADING = re.compile(r"^#{2,6}\s*(?:\d+(?:\.\d+)*\s*)?Entry points\s*$", re.IGNORECASE)
F_ID = re.compile(r"^F-\d+$")
REPORT_SUFFIX = " (report)"


def is_workspace(path: str) -> bool:
    root = Path(path)
    return (root / "manifest.yaml").is_file() and (root / "output").is_dir()


def phase2_document(root: Path) -> Path | None:
    found = sorted((root / "output").glob("*_Phase2_ScreenAnalysis_*.md"))
    return found[0] if found else None


def app_id_of(phase2: Path) -> str:
    return phase2.name.split("_Phase2_", 1)[0]


def conformance_gate(root: Path, phase2: Path) -> tuple[str, str]:
    """`CONFORMS` when the kit's conformance check finds no failure in the Phase 2 document."""
    ak = Path(__file__).resolve().parents[2] / "scripts" / "ak.py"
    if not ak.is_file():
        return "UNKNOWN", f"conformance not available: {ak} not found"
    proc = subprocess.run(
        [sys.executable, str(ak), "conformance", "--outputs", str(root / "output"), "--json"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return "UNKNOWN", (proc.stderr or proc.stdout).strip()[-400:]
    for phase in report.get("phases") or []:
        if phase.get("document") == phase2.name:
            failed = [c["check"] for c in phase.get("checks") or [] if c.get("status") == "FAIL"]
            return ("FAILS", ", ".join(failed)) if failed else ("CONFORMS", "")
    return "UNKNOWN", f"{phase2.name} is not in the conformance report"


def _load(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def identifiers(root: Path, app: str) -> list[tuple[str, str, str]]:
    """(id, object, kind) for every F- identifier, in id order."""
    entries = _load(root / "output" / "registers" / f"{app}_Identifiers.json").get("entries") or []
    out = []
    for e in entries:
        ident, title = str(e.get("id") or ""), str(e.get("title") or "").strip()
        if not F_ID.match(ident) or not title:
            continue
        kind = "report" if title.endswith(REPORT_SUFFIX) else ""
        out.append((ident, title[: -len(REPORT_SUFFIX)] if kind else title, kind))
    return sorted(out, key=lambda r: int(r[0].split("-")[1]))


def references(root: Path) -> tuple[dict[str, set[str]], dict[str, set[str]], set[str], set[str], set[str]]:
    """Form-to-form and form-to-report edges, the form and report names, and forms a module opens."""
    graph = _load(root / ".ak" / "extracted" / "derived-extraction.json")
    kind_of = {}
    for node in graph.get("nodes") or []:
        node_id, label = str(node.get("id") or ""), str(node.get("label") or "")
        for kind in ("form", "report", "module"):
            if node_id.startswith(kind + "_") and label:
                kind_of[node_id] = (kind, label)
    opens: dict[str, set[str]] = {}
    prints: dict[str, set[str]] = {}
    by_module: set[str] = set()
    for edge in graph.get("edges") or []:
        src, dst = kind_of.get(str(edge.get("source"))), kind_of.get(str(edge.get("target")))
        if not src or not dst:
            continue
        if src[0] == "form" and dst[0] == "form" and src[1] != dst[1]:
            opens.setdefault(src[1], set()).add(dst[1])
        elif src[0] == "form" and dst[0] == "report":
            prints.setdefault(src[1], set()).add(dst[1])
        elif src[0] == "module" and dst[0] == "form":
            by_module.add(dst[1])
    forms = {label for kind, label in kind_of.values() if kind == "form"}
    reports = {label for kind, label in kind_of.values() if kind == "report"}
    return opens, prints, forms, reports, by_module


def embedded_forms(root: Path, app: str) -> dict[str, str]:
    """Embedded form name -> the form it is embedded in."""
    model = _load(root / "output" / "registers" / f"{app}_ScreenModel.json")
    out = {}
    for screen in model.get("screens") or []:
        for control in screen.get("controls") or []:
            source = str((control.get("style") or {}).get("SourceObject") or "")
            if control.get("kind") == "subform" and source:
                out[re.sub(r"^(?:Form|Report)\.", "", source)] = screen.get("name") or ""
    return out


def entry_points(phase2: Path) -> list[str]:
    lines = phase2.read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if not ENTRY_HEADING.match(line.strip()):
            continue
        table = []
        for row in lines[i + 1:]:
            if row.startswith("#"):
                break
            if row.strip().startswith("|"):
                table.append([c.strip().strip("`") for c in row.strip().strip("|").split("|")])
        if len(table) > 2:
            header = [c.lower() for c in table[0]]
            if "object" in header:
                col = header.index("object")
                return [r[col] for r in table[2:] if len(r) > col and r[col]]
    return []


def out_of_scope(root: Path) -> set[str]:
    contracts = Path(__file__).resolve().parents[2] / "contracts"
    sys.path.insert(0, str(contracts))
    try:
        from to_be import out_of_scope_objects
    finally:
        sys.path.remove(str(contracts))
    folder = root / "input" / "target-intent"
    texts = [p.read_text(encoding="utf-8") for p in sorted(folder.glob("*.md"))
             if p.name.lower() != "readme.md"] if folder.is_dir() else []
    return out_of_scope_objects(texts)


def inventory(path: str) -> dict:
    """Records for the registry: `active`, `future` and `excluded`, each a list of dicts."""
    root = Path(path)
    phase2 = phase2_document(root)
    if phase2 is None:
        raise FileNotFoundError("no output/*_Phase2_ScreenAnalysis_*.md in the workspace")
    app = app_id_of(phase2)
    gate, gate_detail = conformance_gate(root, phase2)
    ids = identifiers(root, app)
    if not ids:
        raise FileNotFoundError(f"no F- identifiers in output/registers/{app}_Identifiers.json")
    opens, prints, forms, reports, by_module = references(root)
    embedded = embedded_forms(root, app)
    excluded_names = out_of_scope(root)

    id_of: dict[tuple[str, str], str] = {}
    for ident, name, kind in ids:
        kind = kind or ("form" if name in forms or name not in reports else "report")
        id_of.setdefault((kind, name), ident)

    entries = [e for e in entry_points(phase2) if e in forms] or sorted(
        f for f in forms
        if opens.get(f) and not any(f in targets for targets in opens.values()) and f not in by_module)
    reached = set(entries) | by_module
    queue = deque(reached)
    while queue:
        for target in opens.get(queue.popleft(), ()):
            if target not in reached:
                reached.add(target)
                queue.append(target)

    printed_by = {r: sorted(f for f, rs in prints.items() if r in rs) for r in reports}

    def screen_of(form: str) -> str:
        while form in embedded:
            form = embedded[form]
        return form

    active, future, excluded = [], [], []
    for (kind, name), ident in sorted(id_of.items(), key=lambda kv: int(kv[1].split("-")[1])):
        record = {"id": ident, "object": name, "type": kind}
        if name in excluded_names or ident in excluded_names:
            excluded.append({**record, "reason": "out of scope by a recorded decision"})
        elif kind == "form" and name in embedded:
            continue
        elif kind == "report":
            owners = [screen_of(f) for f in printed_by.get(name, [])]
            if not owners:
                future.append({**record, "reason": "no form opens it"})
            elif all(o in excluded_names for o in owners):
                excluded.append({**record, "reason": f"printed only by {', '.join(owners)}, out of scope"})
        elif name in reached:
            active.append(record)
        else:
            future.append({**record, "reason": "nothing in the legacy application opens it"})

    names = {r["object"]: r for r in active + future}
    for report, owners in printed_by.items():
        for owner in {screen_of(f) for f in owners}:
            row = names.get(owner)
            if row is not None and report not in excluded_names:
                row.setdefault("prints", []).append(f"{id_of.get(('report', report), '')} {report}".strip())
    for child, parent in embedded.items():
        row = names.get(screen_of(parent))
        if row is not None:
            row.setdefault("embeds", []).append(f"{id_of.get(('form', child), '')} {child}".strip())
    for row in names.values():
        for key in ("prints", "embeds"):
            if key in row:
                row[key] = sorted(row[key])

    entry_first = {name: i for i, name in enumerate(entries)}
    active.sort(key=lambda r: (entry_first.get(r["object"], len(entries)), int(r["id"].split("-")[1])))
    return {
        "app_id": app,
        "gate": gate,
        "gate_detail": gate_detail,
        "phase2_document": str(phase2),
        "entry_points": entries,
        "active": active,
        "future": future,
        "excluded": excluded,
        "sources": [os.path.relpath(p, root) for p in (
            phase2,
            root / "output" / "registers" / f"{app}_Identifiers.json",
            root / "output" / "registers" / f"{app}_ScreenModel.json",
            root / ".ak" / "extracted" / "derived-extraction.json",
            root / "input" / "target-intent",
        ) if p.exists()],
    }
