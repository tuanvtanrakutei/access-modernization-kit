#!/usr/bin/env python3
"""Normalize compile_commands.json as read-only context without executing commands."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
from pathlib import Path


SECRET_RE = re.compile(r"(?i)(password|passwd|pwd|token|secret|api[_-]?key|access[_-]?key)")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def redact(arguments: list[str]) -> list[str]:
    result: list[str] = []
    hide_next = False
    for value in arguments:
        if hide_next:
            result.append("<REDACTED>")
            hide_next = False
            continue
        if SECRET_RE.search(value):
            if "=" in value:
                result.append(value.split("=", 1)[0] + "=<REDACTED>")
            else:
                result.append(value)
                hide_next = True
        else:
            result.append(value)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="compile_commands.json")
    parser.add_argument("--output", required=True, help="Normalized JSON output")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source = Path(args.input).expanduser().resolve()
    if not source.is_file():
        raise SystemExit(f"Compilation database not found: {source}")
    raw = json.loads(source.read_text(encoding="utf-8-sig"))
    if not isinstance(raw, list):
        raise SystemExit("compile_commands.json must contain a JSON array")
    entries: list[dict] = []
    warnings: list[str] = []
    for index, item in enumerate(raw):
        if not isinstance(item, dict) or not isinstance(item.get("directory"), str) or not isinstance(item.get("file"), str):
            warnings.append(f"entry[{index}] skipped: directory and file strings are required")
            continue
        command_present = isinstance(item.get("command"), str)
        if isinstance(item.get("arguments"), list) and all(isinstance(value, str) for value in item["arguments"]):
            arguments = list(item["arguments"])
        elif command_present:
            try:
                arguments = shlex.split(item["command"], posix=False)
            except ValueError:
                arguments = ["<UNPARSEABLE_COMMAND>"]
                warnings.append(f"entry[{index}] command could not be tokenized")
        else:
            warnings.append(f"entry[{index}] skipped: arguments or command is required")
            continue
        normalized = {
            "directory": item["directory"],
            "file": item["file"],
            "arguments": redact(arguments),
            "command_present": command_present,
        }
        if isinstance(item.get("output"), str):
            normalized["output"] = item["output"]
        entries.append(normalized)
    report = {
        "schema_version": "2.1",
        "source_path": str(source),
        "source_sha256": sha256(source),
        "execution_policy": "NEVER_EXECUTE",
        "entries": entries,
        "warnings": warnings,
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.dry_run:
        print(rendered, end="")
        return 0
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Normalized {len(entries)} entries to {output}; no commands were executed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
