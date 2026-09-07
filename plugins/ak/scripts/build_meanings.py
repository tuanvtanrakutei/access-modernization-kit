#!/usr/bin/env python3
"""List every table and column that still needs a business meaning, for a person to fill.

The catalogues read `_needs DOCUMENT_` on 121 tables and 1,055 columns, and the file
that fills them in had to be typed from a blank page. Nobody types 1,176 entries from
a blank page, so in practice the column was going to stay empty whatever documents
arrived - the same gap `contracts/meanings.py` was written to close, one step further
out. `$ak glossary` has done this for names since it existed; this is the same loop
for meanings.

**It proposes nothing.** `$ak glossary` can offer `商品コード -> product_cd` because a
name is composed from terms that are themselves decided. A meaning cannot be composed
from anything the kit can read: rule EC-01 says schema and code cannot support a
MEANING claim, and rule EC-03 says `商品マスタ` is not master data because it ends in
`マスタ`. So every entry this writes is blank on purpose. It is a worklist, not a
draft, and the difference is the whole point - a generated guess in this file would be
indistinguishable from an answer, which is exactly the failure the kit exists to
prevent.

What it can do is order the work and put the evidence beside it. Each blank entry
carries, as a comment, what the kit does know: who writes the table, how many objects
name it, how many columns it has. A person filling in `WK集計` reads "no writer
attributable, named by 0 objects" and knows what kind of question to ask; a person
filling in the table 12 forms write to knows it is worth getting right. That is USAGE
and STRUCTURE evidence informing the sentence, not being it.

    $ak meanings              write a blank entry for every subject that has none
    $ak meanings --top 50     just the 50 that matter most, to start somewhere
    (fill some in)            a source is required, and you may be the source
    $ak catalogues            the cells you filled stop reading `_needs DOCUMENT_`

Entries you have written are kept exactly as they are, including for a subject that
has since left the bundle - a meaning somebody sourced is not something to drop
because a table was renamed.
"""
from __future__ import annotations

import argparse
import io
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import sql_relationships as sql_contract  # noqa: E402
import workspace as workspace_contract  # noqa: E402

# The bundle readers, the writer profile and the reference counts come from the
# catalogue generator rather than being copied. They are readers that have to stay in
# step with the bundle layout, and a second copy drifting from the first is the defect
# this kit spends most of its time finding.
import generate_catalogues as catalogues  # noqa: E402

HEADER = """# Business meaning, per table and per column. You own this file.
#
# `$ak meanings` adds a blank entry for every subject that has none, and never changes
# one you have written. Nothing here is ever proposed: a name can be composed from
# terms, a meaning cannot. Rule EC-03 - `商品マスタ` is not master data because it ends
# in `マスタ`.
#
# For each entry:
#   meaning         what it is for, in a sentence. This is the cell a reader sees.
#   evidence_class  DOCUMENT, INTERVIEW or OPERATOR_DECLARATION. Nothing else - CODE
#                   and SCHEMA cannot support a meaning, which is rule EC-01.
#   source          who said it and when: a document and a page, a meeting and a date,
#                   or your own name.
#   role            optional, tables only: master, transaction, work, log. Printed in
#                   bold before the meaning.
#
# AN ENTRY WITHOUT A SOURCE IS IGNORED and its cell keeps reading `_needs DOCUMENT_`.
# That is the rule this kit exists to enforce: "somebody said so at some point" is how
# a guess becomes a fact by repetition.
#
# You may be the source. If you know what a table is for - from working the business,
# from a conversation, from reading the code closely - write it with
# `evidence_class: OPERATOR_DECLARATION` and your name and today's date. That is a
# real claim with somebody answerable for it, and it is what the class is for. What is
# not allowed is a meaning with nobody behind it.
#
#   商品マスタ:
#     role: master
#     meaning: One row per sellable product; discontinued rows are kept, not deleted.
#     evidence_class: OPERATOR_DECLARATION
#     source: Vo Ta Tuan, 2026-09-07, confirmed with 業務課
#
# A column may be keyed two ways. `出荷数量` alone is that column wherever it appears,
# which is usually what you want; `受注データ.出荷数量` is that column in that table
# only, and wins over the bare name.
#
# The comment above a blank entry is what the kit knows - who writes it, what names
# it. It is there to inform your sentence, not to be it.
#
# Re-running keeps every entry. It does not keep comments you write between them.
"""

