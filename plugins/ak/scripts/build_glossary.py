#!/usr/bin/env python3
"""Propose an English name for every production name, for a person to accept.

The catalogues render `商品コード (product_cd?)`. The `?` is the whole point: a
composed name is a proposal, and until somebody who knows the business accepts it,
nothing downstream may treat it as decided.

This writes that decision file - `input/decisions/glossary.yaml` - under `input/`,
because the person owns it and the kit does not. Re-running never overwrites a
decision: an entry a person has edited or marked `accepted` is left exactly as it is,
and only names the run has not seen before are added. So the loop is:

    $ak glossary            propose names for everything not yet decided
    (edit the file)         change what is wrong, set status: accepted
    $ak catalogues          the catalogues render the accepted names, without the `?`

Provenance is recorded per entry and matters more than it looks. A term already
decided in the A01 conversion table is precedent binding on later projects; if A05
spells `商品コード` differently from A01, the two systems cannot be integrated later
without a mapping nobody wrote down. Those entries are marked `A01` and a reviewer
should need a reason to override one.
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

import bilingual as bilingual_contract  # noqa: E402
import workspace as workspace_contract  # noqa: E402

HEADER = """# English names for this application's production names.
#
# You own this file. `$ak glossary` adds names it has not proposed before and never
# touches an entry you have edited or accepted.
#
# For each entry:
#   en          the English name. Change it freely.
#   status      `proposed` until you accept it. Set `accepted` and the catalogues
#               stop marking it with a `?`.
#   provenance  `A01` means this name is already decided in the A01 conversion table -
#               overriding it makes the two systems disagree, so have a reason.
#               `analysis` means the kit proposed it from the Japanese.
#   covered     how much of the Japanese name matched a known term. Below 1.0 the
#               proposal is partial and needs finishing by hand.
#
# Nothing here changes a production name. Every document still carries the Japanese
# name as authoritative; this is the second name printed beside it.
"""


def collect(bundle: Path) -> dict[str, list[str]]:
    def rows(relative: str) -> list[dict]:
        path = bundle / relative
        if not path.is_file():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [r for r in data if isinstance(r, dict)]
        for value in data.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value
        return []

    def names(relative: str, key: str = "name") -> list[str]:
        return sorted({str(r.get(key, "")) for r in rows(relative) if r.get(key)})

    return {
        "tables": names("databases/tables.json"),
        "columns": names("databases/fields.json"),
        "screens": sorted(set(names("ui/forms/inventory.json"))
                          | set(names("ui/reports/inventory.json"))),
        "queries": names("code/access-sql/inventory.json"),
        "modules": names("code/vba/inventory.json"),
    }


def existing(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    found: dict[str, dict[str, Any]] = {}
    for section, entries in data.items():
        if isinstance(entries, dict):
            for japanese, entry in entries.items():
                if isinstance(entry, dict):
                    found[str(japanese)] = entry
    return found


def quote(text: str) -> str:
    """YAML-safe key. Quoted always, because `No` is a boolean in YAML 1.1."""
    return '"' + str(text).replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    space = workspace_contract.Workspace(args.app_root)
    bundles = workspace_contract.find_bundle_dirs(space)
    if not bundles:
        print(f"no acquisition bundle under {space.root}; run `$ak acquire` first")
        return 2
    bundle = max(bundles, key=lambda p: (p / "bundle.json").stat().st_mtime)

    target = space.input_dir("decisions") / "glossary.yaml"
    kept = existing(target)
    terms = bilingual_contract.load_terms(PACKAGE)
    accepted = {j: str(e.get("en"))
                for j, e in kept.items()
                if e.get("status") == "accepted" and e.get("en")}

    groups = collect(bundle)
    added = 0
    lines = [HEADER]
    counts: dict[str, dict[str, int]] = {}
    for section, names in groups.items():
        if not names:
            continue
        lines.append(f"\n{section}:")
        summary = {"total": 0, "kept": 0, "accepted": 0, "partial": 0, "a01": 0}
        for japanese in names:
            summary["total"] += 1
            if japanese in kept:
                entry = dict(kept[japanese])
                summary["kept"] += 1
            else:
                rendered = bilingual_contract.compose(japanese, terms, accepted)
                entry = {
                    "en": rendered.english,
                    "status": "proposed",
                    "provenance": rendered.provenance,
                    "covered": round(rendered.covered, 2),
                }
                added += 1
            if entry.get("status") == "accepted":
                summary["accepted"] += 1
            if float(entry.get("covered", 1) or 0) < 0.999:
                summary["partial"] += 1
            if entry.get("provenance") in ("A01", "A01+analysis"):
                summary["a01"] += 1
            rendered_entry = ", ".join(
                f"{key}: {quote(value) if isinstance(value, str) else value}"
                for key, value in entry.items()
            )
            lines.append(f"  {quote(japanese)}: {{{rendered_entry}}}")
        counts[section] = summary

    text = "\n".join(lines) + "\n"
    if args.dry_run:
        for section, summary in counts.items():
            print(f"{section:9s} {summary['total']:4d} names, {summary['kept']:4d} kept, "
                  f"{summary['accepted']:4d} accepted, {summary['partial']:3d} partial, "
                  f"{summary['a01']:4d} touching A01 precedent")
        print(f"\n{added} name(s) would be added to {target}")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    io.open(target, "w", encoding="utf-8", newline="\n").write(text)
    for section, summary in counts.items():
        print(f"{section:9s} {summary['total']:4d} names, {summary['accepted']:4d} accepted, "
              f"{summary['partial']:3d} partial, {summary['a01']:4d} touching A01 precedent")
    print(f"\nwrote {target}")
    print(f"{added} name(s) newly proposed; {sum(c['kept'] for c in counts.values())} "
          "left exactly as you had them")
    if added:
        print("Edit what is wrong, set `status: accepted`, then re-run `$ak catalogues`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
