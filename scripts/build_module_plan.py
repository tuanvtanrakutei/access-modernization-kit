#!/usr/bin/env python3
"""Build a deterministic hierarchical module tree and leaf-first processing order."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path


def slug(value: str) -> str:
    clean = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return clean or "unclassified"


def signature(component: dict) -> str:
    return hashlib.sha256(json.dumps(component, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()


def auto_tree(app_id: str, components: list[dict]) -> dict:
    groups: dict[str, list[str]] = {}
    names: dict[str, str] = {}
    for component in components:
        label = component.get("module_hint") or component.get("container") or component.get("kind") or "Unclassified"
        group_id = f"module-{slug(str(label))}"
        groups.setdefault(group_id, []).append(component["id"])
        names[group_id] = str(label)
    children = [
        {"id": group_id, "name": names[group_id], "component_ids": sorted(component_ids), "children": []}
        for group_id, component_ids in sorted(groups.items())
    ]
    return {"schema_version": "2.1", "app_id": app_id, "root_modules": [{"id": "module-app", "name": app_id, "component_ids": [], "children": children}]}


def validate_tree(tree: dict, component_ids: set[str]) -> tuple[dict[str, dict], dict[str, str | None], dict[str, int]]:
    modules: dict[str, dict] = {}
    parents: dict[str, str | None] = {}
    depths: dict[str, int] = {}
    assignments: list[str] = []

    def visit(node: dict, parent: str | None, depth: int, ancestry: set[str]) -> None:
        module_id = node.get("id")
        if not isinstance(module_id, str) or not module_id:
            raise ValueError("Every module requires a non-empty id")
        if module_id in ancestry:
            raise ValueError(f"Module cycle detected at {module_id}")
        if module_id in modules:
            raise ValueError(f"Duplicate module id: {module_id}")
        modules[module_id] = node
        parents[module_id] = parent
        depths[module_id] = depth
        own = node.get("component_ids", [])
        if not isinstance(own, list) or not all(isinstance(value, str) for value in own):
            raise ValueError(f"Invalid component_ids for {module_id}")
        assignments.extend(own)
        children = node.get("children", [])
        if not isinstance(children, list):
            raise ValueError(f"Invalid children for {module_id}")
        if children and own:
            raise ValueError(f"Parent module {module_id} may not own components directly; assign them to a leaf child")
        for child in children:
            if not isinstance(child, dict):
                raise ValueError(f"Invalid child for {module_id}")
            visit(child, module_id, depth + 1, ancestry | {module_id})

    for root in tree.get("root_modules", []):
        visit(root, None, 0, set())
    duplicates = sorted({value for value in assignments if assignments.count(value) > 1})
    missing = sorted(component_ids - set(assignments))
    unknown = sorted(set(assignments) - component_ids)
    if duplicates or missing or unknown:
        raise ValueError(f"Module assignment must cover each component exactly once; duplicates={duplicates}, missing={missing}, unknown={unknown}")
    return modules, parents, depths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--component-index", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--module-tree", help="Optional curated module tree JSON")
    parser.add_argument("--previous-index", help="Optional prior component index for affected-module refresh")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    index_path = Path(args.component_index).expanduser().resolve()
    index = json.loads(index_path.read_text(encoding="utf-8"))
    components = index.get("components", [])
    if not isinstance(components, list) or not all(isinstance(item, dict) and isinstance(item.get("id"), str) for item in components):
        raise SystemExit("Invalid component index")
    ids = [item["id"] for item in components]
    if len(ids) != len(set(ids)):
        raise SystemExit("Component ids must be unique")
    if args.module_tree:
        tree = json.loads(Path(args.module_tree).expanduser().resolve().read_text(encoding="utf-8"))
        tree["schema_version"] = "2.1"
        tree["app_id"] = index["app_id"]
    else:
        tree = auto_tree(index["app_id"], components)
    try:
        modules, parents, depths = validate_tree(tree, set(ids))
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    ordered_ids: list[str] = []
    def postorder(node: dict) -> None:
        for child in node["children"]:
            postorder(child)
        ordered_ids.append(node["id"])
    for root in tree["root_modules"]:
        postorder(root)

    changed = set(ids)
    if args.previous_index:
        previous = json.loads(Path(args.previous_index).expanduser().resolve().read_text(encoding="utf-8"))
        old = {item["id"]: signature(item) for item in previous.get("components", []) if isinstance(item, dict) and isinstance(item.get("id"), str)}
        new = {item["id"]: signature(item) for item in components}
        changed = {key for key in set(old) | set(new) if old.get(key) != new.get(key)}
    affected = {module_id for module_id, node in modules.items() if changed.intersection(node["component_ids"])}
    for module_id in list(affected):
        parent = parents[module_id]
        while parent is not None:
            affected.add(parent)
            parent = parents[parent]
    processing = {
        "schema_version": "2.1", "app_id": index["app_id"], "strategy": "hierarchical_leaf_first",
        "ordered_modules": [
            {"order": number, "module_id": module_id, "depth": depths[module_id], "leaf": not modules[module_id]["children"], "component_ids": modules[module_id]["component_ids"]}
            for number, module_id in enumerate(ordered_ids, 1)
        ],
        "affected_modules": [module_id for module_id in ordered_ids if module_id in affected],
    }
    output = Path(args.output_dir).expanduser().resolve()
    if args.dry_run:
        print(json.dumps({"tree": tree, "processing": processing}, ensure_ascii=False, indent=2))
        return 0
    output.mkdir(parents=True, exist_ok=True)
    tree["generated_at"] = datetime.now(timezone.utc).isoformat()
    (output / "module-tree.json").write_text(json.dumps(tree, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "processing-order.json").write_text(json.dumps(processing, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {len(modules)} modules in leaf-first order at {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
