#!/usr/bin/env python3
"""Render the errata register as the page a person reads first (A77).

    $ak errata --app-root P             write {APP}_Errata.md beside the phase documents
    $ak errata --app-root P --dry-run   say what it would hold, write nothing

Reads `{APP}_Errata.json` and writes nothing else. The page carries no date, so the same
register gives the same bytes; the phase gate compares the two and fails a page that has
fallen behind its register. It will not overwrite an `_Errata.md` it did not write.

A project with no errata register gets no page: an absent register and an empty one read
differently, and only the empty one says that nothing was corrected.

Exit 0 when every entry can be audited, 1 when one cannot (ER-03: no affected section, no
source, an unknown cause), 2 when the command cannot run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import decision_register as dr  # noqa: E402
import errata_render as er  # noqa: E402
import workspace as workspace_contract  # noqa: E402

CONTRACT = PACKAGE / "specifications" / "errata-contract.yaml"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--replace-handwritten", action="store_true",
                        help="Overwrite an _Errata.md this command did not write.")
    args = parser.parse_args()

    space = workspace_contract.Workspace(args.app_root)
    try:
        output = space.output_dir()
        found = dr._find(output, "*_Errata.json")
        if not found:
            print(f"no *_Errata.json under {output}: nothing has been corrected on record, "
                  "and no page is written")
            return 0
        if len(found) > 1:
            raise dr.RegisterProblem(f"expected one *_Errata.json under {output}, found {len(found)}")
        register = dr.read_register(found[0])
        entries = [e for e in register.get("entries") or [] if isinstance(e, dict)]
        app = str(register.get("app_id") or found[0].name.split("_Errata")[0])
        causes = er.load_causes(CONTRACT)
        text = er.render(entries, app, causes, source=found[0].name)
        problems = er.problems(entries, causes)
        path = er.output_path(output, app)

        if (path.exists() and not dr.read_text(path).startswith(er.GENERATED)
                and not args.replace_handwritten):
            raise dr.RegisterProblem(f"{path.name} exists and this command did not write it; "
                                     "move it aside, or pass --replace-handwritten")

        print(f"{len(entries)} errata entr{'y' if len(entries) == 1 else 'ies'} in {found[0].name}")
        for problem in problems:
            print(f"  PROBLEM {problem}")
        if args.dry_run:
            print(f"dry run: would write {path}")
        else:
            same = path.is_file() and dr.read_text(path) == text
            if not same:
                dr.atomic_write(path, text)
            print(f"{'unchanged' if same else 'wrote'} {path}")
        return 1 if problems else 0
    except (dr.RegisterProblem, OSError, ValueError) as problem:
        print(f"error: {problem}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
