"""What the SQL says about how tables relate, when the database declares nothing.

The A05 databases declare **zero** relationships. That is not a collection gap - DAO
was asked and the answer was none - so the catalogue's `FK` column could never be
filled from the schema, and a migration would have had to guess which columns were
meant to match.

The SQL knows. 79 saved queries and 118 record sources carry `JOIN ... ON` clauses,
and a join is a stronger statement about how the application *actually* relates two
tables than a declared constraint would be: a declared FK says what is permitted, a
join says what is done. It is weaker in the other direction - it constrains nothing,
and two columns joined once may have been a mistake - so everything here is INFERRED
and says so.

Three things are derived, and the limits of each are stated rather than smoothed over:

  relationships   Column pairs joined in real SQL, with how many places do it. Covers
                  only tables that appear in a join; a work table filled by VBA
                  string-built SQL will not.

  candidate keys  The column a table is most often joined *on*. For a master table
                  that is its key in practice. It cannot be confirmed here: proving a
                  column is unique needs rows, which means SAMPLE_DATA. A `WK*` work
                  table having no key is normal, not a finding.

  dangling refs   SQL naming a table or query that exists nowhere and is created
                  nowhere. Five A05 queries do this, which makes them unrunnable, and
                  nothing in the application distinguishes them from working ones.

Alias resolution is the fiddly part and the reason this is a module rather than a
regex at a call site: `ON t1.商品コード = m1.商品コード` names nothing until `FROM
商品マスタ AS m1` is read. An unresolved alias is counted and reported, never guessed.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field

# `ON a.b = c.d`, allowing bracketed names, which Access uses for anything with a
# space or a symbol in it.
ON_CLAUSE = re.compile(
    r"\bON\s+(\[[^\]]+\]|[^\s=().]+)\s*\.\s*(\[[^\]]+\]|[^\s=()]+)"
    r"\s*=\s*(\[[^\]]+\]|[^\s=().]+)\s*\.\s*(\[[^\]]+\]|[^\s=(),;]+)",
    re.IGNORECASE,
)
# `FROM x AS y` / `JOIN x y`. The alias is the short name the ON clause will use.
ALIAS_CLAUSE = re.compile(
    r"\b(?:FROM|JOIN)\s+(\[[^\]]+\]|[^\s,()]+)\s+(?:AS\s+)?([A-Za-z]\w*)\b",
    re.IGNORECASE,
)
# Anything the SQL reads from or writes to.
OBJECT_REF = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE)\s+(\[[^\]]+\]|[^\s,();]+)", re.IGNORECASE
)
# A table this SQL creates, so naming it is not a dangling reference.
CREATES = re.compile(r"\b(?:INTO|CREATE\s+TABLE)\s+(\[[^\]]+\]|[^\s,();]+)", re.IGNORECASE)

# Words that follow FROM/JOIN/INTO without being an object name.
NOT_A_NAME = {"select", "distinct", "distinctrow", "top"}

# A word that follows a table name without being its alias. `FROM 元商品マスタC LEFT
# JOIN ...` reads as alias `LEFT` otherwise, which then put the real table name into
# the alias values and made every dangling reference in the A05 queries invisible -
# the check reported 0 where a plainer regex had found 5.
NOT_AN_ALIAS = {
    "left", "right", "inner", "outer", "full", "cross", "join", "on", "where",
    "group", "order", "having", "union", "as", "in", "and", "or", "not", "with",
    "select", "from", "into", "set", "values", "by", "asc", "desc", "distinct",
}


def unbracket(name: str) -> str:
    return name.strip().strip("[]").strip()


@dataclass
class Relationship:
    """One column pair joined in real SQL."""

    left_table: str
    left_column: str
    right_table: str
    right_column: str
    occurrences: int = 1
    seen_in: list[str] = field(default_factory=list)

    @property
    def same_column_name(self) -> bool:
        """A join between two columns of the same name is the ordinary case here."""
        return self.left_column == self.right_column


@dataclass
class Analysis:
    relationships: list[Relationship]
    candidate_keys: dict[str, list[tuple[str, int]]]
    dangling: dict[str, list[str]]
    unresolved_aliases: dict[str, int]
    joined_through_query: dict[str, int]
    sources_scanned: int

    @property
    def tables_in_a_join(self) -> set[str]:
        return {t for r in self.relationships for t in (r.left_table, r.right_table)}


def analyse(
    sources: dict[str, str],
    table_names: set[str],
    query_names: set[str] | None = None,
) -> Analysis:
    """Read every SQL source and report what it says about relationships.

    `sources` maps a label a reader will recognise - a query or screen name - to its
    SQL. The label is carried into each result so a claim can be followed back.
    """
    query_names = query_names or set()
    known = table_names | query_names

    pairs: dict[tuple[str, str, str, str], Relationship] = {}
    unresolved: Counter[str] = Counter()
    through_query: Counter[str] = Counter()
    dangling: dict[str, list[str]] = {}

    for label, text in sources.items():
        if not text:
            continue
        aliases = {
            alias.lower(): unbracket(real)
            for real, alias in ALIAS_CLAUSE.findall(text)
            if unbracket(real).lower() not in NOT_A_NAME
            and alias.lower() not in NOT_AN_ALIAS
        }

        def resolve(name: str) -> str:
            cleaned = unbracket(name)
            return aliases.get(cleaned.lower(), cleaned)

        for left_table, left_column, right_table, right_column in ON_CLAUSE.findall(text):
            left, right = resolve(left_table), resolve(right_table)
            if left not in table_names or right not in table_names:
                # A join onto a saved query is legitimate and is not a relationship
                # between tables, so it is counted separately rather than reported as
                # unresolved. What remains unresolved is a name that is neither table,
                # nor query, nor a resolvable alias - which in A05 is exactly the two
                # staging variants that do not exist.
                for name in (left, right):
                    if name in table_names:
                        continue
                    if name in query_names:
                        through_query[name] += 1
                    else:
                        unresolved[name] += 1
                continue
            # One ordering, so A-B and B-A are the same relationship.
            key = tuple(sorted([(left, unbracket(left_column)),
                                (right, unbracket(right_column))]))
            flat = (key[0][0], key[0][1], key[1][0], key[1][1])
            existing = pairs.get(flat)
            if existing is None:
                pairs[flat] = Relationship(*flat, occurrences=1, seen_in=[label])
            else:
                existing.occurrences += 1
                if label not in existing.seen_in:
                    existing.seen_in.append(label)

        created = {resolve(name) for name in CREATES.findall(text)}
        absent = sorted({
            resolve(name) for name in OBJECT_REF.findall(text)
            if unbracket(name).lower() not in NOT_A_NAME
            and not unbracket(name).startswith("(")
            and resolve(name) not in known
            and resolve(name) not in aliases.values()
            and resolve(name).lower() not in {a.lower() for a in aliases}
            and resolve(name) not in created
        })
        if absent:
            dangling[label] = absent

    # A table's candidate key: the column it is most often joined on. Both sides
    # count - a join names the same conceptual key from either direction.
    joined_on: dict[str, Counter[str]] = defaultdict(Counter)
    for relationship in pairs.values():
        joined_on[relationship.left_table][relationship.left_column] += relationship.occurrences
        joined_on[relationship.right_table][relationship.right_column] += relationship.occurrences

    return Analysis(
        relationships=sorted(pairs.values(),
                             key=lambda r: (-r.occurrences, r.left_table, r.left_column)),
        candidate_keys={table: counts.most_common()
                        for table, counts in sorted(joined_on.items())},
        dangling=dict(sorted(dangling.items())),
        unresolved_aliases=dict(unresolved.most_common()),
        joined_through_query=dict(through_query.most_common()),
        sources_scanned=len([t for t in sources.values() if t]),
    )


def is_work_table(name: str) -> bool:
    """A work table with no primary key is normal and should not read as a finding.

    Named by convention in this application family: `WK` or `W` prefix, or a `ＢＫ`
    backup prefix. The convention is not a guarantee, which is why the catalogue says
    "by naming convention" wherever it uses this.
    """
    return name.startswith(("WK", "W", "ＷＫ", "ＢＫ", "BK", "tmp", "TMP", "Temp"))