# `role` is offered for tables because the header names four and a person who has
# one in mind should not have to add the key. It is not part of `is_blank`: a role
# with no meaning behind it is still nothing recorded.
BLANK = {"meaning": "", "evidence_class": "", "source": ""}
BLANK_TABLE = {"role": "", **BLANK}


def quote(text: str) -> str:
    """YAML-safe key. Quoted always, because `No` is a boolean in YAML 1.1."""
    return '"' + str(text).replace(chr(92), chr(92) * 2).replace('"', chr(92) + '"') + '"'


def render(value: Any) -> str:
    if isinstance(value, str):
        return quote(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def existing(path: Path) -> dict[str, dict[str, dict[str, Any]]]:
    """Every entry already in the file, per section. Kept verbatim."""
    if not path.is_file():
        return {"tables": {}, "columns": {}}
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    found: dict[str, dict[str, dict[str, Any]]] = {"tables": {}, "columns": {}}
    for section in found:
        for subject, entry in (data.get(section) or {}).items():
            if isinstance(entry, dict):
                found[section][str(subject)] = entry
    return found


def is_blank(entry: dict[str, Any]) -> bool:
    """Nobody has touched it. Matches the rule in `contracts/meanings.py`."""
    return not any(str(entry.get(key, "") or "").strip()
                   for key in ("meaning", "source", "evidence_class"))


def table_subjects(bundle: Path, writes: Any,
                   referenced: dict[tuple[str, str, str], int],
                   fields: list[dict]) -> list[tuple[str, str, tuple]]:
    """Every table, with the note a person reads and the order to work in."""
    columns: dict[tuple[str, str], int] = defaultdict(int)
    for field in fields:
        columns[(field.get("database_id", ""), field.get("table", ""))] += 1

    subjects = []
    for table in catalogues.rows_of(catalogues.read_json(bundle / "databases" / "tables.json")):
        database, name = table.get("database_id", ""), table.get("name", "")
        if not name:
            continue
        names_it = referenced.get((database, "table", name), 0)
        writers = writes.of(name)
        note = (f"{columns[(database, name)]} column(s); {writes.summary(name)}; "
                f"named by {names_it} object(s)")
        if (table.get("metadata") or {}).get("linked"):
            note += "; linked, so it lives in another file"
        if sql_contract.is_work_table(name):
            note += "; work table by naming convention, which is not a guarantee"
        subjects.append((name, note, (-names_it, -len(writers),
                                      -columns[(database, name)], name)))
    return subjects


def column_subjects(fields: list[dict], types: dict[int, dict[str, str]],
                    ) -> list[tuple[str, str, tuple]]:
    """Column names, keyed bare where shared and scoped where they are not.

    A name in seven tables is one question, not seven, and `contracts/meanings.py`
    resolves a bare name for every table - so asking it once is both less work and a
    truer picture of what the person actually knows.
    """
    tables_of: dict[str, list[str]] = defaultdict(list)
    declared: dict[str, set[str]] = defaultdict(set)
    for field in fields:
        name, table = field.get("name", ""), field.get("table", "")
        if not name or not table:
            continue
        if table not in tables_of[name]:
            tables_of[name].append(table)
        declared[name].add(catalogues.declared_type(field, types)[0])

    subjects = []
    for name, tables in tables_of.items():
        kinds = ", ".join(sorted(declared[name]))
        if len(tables) > 1:
            shown = ", ".join(sorted(tables)[:4])
            more = f" and {len(tables) - 4} more" if len(tables) > 4 else ""
            note = f"in {len(tables)} tables: {shown}{more}; declared {kinds}"
            subjects.append((name, note, (-len(tables), name)))
        else:
            note = f"in {tables[0]} only; declared {kinds}"
            subjects.append((f"{tables[0]}.{name}", note, (-1, name)))
    return subjects


def compose(section: str, subjects: list[tuple[str, str, tuple]],
            kept: dict[str, dict[str, Any]], top: int | None,
            blank: dict[str, str]) -> tuple[list[str], dict[str, int]]:
    """The lines for one section, and what to tell the operator about it."""
    known = {subject for subject, _, _ in subjects}
    ordered = sorted(subjects, key=lambda s: s[2])
    filled = sum(1 for entry in kept.values() if not is_blank(entry))

    lines = [f"{section}:"]
    added = 0
    for subject, note, _ in ordered:
        entry = kept.get(subject)
        if entry is None:
            if top is not None and added >= top:
                continue
            entry = dict(blank)
            added += 1
        if is_blank(entry):
            lines.append(f"  # {note}")
        lines.append(f"  {quote(subject)}:")
        lines += [f"    {key}: {render(value)}" for key, value in entry.items()]

    # A meaning somebody sourced outlives the table it was written for. Dropping it
    # because a bundle no longer lists the subject would lose the one thing here that
    # cost a person something to obtain.
    orphans = sorted(s for s in kept if s not in known and not is_blank(kept[s]))
    for subject in orphans:
        lines.append("  # no longer in the bundle; kept because it is sourced")
        lines.append(f"  {quote(subject)}:")
        lines += [f"    {key}: {render(value)}" for key, value in kept[subject].items()]

    counts = {"total": len(subjects), "filled": filled, "added": added,
              "orphans": len(orphans)}
    return lines, counts


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--top", type=int, help="Only add the N highest-priority "
                        "subjects per section, to start somewhere. Re-run without it "
                        "to add the rest.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    space = workspace_contract.Workspace(args.app_root)
    bundles = workspace_contract.find_bundle_dirs(space)
    if not bundles:
        print(f"no acquisition bundle under {space.root}; run `$ak acquire` first")
        return 2
    bundle = max(bundles, key=lambda p: (p / "bundle.json").stat().st_mtime)

    facts_dir = space.extracted("ui-facts")
    fields = catalogues.rows_of(
        catalogues.read_json(bundle / "databases" / "fields.json"))
    table_names = {r.get("name", "") for r in catalogues.rows_of(
        catalogues.read_json(bundle / "databases" / "tables.json"))}
    writes = sql_contract.write_profile(
        catalogues.code_sources(space, bundle, facts_dir), table_names)
    referenced = catalogues.reference_counts(
        catalogues.read_json(space.extracted("derived-extraction.json")))

    target = space.input_dir("decisions") / "meanings.yaml"
    kept = existing(target)
    sections = {
        "tables": table_subjects(bundle, writes, referenced, fields),
        "columns": column_subjects(fields, catalogues.load_types()),
    }

    lines = [HEADER.rstrip(), ""]
    summary: dict[str, dict[str, int]] = {}
    for section, subjects in sections.items():
        blank = BLANK_TABLE if section == "tables" else BLANK
        rendered, counts = compose(section, subjects, kept[section],
                                   args.top, blank)
        lines += rendered + [""]
        summary[section] = counts

    for section, counts in summary.items():
        print(f"{section:8s} {counts['total']:5d} subject(s), {counts['filled']:4d} "
              f"with a sourced meaning, {counts['added']:5d} blank entr(y/ies) added"
              + (f", {counts['orphans']} kept from an earlier bundle"
                 if counts["orphans"] else ""))

    if args.dry_run:
        print(f"\nwould write {target}")
        return 0

    target.parent.mkdir(parents=True, exist_ok=True)
    io.open(target, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
    print(f"\nwrote {target}")
    added = sum(c["added"] for c in summary.values())
    if added:
        print("Every added entry is blank, and blank is the honest state: no schema "
              "and no analysis can say what a table is for.")
        print("Fill what you know, name a source for each - you may be the source, as "
              "OPERATOR_DECLARATION - then re-run `$ak catalogues`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
