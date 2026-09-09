#!/usr/bin/env python3
"""Read a Q&A register and the pages it indexes, and report where they disagree.

INTERVIEW is the one evidence class nothing in this kit can produce - it arrives only
because somebody asked a person a question and wrote the answer down - and five of the
six phases name it in what they lose without it (A19). A project that keeps a register
of those questions is therefore holding the most valuable evidence it has, and until
now the kit could see only that some files existed in `input/interviews/`.

    $ak interviews            read, report, and record what was read
    $ak interviews --dry-run  read and report, write nothing

Two shapes are read, and both are what a Notion "Markdown & CSV" export produces,
because that is the shape the register on a real project actually has:

    a database export   one CSV row per question, carrying ID, Status, Asker,
                        Respondent, both dates, and the screen the question is about
    a page export       one `.md` per question: an H1, a block of `Key: value`
                        properties, then the conversation, with each answer led by
                        a dated marker in full-width brackets

Matched on the `ID` both carry. What the comparison is for is the disagreement: a
register row marked `Answered` whose page holds no answer is not a closed question, and
nothing else in the workspace can tell you so. Observed on A06 the first time this ran
on a real register - ID 6, `Status: Answered`, `Respondent: 榎本 稔`,
`Answer date: 2026/08/30`, and not one answer in the page.

A record is written to `.ak/extracted/interview-register.json` rather than only printed,
which is backlog A24's whole point: `$ak samples` found a real contradiction on A05 and
put it where nothing could cite it. `ScreenCatalogue` reads this record, and says
**not measured** where it is absent - because a screen with no recorded answer over an
unmeasured register cannot be told from one over a measured register.

Exit codes: 0 when nothing is reported, 1 when something is, 2 when there is no register
to read. It is a report, not a gate: an unanswered question is a fact about a project,
not a reason to refuse to work.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import workspace as workspace_contract  # noqa: E402

RECORD = "interview-register.json"
SCHEMA_VERSION = "1.0"

# Notion writes a BOM. `cp932` is last because a register hand-edited in Excel on a
# Japanese host arrives that way, and a mojibake register is worse than a refused one.
ENCODINGS = ("utf-8-sig", "utf-8", "cp932")

# An answer marker, and the reason this is not simply "text in full-width brackets":
# Japanese prose uses them for emphasis, and a real register does - Q&A 5 on A06 opens
# its body with `【質問1：インポートファイルの文字コードについて】`, a heading, not an
# answer. Requiring a date is what separates the two, and a date is also what makes the
# marker citable: `path::person, YYYY-MM-DD` is one of the anchor forms the gates accept.
ANSWER = re.compile(r"【\s*(\d{4})/(\d{1,2})/(\d{1,2})\s*[:：]\s*([^】]+?)\s*】")

# Header names, not positions. The same Notion database exports twice with the columns
# in two different orders (`X.csv` and `X_all.csv` on A06 differ), so a position-mapped
# reader would be right about one file and silently wrong about the other. Several names
# carry a full-width parenthesis, which is why they are matched by prefix.
FIELDS = {
    "id": ("ID",),
    "title": ("詳細", "Detail", "Name"),
    "status": ("Status",),
    "asker": ("Asker",),
    "respondent": ("Respondent",),
    "ask_date": ("Ask date",),
    "answer_date": ("Answer date",),
    "screen": ("機能・画面", "Funct/Scr"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def decode(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ENCODINGS:
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeError(f"{path.name} is not UTF-8, UTF-8 with a BOM, or CP932")


def _column_map(header: list[str]) -> dict[str, str]:
    """Which column answers which field, by name and by prefix."""
    resolved: dict[str, str] = {}
    for field, candidates in FIELDS.items():
        for column in header:
            plain = (column or "").strip()
            if any(plain.startswith(candidate) for candidate in candidates):
                resolved[field] = column
                break
    return resolved


def read_register(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    reader = csv.DictReader(io.StringIO(decode(path)))
    columns = _column_map(list(reader.fieldnames or []))
    if "id" not in columns:
        raise ValueError(f"{path.name} has no ID column; columns are {reader.fieldnames}")
    for row in reader:
        identifier = (row.get(columns["id"]) or "").strip()
        if not identifier:
            continue
        record = {"id": identifier}
        for field, column in columns.items():
            if field != "id":
                record[field] = (row.get(column) or "").strip()
        rows.append(record)
    return rows


def read_page(path: Path) -> dict[str, Any] | None:
    """One exported page: its properties, and every dated answer in its body.

    A page with no property block is not a Q&A page - `input/interviews/` also holds
    the guide `init` writes and any note somebody left - so it is skipped rather than
    reported. Deciding that by shape rather than by filename keeps the rule from
    breaking the moment somebody names a real answer `README.md`.
    """
    text = decode(path)
    lines = text.splitlines()
    properties: dict[str, str] = {}
    body_starts = 0
    started = False
    for index, line in enumerate(lines):
        stripped = line.strip()
        if not started:
            if stripped.startswith("# "):
                started = True
            continue
        if not stripped:
            if properties:
                body_starts = index
                break
            continue
        if ":" not in stripped:
            body_starts = index
            break
        key, _, value = stripped.partition(":")
        key = key.strip()
        # A property key is short and has no spaces around punctuation; a sentence in
        # the body that happens to contain a colon is not one.
        if not key or len(key) > 40 or key.startswith(("#", "-", "*", "[", "!")):
            body_starts = index
            break
        properties[key] = value.strip()
    if not properties or "ID" not in properties:
        return None
    body = "\n".join(lines[body_starts:])
    answers = [
        {
            "recorded_on": f"{year}-{int(month):02d}-{int(day):02d}",
            "person": person.strip(),
        }
        for year, month, day, person in ANSWER.findall(body)
    ]
    return {
        "id": properties["ID"].strip(),
        "title": lines[0].lstrip("# ").strip() if lines else "",
        "properties": properties,
        "answers": answers,
        "path": path,
    }


def _looks_answered(status: str) -> bool:
    return status.strip().casefold() == "answered"


def compare(register: list[dict[str, Any]], pages: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Every disagreement between what the register claims and what the pages hold."""
    findings: list[dict[str, str]] = []
    by_id = {page["id"]: page for page in pages}
    for row in register:
        identifier = row["id"]
        page = by_id.get(identifier)
        status = row.get("status", "")
        title = row.get("title", "")
        if page is None:
            findings.append({
                "id": identifier, "code": "NO_PAGE",
                "detail": f"the register lists {identifier} ({title}) and no exported page carries that ID",
            })
        elif _looks_answered(status) and not page["answers"]:
            findings.append({
                "id": identifier, "code": "ANSWERED_WITHOUT_AN_ANSWER",
                "detail": (
                    f"{identifier} is `{status}`"
                    + (f", answered {row.get('answer_date')}" if row.get("answer_date") else "")
                    + (f" by {row.get('respondent')}" if row.get("respondent") else "")
                    + f", and {page['path'].name} holds no dated answer. "
                    "A closed question with no answer in it cannot be cited, and the "
                    "register is the only place saying it is closed."
                ),
            })
        elif not _looks_answered(status):
            findings.append({
                "id": identifier, "code": "NOT_ANSWERED",
                "detail": (
                    f"{identifier} is `{status}`"
                    + (f", asked {row.get('ask_date')}" if row.get("ask_date") else "")
                    + (f", awaiting {row.get('respondent')}" if row.get("respondent") else "")
                    + f" - {title}"
                ),
            })
    # Collapsed to one line, unlike the two above. Every register row lacking a screen
    # is the same structural gap in the register's own use, not a separate fact about
    # each question - and five identical lines drowned the two findings that were about
    # a specific question, which is the failure a report has instead of a crash.
    without_screen = [row["id"] for row in register if not (row.get("screen") or "").strip()]
    if without_screen:
        findings.append({
            "id": ",".join(without_screen), "code": "NO_SCREEN_NAMED",
            "detail": (
                f"{len(without_screen)} of {len(register)} question(s) name no screen "
                f"({', '.join(without_screen)}), so an answer cannot be tied to a row "
                "in Screens_Registry.md or to a phase document's section. The register "
                "already has the column for it"
            ),
        })
    known = {row["id"] for row in register}
    for page in pages:
        if page["id"] not in known:
            findings.append({
                "id": page["id"], "code": "NOT_IN_REGISTER",
                "detail": f"{page['path'].name} declares ID {page['id']}, which the register does not list",
            })
    return findings


