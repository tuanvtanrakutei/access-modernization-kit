#!/usr/bin/env python3
"""Generate the exhaustive catalogues: every table, every screen, every query.

A phase document is a narrative - it says what matters and why. Measured against the
bundle, the A05 narratives named 20 of 118 tables, 4 of 328 distinct column names, 22
of 51 forms and 5 of 77 queries. That is not a writing failure; a narrative that
listed 1,055 columns would stop being one.

The reference set answers this with a companion document. `A01_Table_Definitions.md`
is 83 KB - the second largest file in that set - and holds every table with every
column. Its Phase 1 narrative is the *shortest* phase document in the set precisely
because the enumeration lives beside it. The kit had no counterpart at all.

These catalogues are generated, never written, and that is the point. Three wrong
counts in one A05 session (QA18, QA18a, E-06) were all the same mistake: a set counted
by one key and then described from a subset of it. Writing 118 rows by hand is that
mistake with more chances to make it. Generated from the bundle, a catalogue is right
by construction and stays right when the bundle is re-acquired.

Three files, one per phase that has an inventory:

    <APP>_DataCatalogue.md     every table, every column, every index      Phase 1
    <APP>_ScreenCatalogue.md   every form and report, what each binds to   Phase 2
    <APP>_LogicCatalogue.md    every query and module, what each does      Phase 3

Columns the evidence cannot fill are present and marked, not omitted. A catalogue
carrying 118 rows with an empty business-role column states the cost of the missing
documents once per row, which is a far harder thing to overlook than one sentence at
the end of a phase document - and it is the file the migration team fills in, which is
what the reference set's conversion table actually is.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

import bilingual as bilingual_contract  # noqa: E402
import meanings as meanings_contract  # noqa: E402
import sql_relationships as sql_contract  # noqa: E402
import workspace as workspace_contract  # noqa: E402

# What a cell says when the evidence class that would fill it was not supplied. One
# spelling, so a reader learns it once and a grep finds every instance.
NEEDS_DOC = "_needs DOCUMENT_"
NEEDS_INTERVIEW = "_needs INTERVIEW_"
NEEDS_DECISION = "_design decision_"
NOT_EXTRACTED = "_not extracted_"


# The deriver slugifies node ids (`table_data_4a6c58e8_c_0ddcf6d8`), so a catalogue
# cannot build one from a name. It maps back through the node list instead: each node
# carries its real `label` and a `source_file` prefixed with the database id.
#
# The first version of this file guessed the id format as `{database}:{kind}:{name}`.
# Every lookup missed, so every object read "referenced by 0" and the unreferenced
# list claimed all 118 - against 37 that Phase 2 had established. A miss in a dict is
# silent, which is the third time that shape has cost something in this kit.
NODE_KIND = {"table": "table", "query": "query", "form": "form", "report": "report",
             "module": "module", "macro": "macro"}


def reference_counts(derived: dict | None) -> dict[tuple[str, str, str], int]:
    """How many edges point at each (database, kind, label)."""
    if not derived:
        return {}
    identity: dict[str, tuple[str, str, str]] = {}
    for node in derived.get("nodes") or []:
        node_id, label = node.get("id") or "", node.get("label") or ""
        source = node.get("source_file") or ""
        database = source.split(":", 1)[0] if ":" in source else ""
        kind = next((v for k, v in NODE_KIND.items() if node_id.startswith(k + "_")), "")
        if node_id and label and kind:
            identity[node_id] = (database, kind, label)
    counts: dict[tuple[str, str, str], int] = defaultdict(int)
    for edge in derived.get("edges") or []:
        key = identity.get(str(edge.get("target") or ""))
        if key:
            counts[key] += 1
    return counts


# `metadata.returns_records` is True even for an UPDATE, so it cannot separate a read
# from a write - the first version of this file trusted it and reported "0 of 79
# queries write" for a database with four writers, one of which multiplies a quantity.
# The verb comes from the SQL the bundle stores beside the inventory.
SQL_VERB = re.compile(
    r"^\s*(?:PARAMETERS[^;]*;\s*)?(SELECT|UPDATE|INSERT|DELETE|TRANSFORM)\b",
    re.IGNORECASE | re.DOTALL,
)


def query_verb(bundle: Path, query: dict) -> str:
    """The statement a saved query actually is, read from its SQL."""
    relative = query.get("path")
    if not relative:
        return "_no SQL in bundle_"
    text = ""
    for candidate in (bundle / "code" / "access-sql" / relative,
                      bundle / "code" / "sql-server" / relative):
        if candidate.is_file():
            for encoding in ("utf-8-sig", "utf-8", "cp932"):
                try:
                    text = candidate.read_text(encoding=encoding)
                    break
                except (UnicodeDecodeError, OSError):
                    continue
            break
    if not text:
        return "_no SQL in bundle_"
    match = SQL_VERB.search(text)
    return match.group(1).upper() if match else "_unrecognised_"


def read_bundle_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp932"):
        try:
            return path.read_text(encoding=encoding)
        except (UnicodeDecodeError, OSError):
            continue
    return ""


def sql_sources(bundle: Path, facts_dir: Path) -> dict[str, str]:
    """Every complete SQL statement the acquisition holds, labelled by where it is.

    Saved queries and screen record sources. VBA is deliberately excluded: its SQL is
    built by string concatenation, so a scan of it would report fragments as if they
    were statements.
    """
    sources: dict[str, str] = {}
    for query in rows_of(read_json(bundle / "code" / "access-sql" / "inventory.json")):
        relative = query.get("path")
        if relative:
            sources[f"query {query.get('name', '')}"] = read_bundle_text(
                bundle / "code" / "access-sql" / relative)
    for path in sorted(facts_dir.glob("*.md")) if facts_dir.is_dir() else []:
        fact = parse_fact(read_bundle_text(path))
        if fact and fact.get("record_source"):
            sources[f"{fact['kind']} {fact['name']}"] = str(fact["record_source"])
    return sources


def analyse_sql(bundle: Path, facts_dir: Path) -> Any:
    tables = {r.get("name", "") for r in rows_of(
        read_json(bundle / "databases" / "tables.json"))}
    queries = {r.get("name", "") for r in rows_of(
        read_json(bundle / "code" / "access-sql" / "inventory.json"))}
    return sql_contract.analyse(sql_sources(bundle, facts_dir), tables, queries)


def code_sources(space: Any, bundle: Path, facts_dir: Path) -> dict[str, str]:
    """Every text a write could be hiding in: query SQL, and the VBA of each object.

    Screen record sources are not enough here. In this application family every write
    performed in normal operation is in VBA - the four saved queries that write are
    manual leftovers - so the module, form and report definition text is where the
    writers are.
    """
    sources = dict(sql_sources(bundle, facts_dir))
    staging = space.staging_root()
    if staging.is_dir():
        for kind, label in (("vba", "module"), ("forms", "form"), ("reports", "report"),
                            ("macros", "macro")):
            for path in sorted(staging.glob(f"*/*/{kind}/*.txt")):
                sources[f"{label} {path.stem}"] = read_bundle_text(path)
    return sources


class Naming:
    """Renders every production name with its English proposal beside it."""

    def __init__(self, package: Path, glossary: Path) -> None:
        self.terms = bilingual_contract.load_terms(package)
        self.accepted = bilingual_contract.load_accepted(glossary)
        self._cache: dict[str, Any] = {}

    def of(self, name: str) -> Any:
        if name not in self._cache:
            self._cache[name] = bilingual_contract.compose(
                name, self.terms, self.accepted)
        return self._cache[name]

    def render(self, name: str) -> str:
        """`商品コード (product_cd?)` - the `?` marks a proposal nobody has accepted."""
        return self.of(name).bilingual()

    def english(self, name: str) -> str:
        rendered = self.of(name)
        if not rendered.english:
            return "_no term matched_"
        # No marker. The column header says these are proposals, and the glossary
        # records which are accepted; a `?` on almost every row said nothing.
        partial = "" if rendered.is_complete else " _partial_"
        return f"`{rendered.english}`{partial}"

    def stats(self) -> dict[str, int]:
        complete = sum(1 for r in self._cache.values() if r.is_complete)
        accepted = sum(1 for r in self._cache.values() if r.accepted)
        return {"names": len(self._cache), "complete": complete, "accepted": accepted}


def load_types() -> dict[int, dict[str, str]]:
    import yaml

    spec = PACKAGE / "specifications" / "dao-field-types.yaml"
    data = yaml.safe_load(spec.read_text(encoding="utf-8")) or {}
    return {int(k): v for k, v in (data.get("types") or {}).items()}


def read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def rows_of(data: Any) -> list[dict]:
    """The list inside a bundle file, whatever the file calls it."""
    if data is None:
        return []
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    for value in data.values():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            return value
    return []


def escape(text: Any) -> str:
    """A production name may contain a pipe, which would break the table it sits in."""
    return str(text if text is not None else "").replace("|", "\\|").replace("\n", " ")


def declared_type(field: dict, types: dict[int, dict[str, str]]) -> tuple[str, str]:
    code = field.get("type")
    entry = types.get(code) if isinstance(code, int) else None
    if entry is None:
        return f"_unknown DAO type {code}_", ""
    name = entry.get("access_type", entry.get("dao_constant", str(code)))
    size = field.get("size")
    if entry.get("dao_constant") in ("dbText", "dbChar") and size:
        return f"{name}({size})", entry.get("dao_constant", "")
    return name, entry.get("dao_constant", "")


def table_meaning(meaning: Any, name: str) -> str:
    """A recorded meaning, or the marker saying what would fill it."""
    entry = meaning.table(name)
    if entry is None:
        return NEEDS_DOC
    role = f"**{escape(entry.role)}** — " if entry.role else ""
    return role + escape(entry.cite())


def column_meaning(meaning: Any, table: str, column: str) -> str:
    entry = meaning.column(table, column)
    return escape(entry.cite()) if entry else NEEDS_DOC


def target_proposal(field: dict, types: dict[int, dict[str, str]]) -> str:
    """A proposed target type, marked as a proposal, with the byte trap called out.

    A `Short Text` size is a maximum in **characters**, and the two ends of a
    migration count bytes differently: the source stores CP932, at most 2 bytes per
    full-width character, while a UTF-8 target needs 3 for the same character (4 for
    some). So a column declared `Short Text(10)` holds ten Japanese characters, which
    occupy up to 20 bytes where they are and need up to 30 where they are going.

    A target column sized in bytes at 10 truncates real data. That is the one
    mechanical mistake this column exists to prevent; choosing the type remains a
    person's decision, which is why every value here carries a `?`.
    """
    entry = types.get(field.get("type")) if isinstance(field.get("type"), int) else None
    if entry is None:
        return NEEDS_DECISION
    hint = str(entry.get("target_hint", "")).strip()
    if not hint:
        return NEEDS_DECISION
    size = field.get("size")
    if "size" in hint and size:
        hint = hint.replace("size", str(size))
        if entry.get("dao_constant") in ("dbText", "dbChar"):
            return f"{hint} **needs {int(size) * 3}B in UTF-8**"
    # No marker, for the same reason the English names carry none: a `?` on all 1,055
    # rows is wallpaper. The column heading and the legend say these are proposals.
    return hint


def data_catalogue(app_id: str, bundle: Path, types: dict[int, dict[str, str]],
                   sql: Any, naming: Any, writes: Any, meaning: Any) -> str:
    tables = rows_of(read_json(bundle / "databases" / "tables.json"))
    fields = rows_of(read_json(bundle / "databases" / "fields.json"))
    indexes = rows_of(read_json(bundle / "databases" / "indexes.json"))
    relationships = rows_of(read_json(bundle / "databases" / "declared-relationships.json"))
    linked = rows_of(read_json(bundle / "interfaces" / "linked-tables.json"))

    by_table: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for field in fields:
        by_table[(field.get("database_id", ""), field.get("table", ""))].append(field)

    key_fields: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(
        lambda: {"primary": [], "unique": []}
    )
    index_names: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for index in indexes:
        key = (index.get("database_id", ""), index.get("table", ""))
        index_names[key].append(index)
        for name in index.get("fields") or []:
            if index.get("primary"):
                key_fields[key]["primary"].append(name)
            elif index.get("unique"):
                key_fields[key]["unique"].append(name)

    linked_by_name = {(r.get("database_id", ""), r.get("name", r.get("table", ""))): r
                      for r in linked}

    out: list[str] = [
        f"# {app_id} — Data Catalogue",
        "",
        "Every table and every column, generated from the acquisition bundle. This is "
        "the exhaustive reference; the reasoning about what matters is in "
        "`Phase1_DataUnderstanding`.",
        "",
        "**Generated, not written.** Re-running `$ak catalogues` after a new "
        "acquisition reproduces it from the bundle, so a count here cannot drift from "
        "the databases it describes.",
        "",
        "## How to read a blank cell",
        "",
        "| Marker | Means |",
        "|---|---|",
        f"| {NEEDS_DOC} | Nobody with the standing to say it has said it yet. A "
        "schema cannot state a business role and neither can more analysis; rule "
        "EC-01. It fills when a document, an interview or an operator's declaration "
        "arrives and is recorded in `input/decisions/meanings.yaml` — **an entry there "
        "must name its source, or it is ignored**. |",
        "| `name` | The English name, composed from "
        "`specifications/ja-en-terms.yaml`. **Treat every one as a proposal** unless "
        "`input/decisions/glossary.yaml` marks it accepted - that file is where a "
        "correction is made, and an accepted name always wins. A name whose every term "
        "was already decided in the A01 conversion table is precedent rather than a "
        "proposal, and overriding one makes the two systems disagree. |",
        "| `name` _partial_ | Only part of the Japanese matched a known term. Finish it "
        "by hand, or add the missing term to the dictionary. |",
        "| Target type | A **proposal** from the DAO type spec, never a decision — "
        "choosing the real one is a person's job, and in the reference set that "
        "decision is a separate document with an author. "
        "A text size is in characters: the source stores CP932 at up to 2 bytes per "
        "full-width character and a UTF-8 target needs up to 3, so "
        "`needs nB in UTF-8` is the byte width the target column must actually have. |",
        f"| {NEEDS_INTERVIEW} | Nobody could be asked. |",
        f"| {NEEDS_DECISION} | A person's design choice, not an analysis result. In the "
        "reference set the target types are a separate document with an author. |",
        f"| {NOT_EXTRACTED} | The extraction does not carry it; "
        "`specifications/dao-field-types.yaml` says which and why. |",
        "",
    ]

    out += [
        "## 1. Table list",
        "",
        f"{len(tables)} table objects.",
        "",
        "| No. | Table (production name) | English (proposed) | Database | Linked | "
        "Columns | Primary key | Written by | Business role |",
        "|---:|---|---|---|---|---:|---|---|---|",
    ]
    for number, table in enumerate(sorted(tables, key=lambda t: (t.get("database_id", ""),
                                                                 t.get("name", ""))), 1):
        database, name = table.get("database_id", ""), table.get("name", "")
        key = (database, name)
        metadata = table.get("metadata") or {}
        is_linked = bool(metadata.get("linked")) or key in linked_by_name
        primary = key_fields[key]["primary"]
        out.append(
            f"| {number} | `{escape(name)}` | {naming.english(name)} | "
            f"{escape(database)} | {'yes' if is_linked else '—'} | {len(by_table[key])} | "
            f"{'`' + '`, `'.join(escape(p) for p in primary) + '`' if primary else '**none**'} | "
            f"{escape(writes.summary(name))} | {table_meaning(meaning, name)} |"
        )

    without_key = [t for t in tables
                   if not key_fields[(t.get("database_id", ""), t.get("name", ""))]["primary"]]
    out += [
        "",
        f"**{len(without_key)} of {len(tables)} table objects have no primary key.** A "
        "table with no key cannot be updated by key, and a migration has to invent one "
        "or accept duplicates.",
        "",
        "## 2. Declared relationships",
        "",
    ]
    if relationships:
        out += ["| From | To | Enforced |", "|---|---|---|"]
        for relationship in relationships:
            out.append(
                f"| `{escape(relationship.get('from'))}` | `{escape(relationship.get('to'))}` "
                f"| {escape(relationship.get('enforced', '—'))} |"
            )
    else:
        out += [
            "**None. Zero relationships are declared in any acquired database.**",
            "",
            "This is a finding about the application, not a gap in the extraction. "
            "Referential integrity is not enforced anywhere by the database engine, so "
            "every join in this system is a convention held in a query or in VBA, and "
            "a migration that adds foreign keys will find rows that violate them.",
            "",
            "**The SQL still knows.** Section 2.1 reads the joins the application "
            "actually performs. A declared constraint says what is permitted; a join "
            "says what is done, which for a migration is the more useful of the two - "
            "but it constrains nothing, so every row there is INFERRED.",
        ]

    out += ["", "### 2.1 Relationships inferred from real joins", ""]
    if not sql.relationships:
        out += ["No `JOIN ... ON` clause resolved to a pair of tables.", ""]
    else:
        covered = sql.tables_in_a_join
        out += [
            f"{len(sql.relationships)} distinct column pairs, from "
            f"{sql.sources_scanned} SQL statements - every saved query and every screen "
            "record source. Confidence is the number of places that perform the join: a "
            "pair joined in one place may be a mistake, a pair joined in five is how "
            "the application works.",
            "",
            f"**Coverage: {len(covered)} of {len(tables)} table objects appear in a "
            "join at all.** The rest are joined only in VBA, whose SQL is built by "
            "string concatenation and cannot be read as statements, or are not joined. "
            "Absence from this table is not evidence that a table stands alone.",
            "",
            "| Table | Column | Table | Column | Joined in | Status |",
            "|---|---|---|---|---:|---|",
        ]
        for relationship in sql.relationships:
            out.append(
                f"| `{escape(relationship.left_table)}` | "
                f"`{escape(relationship.left_column)}` | "
                f"`{escape(relationship.right_table)}` | "
                f"`{escape(relationship.right_column)}` | "
                f"{relationship.occurrences} | INFERRED |"
            )
        if sql.unresolved_aliases:
            out += [
                "",
                "**Names a join used that resolve to nothing:**",
                "",
                "| Name | Times | |",
                "|---|---:|---|",
            ]
            for name, count in sql.unresolved_aliases.items():
                note = ("an alias whose `FROM` this reader could not bind"
                        if len(name) <= 3 else
                        "**exists nowhere** - see the Logic Catalogue")
                out.append(f"| `{escape(name)}` | {count} | {note} |")

    out += ["", "### 2.2 Candidate keys, where none is declared", ""]
    real_candidates = []
    for table_object in tables:
        database, name = table_object.get("database_id", ""), table_object.get("name", "")
        if key_fields[(database, name)]["primary"]:
            continue
        columns = sql.candidate_keys.get(name)
        if columns:
            real_candidates.append((database, name, columns))
    if not real_candidates:
        out += ["No unkeyed table is joined on any column, so nothing can be "
                "suggested here.", ""]
    else:
        out += [
            f"{len(real_candidates)} table objects have no declared primary key but are "
            "joined on a column, which is that column acting as a key in practice.",
            "",
            "**This cannot be confirmed from the evidence supplied.** Proving a column "
            "is unique requires rows, which means SAMPLE_DATA. A join tells you the "
            "column is used to identify a row; it does not tell you that it does so "
            "uniquely.",
            "",
            "| Table | Database | Joined on | Times | Reads as |",
            "|---|---|---|---:|---|",
        ]
        for database, name, columns in sorted(real_candidates):
            column, count = columns[0]
            reads = ("work table by naming convention - no key expected"
                     if sql_contract.is_work_table(name) else
                     "**a key is expected here and none is declared**")
            out.append(f"| `{escape(name)}` | {escape(database)} | "
                       f"`{escape(column)}` | {count} | {reads} |")

    out += ["", "## 3. Column detail", "",
            f"{len(fields)} columns across {len(by_table)} tables.", ""]
    for table in sorted(tables, key=lambda t: (t.get("database_id", ""), t.get("name", ""))):
        database, name = table.get("database_id", ""), table.get("name", "")
        key = (database, name)
        columns = by_table[key]
        out += [f"### `{escape(name)}`", "",
                f"- database: `{escape(database)}`",
                f"- columns: {len(columns)}"]
        metadata = table.get("metadata") or {}
        if metadata.get("connect"):
            out.append(f"- linked, connect: `{escape(metadata['connect'])}`")
        if metadata.get("source_table_name"):
            out.append(f"- source table: `{escape(metadata['source_table_name'])}`")
        for index in index_names[key]:
            kind = "primary key" if index.get("primary") else (
                "unique" if index.get("unique") else "index")
            out.append(f"- {kind} `{escape(index.get('name'))}`: "
                       f"`{'`, `'.join(escape(f) for f in index.get('fields') or [])}`")
        if not columns:
            out += ["", "_No column detail in the bundle for this object._", ""]
            continue
        out += ["",
                "| No. | Column (production name) | English (proposed) | Type (current) | "
                "Target type | PK | FK | Required | Business meaning |",
                "|---:|---|---|---|---|---|---|---|---|"]
        primary = set(key_fields[key]["primary"])
        for number, field in enumerate(columns, 1):
            column = field.get("name", "")
            type_text, _ = declared_type(field, types)
            out.append(
                f"| {number} | `{escape(column)}` | {naming.english(column)} | "
                f"{escape(type_text)} | {target_proposal(field, types)} | "
                f"{'PK' if column in primary else '—'} | — | "
                f"{'yes' if field.get('required') else 'no'} | "
                f"{column_meaning(meaning, name, column)} |"
            )
        out.append("")

    # A column name used in several tables with several declared types is the finding
    # a catalogue exists to surface: it cannot be seen by reading one table, and it
    # decides whether a single target type is even possible.
    shapes: dict[str, set[tuple[Any, Any]]] = defaultdict(set)
    holders: dict[str, set[str]] = defaultdict(set)
    for field in fields:
        column = field.get("name", "")
        shapes[column].add((field.get("type"), field.get("size")))
        holders[column].add(field.get("table", ""))
    inconsistent = {c: s for c, s in shapes.items() if len(s) > 1}

    out += ["", "## 4. Columns whose declared type differs between tables", ""]
    if not inconsistent:
        out += ["Every column name carries one declared type everywhere it appears.", ""]
    else:
        out += [
            f"**{len(inconsistent)} of {len(shapes)} column names are declared with "
            "more than one type.**",
            "",
            "This cannot be seen by reading any single table, and it decides whether "
            "one target type is even possible. Where two of these are joined, the "
            "database is coercing on every comparison; where a migration picks one "
            "type, the other side stops fitting.",
            "",
            "| Column | Declared as | In tables |",
            "|---|---|---:|",
        ]
        def described(shape: tuple[Any, Any]) -> str:
            code, size = shape
            entry = types.get(code) if isinstance(code, int) else None
            if entry is None:
                return f"_unknown DAO type {code}_"
            label = str(entry.get("access_type", code))
            if entry.get("dao_constant") in ("dbText", "dbChar") and size:
                return f"{label}({size})"
            return label

        for column, shape_set in sorted(inconsistent.items(),
                                        key=lambda kv: (-len(kv[1]), kv[0])):
            rendered = ", ".join(sorted(described(s) for s in shape_set))
            out.append(f"| `{escape(column)}` {naming.english(column)} | "
                       f"{escape(rendered)} | {len(holders[column])} |")
        worst = max(inconsistent.items(), key=lambda kv: len(kv[1]))
        out += [
            "",
            f"The widest is `{escape(worst[0])}`, declared "
            f"{len(worst[1])} different ways across {len(holders[worst[0]])} tables. "
            "A key that is a number in one table and text in another is not one key.",
        ]

    out += [
        "## 5. What a target type needs before it can be chosen",
        "",
        "The `Target type` column is deliberately unfilled. Two of these decide "
        "correctness rather than style:",
        "",
        "- **Short Text sizes are in characters, not bytes.** A column declared "
        "`Short Text(10)` accepts ten Japanese characters, which under CP932 occupy up "
        "to twenty bytes. A target column sized in bytes at 10 truncates real data.",
        "- **A Long Integer may or may not be an AutoNumber.** The two are the same DAO "
        "type and differ only in field attributes this extraction does not collect, so "
        "no row here claims either way.",
        "",
        "`specifications/dao-field-types.yaml` carries the constraint each type "
        "actually imposes, and names everything the extraction does not carry.",
    ]
    return "\n".join(out) + "\n"


def screen_catalogue(app_id: str, bundle: Path, facts_dir: Path,
                     derived: dict | None, naming: Any) -> str:
    forms = rows_of(read_json(bundle / "ui" / "forms" / "inventory.json"))
    reports = rows_of(read_json(bundle / "ui" / "reports" / "inventory.json"))
    macros = rows_of(read_json(bundle / "ui" / "macros" / "inventory.json"))

    # The distilled facts, keyed the way the deriver names its files.
    facts: dict[tuple[str, str, str], dict[str, list[str] | str]] = {}
    for path in sorted(facts_dir.glob("*.md")) if facts_dir.is_dir() else []:
        parsed = parse_fact(path.read_text(encoding="utf-8"))
        if parsed:
            facts[(parsed["database"], parsed["kind"], parsed["name"])] = parsed

    referenced = reference_counts(derived)

    out: list[str] = [
        f"# {app_id} — Screen Catalogue",
        "",
        f"Every form and report: {len(forms)} forms, {len(reports)} reports, "
        f"{len(macros)} macro(s). Generated from the acquisition bundle and the "
        "distilled object facts. The reasoning is in `Phase2_ScreenAnalysis`.",
        "",
        "`Record source` and `Bound fields` are read from the object definition. They "
        "say what the screen is connected to, which is not the same as what it is for: "
        f"a purpose needs a document or an interview ({NEEDS_DOC}).",
        "",
        "**Layout is invisible here and everywhere.** A definition carries control "
        "positions but not what an operator can see, reach by tab order, or read as "
        "grouped. That needs SCREENSHOT evidence.",
        "",
    ]

    for kind, items in (("form", forms), ("report", reports)):
        out += [
            f"## {kind.capitalize()}s ({len(items)})",
            "",
            "| No. | Object (production name) | Database | Record source | Bound fields | "
            "Event procedures | Embedded controls | Referenced by | Business purpose |",
            "|---:|---|---|---|---:|---:|---|---:|---|",
        ]
        for number, item in enumerate(sorted(items, key=lambda i: (i.get("database_id", ""),
                                                                   i.get("name", ""))), 1):
            database, name = item.get("database_id", ""), item.get("name", "")
            fact = facts.get((database, kind, name), {})
            source = fact.get("record_source") or ""
            bound = fact.get("bound_fields") or []
            events = fact.get("event_procedures") or []
            controls = fact.get("embedded_controls") or []
            out.append(
                f"| {number} | `{escape(name)}` | {naming.english(name)} | "
                f"{escape(database)} | "
                f"{('`' + escape(source) + '`') if source else '**none declared**'} | "
                f"{len(bound)} | {len(events)} | "
                f"{('`' + '`, `'.join(escape(c) for c in controls) + '`') if controls else '—'} | "
                f"{referenced.get((database, kind, name), 0)} | {NEEDS_DOC} |"
            )
        out.append("")

    unreached = [
        (item.get("database_id", ""), item.get("name", ""), kind)
        for kind, items in (("form", forms), ("report", reports))
        for item in items
        if referenced.get((item.get("database_id", ""), kind, item.get("name", "")), 0) == 0
    ]
    out += [
        f"## Objects referenced by nothing ({len(unreached)})",
        "",
        "No module, macro, form or report definition names these. That means "
        "unreachable **by code**, not unused, and the difference matters here: Access "
        "opens an object from the navigation pane, from a custom menu, or from the "
        "database's own startup property, none of which appears in any definition. "
        "**A startup form belongs in this list and is not dead** - it is opened by a "
        "database property rather than by code. Rule EC-05: absence of a reference is "
        "unreachability, not disuse, and settling it needs an interview.",
        "",
        "| Object | Database | Kind |",
        "|---|---|---|",
    ]
    for database, name, kind in sorted(unreached):
        out.append(f"| `{escape(name)}` | {escape(database)} | {kind} |")

    if macros:
        out += ["", f"## Macros ({len(macros)})", "", "| Macro | Database |", "|---|---|"]
        for macro in sorted(macros, key=lambda m: m.get("name", "")):
            out.append(f"| `{escape(macro.get('name'))}` | {escape(macro.get('database_id'))} |")
    return "\n".join(out) + "\n"


FACT_FIELDS = {
    "record source": "record_source",
    "bound fields": "bound_fields",
    "event procedures": "event_procedures",
    "embedded controls": "embedded_controls",
}


def parse_fact(text: str) -> dict[str, Any] | None:
    """Read one distilled object fact back. The deriver writes it; this reads it."""
    lines = text.splitlines()
    if not lines or not lines[0].startswith("# "):
        return None
    parsed: dict[str, Any] = {"name": lines[0][2:].strip(), "database": "", "kind": "",
                              "record_source": "", "bound_fields": [],
                              "event_procedures": [], "embedded_controls": []}
    current: str | None = None
    for line in lines[1:]:
        single = re.match(r"^- ([a-z ]+): (.*)$", line)
        if single:
            label, value = single.group(1).strip(), single.group(2).strip()
            if label == "database":
                parsed["database"] = value
            elif label == "kind":
                parsed["kind"] = value
            elif label == "record source":
                parsed["record_source"] = "" if value.startswith("(") else value
            current = None
            continue
        header = re.match(r"^- ([a-z ]+):$", line)
        if header:
            current = FACT_FIELDS.get(header.group(1).strip())
            continue
        member = re.match(r"^  - (.+)$", line)
        if member and current:
            parsed[current].append(member.group(1).strip())
    return parsed


def logic_catalogue(app_id: str, bundle: Path, derived: dict | None,
                    sql: Any, naming: Any) -> str:
    queries = rows_of(read_json(bundle / "code" / "access-sql" / "inventory.json"))
    modules = rows_of(read_json(bundle / "code" / "vba" / "inventory.json"))
    interfaces = rows_of(read_json(bundle / "interfaces" / "file-interfaces.json"))
    linked = rows_of(read_json(bundle / "interfaces" / "linked-tables.json"))

    referenced = reference_counts(derived)
    verbs = {(q.get("database_id", ""), q.get("name", "")): query_verb(bundle, q)
             for q in queries}
    writes = {"UPDATE", "INSERT", "DELETE"}

    out: list[str] = [
        f"# {app_id} — Logic Catalogue",
        "",
        f"Every saved query and every VBA module: {len(queries)} queries, "
        f"{len(modules)} modules. Generated from the acquisition bundle. The reasoning "
        "is in `Phase3_LogicProcessing`.",
        "",
        "`Statement` is read from the query's own SQL, not from its metadata: the "
        "bundle records `returns_records: true` even for an UPDATE, so the metadata "
        "cannot separate a read from a write. A query nothing references is still "
        "reachable from the navigation pane, so zero references is not evidence of "
        "disuse (rule EC-05).",
        "",
        f"## Saved queries ({len(queries)})",
        "",
        "| No. | Query (production name) | English (proposed) | Database | Statement | "
        "Referenced by | What it does |",
        "|---:|---|---|---|---|---:|---|",
    ]
    for number, query in enumerate(sorted(queries, key=lambda q: (q.get("database_id", ""),
                                                                  q.get("name", ""))), 1):
        database, name = query.get("database_id", ""), query.get("name", "")
        verb = verbs[(database, name)]
        out.append(
            f"| {number} | `{escape(name)}` | {naming.english(name)} | "
            f"{escape(database)} | {('**' + verb + '**') if verb in writes else verb} | "
            f"{referenced.get((database, 'query', name), 0)} | {NEEDS_DOC} |"
        )

    writers = [q for q in queries
               if verbs[(q.get("database_id", ""), q.get("name", ""))] in writes]
    unreferenced_writers = [
        q for q in writers
        if referenced.get((q.get("database_id", ""), "query", q.get("name", "")), 0) == 0
    ]
    out += [
        "",
        f"**{len(writers)} of {len(queries)} queries write**, and "
        f"{len(unreferenced_writers)} of those are referenced by nothing. A write "
        "query reachable only from the navigation pane, with no guard and no "
        "idempotency, is the highest-consequence thing in a catalogue like this.",
        "",
        f"## VBA modules ({len(modules)})",
        "",
        "`Referenced by` counts text naming the **module**, and VBA calls a "
        "**procedure**: code writes `Call S色設定`, never `共通ルーチン.S色設定`. So a "
        "module referenced by nothing may hold procedures called from everywhere, and "
        "this column is not evidence about the module's contents. Reading it as such "
        "is what produced `E-16` — a published finding that `S色設定` is never "
        "called, when it is the first statement of the main menu's `Form_Open`.",
        "",
        "| No. | Module | English (proposed) | Database | Module name referenced by |",
        "|---:|---|---|---|---:|",
    ]
    for number, module in enumerate(sorted(modules, key=lambda m: (m.get("database_id", ""),
                                                                   m.get("name", ""))), 1):
        database, name = module.get("database_id", ""), module.get("name", "")
        out.append(f"| {number} | `{escape(name)}` | {naming.english(name)} | "
                   f"{escape(database)} | "
                   f"{referenced.get((database, 'module', name), 0)} |")

    out += ["", f"## SQL naming an object that does not exist ({len(sql.dangling)})", ""]
    if not sql.dangling:
        out += ["Every table and query named in a saved query or a screen record "
                "source exists.", ""]
    else:
        out += [
            "Each statement below reads from or writes to a name that is **not a "
            "table, not a saved query, and not created by the statement itself**. "
            "A saved query in this state cannot run; a screen whose record source is "
            "in this state cannot open.",
            "",
            "Checked against the full inventory of both databases, and against every "
            "`SELECT INTO` and `CREATE TABLE` in the acquisition - so a work table "
            "built at runtime is not reported here.",
            "",
            "| Statement | Names, which does not exist |",
            "|---|---|",
        ]
        for label, absent in sql.dangling.items():
            out.append(f"| {escape(label)} | "
                       f"`{'`, `'.join(escape(a) for a in absent)}` |")
        out += ["",
                "This is the check that has no counterpart in the phase documents: a "
                "name is only ever read in the context that uses it, so a reference to "
                "something absent reads exactly like a reference to something present.",
                ""]

    external = getattr(sql, "external_databases", {}) or {}
    out += ["", f"## SQL that runs against another database file ({len(external)})", ""]
    if not external:
        out += ["No statement carries an `IN` clause.", ""]
    else:
        targets: dict[str, int] = defaultdict(int)
        for names in external.values():
            for name in names:
                targets[name] += 1
        out += [
            f"{len(external)} statements carry an `IN \"…\"` clause, which makes the "
            "query run against **another database file named by absolute path** rather "
            "than against this application's linked tables. A table absent from the "
            "acquired copy is therefore not missing; it is expected at the end of that "
            "path, in a database this run never opened.",
            "",
            "| Target named in the clause | Statements |",
            "|---|---:|",
        ]
        for name, count in sorted(targets.items(), key=lambda kv: -kv[1]):
            note = ("**a variable** — check it is assigned"
                    if not ("\\" in name or "/" in name) else "")
            out.append(f"| `{escape(name)}` {note} | {count} |")
        out += [
            "",
            "**This is a boundary, and it is wider than the stored links.** A migration "
            "planned against the linked tables alone would miss every one of these.",
            "",
            "**Scope.** This counts stored record sources only. SQL that a form builds "
            "in VBA carries `IN` clauses too, and those cannot be counted as statements "
            "because the path is a variable rather than a literal - which is itself the "
            "finding: in A05 the variable is `Sパス名`, declared `Public` and assigned "
            "nowhere in either database. See `Q20`.",
            "",
        ]

    out += ["", f"## Files crossing the boundary ({len(linked) + len(interfaces)})", "",
            "Every declared inbound and outbound file. A format claim about any of "
            f"these needs one real sample ({NOT_EXTRACTED} means the declaration says "
            "nothing about it).", "",
            "| File or link | Database | Direction | Declared format |",
            "|---|---|---|---|"]
    for row in sorted(linked, key=lambda r: str(r.get("name", ""))):
        connect = (row.get("connect") or (row.get("metadata") or {}).get("connect") or "")
        out.append(f"| `{escape(row.get('name'))}` | {escape(row.get('database_id'))} | "
                   f"inbound link | `{escape(connect) or NOT_EXTRACTED}` |")
    for row in sorted(interfaces, key=lambda r: str(r.get("name", r.get("path", "")))):
        out.append(f"| `{escape(row.get('name') or row.get('path'))}` | "
                   f"{escape(row.get('database_id'))} | "
                   f"{escape(row.get('direction') or NEEDS_DOC)} | "
                   f"`{escape(row.get('format')) or NOT_EXTRACTED}` |")
    return "\n".join(out) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--app-id", help="Defaults to the manifest's app id, else the folder name.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    space = workspace_contract.Workspace(args.app_root)
    bundles = workspace_contract.find_bundle_dirs(space)
    if not bundles:
        print(f"no acquisition bundle under {space.root}; run `$ak acquire` first")
        return 2
    bundle = max(bundles, key=lambda p: (p / "bundle.json").stat().st_mtime)

    app_id = args.app_id or read_app_id(space.root) or space.root.name
    derived = read_json(space.extracted("derived-extraction.json"))
    types = load_types()
    facts_dir = space.extracted("ui-facts")
    sql = analyse_sql(bundle, facts_dir)
    naming = Naming(PACKAGE, space.input_dir("decisions") / "glossary.yaml")
    table_names = {r.get("name", "") for r in rows_of(
        read_json(bundle / "databases" / "tables.json"))}
    writes = sql_contract.write_profile(
        code_sources(space, bundle, facts_dir), table_names)
    meaning = meanings_contract.load(
        space.input_dir("decisions") / "meanings.yaml")
    for problem in meaning.incomplete:
        print(f"meanings.yaml: ignored, {problem}")
    if meaning.unfilled:
        # One line, not one per subject: these are the blank entries `$ak meanings`
        # wrote, and a worklist is not a list of defects.
        print(f"meanings.yaml: {len(meaning.unfilled)} subject(s) still blank, so "
              f"their cells read {NEEDS_DOC}")

    written: list[str] = []
    catalogues = {
        f"{app_id}_DataCatalogue.md": data_catalogue(
            app_id, bundle, types, sql, naming, writes, meaning),
        f"{app_id}_ScreenCatalogue.md": screen_catalogue(
            app_id, bundle, space.extracted("ui-facts"), derived, naming),
        f"{app_id}_LogicCatalogue.md": logic_catalogue(
            app_id, bundle, derived, sql, naming),
    }
    if args.dry_run:
        for name, text in catalogues.items():
            print(f"{name}: {len(text):,} bytes, {len(text.splitlines())} lines")
        return 0

    output = space.output_dir()
    output.mkdir(parents=True, exist_ok=True)
    for name, text in catalogues.items():
        io.open(output / name, "w", encoding="utf-8", newline="\n").write(text)
        written.append(f"{name} ({len(text):,} bytes)")
    for entry in written:
        print(f"wrote {entry}")
    print(f"into {output}")
    return 0


def read_app_id(root: Path) -> str | None:
    manifest = root / "manifest.yaml"
    if not manifest.is_file():
        return None
    try:
        import yaml

        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        return ((data.get("app") or {}).get("id")) or None
    except Exception:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
