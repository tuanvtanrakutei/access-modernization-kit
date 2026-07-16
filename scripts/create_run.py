#!/usr/bin/env python3
"""Create an isolated, resumable multi-agent run without dispatching agents."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path


RUN_DIRS = (
    "tasks",
    "work",
    "evidence/fragments",
    "conflicts",
    "handoffs",
    "qa",
    "outputs",
    "derived/e2e",
    "derived/boundary",
    "derived/presentation",
    "graphify-out",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--app-root", required=True)
    parser.add_argument("--runtime", choices=("codex", "claude", "generic"), default="generic")
    parser.add_argument("--max-parallel", type=int, default=4)
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_category(relative: Path) -> str:
    suffix = relative.suffix.lower()
    if "build-context" in relative.parts:
        return "BUILD_CONTEXT"
    if "reports" in relative.parts:
        return "REPORT"
    if suffix in {".mdb", ".accdb", ".adp"}:
        return "ACCESS_DATABASE"
    if relative.name.lower() in {"compile_commands.json", "compile_flags.txt"}:
        return "BUILD_CONTEXT"
    if suffix in {".sln", ".vcxproj", ".csproj", ".vbproj", ".dsp", ".dsw"}:
        return "PROJECT"
    if "vba" in relative.parts or suffix in {".bas", ".cls", ".frm", ".vb"}:
        return "VBA"
    if "sql" in relative.parts or suffix == ".sql":
        return "SQL"
    return {".png": "SCREENSHOT", ".jpg": "SCREENSHOT", ".jpeg": "SCREENSHOT", ".xlsx": "XLSX", ".xls": "XLSX", ".pdf": "PDF", ".csv": "CSV", ".txt": "TXT"}.get(suffix, "OTHER")


def manifest_source_policy(path: Path) -> tuple[str, list[str], list[str]]:
    try:
        import yaml  # type: ignore[import-not-found]
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        policy = data.get("analysis", {}).get("source_policy", {})
        return str(policy.get("ignore_file", ".investigationignore")), list(policy.get("include_patterns", [])), list(policy.get("ignore_patterns", []))
    except (ImportError, AttributeError, TypeError, ValueError):
        text = path.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"(?m)^\s*ignore_file:\s*[\"']?([^\"'\r\n#]+)", text)
        return (match.group(1).strip() if match else ".investigationignore"), [], []


def read_ignore_patterns(path: Path) -> list[str]:
    if not path.is_file():
        return []
    return [line.strip().replace("\\", "/") for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip() and not line.lstrip().startswith("#")]


def ignored_by(relative: Path, patterns: list[str]) -> str | None:
    value = relative.as_posix()
    decision: str | None = None
    for raw in patterns:
        negate = raw.startswith("!")
        pattern = raw[1:] if negate else raw
        pattern = pattern.lstrip("/")
        candidates = (value, value + "/")
        matched = any(fnmatch.fnmatch(candidate, pattern) for candidate in candidates)
        if pattern.endswith("/") and (value == pattern[:-1] or value.startswith(pattern)):
            matched = True
        if matched:
            decision = None if negate else raw
    return decision


def detect_encoding(path: Path, category: str) -> str:
    if category == "ACCESS_DATABASE" or path.suffix.lower() in {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".xlsx", ".xls", ".pdf", ".doc", ".docx", ".ppt", ".pptx"}:
        return "BINARY"
    head = path.read_bytes()[:65536]
    if head.startswith(b"\xef\xbb\xbf"):
        return "UTF-8-BOM"
    if head.startswith(b"\xff\xfe"):
        return "UTF-16LE"
    if head.startswith(b"\xfe\xff"):
        return "UTF-16BE"
    try:
        head.decode("utf-8")
        return "UTF-8"
    except UnicodeDecodeError:
        try:
            head.decode("cp932")
            return "CP932"
        except UnicodeDecodeError:
            return "UNKNOWN"


def language_metadata(relative: Path, category: str) -> tuple[str, str, str]:
    suffix = relative.suffix.lower()
    if category == "ACCESS_DATABASE":
        return "ACCESS_BINARY", relative.suffix[1:].upper(), "EXTRACT_FIRST"
    if category == "VBA":
        return "ACCESS_VBA", "ACCESS_VBA", "NOT_ATTEMPTED"
    if category == "SQL":
        dialect = "ACCESS_SQL" if "access" in relative.as_posix().lower() else "TSQL"
        return "SQL", dialect, "NOT_ATTEMPTED"
    mapping = {".ps1": "POWERSHELL", ".bat": "BATCH", ".cmd": "BATCH", ".vbs": "VBSCRIPT", ".py": "PYTHON", ".js": "JAVASCRIPT", ".ts": "TYPESCRIPT", ".c": "C", ".cpp": "CPP", ".cs": "CSHARP", ".java": "JAVA"}
    return mapping.get(suffix, "NONE"), "UNKNOWN", "NOT_ATTEMPTED"


def main() -> int:
    args = parse_args()
    if args.max_parallel < 1:
        raise SystemExit("--max-parallel must be at least 1")
    app_root = Path(args.app_root).expanduser().resolve()
    manifest = app_root / "manifest.yaml"
    if not manifest.is_file():
        raise SystemExit(f"Manifest not found: {manifest}")
    text = manifest.read_text(encoding="utf-8")
    match = re.search(r"(?m)^\s*id:\s*[\"']?([A-Z][A-Z0-9_-]{1,15})", text)
    if not match:
        raise SystemExit("Cannot read app.id from manifest.yaml")
    app_id = match.group(1)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    run_id = args.run_id or f"{app_id}-{stamp}"
    run_root = app_root / "runs" / run_id
    package_root = Path(__file__).resolve().parent.parent
    package_version = json.loads((package_root / "specifications/package.json").read_text(encoding="utf-8"))["version"]
    waves = json.loads((package_root / "orchestration/waves.json").read_text(encoding="utf-8"))["waves"]

    source_roots = [app_root / "sources", app_root / "shared-docs", app_root / "extracted"]
    ignore_file, include_patterns, inline_ignore_patterns = manifest_source_policy(manifest)
    ignore_path = app_root / ignore_file
    patterns = read_ignore_patterns(ignore_path) + [value.replace("\\", "/") for value in inline_ignore_patterns]
    candidates = sorted({path for root in source_roots if root.exists() for path in root.rglob("*") if path.is_file()})
    source_files: list[Path] = []
    ignored: list[dict[str, str]] = []
    for path in candidates:
        relative = path.relative_to(app_root)
        included = not include_patterns or any(fnmatch.fnmatch(relative.as_posix(), pattern.replace("\\", "/")) for pattern in include_patterns)
        reason = None if included else "not_in_include_patterns"
        reason = reason or ignored_by(relative, patterns)
        if reason:
            ignored.append({"relative_path": relative.as_posix(), "reason": reason if reason == "not_in_include_patterns" else f"matched:{reason}"})
        else:
            source_files.append(path)
    if args.dry_run:
        print(json.dumps({"run_id": run_id, "run_root": str(run_root), "source_file_count": len(source_files), "runtime": args.runtime, "max_parallel": args.max_parallel}, indent=2))
        return 0
    if run_root.exists():
        raise SystemExit(f"Run already exists: {run_root}")

    for relative in RUN_DIRS:
        (run_root / relative).mkdir(parents=True, exist_ok=True)
    shutil.copy2(manifest, run_root / "manifest.lock.yaml")

    now = datetime.now(timezone.utc).isoformat()
    inventory = {
        "app_id": app_id,
        "generated_at": now,
        "policy": {"ignore_file": ignore_file, "source_roots": [root.relative_to(app_root).as_posix() for root in source_roots], "include_patterns": include_patterns, "ignore_patterns": inline_ignore_patterns},
        "files": [
            {
                "relative_path": (relative := path.relative_to(app_root)).as_posix(),
                "size": path.stat().st_size,
                "sha256": sha256(path),
                "source_category": (category := source_category(relative)),
                "human_language": "UNKNOWN",
                "programming_language": (metadata := language_metadata(relative, category))[0],
                "dialect": metadata[1],
                "encoding": detect_encoding(path, category),
                "parser": "",
                "parser_version": "",
                "parse_status": metadata[2],
                "sensitive": any(token in path.name.lower() for token in ("password", "secret", "credential", ".env")),
            }
            for path in source_files
        ],
        "ignored": ignored,
    }
    (run_root / "source-inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    state = {
        "run_id": run_id,
        "package_version": package_version,
        "app_id": app_id,
        "manifest_path": "manifest.lock.yaml",
        "manifest_sha256": sha256(run_root / "manifest.lock.yaml"),
        "runtime": args.runtime,
        "max_parallel": args.max_parallel,
        "status": "CREATED",
        "current_wave": waves[0]["id"],
        "wave_status": {
            wave["id"]: ("RUNNING" if index == 0 else "PENDING")
            for index, wave in enumerate(waves)
        },
        "phase_gates": {f"phase{i}": "PENDING" for i in range(1, 7)},
        "created_at": now,
        "updated_at": now,
    }
    (run_root / "run-state.json").write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    print(f"Created run {run_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
