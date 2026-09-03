"""Compose an English name from Japanese terms, and say how much of it was covered.

Every published name in this kit is the production name, unchanged - that rule does
not move. What this adds is a second name beside it, for the people who have to build
the replacement and cannot type `雑貨Ⅱアイテム別確認表フッタ` into a migration script.

Three things keep it honest:

  Coverage is reported, never hidden. A name composed from terms that cover 60% of
  its characters is a *partial* proposal and says so. A fully covered name is still a
  proposal - composition is mechanical, and mechanical is not the same as correct.

  Provenance travels with the name. A term decided in the A01 conversion table is
  precedent, binding on later projects; a term this analysis proposed is a suggestion
  a person has not yet accepted. A rendered name that mixes them is only as settled
  as its weakest term, and `provenance` returns that.

  A trailing index is a position, not a word. `店舗コード1` … `店舗コード21` are one
  term twenty-one times, which is why 328 A05 columns collapse to 137 base names -
  and why the index is stripped before matching and re-attached afterwards.

Nothing here decides anything. `input/decisions/glossary.yaml` is where a person
accepts or overrides a name, and an accepted name always wins over a composed one.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SPEC_NAME = "ja-en-terms.yaml"

# A run of digits at the end, in either width. `数量12` -> `数量` + `12`.
TRAILING_INDEX = re.compile(r"([0-9０-９]+)$")
# A run of characters that is already Latin and needs no translation. A run, not a
# character, so a date or a code inside a name survives as one token.
LATIN_RUN = re.compile(r"[A-Za-z0-9_\-. ]+")


@dataclass
class Rendered:
    """One name, its English proposal, and how much of it is actually accounted for."""

    japanese: str
    english: str
    terms_used: list[str]
    covered: float
    provenance: str
    accepted: bool = False

    @property
    def is_complete(self) -> bool:
        return self.covered >= 0.999

    def bilingual(self) -> str:
        """`商品コード (product_cd)`, the form a reader sees.

        A partial proposal is marked so nobody mistakes it for a settled name, and a
        name with no English at all renders as the Japanese alone rather than as an
        empty parenthesis.
        """
        if not self.english:
            return self.japanese
        if self.accepted:
            return f"{self.japanese} ({self.english})"
        if self.is_complete:
            return f"{self.japanese} ({self.english}?)"
        return f"{self.japanese} ({self.english}? partial)"


def load_terms(package_root: Path) -> dict[str, dict[str, Any]]:
    import yaml

    path = Path(package_root) / "specifications" / SPEC_NAME
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # Keys are coerced to text because YAML 1.1 turns a bare `No`, `Yes`, `On` or
    # `Off` into a boolean, and a term dictionary for Japanese business names has
    # every reason to contain a column called `No`. A spec typo should read oddly,
    # not raise from inside a normaliser three calls away.
    return {str(key): value for key, value in (data.get("terms") or {}).items()}


def normalise(text: str) -> str:
    """NFKC, because `ＦＬＧ` and `FLG` are the same term written two ways.

    Access names differ by width freely - the most-joined column pair in A05 is
    `DPコード` against `ＤＰコード` - so matching without normalising would translate
    one and miss the other.
    """
    return unicodedata.normalize("NFKC", text)


def compose(
    name: str,
    terms: dict[str, dict[str, Any]],
    accepted: dict[str, str] | None = None,
) -> Rendered:
    """Render one Japanese name, longest term first, left to right."""
    accepted = accepted or {}
    if name in accepted:
        return Rendered(name, accepted[name], ["(accepted)"], 1.0, "accepted", True)

    stem, index = name, ""
    match = TRAILING_INDEX.search(name)
    if match and len(match.group(1)) < len(name):
        stem, index = name[: match.start()], normalise(match.group(1))

    if stem in accepted:
        english = accepted[stem] + (f"_{index}" if index else "")
        return Rendered(name, english, ["(accepted)"], 1.0, "accepted", True)

    # Normalised lookup, longest first, so `移動元` wins over `元` and `ＤＰコード`
    # over `コード`.
    lookup = {normalise(k): (k, v) for k, v in terms.items()}
    ordered = sorted(lookup, key=len, reverse=True)

    target = normalise(stem)
    pieces: list[tuple[int, str, str]] = []  # position, english, original term
    consumed = [False] * len(target)
    for key in ordered:
        start = 0
        while True:
            at = target.find(key, start)
            if at < 0:
                break
            if not any(consumed[at : at + len(key)]):
                original, entry = lookup[key]
                pieces.append((at, str(entry.get("en", "")), original))
                for i in range(at, at + len(key)):
                    consumed[i] = True
            start = at + 1

    # Anything already Latin is its own translation. Digits and letters are taken as
    # runs rather than character by character: `配送コースマスタ20241231バックアップ`
    # rendered as `..._2_0_2_4_1_2_3_1` before this, which is not a name anyone would
    # accept and buried the real problem - a date in a table name.
    for run in LATIN_RUN.finditer(target):
        if any(consumed[run.start():run.end()]):
            continue
        pieces.append((run.start(), run.group(0).lower().strip(" ."), run.group(0)))
        for i in range(run.start(), run.end()):
            consumed[i] = True

    pieces.sort(key=lambda p: p[0])
    english = "_".join(p[1] for p in pieces if p[1])
    english = re.sub(r"_+", "_", english).strip("_")
    if index and english:
        english = f"{english}_{index}"

    covered = (sum(consumed) / len(consumed)) if consumed else 0.0
    used = [p[2] for p in pieces]
    provenances = {
        str(terms[t].get("provenance", "analysis")) for t in used if t in terms
    }
    if not provenances:
        provenance = "none"
    elif provenances == {"A01"}:
        provenance = "A01"
    elif "analysis" in provenances and "A01" in provenances:
        provenance = "A01+analysis"
    else:
        provenance = sorted(provenances)[0]
    return Rendered(name, english, used, covered, provenance)


def load_accepted(glossary_path: Path) -> dict[str, str]:
    """Names a person has accepted or overridden. These always win.

    A missing file is not an error: it means nobody has accepted anything yet, which
    is the correct state for a run that has just been published.
    """
    if not glossary_path.is_file():
        return {}
    import yaml

    data = yaml.safe_load(glossary_path.read_text(encoding="utf-8")) or {}
    accepted: dict[str, str] = {}
    for section in ("tables", "columns", "terms"):
        for japanese, entry in (data.get(section) or {}).items():
            if isinstance(entry, dict) and entry.get("status") == "accepted":
                english = entry.get("en")
                if english:
                    accepted[japanese] = str(english)
            elif isinstance(entry, str):
                accepted[japanese] = entry
    return accepted
