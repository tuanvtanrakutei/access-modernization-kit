#!/usr/bin/env python3
"""Detect candidate Screens_Registry.md rows from a six-phase run's Phase 2 output.

Reports only. It never writes Screens_Registry.md or any other project file -
machine detects, human decides, agent executes. The bootstrap-project skill
presents this script's proposal as one table and waits for a single `ok` /
`cancel` before writing - one accept for the whole batch, not one per row.
That single accept exists for exactly one reason: `module` is a new-system
architecture decision Phase 2 cannot know, so it is the one guess worth a
human's eyes before it is written - everything else below is filled, not
blocked, because it either comes straight from an already-QA'd phase output
or is a deterministic derivation with no real ambiguity.

Everything else in this proposal is filled automatically, not left pending,
because leaving it pending defeats bootstrap automation for the case that is
actually the norm here (Japanese legacy object names) rather than the
exception:

  screen / type / business_purpose / entry_path / evidence_ids
      Taken directly from Phase 2. This step only runs once that phase's
      gate reads PUBLISHED in run-state.json - ak's own six-phase process has
      already QA'd this content (QuestionList.md / QA_Report.md), so
      re-confirming the legacy fact itself here would be redundant, not safe.

  screen_key
      Auto-generated always. ASCII object names are slugified with a
      camelCase/PascalCase-aware split (OrderEntryForm -> order_entry_form),
      since legacy Access object names routinely have no separator at all.
      Non-ASCII names (the common case for a Japanese legacy screen) fall
      back to `screen_<inventory row ID>` - the inventory's own ID column is
      unique per row, so this can never collide, at the cost of a slug that
      is not human-readable until renamed. That rename stays cheap: nothing
      in this pipeline creates an artifact folder keyed on screen_key until
      Stage 1 actually runs for that screen.

  module
      Best-effort guess by word overlap between the row's business purpose
      and each module's declared scope in PROJECT_CONFIG.md section 3, when
      given. Falls back to the literal sentinel `UNASSIGNED` when no config
      was given or no module scored an overlap - written, not blocked, so
      the registry stays syntactically complete; `UNASSIGNED` is chosen to
      be unmistakably a placeholder rather than a real Django app name.

  module_prefix
      Not a guess - a direct lookup of the resolved module's own declared
      URL prefix in the same PROJECT_CONFIG.md section 3 row. `UNASSIGNED`
      only when module itself is `UNASSIGNED`.

  url_segment / fe_route
      Deterministic defaults derived from screen_key, per their own stated
      definitions in Screens_Registry.md ("path segment after the module
      prefix" / "route under FE_ROUTE_BASE") - not guesses either.

`Type` is never used to filter rows out. A legacy Report can become its own
screen in the new system just as often as a Form does; which inventory rows
become registry rows is the one thing left for the accept step to catch, by
reading the table, not for this script to decide by itself.

Exit status: 0 proposal produced, 1 phase2 not ready to seed from (gate not
PUBLISHED, or --ak-run-dir is n/a - fall back to manual seeding), 2 could not
run (bad args, run-state.json/phase2 doc missing or unparseable).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

HEADING_RE = re.compile(r"^#{1,6}\s*1\.\s*Screen,\s*Form,?\s*and\s*Report\s*Inventory", re.IGNORECASE)
NEXT_HEADING_RE = re.compile(r"^#{1,2}\s+\S")
SEPARATOR_ROW_RE = re.compile(r"^\|?[\s:|-]+\|?$")
UNASSIGNED = "UNASSIGNED"

# Canonical column name -> accepted header-cell spellings (case-insensitive, stripped).
COLUMN_ALIASES = {
    "id": {"id"},
    "object": {"object"},
    "type": {"type"},
    "business_purpose": {"business purpose"},
    "entry_path": {"entry path"},
    "evidence_ids": {"evidence ids", "evidence id"},
}
REQUIRED_COLUMNS = {"object"}

# PROJECT_CONFIG.md section 3 "Modules" row: | module | url prefix | owns |
MODULE_ROW_RE = re.compile(
    r"^\|\s*`?([A-Za-z0-9_]+)`?\s*\|\s*`?([^|]*?)`?\s*\|\s*`?([^|]*?)`?\s*\|\s*$",
    re.MULTILINE,
)
# Scope the module-row search to the "### Modules" section only - PROJECT_CONFIG.md has
# other 3-column tables (Shared Backend Components, Naming Conventions) that would
# otherwise false-match the same generic pipe-row shape.
MODULES_HEADING_RE = re.compile(r"^#{1,6}\s*Modules\s*$", re.IGNORECASE)
MODULES_NEXT_HEADING_RE = re.compile(r"^#{1,3}\s+\S")


def io_open(path: str):
    return open(path, encoding="utf-8")


def find_phase2_doc(ak_run_dir: str) -> tuple[str | None, list[str]]:
    # The real output contract (specifications/output-contract.yaml in the sibling ak
    # plugin) names this file "{APP_ID}_Phase2_ScreenAnalysis_{LANG}.md" - "phase2" is a
    # substring after the app ID prefix, not the start of the filename. A `startswith`
    # check here would never match a real run's output, only this plugin's own template
    # (which happens to be named "phase2-screen-analysis.md"). Match as a substring.
    candidates = []
    for root, _dirs, files in os.walk(ak_run_dir):
        for name in files:
            if "phase2" in name.lower() and name.lower().endswith(".md"):
                candidates.append(os.path.join(root, name))
    if not candidates:
        return None, []
    candidates.sort(key=lambda p: (p.count(os.sep), len(p)))
    return candidates[0], candidates[1:]


def read_phase_gates(ak_run_dir: str) -> dict:
    with io_open(os.path.join(ak_run_dir, "run-state.json")) as f:
        return json.load(f).get("phase_gates", {})


def extract_section(text: str, heading_re: "re.Pattern", next_heading_re: "re.Pattern") -> list[str] | None:
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if heading_re.match(line.strip()):
            start = i + 1
            break
    if start is None:
        return None
    block = []
    for line in lines[start:]:
        if next_heading_re.match(line):
            break
        block.append(line)
    return block


def extract_inventory_block(text: str) -> list[str] | None:
    return extract_section(text, HEADING_RE, NEXT_HEADING_RE)


def parse_pipe_table(block: list[str]) -> tuple[list[str], list[list[str]]] | None:
    table_lines = [ln for ln in block if ln.strip().startswith("|")]
    if len(table_lines) < 2:
        return None
    header_cells = [c.strip() for c in table_lines[0].strip().strip("|").split("|")]
    data_rows = []
    for line in table_lines[1:]:
        if SEPARATOR_ROW_RE.match(line.strip()):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < len(header_cells):
            cells += [""] * (len(header_cells) - len(cells))
        data_rows.append(cells[: len(header_cells)])
    return header_cells, data_rows


def map_columns(header_cells: list[str]) -> dict[int, str]:
    mapping = {}
    for idx, raw in enumerate(header_cells):
        norm = raw.strip().lower().strip("*` ")
        for canon, aliases in COLUMN_ALIASES.items():
            if norm in aliases:
                mapping[idx] = canon
                break
    return mapping


def is_ascii(s: str) -> bool:
    try:
        s.encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def slugify_ascii(name: str, case: str) -> str:
    # Legacy Access object names are routinely PascalCase/camelCase (OrderEntryForm,
    # frmOrderEntry) with no separator at all - split word boundaries before
    # collapsing to the target case, or the whole name collapses into one token.
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", name.strip())
    spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", "_", spaced)
    tokens = re.split(r"[^A-Za-z0-9]+", spaced)
    tokens = [t for t in tokens if t]
    sep = "-" if case == "kebab-case" else "_"
    return sep.join(t.lower() for t in tokens)


def fallback_screen_key(row_id: str, priority: int, case: str) -> str:
    ident = re.sub(r"[^A-Za-z0-9]+", "", row_id) or str(priority)
    return f"screen{'-' if case == 'kebab-case' else '_'}{ident}"


def parse_module_table(cfg_text: str) -> list[tuple[str, str, str]]:
    block = extract_section(cfg_text, MODULES_HEADING_RE, MODULES_NEXT_HEADING_RE)
    if not block:
        return []
    rows = []
    for module, prefix, scope in MODULE_ROW_RE.findall("\n".join(block)):
        if not module or module.startswith("{{") or module.upper().startswith("MODULE_"):
            continue
        rows.append((module, prefix, scope))
    return rows


def read_config_value(cfg_text: str, key: str) -> str | None:
    m = re.search(r"^\|\s*`" + re.escape(key) + r"`\s*\|\s*(.+?)\s*\|", cfg_text, re.MULTILINE)
    if not m:
        return None
    value = m.group(1).strip().strip("`")
    if value.startswith("{{") and value.endswith("}}"):
        return None
    return value


def guess_module(business_purpose: str, modules: list[tuple[str, str, str]]) -> tuple[str, str, bool]:
    purpose_tokens = set(re.findall(r"[A-Za-z0-9]+", business_purpose.lower()))
    if not purpose_tokens or not modules:
        return UNASSIGNED, UNASSIGNED, False
    best_module, best_prefix, best_score = UNASSIGNED, UNASSIGNED, 0
    for module, prefix, scope in modules:
        scope_tokens = set(re.findall(r"[A-Za-z0-9]+", scope.lower()))
        score = len(purpose_tokens & scope_tokens)
        if score > best_score:
            best_module, best_prefix, best_score = module, prefix or UNASSIGNED, score
    if best_score == 0:
        return UNASSIGNED, UNASSIGNED, False
    return best_module, best_prefix, True


def build_proposal(
    rows_raw: list[list[str]],
    col_map: dict[int, str],
    case: str,
    modules: list[tuple[str, str, str]],
    fe_route_base: str | None,
):
    proposal = []
    for i, cells in enumerate(rows_raw, start=1):
        record = {}
        for idx, canon in col_map.items():
            record[canon] = cells[idx] if idx < len(cells) else ""
        object_name = record.get("object", "").strip()
        if not object_name:
            continue  # blank padding row, not a real entry
        flags = []
        if is_ascii(object_name):
            screen_key = slugify_ascii(object_name, case)
        else:
            screen_key = fallback_screen_key(record.get("id", ""), i, case)
            flags.append("screen_key_auto_from_row_id_non_ascii_object_name")
        module, module_prefix, guessed = guess_module(record.get("business_purpose", ""), modules)
        if module == UNASSIGNED:
            flags.append("module_unassigned_needs_human_input")
        else:
            flags.append("module_guessed")
        url_segment = screen_key
        fe_route = f"{fe_route_base}/{screen_key}" if fe_route_base else f"/{screen_key}"
        if not fe_route_base:
            flags.append("fe_route_base_not_resolved_relative_path_only")
        proposal.append(
            {
                "priority": i,
                "screen": object_name,
                "screen_key": screen_key,
                "type": record.get("type", "").strip(),
                "business_purpose": record.get("business_purpose", "").strip(),
                "entry_path": record.get("entry_path", "").strip(),
                "evidence_ids": record.get("evidence_ids", "").strip(),
                "module": module,
                "module_prefix": module_prefix,
                "url_segment": url_segment,
                "fe_route": fe_route,
                "status_be": "not_started",
                "status_fe": "not_started",
                "flags": flags,
            }
        )
    return proposal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--ak-run-dir", required=True, help="Root of a six-phase run, or literal 'n/a'")
    parser.add_argument("--screen-key-case", default="snake_case", choices=["snake_case", "kebab-case"])
    parser.add_argument("--project-config", default=None, help="Path to the target project's PROJECT_CONFIG.md")
    parser.add_argument("--out", required=True, help="Where to write the JSON proposal (UTF-8)")
    args = parser.parse_args()

    if args.ak_run_dir.strip().lower() == "n/a":
        print("AK_RUN_DIR is n/a - no phase output to seed from, fall back to manual registry seeding.")
        return 1

    if not os.path.isdir(args.ak_run_dir):
        print(f"error: --ak-run-dir not found: {args.ak_run_dir}", file=sys.stderr)
        return 2

    try:
        gates = read_phase_gates(args.ak_run_dir)
    except FileNotFoundError:
        print("error: run-state.json not found under --ak-run-dir", file=sys.stderr)
        return 2
    except (json.JSONDecodeError, OSError) as exc:
        print(f"error: could not read run-state.json: {exc}", file=sys.stderr)
        return 2

    phase2_gate = gates.get("phase2")
    if phase2_gate != "PUBLISHED":
        print(f"phase2 gate is {phase2_gate!r}, not PUBLISHED - nothing safe to seed from yet.")
        return 1

    doc_path, other_candidates = find_phase2_doc(args.ak_run_dir)
    if doc_path is None:
        print("error: no phase2*.md document found under --ak-run-dir", file=sys.stderr)
        return 2

    with io_open(doc_path) as f:
        text = f.read()

    block = extract_inventory_block(text)
    if block is None:
        print(f"error: heading 'Screen, Form, and Report Inventory' not found in {doc_path}", file=sys.stderr)
        return 2

    parsed = parse_pipe_table(block)
    if parsed is None:
        print(f"error: no pipe table found under the inventory heading in {doc_path}", file=sys.stderr)
        return 2

    header_cells, rows_raw = parsed
    col_map = map_columns(header_cells)
    missing = REQUIRED_COLUMNS - set(col_map.values())
    if missing:
        print(f"error: inventory table missing required column(s): {sorted(missing)}", file=sys.stderr)
        return 2

    modules: list[tuple[str, str, str]] = []
    fe_route_base = None
    if args.project_config and os.path.isfile(args.project_config):
        with io_open(args.project_config) as f:
            cfg_text = f.read()
        modules = parse_module_table(cfg_text)
        fe_route_base = read_config_value(cfg_text, "FE_ROUTE_BASE")

    proposal = build_proposal(rows_raw, col_map, args.screen_key_case, modules, fe_route_base)

    result = {
        "status": "ok",
        "phase2_gate": phase2_gate,
        "source_file": doc_path,
        "other_phase2_candidates": other_candidates,
        "row_count": len(proposal),
        "rows": proposal,
    }
    with open(args.out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    unassigned_count = sum(1 for r in proposal if r["module"] == UNASSIGNED)
    print(
        f"ok: {len(proposal)} candidate row(s) fully filled, {unassigned_count} with module=UNASSIGNED. "
        f"Wrote {args.out}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
