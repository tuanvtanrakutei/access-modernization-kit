"""What a linked table points at, and how many distinct tables that adds up to.

A06's frontend holds 188 table objects and 35 tables. The difference is not a
miscount - every one of the 188 is a real object in the `.mdb` - it is the wrong
subject. 180 of them are links, and 153 of those point at a table already linked,
under a name Access numbered on its own: residue of a 97->2003 conversion, a Windows
10 migration, a UNC path replaced by a mapped drive, and one developer's desktop, each
leaving its links behind.

Two rules live here, and the second is written out because its obvious form is wrong.

Access appends the number to the *link* name and leaves the *source* name alone, so a
duplicate is a link whose name is its source table's name followed by digits. Written
the shorter way - `name != source_table_name` - the rule destroys every ODBC link,
because SQL Server answers `dbo.仕入商品マスタ` for a link named `仕入商品マスタ`. Those
same three tables were already misclassified once on this project by exactly that
comparison. The narrow form also keeps `商品情報20121115`, whose source table really
does carry the date, the way five local `受YYYYMMDD` tables do - a rule of thumb about
trailing digits would have thrown it away.

What this module refuses to decide is that two paths are one database. The same
backend here is reached by drive letter and by UNC, and under two generations of
filename; whether those are copies is a question about the estate, not a fact in the
connect string. For ODBC it is not answerable from the string at all, a DSN being a
client-side alias. So the counts are reported as the two bounds those two readings
give, the aliases are named, and a person resolves them.
"""
from __future__ import annotations

import re
from typing import Any, Iterable

# Defensive, not primary. `extract_access.ps1` and `tools/ExportAccessObjects.bas`
# both redact before anything reaches a contribution, and the two do not redact the
# same key set - the macro covers PWD, PASSWORD and UID, the PowerShell also TOKEN,
# SECRET and API_KEY. This function writes into a bundle section whose name promises
# the property, so it applies the wider set again rather than trusting whichever route
# a row arrived by.
_SECRET_KEYS = re.compile(
    r"(?i)\b(PWD|PASSWORD|TOKEN|SECRET|API[_-]?KEY|UID|USER\s+ID)(\s*=\s*)[^;]*"
)


def redact(connect: str) -> str:
    return _SECRET_KEYS.sub(lambda match: f"{match.group(1)}{match.group(2)}<REDACTED>",
                            str(connect or ""))


def field(row: dict[str, Any], key: str) -> str:
    """One link field, from either shape a contribution can carry.

    Two routes describe the same link: `imported_sources` flat, with `connect` and
    `source_table_name` at the top level, and `managed_access` as a component, with
    both inside `metadata`. A40 collapses the pair and keeps the richer row, which is
    the component - so every reader of a link has to look in both places, and looking
    in one is how a consumer sees an empty connect string on a link that has one.
    """
    value = row.get(key)
    if value in (None, ""):
        value = (row.get("metadata") or {}).get(key)
    return "" if value is None else str(value)


def is_autonumbered_duplicate(name: str, source_table_name: str) -> bool:
    """Whether Access named this link itself, because the name was already taken.

    True only when the link name is the source table's name plus digits. Never true
    for a link whose source name differs in any other way - which is what keeps the
    `dbo.` prefixed ODBC links, and what keeps a source table that genuinely carries
    a number.
    """
    link = str(name or "")
    source = str(source_table_name or "")
    if not source or link == source or not link.startswith(source):
        return False
    return link[len(source):].isdigit()


def parse_connect(connect: str) -> dict[str, str]:
    """A connect string as a comparable target, without deciding what is the same.

    `target` is a comparison key only: two links with the same `target` name the same
    database *as written*. Two links with different targets may still be the same
    database, and this module will not say so.
    """
    text = redact(connect)
    if not text:
        return {"kind": "local", "driver": "", "dsn": "", "database": "",
                "target": "", "connect": ""}
    parts = text.split(";")
    driver = parts[0].strip()
    fields: dict[str, str] = {}
    for part in parts[1:]:
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        fields.setdefault(key.strip().upper(), value.strip())
    database = fields.get("DATABASE", "")
    dsn = fields.get("DSN", "")
    if driver.upper() == "ODBC":
        kind, target = "odbc", f"odbc:dsn={dsn.casefold()};database={database.casefold()}"
    elif database:
        # Jet leaves the driver empty; `Excel 8.0`, `Text` and `dBase` name themselves
        # and are still a file, so the kind is what the target is, not who reads it.
        kind, target = "file", f"file:{database.casefold()}"
    else:
        kind, target = "other", f"other:{text.casefold()}"
    return {"kind": kind, "driver": driver, "dsn": dsn, "database": database,
            "target": target, "connect": text}


