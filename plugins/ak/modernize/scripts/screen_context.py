#!/usr/bin/env python3
"""Say what a Docker build would send, and refuse a build context that holds what an image must not.

    python3 screen_context.py --context <folder> [--dockerfile <path>] [--forbid PATTERN ...] [--json]

`.gitignore` does not apply to Docker. A folder git ignores (the project's documentation with the
customer's data, local `.env` files, agent folders, `.git` itself) is still sent to the build and,
with a `COPY . .`, ends up in the image. Reading `.dockerignore` and guessing what it leaves out
repeats Docker's rules, and a mistake there reads as a pass. This script asks Docker instead: it
builds a throwaway stage from `scratch` that copies the context and exports it to a temporary
folder (no base image, nothing pulled, no image or layer kept), then lists that folder.

The ignore file Docker would use is the one it uses for the real build: `<dockerfile>.dockerignore`
beside the Dockerfile when that exists, else the context's `.dockerignore`.

A pattern is matched against every path in the context, relative and with `/`, and against every
folder above it: `docs` refuses the folder and all under it, `**/.env` a `.env` at any depth,
`*.mdb` any such file. `.git` and `**/.env` are always refused; `--forbid` adds the project's own
(its documentation folder, data exports).

Exit status: 0 the context holds nothing refused; 1 it does (each refused path is listed, up to 50);
2 Docker or the input cannot be used (Docker not running, no BuildKit, the folder missing). Writes
only a temporary folder, removed before it exits. Stdlib only.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ALWAYS = (".git", "**/.env")
SHOWN = 50


class Problem(Exception):
    """Docker or the input cannot be used."""


def refused_by(path: str, patterns: list[str]) -> str | None:
    """The first pattern that refuses `path` (posix, relative) or a folder above it, or None."""
    parts = path.split("/")
    prefixes = ["/".join(parts[: n + 1]) for n in range(len(parts))]
    for pattern in patterns:
        bare = pattern.rstrip("/")
        tail = bare[3:] if bare.startswith("**/") else None
        for prefix in prefixes:
            if fnmatch.fnmatchcase(prefix, bare):
                return pattern
            if tail is not None and fnmatch.fnmatchcase(prefix.rsplit("/", 1)[-1], tail):
                return pattern
    return None


def inspect(exported: Path, patterns: list[str]) -> dict[str, Any]:
    """List an exported context and say what in it is refused."""
    files: list[tuple[str, int]] = []
    for item in sorted(exported.rglob("*")):
        if item.is_file() or item.is_symlink():
            rel = item.relative_to(exported).as_posix()
            files.append((rel, item.lstat().st_size))
    top: dict[str, int] = {}
    for rel, size in files:
        head = rel.split("/", 1)[0]
        top[head] = top.get(head, 0) + size
    refused = [{"path": rel, "pattern": p} for rel, _ in files if (p := refused_by(rel, patterns))]
    return {"files": len(files), "bytes": sum(size for _, size in files),
            "top": [{"entry": k, "bytes": v} for k, v in sorted(top.items())],
            "refused": refused, "patterns": patterns}


def export(context: Path, dockerfile: Path | None, out: Path, work: Path) -> None:
    """Have Docker send `context` through its own ignore rules and write what arrives into `out`."""
    probe = work / "context.Dockerfile"
    probe.write_text("FROM scratch\nCOPY . /\n", encoding="utf-8")
    beside = Path(f"{dockerfile}.dockerignore") if dockerfile is not None else None
    if beside is not None and beside.is_file():
        shutil.copyfile(beside, work / "context.Dockerfile.dockerignore")
    elif (context / ".dockerignore").is_file():
        shutil.copyfile(context / ".dockerignore", work / "context.Dockerfile.dockerignore")
    cmd = ["docker", "build", "-q", "-f", str(probe), "--output", f"type=local,dest={out}", str(context)]
    try:
        done = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                              env=None, timeout=1800)
    except FileNotFoundError:
        raise Problem("docker is not on PATH")
    except subprocess.TimeoutExpired:
        raise Problem("docker build did not finish in 30 minutes")
    if done.returncode:
        detail = "\n".join((done.stdout + done.stderr).strip().splitlines()[-8:])
        raise Problem(f"docker could not export the context (is Docker running, with BuildKit?):\n{detail}")


def render(report: dict[str, Any]) -> str:
    mb = lambda n: f"{n / 1_048_576:.1f} MB"
    out = [f"Build context of {report['context']}: {report['files']} files, {mb(report['bytes'])}"]
    out += [f"  {t['entry']:<32}{mb(t['bytes']):>10}" for t in report["top"]]
    if report["refused"]:
        out.append(f"REFUSED: {len(report['refused'])} path(s) the image must not hold:")
        out += [f"  {r['path']}  ({r['pattern']})" for r in report["refused"][:SHOWN]]
        if len(report["refused"]) > SHOWN:
            out.append(f"  ... and {len(report['refused']) - SHOWN} more")
        out.append("Leave them out in .dockerignore (an allow-list of what the image needs is the safest form).")
    else:
        out.append(f"Nothing refused (patterns: {', '.join(report['patterns'])}).")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--context", type=Path, required=True, help="the build context folder")
    ap.add_argument("--dockerfile", type=Path, help="the real Dockerfile, so its own <name>.dockerignore is used if it has one")
    ap.add_argument("--forbid", action="append", default=[], metavar="PATTERN", help="a path the image must not hold")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    patterns = list(ALWAYS) + [p for p in args.forbid if p.strip()]
    work = Path(tempfile.mkdtemp(prefix="screen-context-"))
    try:
        context = args.context.resolve()
        if not context.is_dir():
            raise Problem(f"--context {args.context} is not a folder")
        if args.dockerfile is not None and not args.dockerfile.is_file():
            raise Problem(f"--dockerfile {args.dockerfile} is not a file")
        out = work / "out"
        export(context, args.dockerfile.resolve() if args.dockerfile else None, out, work)
        report = {"context": str(context), **inspect(out, patterns)}
    except Problem as err:
        print(f"screen_context: {err}", file=sys.stderr)
        return 2
    finally:
        shutil.rmtree(work, ignore_errors=True)
    sys.stdout.write(json.dumps(report, ensure_ascii=False, indent=1) + "\n" if args.json else render(report))
    return 1 if report["refused"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
