#!/usr/bin/env python3
"""Prepare, validate, and query the Graphify context required by one phase."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from graphify_runtime import ensure_runtime, load_spec, runtime_report


PHASE_QUERIES = {
    1: "Identify the application data entities, tables, columns, keys, indexes, relationships, queries, and data ownership boundaries relevant to Phase 1.",
    2: "Identify forms, reports, controls, user actions, events, validations, navigation, and triggered logic relevant to Phase 2.",
    3: "Trace VBA, QueryDefs, SQL, calculations, filters, updates, file operations, transactions, and error handling relevant to Phase 3.",
    4: "Trace end-to-end paths from user action through screen, processing, database or file effects, and outputs relevant to Phase 4.",
    5: "Locate business-document rules and their links or mismatches with code, data, screens, reports, and workflows relevant to Phase 5.",
    6: "Summarize the system structure, major workflows, cross-module dependencies, legacy risks, evidence gaps, and unresolved boundaries relevant to Phase 6.",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(path: Path) -> dict:
    try:
        import yaml  # type: ignore[import-not-found]
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        text = path.read_text(encoding="utf-8")
        output = re.search(r"(?m)^\s{2}output_dir:\s*[\"']?([^\"'\r\n#]+)", text)
        enabled = not bool(re.search(r"(?m)^\s{2}enabled:\s*false\s*$", text))
        required = not bool(re.search(r"(?m)^\s{2}required_before_phases:\s*false\s*$", text))
        return {"graphify": {"enabled": enabled, "required_before_phases": required, "output_dir": output.group(1).strip() if output else "graphify-out"}}


def graph_root(app_root: Path, manifest: dict) -> Path:
    result = (app_root / str(manifest.get("graphify", {}).get("output_dir", "graphify-out"))).resolve()
    try:
        result.relative_to(app_root)
    except ValueError as exc:
        raise RuntimeError("graphify.output_dir must remain inside the app workspace") from exc
    return result


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def graph_shape(path: Path) -> tuple[int, int]:
    data = read_json(path)
    nodes = data.get("nodes", [])
    edges = data.get("edges", [])
    node_count = len(nodes) if isinstance(nodes, (list, dict)) else 0
    edge_count = len(edges) if isinstance(edges, (list, dict)) else 0
    if node_count == 0:
        raise RuntimeError("graph.json contains no nodes")
    return node_count, edge_count


def gate_status(app_root: Path, phase: int, runtime: dict[str, object]) -> dict[str, object]:
    manifest = load_manifest(app_root / "manifest.yaml")
    config = manifest.get("graphify", {}) or {}
    if not config.get("enabled", True) or not config.get("required_before_phases", True):
        return {"status": "BLOCKED", "reason": "GRAPHIFY_REQUIRED_BY_KIT", "phase": phase}
    declared_version = config.get("runtime_version")
    if declared_version and declared_version != runtime.get("requested_version"):
        return {
            "status": "BLOCKED", "reason": "GRAPHIFY_VERSION_MISMATCH", "phase": phase,
            "manifest_version": declared_version, "kit_version": runtime.get("requested_version"),
        }
    root = graph_root(app_root, manifest)
    audit_path = root / "CORPUS_AUDIT.json"
    graph_path = root / "graph.json"
    state_path = root / "GRAPH_STATE.json"
    if not audit_path.is_file():
        return {"status": "BLOCKED", "reason": "CORPUS_NOT_PREPARED", "phase": phase, "graph_root": str(root)}
    audit = read_json(audit_path)
    if audit.get("status") == "BLOCKED" or audit.get("binary_files_ingested") != 0:
        return {"status": "BLOCKED", "reason": "CORPUS_VALIDATION_FAILED", "phase": phase, "audit": str(audit_path)}
    if not graph_path.is_file():
        return {
            "status": "BLOCKED", "reason": "GRAPH_BUILD_REQUIRED", "phase": phase,
            "corpus_root": str(app_root / str(audit["corpus_root"])), "graph_root": str(root),
        }
    if any((root / marker).exists() for marker in (".needs_update", "needs_update")):
        return {"status": "BLOCKED", "reason": "GRAPH_SEMANTIC_UPDATE_REQUIRED", "phase": phase, "graph_root": str(root)}
    try:
        nodes, edges = graph_shape(graph_path)
    except (OSError, ValueError, RuntimeError) as exc:
        return {"status": "BLOCKED", "reason": "GRAPH_INVALID", "phase": phase, "detail": str(exc)}
    if not state_path.is_file():
        return {"status": "BLOCKED", "reason": "GRAPH_NOT_ACCEPTED", "phase": phase, "graph": str(graph_path)}
    state = read_json(state_path)
    if state.get("corpus_fingerprint") != audit.get("corpus_fingerprint"):
        return {
            "status": "BLOCKED", "reason": "GRAPH_UPDATE_REQUIRED", "phase": phase,
            "previous_fingerprint": state.get("corpus_fingerprint"), "current_fingerprint": audit.get("corpus_fingerprint"),
        }
    current_graph_hash = sha256(graph_path)
    if state.get("graph_sha256") != current_graph_hash:
        return {"status": "BLOCKED", "reason": "GRAPH_CHANGED_REQUIRES_ACCEPTANCE", "phase": phase}
    receipt = (state.get("phase_queries") or {}).get(str(phase))
    if not isinstance(receipt, dict) or receipt.get("corpus_fingerprint") != audit.get("corpus_fingerprint"):
        return {"status": "BLOCKED", "reason": "PHASE_QUERY_REQUIRED", "phase": phase, "query": PHASE_QUERIES[phase]}
    return {
        "status": "READY", "phase": phase, "graph": str(graph_path), "graph_sha256": current_graph_hash,
        "nodes": nodes, "edges": edges, "corpus_fingerprint": audit.get("corpus_fingerprint"),
        "corpus_status": audit.get("status"), "coverage_gaps": audit.get("gap_count", 0),
        "phase_context": receipt.get("output_path"), "runtime": runtime,
    }


def run_query(app_root: Path, phase: int, executable: Path, root: Path, fingerprint: str) -> dict[str, object]:
    graph = root / "graph.json"
    command = [
        str(executable), "query", PHASE_QUERIES[phase], "--graph", str(graph), "--budget", "4000",
    ]
    result = subprocess.run(command, cwd=app_root, check=False, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Graphify phase query failed: {result.stderr.strip() or result.stdout.strip()}")
    context_dir = root / "phase-context"
    context_dir.mkdir(parents=True, exist_ok=True)
    output = context_dir / f"phase-{phase}.json"
    receipt = {
        "phase": phase,
        "query": PHASE_QUERIES[phase],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_fingerprint": fingerprint,
        "graph_sha256": sha256(graph),
        "result": result.stdout.strip(),
    }
    output.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    receipt["output_path"] = output.relative_to(app_root).as_posix()
    return receipt


def accept_graph(app_root: Path, phase: int, runtime: dict[str, object], executable: Path) -> dict[str, object]:
    manifest = load_manifest(app_root / "manifest.yaml")
    root = graph_root(app_root, manifest)
    audit = read_json(root / "CORPUS_AUDIT.json")
    graph = root / "graph.json"
    if any((root / marker).exists() for marker in (".needs_update", "needs_update")):
        raise RuntimeError("Graphify reports pending semantic extraction; complete the Graphify update before finalizing the phase gate")
    nodes, edges = graph_shape(graph)
    fingerprint = str(audit["corpus_fingerprint"])
    state_path = root / "GRAPH_STATE.json"
    previous = read_json(state_path) if state_path.is_file() else {}
    prior_queries = previous.get("phase_queries", {}) if previous.get("corpus_fingerprint") == fingerprint else {}
    receipt = run_query(app_root, phase, executable, root, fingerprint)
    prior_queries[str(phase)] = receipt
    state = {
        "schema_version": "2.1",
        "status": "READY",
        "accepted_at": datetime.now(timezone.utc).isoformat(),
        "corpus_fingerprint": fingerprint,
        "graph_sha256": sha256(graph),
        "graphify_version": runtime.get("installed_version"),
        "graphify_executable": runtime.get("graphify_executable"),
        "nodes": nodes,
        "edges": edges,
        "corpus_status": audit.get("status"),
        "coverage_gaps": audit.get("gap_count", 0),
        "phase_queries": prior_queries,
    }
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return gate_status(app_root, phase, runtime)


def prepare_corpus(app_root: Path, runtime: dict[str, object], dry_run: bool) -> dict[str, object]:
    python = Path(str(runtime["python_executable"]))
    command = [str(python), str(Path(__file__).with_name("normalize_graphify_corpus.py")), "--app-root", str(app_root)]
    if dry_run:
        command.append("--dry-run")
    result = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8")
    if result.returncode != 0:
        raise RuntimeError(f"Corpus normalization failed: {result.stderr.strip() or result.stdout.strip()}")
    return json.loads(result.stdout)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("prepare", "check", "finalize"))
    parser.add_argument("--app-root", required=True)
    parser.add_argument("--phase", required=True, type=int, choices=range(1, 7))
    parser.add_argument("--runtime", choices=("codex", "claude", "generic"), default="generic")
    parser.add_argument("--install-missing", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--register-skill", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    app_root = Path(args.app_root).expanduser().resolve()
    spec = load_spec()
    try:
        runtime = runtime_report(spec)
        if args.action == "prepare" and (runtime["status"] != "READY" or args.install_missing):
            runtime = ensure_runtime(spec, args.runtime, args.register_skill, args.dry_run)
        if runtime["status"] not in {"READY", "INSTALL_PLANNED"}:
            raise RuntimeError("The kit-managed Graphify runtime is not READY")
        if args.dry_run:
            corpus = prepare_corpus(app_root, runtime, True) if runtime["status"] == "READY" else {"status": "INSTALL_FIRST"}
            report = {"status": "PREFLIGHT_ONLY", "phase": args.phase, "runtime": runtime, "corpus": corpus}
        elif args.action == "prepare":
            corpus = prepare_corpus(app_root, runtime, False)
            report = gate_status(app_root, args.phase, runtime)
            report["corpus"] = {key: corpus.get(key) for key in ("status", "corpus_file_count", "gap_count", "corpus_fingerprint")}
            if report.get("reason") == "PHASE_QUERY_REQUIRED":
                report = accept_graph(app_root, args.phase, runtime, Path(str(runtime["graphify_executable"])))
        elif args.action == "finalize":
            report = accept_graph(app_root, args.phase, runtime, Path(str(runtime["graphify_executable"])))
        else:
            report = gate_status(app_root, args.phase, runtime)
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as exc:
        report = {"status": "BLOCKED", "phase": args.phase, "reason": "GRAPHIFY_GATE_FAILED", "detail": str(exc)}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] in {"READY", "PREFLIGHT_ONLY"} else 4


if __name__ == "__main__":
    raise SystemExit(main())