def connections(link_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """One record per distinct external target, from the links that name it.

    A41: `interfaces/connections.redacted.json` was created as an adapter bucket in
    `adapters/base.py`, written out as a bundle section, and appended to by nothing in
    the repository - so a bundle answered "what does this application connect to" with
    `[]` while holding three ODBC links to two SQL Server databases. Derived here
    instead of asked of each adapter, because a bucket every adapter must remember to
    fill is a bucket that stays empty, and because two readers of one rule cannot
    drift (A33).

    Sorted, and carrying no timestamps, so re-acquiring unchanged sources produces the
    same bundle.
    """
    groups: dict[str, dict[str, Any]] = {}
    for row in link_rows:
        connect = field(row, "connect")
        if not connect:
            continue
        parsed = parse_connect(connect)
        entry = groups.get(parsed["target"])
        if entry is None:
            entry = groups[parsed["target"]] = {
                "target": parsed["target"], "kind": parsed["kind"],
                "driver": parsed["driver"], "dsn": parsed["dsn"],
                "database": parsed["database"], "connect": parsed["connect"],
                "database_ids": set(), "source_tables": set(),
                "link_count": 0, "unreadable_link_count": 0,
                "autonumbered_duplicate_link_count": 0,
            }
        entry["link_count"] += 1
        database_id = row.get("database_id")
        if database_id:
            entry["database_ids"].add(str(database_id))
        source = field(row, "source_table_name")
        if source:
            entry["source_tables"].add(source)
        if field(row, "read_error"):
            entry["unreadable_link_count"] += 1
        if is_autonumbered_duplicate(str(row.get("name") or ""), source):
            entry["autonumbered_duplicate_link_count"] += 1

    records: list[dict[str, Any]] = []
    for target in sorted(groups):
        entry = groups[target]
        records.append({
            "target": entry["target"], "kind": entry["kind"], "driver": entry["driver"],
            "dsn": entry["dsn"], "database": entry["database"],
            "connect": entry["connect"],
            "linked_from": sorted(entry["database_ids"]),
            "link_count": entry["link_count"],
            "autonumbered_duplicate_link_count": entry["autonumbered_duplicate_link_count"],
            "unreadable_link_count": entry["unreadable_link_count"],
            "source_tables": sorted(entry["source_tables"]),
        })
    return records


def unresolved_aliases(link_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Source tables named by more than one target - the question this module leaves open.

    A row here is not a defect. It says the same table name was reached through two or
    more targets, and that whether those targets are one database cannot be read from
    a connect string.
    """
    seen: dict[str, set[str]] = {}
    for row in link_rows:
        source = field(row, "source_table_name")
        connect = field(row, "connect")
        if not source or not connect:
            continue
        seen.setdefault(source, set()).add(parse_connect(connect)["target"])
    return [{"source_table_name": name, "targets": sorted(targets)}
            for name, targets in sorted(seen.items()) if len(targets) > 1]


def summarise(table_rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per database: how many table objects, and how many tables.

    Both bounds are reported because the gap between them is a real open question, not
    a rounding choice. `tables_if_targets_are_copies` reads two paths naming the same
    table as one table; `tables_if_targets_are_distinct` reads them as two. On A06's
    frontend that is 35 against 82, from 188 objects.
    """
    per_database: dict[str, dict[str, Any]] = {}
    for row in table_rows:
        database_id = str(row.get("database_id") or "")
        entry = per_database.get(database_id)
        if entry is None:
            entry = per_database[database_id] = {
                "database_id": database_id, "table_objects": 0, "local_tables": 0,
                "link_objects": 0, "autonumbered_duplicate_links": 0,
                "names": set(), "pairs": set(),
            }
        entry["table_objects"] += 1
        connect = field(row, "connect")
        if not connect:
            entry["local_tables"] += 1
            continue
        entry["link_objects"] += 1
        declared = field(row, "source_table_name")
        source = declared or str(row.get("name") or "")
        if is_autonumbered_duplicate(str(row.get("name") or ""), declared):
            entry["autonumbered_duplicate_links"] += 1
        entry["names"].add(source)
        entry["pairs"].add((parse_connect(connect)["target"], source))

    summary: list[dict[str, Any]] = []
    for database_id in sorted(per_database):
        entry = per_database[database_id]
        names, pairs = len(entry["names"]), len(entry["pairs"])
        summary.append({
            "database_id": entry["database_id"],
            "table_objects": entry["table_objects"],
            "local_tables": entry["local_tables"],
            "link_objects": entry["link_objects"],
            "autonumbered_duplicate_links": entry["autonumbered_duplicate_links"],
            "distinct_source_table_names": names,
            "distinct_target_and_source_pairs": pairs,
            "tables_if_targets_are_copies": entry["local_tables"] + names,
            "tables_if_targets_are_distinct": entry["local_tables"] + pairs,
        })
    return summary

def collapse(rows: list[dict[str, Any]], identity: tuple[str, ...] = ("database_id", "name")) -> list[dict[str, Any]]:
    """Rows describing the same link, folded to one - for a reader of a sealed bundle.

    A40 folds them during assembly, so a bundle sealed after that fix holds one row
    per link. Every bundle sealed before it holds two, and a consumer that trusts the
    file doubles every number it reports from it. So the same fold is available at read
    time, delegating to the assembly function rather than restating the rule: A33 was
    two readers of one map drifting apart, and this is the same map.
    """
    import bundle_assembly

    folded = list(rows)
    bundle_assembly._dedupe_schema(folded, identity)
    return folded
