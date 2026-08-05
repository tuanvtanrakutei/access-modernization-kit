#!/usr/bin/env python3
"""PostToolUse sensor: warn when an edit lands somewhere it probably should not.

This is a sensor. It emits a message and returns no permission decision, never
edits, never formats, never creates a file. Machine detects, human decides.

Two checks, both chosen because the corresponding mistake actually happened here:

  parent-owned file   Screens_Registry.md and Known_Issues.md are written by the
                      run parent only. A group agent editing either corrupts it
                      quietly - a row that loses a column still renders as a
                      table, which is how a malformed row survived for weeks.

  over-long line      The project declares a maximum line length. Catching it at
                      edit time costs nothing; catching it at a lint gate later
                      means a second pass over work already believed finished.

Deliberately NOT done here:

  Running the project lint command. LINT_CMD is a whole-project script that
  usually cannot take a single file, so firing it on every edit would be slow
  enough that people disable the hook - and a disabled gate is worse than none.
  Lint stays a stage closing gate.

  Anything with --fix. A formatter run over a whole change list once reformatted
  seven files belonging to other people's work in progress, and it reached a
  shared branch. A hook doing that on every save would be the same damage on a
  loop.

Always exits 0. A sensor must not block a turn, and it must not turn its own
failure into the user's problem: any unexpected condition exits quietly.
"""

from __future__ import annotations

import io
import json
import os
import sys

PARENT_OWNED = ("Screens_Registry.md", "Known_Issues.md")
SOURCE_SUFFIXES = (".py", ".ts", ".tsx", ".js", ".jsx")
CONFIG_NAME = "PROJECT_CONFIG.md"


def hook_input() -> dict:
    try:
        raw = sys.stdin.read()
    except Exception:
        return {}
    if not raw.strip():
        return {}
    try:
        data = json.loads(raw)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def edited_path(data: dict) -> str:
    """Find the edited file path without assuming one exact payload shape.

    The event schema is not something this script should depend on, so it looks
    in the plausible places and gives up silently rather than guessing wrong.
    """
    for container in (data, data.get("tool_input"), data.get("toolInput"), data.get("input")):
        if isinstance(container, dict):
            for key in ("file_path", "filePath", "path", "notebook_path"):
                value = container.get(key)
                if isinstance(value, str) and value.strip():
                    return value
    return ""


def find_config(start: str) -> str:
    here = os.path.abspath(start)
    for _ in range(5):
        direct = os.path.join(here, CONFIG_NAME)
        if os.path.isfile(direct):
            return direct
        try:
            for name in os.listdir(here):
                nested = os.path.join(here, name, CONFIG_NAME)
                if os.path.isfile(nested):
                    return nested
        except OSError:
            pass
        parent = os.path.dirname(here)
        if parent == here:
            break
        here = parent
    return ""


def max_line_length(config_path: str) -> int:
    if not config_path:
        return 0
    try:
        text = io.open(config_path, encoding="utf-8", errors="replace").read()
    except OSError:
        return 0
    import re

    m = re.search(r"^\|\s*`MAX_LINE_LENGTH`\s*\|\s*`?(\d+)`?", text, re.M)
    return int(m.group(1)) if m else 0


def main() -> int:
    data = hook_input()
    path = edited_path(data)
    if not path:
        return 0

    notes: list[str] = []
    base = os.path.basename(path)

    if base in PARENT_OWNED:
        notes.append(
            "%s is written by the run parent only. If you are running as a screen group "
            "agent, return the intended row in your handoff instead of editing this file - "
            "concurrent edits corrupt it quietly, and a row that loses a column still "
            "renders as a table." % base
        )

    if path.endswith(SOURCE_SUFFIXES) and os.path.isfile(path):
        limit = max_line_length(find_config(os.path.dirname(os.path.abspath(path))))
        if limit:
            try:
                lines = io.open(path, encoding="utf-8", errors="replace").read().split("\n")
            except OSError:
                lines = []
            long_lines = [i for i, line in enumerate(lines, 1) if len(line) > limit]
            if long_lines:
                shown = ", ".join(str(n) for n in long_lines[:8])
                more = "" if len(long_lines) <= 8 else " (+%d more)" % (len(long_lines) - 8)
                notes.append(
                    "%s has %d line(s) over the declared %d-character limit: %s%s. Fix them "
                    "now rather than at the stage gate."
                    % (base, len(long_lines), limit, shown, more)
                )

    if notes:
        sys.stdout.write("scope sensor:\n" + "\n".join("  - " + n for n in notes) + "\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # A sensor that crashes must not become the user's problem.
        sys.exit(0)
