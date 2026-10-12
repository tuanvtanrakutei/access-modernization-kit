#!/usr/bin/env python3
"""Draw every form the bundle defines, as one self-contained page (A79).

    $ak wireframes --app-root P             write {APP}_Wireframes.html beside the catalogues
    $ak wireframes --app-root P --dry-run   say what it would hold, write nothing

Reads the newest acquisition bundle (`ui/forms/inventory.json` for each form's definition
text, `ui/controls.json` for its controls), the identifier register for each form's `F-`,
and `{APP}_DecisionQueue.json`, when there is one, for the open items that name a form.
Writes one HTML file and nothing else. The page carries no date, so the same inputs give
the same bytes. It will not overwrite a `_Wireframes.html` it did not write.

Legacy as-is: it draws what the definition says, hidden controls included, and proposes
nothing about the replacement. Reports are not drawn.

Exit 0 when the page was written (or would be), 2 when the command cannot run.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import decision_register as dr  # noqa: E402
import generate_catalogues as catalogues  # noqa: E402
import to_be  # noqa: E402
import wireframe  # noqa: E402
import workspace as workspace_contract  # noqa: E402

TEMPLATE = PACKAGE / "templates" / "wireframes.html"
GENERATED = "<!-- generated-by: ak wireframes -->"


def page(app_id: str, screens: list[dict]) -> str:
    data = json.dumps(screens, ensure_ascii=False, separators=(",", ":"))
    # The data sits inside a <script> element: a name holding `</script>` or `<!--` would
    # end or corrupt it. `<` is a JSON escape, so the parsed value is unchanged.
    data = data.replace("<", "\\u003c")
    text = TEMPLATE.read_text(encoding="utf-8")
    return text.replace("{{APP_ID}}", app_id).replace("{{SCREENS_JSON}}", data)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--app-id", help="Defaults to the manifest's app id, else the folder name.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace-handwritten", action="store_true",
                        help="Overwrite a _Wireframes.html this command did not write.")
    args = parser.parse_args()

    space = workspace_contract.Workspace(args.app_root)
    bundles = workspace_contract.find_bundle_dirs(space)
    if not bundles:
        print(f"no acquisition bundle under {space.root}; run `$ak acquire` first", file=sys.stderr)
        return 2
    bundle = max(bundles, key=lambda p: (p / "bundle.json").stat().st_mtime)
    app_id = args.app_id or catalogues.read_app_id(space.root) or space.root.name
    output = space.output_dir()

    forms = catalogues.rows_of(catalogues.read_json(bundle / "ui" / "forms" / "inventory.json"))
    controls = {str(r.get("object") or ""): r.get("controls") or []
                for r in catalogues.rows_of(catalogues.read_json(bundle / "ui" / "controls.json"))
                if str(r.get("kind") or "form") == "form"}
    queue_files = dr._find(output, "*_DecisionQueue.json") if output.is_dir() else []
    queue = dr.read_register(queue_files[0]) if len(queue_files) == 1 else None
    texts = {str(item.get("name") or ""): str(item.get("text") or "") for item in forms}
    mockup_file = space.root / ".ak" / "extracted" / "mockup-data.json"
    mockup = catalogues.read_json(mockup_file) if mockup_file.is_file() else None
    screens = wireframe.build(forms, controls, catalogues.screen_indices(output), queue, mockup)
    if mockup is None:
        print("  no mockup data; run `$ak mockup-data` to fill the runtime view with the "
              "application's own rows (values are made up from field types until then)")

    # A92. The neutral to-be beside each legacy screen, scoped by the project's recorded
    # decisions, so the two can be compared before any code exists.
    intent_dir = space.input_dir("target-intent")
    records = [dr.read_text(p) for p in sorted(intent_dir.glob("*.md"))
               if p.name.lower() != "readme.md"] if intent_dir.is_dir() else []
    excluded = to_be.out_of_scope_objects(records)
    ids = {s["name"]: s["id"] for s in screens if s["id"]}
    for s in screens:
        s["to_be"] = to_be.propose(s, texts.get(s["name"], ""), ids, excluded)

    drawn = sum(len(s["controls"]) for s in screens)
    hidden = sum(s["hidden"] for s in screens)
    print(f"{len(screens)} form(s), {drawn} control(s) drawn, {hidden} hidden from an operator, "
          f"{sum(1 for s in screens if s['id'])} with an F- identifier"
          + ("" if queue is not None else "; no decision queue, so no open items are shown"))
    without = [s["name"] for s in screens if not s["controls"]]
    if without:
        print(f"  {len(without)} form(s) with no controls in ui/controls.json: {', '.join(without[:5])}")

    registers = output / "registers"
    model = [{k: v for k, v in s.items() if k not in ("data", "row_sources", "to_be")} for s in screens]
    proposals = [s["to_be"] for s in screens]
    path = output / f"{app_id}_Wireframes.html"
    text = page(app_id, screens)
    if path.exists() and GENERATED not in dr.read_text(path)[:600] and not args.replace_handwritten:
        print(f"error: {path.name} exists and this command did not write it; move it aside, "
              "or pass --replace-handwritten", file=sys.stderr)
        return 2
    if args.dry_run:
        print(f"dry run: would write {path} ({len(text):,} bytes)")
        return 0
    output.mkdir(parents=True, exist_ok=True)
    # The model and the proposal, for the modernize pipeline to read. Neither carries a
    # row of data: the mockup's rows stay in the workspace's `.ak/extracted/`.
    registers.mkdir(parents=True, exist_ok=True)
    for name, payload in ((f"{app_id}_ScreenModel.json", model), (f"{app_id}_ToBe.json", proposals)):
        dr.atomic_write(registers / name, json.dumps(
            {"app_id": app_id, "generated_by": "ak wireframes", "status": "proposal" if "ToBe" in name else "legacy as-is",
             "screens": payload}, ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {registers / (app_id + '_ScreenModel.json')} and {app_id}_ToBe.json "
          f"({sum(1 for p in proposals if p['pattern'] != 'out of scope')} screens proposed, "
          f"{sum(1 for p in proposals if p['pattern'] == 'out of scope')} out of scope)")
    same = path.is_file() and dr.read_text(path) == text
    if not same:
        dr.atomic_write(path, text)
    print(f"{'unchanged' if same else 'wrote'} {path} ({len(text):,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
