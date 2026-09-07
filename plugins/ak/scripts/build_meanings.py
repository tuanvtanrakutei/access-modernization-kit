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
import re
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
#   evidence_class  DOCUMENT or INTERVIEW. Nothing else - CODE and SCHEMA cannot
#                   support a meaning, which is rule EC-01.
#   source          who said it and when: a document and a page, a meeting and a date,
#                   or your own name.
#   role            optional, tables only: master, transaction, work, log. Printed in
#                   bold before the meaning.
#
# AN ENTRY WITHOUT A SOURCE IS IGNORED and its cell keeps reading `_needs DOCUMENT_`.
# That is the rule this kit exists to enforce: "somebody said so at some point" is how
# a guess becomes a fact by repetition.
#
# What you know from a conversation is INTERVIEW, and it counts. Name who said it and
# when - that is the whole requirement, and it is met by a name and a date. A meeting,
# a phone call and a passing remark at somebody's desk are all interviews if you write
# down whose remark it was.
#
#   商品マスタ:
#     role: master
#     meaning: One row per sellable product; discontinued rows are kept, not deleted.
#     evidence_class: INTERVIEW
#     source: 業務課 (堀内), 2026-09-07, asked by Vo Ta Tuan
#
# What you worked out from reading the code is NOT a meaning. Code is CODE, and rule
# EC-01 says no volume of it establishes what a table is for - that is the finding this
# whole kit is built around, and it applies to a careful reading as much as a careless
# one. Ask the person instead and record their answer.
#
# `OPERATOR_DECLARATION` is not accepted here, settled 2026-09-07 (backlog A18). The
# class is a statement about the *inputs* - which file is the backend, which copy is
# current - and it cannot carry what a table is for. If the answer is your own, that
# does not make it a declaration about the inputs: record it the way the example above
# does, with a name and a date. Your own name counts.
#
# A column may be keyed two ways. `出荷数量` alone is that column wherever it appears,
# which is usually what you want; `受注データ.出荷数量` is that column in that table
# only, and wins over the bare name.
#
# The comment above a blank entry is what the kit knows - who writes it, what names
# it. It is there to inform your sentence, not to be it.
#
# Re-running keeps every entry, and keeps any section other than `tables` and
# `columns` exactly as you wrote it, comments and all. What it does not keep is a
# comment you write between the entries of those two sections.
"""

# `role` is offered for tables because the header names four and a person who has
# one in mind should not have to add the key. It is not part of `is_blank`: a role
# with no meaning behind it is still nothing recorded.
BLANK = {"meaning": "", "evidence_class": "", "source": ""}
BLANK_TABLE = {"role": "", **BLANK}

# The sections this tool writes. Anything else in the file is carried through as text
# by `unmanaged()` - a real A05 file had a sourced `system:` section that a rewrite
# from the parsed sections would have deleted.
MANAGED_SECTIONS = ("tables", "columns", "screens")


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
        return {section: {} for section in MANAGED_SECTIONS}
    import yaml

    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    found: dict[str, dict[str, dict[str, Any]]] = {
        section: {} for section in MANAGED_SECTIONS}
    for section in found:
        for subject, entry in (data.get(section) or {}).items():
            if isinstance(entry, dict):
                found[section][str(subject)] = entry
    return found


TOP_LEVEL_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_-]*):")


def unmanaged(path: Path) -> str:
    """The raw text of every top-level section this tool does not manage.

    Found by running the first version of this script against the real A05 workspace,
    where `meanings.yaml` carried a third section - `system:` - holding a sourced,
    DOCUMENT-class statement of what the whole application is for, and a note saying
    why the per-table meanings below it were still empty. Rewriting the file from its
    parsed `tables` and `columns` would have deleted both without a word.

    Copied as text rather than re-serialised, so the comments inside a section survive
    with it. A comment in a person-owned file is often the only record of why an entry
    reads the way it does, and the entry costs less to re-derive than the reason does.
    """
    if not path.is_file():
        return ""
    lines = path.read_text(encoding="utf-8").splitlines()
    starts = [(index, match.group(1)) for index, line in enumerate(lines)
              if (match := TOP_LEVEL_KEY.match(line))]
    kept: list[str] = []
    for position, (index, key) in enumerate(starts):
        if key in MANAGED_SECTIONS:
            continue
        # Walk back over the comment block attached to the section, so the note that
        # explains it travels with it. Blank lines are crossed, because a note is
        # usually separated from its section by one and the first version of this
        # stopped there - which lost the A05 note saying why the tables below were
        # empty, on the very run it was written to protect. Only a comment starting at
        # column 0 counts: an indented `# note` belongs to the entry above it.
        first = index
        while first and (not lines[first - 1].strip()
                         or lines[first - 1].startswith("#")):
            first -= 1
        while first < index and not lines[first].strip():
            first += 1
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        kept.append("\n".join(lines[first:end]).rstrip())
    return "\n\n".join(kept)


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

    # Grouped by name, not by (database, name). `contracts/meanings.py` resolves a
    # table meaning by name alone, so two same-named tables are one question - and
    # emitting one key per database put a duplicate key in the YAML, where the last
    # silently wins. On A05 that lost three tables' notes, `商品情報` among them, which
    # is a table the evidence request has an open question about precisely *because*
    # it exists in both databases.
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for table in catalogues.rows_of(catalogues.read_json(bundle / "databases" / "tables.json")):
        if table.get("name"):
            grouped[str(table["name"])].append(table)

    subjects = []
    for name, tables in grouped.items():
        databases = sorted({str(t.get("database_id", "")) for t in tables})
        names_it = sum(referenced.get((database, "table", name), 0)
                       for database in databases)
        writers = writes.of(name)
        counts = sorted({columns[(str(t.get("database_id", "")), name)] for t in tables})
        widths = " or ".join(str(count) for count in counts)
        where = (f"in {len(databases)} databases ({', '.join(databases)}); "
                 if len(databases) > 1 else "")
        note = (f"{where}{widths} column(s); {writes.summary(name)}; "
                f"named by {names_it} object(s)")
        if any((t.get("metadata") or {}).get("linked") for t in tables):
            note += "; linked, so it lives in another file"
        if sql_contract.is_work_table(name):
            note += "; work table by naming convention, which is not a guarantee"
        subjects.append((name, note, (-names_it, -len(writers), -max(counts), name)))
    return subjects


def screen_subjects(bundle: Path, facts_dir: Path,
                    referenced: dict[tuple[str, str, str], int],
                    ) -> list[tuple[str, str, tuple]]:
    """Every form and report, with what the definition already says about it.

    Keyed `"{kind} {name}"`. A form and a report may share a name - A05 has two objects
    called the same thing - so keying by name alone would make them one question and
    silently drop one, which is the duplicate-key defect the table section already had
    to be fixed for.

    The note is USAGE and STRUCTURE evidence informing the question, not answering it.
    A person filling in a form with 14 event procedures that 3 objects open knows it is
    worth getting right; one with no record source and nothing opening it knows to ask
    whether it is still reachable at all.
    """
    facts: dict[tuple[str, str, str], dict] = {}
    for path in sorted(facts_dir.glob("*.md")) if facts_dir.is_dir() else []:
        parsed = catalogues.parse_fact(path.read_text(encoding="utf-8"))
        if parsed:
            facts[(parsed["database"], parsed["kind"], parsed["name"])] = parsed

    grouped: dict[tuple[str, str], list[str]] = defaultdict(list)
    for kind, container in (("form", "forms"), ("report", "reports")):
        for item in catalogues.rows_of(catalogues.read_json(
                bundle / "ui" / container / "inventory.json")):
            if item.get("name"):
                grouped[(kind, str(item["name"]))].append(
                    str(item.get("database_id", "")))

    subjects = []
    for (kind, name), databases in grouped.items():
        databases = sorted(set(databases))
        opens = sum(referenced.get((database, kind, name), 0)
                    for database in databases)
        events = bound = 0
        sources: set[str] = set()
        for database in databases:
            fact = facts.get((database, kind, name)) or {}
            events = max(events, len(fact.get("event_procedures") or []))
            bound = max(bound, len(fact.get("bound_fields") or []))
            if fact.get("record_source"):
                sources.add(str(fact["record_source"]))
        where = (f"in {len(databases)} databases ({', '.join(databases)}); "
                 if len(databases) > 1 else "")
        source = (f"record source `{'` or `'.join(sorted(sources))}`"
                  if sources else "no record source declared")
        note = (f"{kind}; {where}{source}; {bound} bound field(s); "
                f"{events} event procedure(s); opened by {opens} object(s)")
        if not opens:
            note += ("; no code path opens it, which is unreachability and not disuse "
                     "- a navigation pane or a custom menu may still reach it (EC-05)")
        subjects.append((f"{kind} {name}", note, (-opens, -events, -bound, kind, name)))
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
        "screens": screen_subjects(bundle, facts_dir, referenced),
    }

    lines = [HEADER.rstrip(), ""]
    summary: dict[str, dict[str, int]] = {}
    for section, subjects in sections.items():
        blank = BLANK_TABLE if section == "tables" else BLANK
        rendered, counts = compose(section, subjects, kept[section],
                                   args.top, blank)
        lines += rendered + [""]
        summary[section] = counts

    carried = unmanaged(target)
    if carried:
        lines += [carried, ""]

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
        print("Every added entry is blank, and blank is the honest state: no schema, "
              "no definition text and no analysis can say what a thing is for.")
        print("Fill what you know, name a source for each - you may be the source, "
              "recorded as INTERVIEW with your name and the date - then re-run "
              "`$ak catalogues`.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
