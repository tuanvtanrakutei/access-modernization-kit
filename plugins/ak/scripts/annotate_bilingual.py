#!/usr/bin/env python3
"""Print the English name beside every production name, in the narratives too.

The catalogues render `商品コード (product_cd?)` because they are generated. The phase
documents are written, so they carried the Japanese alone - which is right for
authority and wrong for a developer who has to build the replacement and cannot type
`雑貨Ⅱアイテム別確認表フッタ` into anything.

This annotates the published documents in place. Three rules keep it from doing harm:

  **First occurrence only.** A name annotated on every mention turns a table row into
  a wall. The first mention in each document carries the English; after that the
  reader knows it, and the appendix at the end of the document lists every name in
  full. That is how a technical document normally handles a second vocabulary.

  **Never inside a fenced block.** A mermaid diagram, a VBA snippet or a SQL
  statement is code: inserting a parenthesis into it changes what it means, and in a
  diagram it breaks the render. Fenced regions are skipped entirely.

  **Idempotent.** A name already followed by a parenthesis is left alone, so running
  this twice - or after re-publishing one document - does not produce
  `商品コード (product_cd?) (product_cd?)`.

The Japanese name stays exactly as it was, and stays authoritative. Nothing here
translates anything in place.
"""
from __future__ import annotations

import argparse
import io
import re
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / "contracts"))

import bilingual as bilingual_contract  # noqa: E402
import workspace as workspace_contract  # noqa: E402

FENCE = re.compile(r"^(```|~~~)", re.MULTILINE)
# A production name as the documents write it: inside backticks.
BACKTICKED = re.compile(r"`([^`\n]{1,120})`")
JAPANESE = re.compile(r"[぀-ヿ一-鿿＀-￯]")
# Already annotated. The `?` a name used to carry is still accepted here, so a
# document annotated by an older version is recognised and not annotated a second
# time.
#
# The character class has to admit a dot and a hyphen, because a composed name can be
# `assortment_support_data.mdb`, and the match has to run against the whole remaining
# text rather than a fixed peek: the first version looked at 40 characters, and
# `produce_aggregate_product_master_footer?` is 41, so the closing bracket fell
# outside the window and the name was annotated a second time. 14 duplicates in the
# published set, and the test that was supposed to catch it used `order_data`, which
# is short and has no dot.
ALREADY = re.compile(r"\s*\([a-z0-9_.\-]+\??(?:\s+partial)?\)")


def fenced_spans(text: str) -> list[tuple[int, int]]:
    """Where the code blocks are, so nothing is inserted into one."""
    spans: list[tuple[int, int]] = []
    open_at: int | None = None
    for match in FENCE.finditer(text):
        if open_at is None:
            open_at = match.start()
        else:
            spans.append((open_at, match.end()))
            open_at = None
    if open_at is not None:
        spans.append((open_at, len(text)))
    return spans


def annotate(text: str, naming: object, seen: set[str] | None = None) -> tuple[str, int]:
    """Annotate the first mention of each production name. Returns text and a count."""
    seen = seen if seen is not None else set()
    spans = fenced_spans(text)

    def inside_fence(position: int) -> bool:
        return any(start <= position < end for start, end in spans)

    out: list[str] = []
    cursor = 0
    added = 0
    for match in BACKTICKED.finditer(text):
        name = match.group(1)
        if inside_fence(match.start()):
            continue
        if not JAPANESE.search(name):
            continue
        if name in seen:
            continue
        if ALREADY.match(text, match.end()):
            seen.add(name)
            continue
        rendered = naming.of(name)  # type: ignore[attr-defined]
        if not rendered.english or not rendered.is_complete:
            # A partial proposal is not printed inline. It would put a half-finished
            # name in front of a reader as though it were a name.
            continue
        seen.add(name)
        out.append(text[cursor:match.end()])
        out.append(f" ({rendered.english})")
        cursor = match.end()
        added += 1
    out.append(text[cursor:])
    return "".join(out), added


APPENDIX_HEADING = "## Appendix — production names and their English proposals"


def appendix(text: str, naming: object) -> str:
    """Every production name the document mentions, in full, at the end."""
    names: list[str] = []
    spans = fenced_spans(text)
    for match in BACKTICKED.finditer(text):
        name = match.group(1)
        if any(s <= match.start() < e for s, e in spans):
            continue
        if JAPANESE.search(name) and name not in names:
            names.append(name)
    if not names:
        return ""
    lines = [
        "",
        "---",
        "",
        APPENDIX_HEADING,
        "",
        "The Japanese name is the production name and is authoritative. The English is "
        "composed from `specifications/ja-en-terms.yaml`. The table below says what "
        "each one's standing is: **accepted** means a person settled it; **A01 "
        "precedent** means every term in it was already decided in the A01 conversion "
        "table, so overriding it makes the two systems disagree; **proposed** means "
        "this analysis composed it and nobody has confirmed it; **partial** means only "
        "part of the Japanese matched a known term. Correct any of them in "
        "`input/decisions/glossary.yaml` and re-run `$ak bilingual`.",
        "",
        "| Production name | English | |",
        "|---|---|---|",
    ]
    for name in sorted(names):
        rendered = naming.of(name)  # type: ignore[attr-defined]
        if not rendered.english:
            english, note = "—", "no term matched"
        else:
            english = f"`{rendered.english}`"
            if rendered.accepted:
                note = "accepted"
            elif rendered.provenance == "A01" and rendered.is_complete:
                note = "A01 precedent"
            else:
                note = "proposed" if rendered.is_complete else "**partial**"
        lines.append(f"| `{name}` | {english} | {note} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", type=Path,
                        help="Workspace root; its output/ is annotated.")
    parser.add_argument("--outputs", type=Path, help="Annotate this directory instead.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.outputs:
        outputs = args.outputs
        glossary = outputs.parent / "input" / "decisions" / "glossary.yaml"
    elif args.app_root:
        space = workspace_contract.Workspace(args.app_root)
        outputs = space.output_dir()
        glossary = space.input_dir("decisions") / "glossary.yaml"
    else:
        print("give --app-root or --outputs")
        return 2
    if not outputs.is_dir():
        print(f"no such directory: {outputs}")
        return 2

    class Naming:
        def __init__(self) -> None:
            self.terms = bilingual_contract.load_terms(PACKAGE)
            self.accepted = bilingual_contract.load_accepted(glossary)
            self.cache: dict[str, object] = {}

        def of(self, name: str) -> object:
            if name not in self.cache:
                self.cache[name] = bilingual_contract.compose(
                    name, self.terms, self.accepted)
            return self.cache[name]

    naming = Naming()
    # The catalogues already render both names in every row; annotating them again
    # would duplicate what they are for.
    skip = ("Catalogue.md", "Catalogue.MD")
    total = 0
    for path in sorted(outputs.glob("*.md")):
        if path.name.endswith(skip):
            continue
        text = path.read_text(encoding="utf-8")
        body = text.split(APPENDIX_HEADING)[0].rstrip("\n-\r \t")
        annotated, added = annotate(body, naming)
        final = annotated.rstrip("\n") + "\n" + appendix(annotated, naming)
        if args.dry_run:
            print(f"{path.name}: {added} first-mention annotation(s)")
        elif final != text:
            io.open(path, "w", encoding="utf-8", newline="\n").write(final)
            print(f"{path.name}: {added} annotated, appendix refreshed")
        total += added
    if not args.dry_run:
        print(f"\n{total} name(s) annotated across {outputs}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
