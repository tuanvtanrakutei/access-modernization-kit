#!/usr/bin/env python3
"""Bump the kit version across every manifest and doc in one command.

Usage:
    py -3.11 scripts/bump_version.py <new_version>
    py -3.11 scripts/bump_version.py <new_version> --check

The canonical version lives in the manifests below. The README no longer
hardcodes a version, so it does not need updating on release.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Files that carry the semantic version, with the exact surrounding text so
# replacement never touches an unrelated field (e.g. "contract_version").
JSON_MANIFESTS = [
    "plugins/ak/specifications/package.json",
    "plugins/ak/.codex-plugin/plugin.json",
    "plugins/ak/.claude-plugin/plugin.json",
    ".claude-plugin/marketplace.json",  # two occurrences: metadata + plugin
]
DOCS = [
    "docs/first-access-mdb-investigation.md",  # "version X.Y.Z or later"
]

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
CURRENT_VERSION = re.compile(r'"version"\s*:\s*"([^"]+)"')


def read_current_version() -> str:
    text = (REPO_ROOT / "plugins/ak/specifications/package.json").read_text(
        encoding="utf-8"
    )
    match = CURRENT_VERSION.search(text)
    if not match:
        raise SystemExit("ERROR: could not find current version in package.json")
    return match.group(1)


def replace_in_file(rel_path: str, old: str, new: str, *, dry_run: bool) -> int:
    path = REPO_ROOT / rel_path
    text = path.read_text(encoding="utf-8")
    if rel_path.endswith(".json"):
        needle, repl = f'"version": "{old}"', f'"version": "{new}"'
    else:
        needle, repl = f"version {old}", f"version {new}"
    count = text.count(needle)
    if count and not dry_run:
        path.write_text(text.replace(needle, repl), encoding="utf-8")
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Bump the kit version everywhere.")
    parser.add_argument("new_version", help="Target version, e.g. 2.3.1")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Report what would change without writing.",
    )
    args = parser.parse_args()

    new = args.new_version.lstrip("v")
    if not SEMVER.match(new):
        raise SystemExit(f"ERROR: '{args.new_version}' is not X.Y.Z semver")

    old = read_current_version()
    if old == new:
        print(f"Already at {new}; nothing to do.")
        return 0

    print(f"Bumping {old} -> {new}{' (check only)' if args.check else ''}\n")
    total = 0
    missing: list[str] = []
    for rel_path in JSON_MANIFESTS + DOCS:
        hits = replace_in_file(rel_path, old, new, dry_run=args.check)
        total += hits
        status = f"{hits} occurrence(s)" if hits else "NOT FOUND"
        print(f"  {rel_path}: {status}")
        if not hits:
            missing.append(rel_path)

    if missing:
        print(
            f"\nWARNING: no '{old}' found in: {', '.join(missing)}. "
            "Check these files manually."
        )

    print(f"\nTotal replacements: {total}")
    if not args.check:
        print(
            "\nNext:\n"
            f"  git commit -am 'release {new}'\n"
            f"  git tag v{new} && git push && git push --tags\n"
            "  Then create a GitHub Release for the tag so the README badge updates.\n"
            "  Note: the 'V2.x' heading in skills/investigate/SKILL.md is brand text; "
            "update it by hand only on a major/minor change."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