def observe(space: Any) -> dict[str, Any]:
    root = Path(space.root)
    directory = space.input_dir("interviews")
    if not directory.is_dir():
        return {"registers": [], "pages": [], "register": [], "findings": []}
    registers, pages, unreadable = [], [], []
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        try:
            if path.suffix.lower() == ".csv":
                rows = read_register(path)
                registers.append({
                    "path": path.relative_to(root).as_posix(),
                    "sha256": sha256(path), "rows": rows,
                })
            elif path.suffix.lower() == ".md":
                page = read_page(path)
                if page is not None:
                    pages.append({**page, "relative": path.relative_to(root).as_posix(),
                                  "sha256": sha256(path)})
        except (OSError, ValueError, UnicodeError) as exc:
            unreadable.append({"path": path.relative_to(root).as_posix(), "detail": str(exc)})
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for register in registers:
        for row in register["rows"]:
            if row["id"] not in seen:
                seen.add(row["id"])
                merged.append(row)
    findings = compare(merged, pages)
    # Ordered so the two findings about a specific question are read before the notes
    # about the register's own shape. A report nobody reads to the end is a report.
    order = {"ANSWERED_WITHOUT_AN_ANSWER": 0, "NO_PAGE": 1, "NOT_IN_REGISTER": 2,
             "NOT_ANSWERED": 3, "NO_SCREEN_NAMED": 4}
    findings.sort(key=lambda item: (order.get(item["code"], 9), item["id"]))
    return {
        "registers": [{"path": r["path"], "sha256": r["sha256"], "rows": len(r["rows"])}
                      for r in registers],
        "pages": [{"path": p["relative"], "sha256": p["sha256"], "id": p["id"],
                   "answers": p["answers"]} for p in pages],
        "register": merged,
        "unreadable": unreadable,
        "findings": findings,
    }


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    space = workspace_contract.Workspace(args.app_root)
    result = observe(space)
    if not result["registers"] and not result["pages"]:
        print(f"no Q&A register or exported page under {space.input_dir('interviews')}")
        print("Export the register as Markdown & CSV: the CSV is the register itself, "
              "and a PDF is a rendering of it that breaks whenever the template does.")
        return 2

    print(f"{len(result['register'])} question(s) in {len(result['registers'])} register "
          f"file(s), {len(result['pages'])} exported page(s)")
    answered = sum(1 for page in result["pages"] if page["answers"])
    print(f"{answered} page(s) hold at least one dated answer")
    for entry in result.get("unreadable", []):
        print(f"  UNREADABLE {entry['path']}: {entry['detail']}")

    for finding in result["findings"]:
        print(f"  {finding['code']} {finding['detail']}")
    if not result["findings"]:
        print("nothing to report: every register row has a page, every closed question "
              "holds an answer, and every question names a screen")

    if not args.dry_run:
        record = space.extracted(RECORD)
        record.parent.mkdir(parents=True, exist_ok=True)
        record.write_text(
            json.dumps({"schema_version": SCHEMA_VERSION, **result},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"recorded {record}")
    return 1 if (result["findings"] or result.get("unreadable")) else 0


if __name__ == "__main__":
    raise SystemExit(main())
