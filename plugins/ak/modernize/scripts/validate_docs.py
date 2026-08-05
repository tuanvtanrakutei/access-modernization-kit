#!/usr/bin/env python3
"""Validate a bootstrapped modernization project's documentation set.

Reports only. It never edits, formats, or creates a file - machine detects,
human decides, agent executes.

Every check here exists because the corresponding defect actually occurred in a
real project, not because it seemed plausible:

  unresolved-placeholder  a path was guessed because a config row was never filled
  missing-config-key      a document consumes a key PROJECT_CONFIG never defines
  dead-config-key         a key must be filled that nothing reads, implying a
                          capability the pipeline does not have
  dangling-doc-ref        a document cites a file that does not exist
  issue-row-malformed     an issue row had 9 columns instead of 10 and rendered wrong
  issue-status-unknown    a status outside the documented vocabulary
  issue-number-duplicate  two rows claimed the same number
  dangling-issue-ref      source code cited an issue number with no row; this
                          happened with five code comments pointing at nothing
  stale-resolved-anchor   a row marked resolved cites a file that no longer
                          exists, which is how a row came to describe code that
                          had been reverted
  registry-*              the registry is the single source of truth for screen
                          identity; a parse failure there silently mis-scopes work
  missing-folder/readme   a per-screen artifact folder or its README is absent

Output is written as UTF-8 to a report file; the console summary stays ASCII so a
cp932 console cannot turn a passing run into a UnicodeEncodeError.

Exit status: 0 clean, 1 findings, 2 could not run.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys

ISSUE_STATUSES = {"open", "in_progress", "resolved", "deferred", "wont_fix"}
REGISTRY_STATUSES = {"not_started", "in_progress", "implemented", "verified", "deferred"}
ARTIFACT_FOLDERS = [
    "Business_flows",
    "Screen_plans",
    "Coding_Records",
    "Test_Instruction",
    "Code_Review",
    "Final_Acceptance",
    "Bug_Reports",
]
SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
# Tokens appearing in method documents as illustrations, not as config lookups.
DOC_EXAMPLE_TOKENS = {"PLACEHOLDER", "KEY", "SCREEN", "FIELD", "VALUE", "FILL"}
# Per-row example tokens inside templates, e.g. {{SCREEN_1_KEY}}, {{SCREEN_2_URL}}.
ROW_TOKEN_RE = re.compile(r"^SCREEN_\d+(_[A-Z_]+)?$")
# A bare lowercase single-word .md in prose is an illustration, not a reference:
# "instead of splitting `legacy.md` and `new.md`" must not be read as two refs.
PROSE_DOC_RE = re.compile(r"^[a-z][a-z0-9-]*\.md$")


class Findings:
    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str, str]] = []

    def add(self, severity: str, kind: str, where: str, detail: str) -> None:
        self.rows.append((severity, kind, where, detail))

    def sorted_rows(self):
        return sorted(self.rows, key=lambda r: (SEVERITY_ORDER.get(r[0], 9), r[1], r[2]))

    def __len__(self) -> int:
        return len(self.rows)


def read(path: str) -> str:
    return io.open(path, encoding="utf-8", errors="replace").read()


def md_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
        for name in filenames:
            if name.endswith(".md"):
                yield os.path.join(dirpath, name)


def rel(path: str, base: str) -> str:
    try:
        return os.path.relpath(path, base).replace(os.sep, "/")
    except ValueError:
        return path


# ---------------------------------------------------------------- config checks


def parse_config_keys(config_text: str) -> set[str]:
    """Keys the project is asked to fill: rows shaped | `KEY` | value | note |."""
    return set(re.findall(r"^\|\s*`([A-Z][A-Z0-9_]*)`\s*\|", config_text, re.M))


def unfilled_config_keys(config_text: str) -> set[str]:
    """Rows whose value cell is still the literal placeholder or empty."""
    out = set()
    for m in re.finditer(r"^\|\s*`([A-Z][A-Z0-9_]*)`\s*\|([^|]*)\|", config_text, re.M):
        key, value = m.group(1), m.group(2).strip().strip("`")
        if not value or value == "{{%s}}" % key or value.lower() in {"fill", "{{fill}}", "tbd"}:
            out.add(key)
    return out


def check_config(f: Findings, docs_dir: str, plugin_dir: str, config_path: str) -> None:
    cfg = read(config_path)
    declared = parse_config_keys(cfg)
    unfilled = unfilled_config_keys(cfg)

    for key in sorted(unfilled):
        f.add("HIGH", "unresolved-placeholder", rel(config_path, docs_dir),
              "key %s has no value; a downstream stage would guess a path" % key)

    # Two different questions need two different consumer sets, and conflating them
    # produced false positives in both directions on the first two runs.
    #
    #   missing-config-key  asks "does a method document read a key nobody declares?"
    #                       Only method documents count. A template's row tokens such
    #                       as {{SCREEN_1_KEY}} are filled in when an author writes a
    #                       row, not resolved from config, so counting them reported
    #                       seven keys as missing that should never be declared.
    #
    #   dead-config-key     asks "must the project fill a key nothing ever reads?"
    #                       Here templates DO count - {{SUBSYSTEM_CODE}} and friends
    #                       are substituted at instantiation. Excluding templates
    #                       reported eighteen dead keys where nine are dead.
    consumed_docs: dict[str, set[str]] = {}
    consumed_any: set[str] = set()

    def scan(root: str, into_docs: bool) -> None:
        if not root or not os.path.isdir(root):
            return
        for path in md_files(root):
            if os.path.basename(path) == "PROJECT_CONFIG.md":
                continue
            for key in set(re.findall(r"\{\{([A-Z][A-Z0-9_]*)\}\}", read(path))):
                if key in DOC_EXAMPLE_TOKENS or ROW_TOKEN_RE.match(key):
                    continue
                consumed_any.add(key)
                if into_docs:
                    consumed_docs.setdefault(key, set()).add(rel(path, root))

    scan(docs_dir, True)
    if plugin_dir:
        scan(os.path.join(plugin_dir, "docs"), True)
        scan(os.path.join(plugin_dir, "templates"), False)

    for key in sorted(k for k in consumed_docs if k not in declared):
        f.add("HIGH", "missing-config-key", ", ".join(sorted(consumed_docs[key])),
              "{{%s}} is consumed but PROJECT_CONFIG declares no such row" % key)

    # Only meaningful when a plugin tree is available to scan. A resolved project
    # instance has no placeholders left by definition, so every key would look dead.
    if plugin_dir and os.path.isdir(plugin_dir):
        for key in sorted(declared - consumed_any):
            f.add("LOW", "dead-config-key", rel(config_path, docs_dir),
                  "%s must be filled but no document or template reads it" % key)


# ------------------------------------------------------------ reference checks


def check_placeholders_in_instance(f: Findings, docs_dir: str) -> None:
    """A project instance should carry no unresolved placeholder outside its config."""
    for path in md_files(docs_dir):
        if os.path.basename(path) == "PROJECT_CONFIG.md":
            continue
        for line_no, line in enumerate(read(path).split("\n"), 1):
            for key in set(re.findall(r"\{\{([A-Z][A-Z0-9_]*)\}\}", line)):
                f.add("MEDIUM", "unresolved-placeholder", "%s:%d" % (rel(path, docs_dir), line_no),
                      "{{%s}} was never substituted" % key)


def check_dangling_doc_refs(f: Findings, docs_dir: str, extra_roots: list[str]) -> None:
    """A cited .md counts as present if it exists anywhere the project keeps documents.

    Screen artifacts legitimately cite design notes living beside the code, such as
    `backend/.../docs/purchasing_data.md`, and root files like `CLAUDE.md`. Searching
    only the docs directory reported those as dangling on the first run.
    """
    present = set()
    for root in [docs_dir] + [r for r in extra_roots if r and os.path.isdir(r)]:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in {".git", "node_modules", "__pycache__"}]
            for name in filenames:
                if name.endswith(".md"):
                    present.add(name)

    for path in md_files(docs_dir):
        text = read(path)
        for name in sorted(set(re.findall(r"`([A-Za-z0-9_][A-Za-z0-9_./-]*\.md)`", text))):
            base = os.path.basename(name)
            # {screen}.md and similar are patterns, not filenames
            if "{" in name or base in present or PROSE_DOC_RE.match(base):
                continue
            f.add("MEDIUM", "dangling-doc-ref", rel(path, docs_dir),
                  "cites `%s`, which exists nowhere in the docs or source trees" % name)


# ---------------------------------------------------------------- issue checks


def issue_rows(text: str):
    for line_no, line in enumerate(text.split("\n"), 1):
        m = re.match(r"^\|\s*(\d+)\s*\|", line)
        if m:
            yield line_no, int(m.group(1)), line


def check_issues(f: Findings, docs_dir: str, issues_path: str, source_dir: str | None) -> None:
    text = read(issues_path)
    where_base = rel(issues_path, docs_dir)
    seen: dict[int, int] = {}

    for line_no, num, line in issue_rows(text):
        fields = line.split("|")
        if len(fields) != 10:
            f.add("MEDIUM", "issue-row-malformed", "%s:%d" % (where_base, line_no),
                  "row #%d has %d pipe-separated fields, expected 10" % (num, len(fields)))
            continue

        status_cell = fields[6].strip()
        status_word = status_cell.split("(")[0].strip()
        if status_word and status_word not in ISSUE_STATUSES:
            f.add("MEDIUM", "issue-status-unknown", "%s:%d" % (where_base, line_no),
                  "row #%d status %r is outside the documented vocabulary" % (num, status_cell))

        if num in seen:
            f.add("HIGH", "issue-number-duplicate", "%s:%d" % (where_base, line_no),
                  "row #%d also appears at line %d" % (num, seen[num]))
        else:
            seen[num] = line_no

        if status_word == "resolved":
            for path_ref in set(re.findall(r"`([A-Za-z0-9_][A-Za-z0-9_/.-]*\.(?:py|ts|tsx|vb|sql))`", line)):
                if "{" in path_ref or "*" in path_ref:
                    continue
                if source_dir and not _exists_under(source_dir, path_ref):
                    f.add("LOW", "stale-resolved-anchor", "%s:%d" % (where_base, line_no),
                          "row #%d is resolved but cites `%s`, not found under the source tree"
                          % (num, path_ref))

    if source_dir and os.path.isdir(source_dir):
        cited: dict[int, set[str]] = {}
        for dirpath, dirnames, filenames in os.walk(source_dir):
            dirnames[:] = [d for d in dirnames if d not in {"__pycache__", "node_modules", ".git"}]
            for name in filenames:
                if not name.endswith((".py", ".ts", ".tsx", ".md")):
                    continue
                p = os.path.join(dirpath, name)
                for n in re.findall(r"Known_Issues\.md\s*#(\d+)", read(p)):
                    cited.setdefault(int(n), set()).add(rel(p, source_dir))
        for num in sorted(n for n in cited if n not in seen):
            f.add("HIGH", "dangling-issue-ref", ", ".join(sorted(cited[num])),
                  "code cites Known_Issues.md #%d but no such row exists" % num)


def _exists_under(root: str, needle: str) -> bool:
    tail = needle.replace("/", os.sep)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in {"__pycache__", "node_modules", ".git"}]
        for name in filenames:
            if os.path.join(dirpath, name).endswith(tail):
                return True
    return False


# ------------------------------------------------------------- registry checks


def check_registry(f: Findings, docs_dir: str, registry_path: str) -> None:
    text = read(registry_path)
    where_base = rel(registry_path, docs_dir)

    # Pick the header of the table that actually carries both status columns. Taking
    # the first table mentioning "screen" matched a legend table earlier in the file
    # and declared a perfectly good registry unparseable.
    header = None
    for line in text.split("\n"):
        if not line.startswith("|"):
            continue
        cells = [c.strip().strip("*` ").lower() for c in line.split("|")]
        if "status_be" in cells and "status_fe" in cells:
            header = cells
            break
    if header is None:
        f.add("HIGH", "registry-unparseable", where_base,
              "no table header row containing a screen column was found")
        return

    def col(name: str):
        return header.index(name) if name in header else None

    i_screen, i_key = col("screen"), col("screen_key")
    i_be, i_fe = col("status_be"), col("status_fe")
    if i_be is None or i_fe is None:
        f.add("HIGH", "registry-unparseable", where_base,
              "expected both status_be and status_fe columns; header is %s" % header)
        return

    keys: dict[str, int] = {}
    for line_no, line in enumerate(text.split("\n"), 1):
        if not line.startswith("|") or set(line.strip()) <= set("|- "):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) <= max(i_be, i_fe) or cells == header:
            continue
        if i_screen is not None and cells[i_screen].lower() == "screen":
            continue
        for idx, label in ((i_be, "status_be"), (i_fe, "status_fe")):
            value = cells[idx].strip("*` ")
            if value and value not in REGISTRY_STATUSES:
                f.add("MEDIUM", "registry-status-unknown", "%s:%d" % (where_base, line_no),
                      "%s is %r, outside the documented vocabulary" % (label, value))
        if i_key is not None and len(cells) > i_key:
            key = cells[i_key].strip("*` ")
            if key and key.lower() != "screen_key":
                if key in keys:
                    f.add("HIGH", "registry-duplicate-key", "%s:%d" % (where_base, line_no),
                          "screen_key %r also appears at line %d" % (key, keys[key]))
                else:
                    keys[key] = line_no


# -------------------------------------------------------------- layout checks


def check_layout(f: Findings, docs_dir: str) -> None:
    for folder in ARTIFACT_FOLDERS:
        path = os.path.join(docs_dir, folder)
        if not os.path.isdir(path):
            f.add("HIGH", "missing-folder", folder, "per-screen artifact folder is absent")
        elif not os.path.isfile(os.path.join(path, "README.md")):
            f.add("MEDIUM", "missing-readme", folder + "/", "folder has no README.md agent prompt")


# --------------------------------------------------------------------- runner


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Validate a modernization project's documentation set.")
    ap.add_argument("--docs-dir", required=True, help="the project's per-screen artifact directory")
    ap.add_argument("--plugin-dir", default="", help="plugin root, to learn which config keys are consumed")
    ap.add_argument("--source-dir", default="", help="source tree, to resolve issue citations and anchors")
    ap.add_argument("--report", default="", help="where to write the UTF-8 report (default: stdout only)")
    args = ap.parse_args(argv)

    docs = args.docs_dir
    if not os.path.isdir(docs):
        sys.stderr.write("cannot run: --docs-dir %s is not a directory\n" % docs)
        return 2

    f = Findings()
    config_path = os.path.join(docs, "PROJECT_CONFIG.md")
    if os.path.isfile(config_path):
        check_config(f, docs, args.plugin_dir, config_path)
    else:
        f.add("HIGH", "missing-config", "PROJECT_CONFIG.md",
              "not found in the docs directory; every stage reads it")

    check_placeholders_in_instance(f, docs)
    check_dangling_doc_refs(f, docs, [args.source_dir, os.path.dirname(os.path.abspath(docs))])
    check_layout(f, docs)

    issues_path = os.path.join(docs, "Known_Issues.md")
    if os.path.isfile(issues_path):
        check_issues(f, docs, issues_path, args.source_dir or None)
    else:
        f.add("MEDIUM", "missing-issue-log", "Known_Issues.md", "cross-screen issue log is absent")

    registry_path = os.path.join(docs, "Screens_Registry.md")
    if os.path.isfile(registry_path):
        check_registry(f, docs, registry_path)
    else:
        f.add("HIGH", "missing-registry", "Screens_Registry.md",
              "the single source of truth for screen identity is absent")

    lines = ["# validate-docs report", "", "docs-dir: %s" % docs, ""]
    if not len(f):
        lines.append("No findings.")
    else:
        counts: dict[str, int] = {}
        for sev, kind, where, detail in f.sorted_rows():
            counts[sev] = counts.get(sev, 0) + 1
        lines.append("| Severity | Kind | Where | Detail |")
        lines.append("|---|---|---|---|")
        for sev, kind, where, detail in f.sorted_rows():
            lines.append("| %s | %s | %s | %s |" % (sev, kind, where, detail.replace("|", "\\|")))
        lines.append("")
        lines.append("Totals: " + ", ".join("%s %d" % (s, counts[s]) for s in ("HIGH", "MEDIUM", "LOW") if s in counts))

    report = "\n".join(lines) + "\n"
    if args.report:
        io.open(args.report, "w", encoding="utf-8", newline="\n").write(report)

    # ASCII-only console summary: a cp932 console must not turn a pass into a crash
    counts = {}
    for sev, _, _, _ in f.rows:
        counts[sev] = counts.get(sev, 0) + 1
    if not len(f):
        sys.stdout.write("validate-docs: clean (0 findings)\n")
    else:
        sys.stdout.write("validate-docs: %d findings (%s)\n" % (
            len(f), ", ".join("%s=%d" % (s, counts[s]) for s in ("HIGH", "MEDIUM", "LOW") if s in counts)))
        for sev, kind, where, _ in f.sorted_rows()[:40]:
            sys.stdout.write("  %-6s %-24s %s\n" % (sev, kind, where))
        if len(f) > 40:
            sys.stdout.write("  ... %d more; see the report file\n" % (len(f) - 40))
    if args.report:
        sys.stdout.write("report: %s\n" % args.report)
    return 1 if len(f) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
