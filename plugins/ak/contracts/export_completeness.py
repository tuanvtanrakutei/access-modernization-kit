"""What an export does not say: whether the exporter wrote the whole object.

The imported-sources adapter verifies every file against the SHA-256 the export
manifest declares, and the manifest against the source database's own digest. On A05
all of it passed, and the definition text was still materially incomplete:
`メインメニュー` arrived with 21 of its 45 procedures, 45 of its 114 control blocks and
1,642 of its 4,886 lines. Ten errata followed from that gap, and the largest was a
third of the reachability figure.

Integrity answers "is this the file the exporter wrote". Nothing answered "did the
exporter write the whole object", and the position this module is built around is that
**one observation cannot answer it**. A file whose digest is correct, whose object
count matches the other route's, and which ends on a complete `End Sub` is
indistinguishable from a complete one - which is precisely how A05's export passed
every gate the kit has. Pretending otherwise would put a checkmark where the doubt
belongs.

So two things, neither of which claims to be the check that does not exist:

  **Shape, recorded.** Lines, `Begin`/`End` blocks, procedures, per object. A first
  export has nothing to be compared against; recording its shape is what gives the
  second one something. This costs nothing and is the part that would have made A05
  visible the moment the re-export arrived, rather than after somebody thought to diff.

  **Shape, compared.** Where the workspace has seen an object before - a previous run's
  record, or the other acquisition route's staging - a disagreement about its size is
  reported. That is "re-export and diff", which is what actually found this, turned
  into something that happens without anyone deciding to do it.

A disagreement is reported in both directions and never as "it shrank". A05's first
export was the incomplete one, so the correction arrived as a *rise*; a rule that only
watched for drops would have said nothing at the exact moment the evidence appeared.
What is reportable is that two observations of one object disagree, and which of them
is smaller.

Unbalanced nesting is reported outright, because that one *is* decidable from a single
file. It would not have caught A05 - the truncated `メインメニュー` balanced - and it is
worth having anyway, for the ordinary truncation: a transfer that stopped early, a
file cut at a byte boundary, a disk that filled.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

# A SaveAsText definition nests `Begin`/`End` blocks, one per control. `End` alone on
# its line is the block terminator; `End Sub`, `End If` and the rest are VBA and are
# not counted here, which is why the pattern anchors to the end of the line.
BEGIN_RE = re.compile(r"(?m)^[ \t]*Begin\b")
END_RE = re.compile(r"(?m)^[ \t]*End[ \t]*$")

# `Declare` is excluded because an API declaration is a `Function` with no body and no
# `End Function`; counting it would make every module with a Win32 declaration look
# truncated. This is the kind of detail that turns a check into a nuisance nobody
# reads, which is worse than no check.
#
# The name is `[^\s(]`, not `[A-Za-z0-9_]`. VBA takes an identifier in the local
# codepage, and in this application family half of them are Japanese: the ASCII class
# counted `Private Sub btn1_Click()` and skipped `Public Function 合計()`, which is a
# completeness check that under-counts procedures in exactly the population it was
# written for.
PROCEDURE_RE = re.compile(
    r"(?m)^[ \t]*(?!.*\bDeclare\b)"
    r"(?:(?:Private|Public|Friend|Static)[ \t]+)*"
    r"(?:Sub|Function|Property[ \t]+(?:Get|Let|Set))[ \t]+[^\s(]")
PROCEDURE_END_RE = re.compile(r"(?m)^[ \t]*End[ \t]+(?:Sub|Function|Property)\b")


@dataclass(frozen=True)
class Shape:
    """How big an object's definition text is, in the units that reveal a gap."""

    lines: int
    characters: int
    blocks: int
    block_ends: int
    procedures: int
    procedure_ends: int

    @property
    def balanced(self) -> bool:
        return self.blocks == self.block_ends and self.procedures == self.procedure_ends

    @property
    def imbalance(self) -> str:
        if self.blocks != self.block_ends:
            return (f"{self.blocks} Begin against {self.block_ends} End: the "
                    "definition stops inside a control block")
        if self.procedures != self.procedure_ends:
            return (f"{self.procedures} procedure(s) declared against "
                    f"{self.procedure_ends} closed: the code stops inside a procedure")
        return ""

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def shape_of(text: str) -> Shape:
    # Trailing whitespace is stripped before counting lines, because one export ending
    # with a blank line and another not is not a difference about the object, and a
    # comparison that reports it teaches the reader to skim past this whole report.
    return Shape(
        lines=len(text.rstrip().splitlines()),
        characters=len(text),
        blocks=len(BEGIN_RE.findall(text)),
        block_ends=len(END_RE.findall(text)),
        procedures=len(PROCEDURE_RE.findall(text)),
        procedure_ends=len(PROCEDURE_END_RE.findall(text)),
    )


def from_json(value: Any) -> Shape | None:
    if not isinstance(value, dict):
        return None
    try:
        return Shape(**{key: int(value[key]) for key in Shape.__dataclass_fields__})
    except (KeyError, TypeError, ValueError):
        return None


# Below this, a difference is a line ending or a trailing newline, not a missing
# procedure. Stated as a fraction rather than a line count because the objects range
# from a 12-line macro to a 4,886-line main menu, and a rule that suits one insults the
# other.
MATERIAL = 0.02


def disagreements(previous: Shape, current: Shape) -> list[str]:
    """Where two observations of one object disagree about its size.

    Both directions. A05's first export was the incomplete one, so the correction
    arrived as a rise, and a rule that only watched for drops would have said nothing
    at the moment the evidence turned up.
    """
    found = []
    for field, label in (("procedures", "procedure(s)"), ("blocks", "control block(s)"),
                         ("lines", "line(s)")):
        was, now = getattr(previous, field), getattr(current, field)
        if was == now:
            continue
        largest = max(was, now)
        if largest and abs(now - was) / largest < MATERIAL:
            continue
        smaller = "the one now in the bundle" if now < was else "the earlier one"
        found.append(f"{label}: {was} then, {now} now - {smaller} is missing content")
    return found
