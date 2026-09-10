#!/usr/bin/env python3
"""Compare each supplied sample with the import specification its link names.

The gap this closes is A23. A17 put the two tables that declare a text link's columns
into the bundle and predicted the useful check without building it; A21 proved the
second acquisition route reads them too. Both halves then existed for the first time -
the specifications, and real files an operator placed on the share - and nothing put
them side by side. `input/samples/` was inventoried and hashed; no reader opened a
sample's bytes.

    $ak samples --app-root <PATH>

The reasoning for what is compared, and for what a comparison like this must not
claim, lives in `contracts/feed_samples.py`. Nothing is recorded: unlike
`$ak completeness`, both halves of this comparison are present at read time, so a
previous run's record would add nothing.

Exit codes: 0 when nothing is reported, 1 when something is, 2 when there is no bundle
to read. It is a report, not a gate - a sender that added a column is a question for
the operations team, not a verdict this can reach on its own.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

PACKAGE = Path(__file__).resolve().parents[1]
for _path in (PACKAGE / "contracts", PACKAGE / "scripts"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

import feed_samples as feeds_contract  # noqa: E402
import link_targets  # noqa: E402
import workspace as workspace_contract  # noqa: E402


def read_json(path: Path) -> Any:
    """A bundle file, or None. `utf-8-sig` because the VBA exporter writes a BOM."""
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows_of(data: Any) -> list[dict]:
    """The list inside a bundle file, whatever the file calls it."""
    if data is None:
        return []
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for value in data.values():
            if isinstance(value, list) and value and isinstance(value[0], dict):
                return value
    return []


def supplied_samples(root: Path) -> dict[str, list[Path]]:
    """Every file under `input/samples/`, by lowercased name.

    Walked rather than listed, because an operator collecting files from several
    senders puts them in a folder each, and the link names only the file. Every match
    is kept: two senders both supplying `order.txt` is exactly the case where picking
    one would compare the declaration against the wrong file and say it agreed.
    """
    found: dict[str, list[Path]] = {}
    if not root.is_dir():
        return found
    for path in sorted(root.rglob("*")):
        if path.is_file():
            found.setdefault(path.name.lower(), []).append(path)
    return found


def describe(feed: feeds_contract.Feed, spec: feeds_contract.Specification,
             sample: feeds_contract.Sample) -> str:
    """One line of what was read, before anything is called a disagreement."""
    parts = [feed.table, feed.file_name]
    if sample.problem:
        parts.append(sample.problem)
        return " | ".join(part for part in parts if part)
    parts += [
        f"{sample.codec}{' with a BOM' if sample.bom else ''}",
        f"{sample.records:,} record(s)",
        f"spec {len(spec.columns)}",
        f"file {sample.fields}",
        sample.header.detail,
        f"StartRow={spec.start_row}",
    ]
    return " | ".join(part for part in parts if part)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--app-root", required=True, type=Path)
    args = parser.parse_args()

    space = workspace_contract.Workspace(args.app_root)
    bundles = workspace_contract.find_bundle_dirs(space)
    if not bundles:
        print(f"no acquisition bundle under {space.root}; run `$ak acquire` first")
        return 2
    bundle = max(bundles, key=lambda path: (path / "bundle.json").stat().st_mtime)

    interfaces = bundle / "interfaces"
    declared = feeds_contract.feeds(
        link_targets.collapse(rows_of(read_json(interfaces / "linked-tables.json")))
        + rows_of(read_json(interfaces / "file-interfaces.json")))
    specs = feeds_contract.specifications(
        rows_of(read_json(interfaces / "imex-specs.json")))
    samples_root = space.input_dir("samples")
    on_disk = supplied_samples(samples_root)

    print(f"bundle {bundle.name}")
    if not declared:
        print("no link in this bundle names an import specification; nothing to compare")
        return 0

    print(f"{len(declared)} link(s) name an import specification, "
          f"{len(specs)} specification(s) in the bundle, "
          f"{sum(len(paths) for paths in on_disk.values())} file(s) under "
          f"{samples_root}")

    lines: list[str] = []
    findings: list[tuple[str, str, str]] = []
    read: list[tuple[feeds_contract.Specification, feeds_contract.Sample]] = []
    claimed: set[str] = set()

    for feed in sorted(declared, key=lambda item: (item.database_id, item.table)):
        where = f"{feed.table} ({feed.file_name or 'no file named'})"
        spec = specs.get(feed.spec_name)
        matches = on_disk.get(feed.file_name.lower(), []) if feed.file_name else []
        if matches:
            claimed.add(feed.file_name.lower())
        if len(matches) > 1:
            findings.append(("AMBIGUOUS", where, "more than one file under "
                             "input/samples carries this name, and the link says "
                             "nothing about which: " + ", ".join(
                                 path.relative_to(samples_root).as_posix()
                                 for path in matches)))
            continue
        path = matches[0] if matches else None
        if spec is None:
            findings.append(("NO SPEC", where, f"the link names `{feed.spec_name}`, "
                             "which this bundle does not carry - the layout of a "
                             "headerless file is then declared nowhere"))
            continue
        if path is None:
            findings.append(("NO SAMPLE", where, f"`{feed.spec_name}` declares "
                             f"{len(spec.columns)} column(s) and no file of this name "
                             "is under input/samples, so nothing checks the "
                             "declaration (EC-02)"))
            continue
        unreadable = feeds_contract.format_problem(feed)
        if unreadable is not None:
            findings.append((unreadable.tag, where, unreadable.says))
            continue
        sample = feeds_contract.sample_of(path.read_bytes(), spec)
        read.append((spec, sample))
        lines.append(f"  {describe(feed, spec, sample)}")
        for finding in feeds_contract.disagreements(spec, sample, feed):
            findings.append((finding.tag, where, finding.says))

    for name in sorted(set(on_disk) - claimed):
        for path in on_disk[name]:
            # Relative to the samples root, because the walk goes into subfolders an
            # operator collecting from several senders makes, and a bare file name
            # would not tell them which one to look in.
            findings.append(("UNCLAIMED", path.relative_to(samples_root).as_posix(),
                             "no link in this bundle names this file"))

    spread = feeds_contract.encoding_spread(read)
    if spread:
        findings.append(("ENCODING", "the application's inbound feeds", spread))

    if lines:
        print()
        print("\n".join(lines))
    print()
    if not findings:
        print("every declared layout agrees with the file it describes")
        return 0
    for tag, where, says in findings:
        print(f"{tag:<10}  {where}: {says}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
