#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class DirNode:
    path: str
    source_files: List[str]
    source_loc: int
    subdirs: List[str]
    has_generated: bool
    children: List[str] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="repo-processor plan")
    parser.add_argument("recon_json", help="Path to recon_output.json")
    parser.add_argument("plan_json", help="Path to execution_plan.json")
    return parser.parse_args()


def detail_level(source_loc: int, file_count: int) -> str:
    if source_loc < 500 and file_count <= 5:
        return "exhaustive"
    if source_loc < 2000 and file_count <= 15:
        return "standard"
    return "overview"


def main() -> int:
    args = parse_args()
    recon_path = Path(args.recon_json)
    plan_path = Path(args.plan_json)

    data = json.loads(recon_path.read_text(encoding="utf-8"))
    directory_tree = data.get("directory_tree", [])

    nodes: Dict[str, DirNode] = {}
    for entry in directory_tree:
        path = entry.get("path", "")
        nodes[path] = DirNode(
            path=path,
            source_files=list(entry.get("source_files", [])),
            source_loc=int(entry.get("source_loc", 0)),
            subdirs=list(entry.get("subdirs", [])),
            has_generated=bool(entry.get("has_generated", False)),
        )

    for path, node in nodes.items():
        for child_name in node.subdirs:
            child_path = f"{path}/{child_name}" if path else child_name
            if child_path in nodes:
                node.children.append(child_path)

    def has_source_in_subtree(path: str) -> bool:
        node = nodes[path]
        if node.source_files:
            return True
        for child in node.children:
            if has_source_in_subtree(child):
                return True
        return False

    children_with_source_count: Dict[str, int] = {}
    for path, node in nodes.items():
        count = 0
        for child in node.children:
            if has_source_in_subtree(child):
                count += 1
        children_with_source_count[path] = count

    def classify(path: str) -> str:
        node = nodes[path]
        has_source = len(node.source_files) > 0
        has_children = len(node.subdirs) > 0
        children_with_source = children_with_source_count[path]

        if has_source and not has_children:
            return "leaf"
        if has_source and has_children:
            return "leaf_and_rollup"
        if (not has_source) and children_with_source >= 2:
            return "rollup"
        return "skip"

    classifications: Dict[str, str] = {path: classify(path) for path in nodes}

    doc_dirs = {path for path, c in classifications.items() if c in {"leaf", "leaf_and_rollup", "rollup"}}

    def level_for(path: str) -> int:
        node = nodes[path]
        child_levels = []
        for child in node.children:
            if child in doc_dirs:
                child_levels.append(level_for(child))
        if not child_levels:
            return 0
        return max(child_levels) + 1

    levels_map: Dict[int, List[dict]] = {}

    for path in sorted(doc_dirs):
        c = classifications[path]
        node = nodes[path]

        if c == "leaf":
            task = {
                "task_id": f"leaf-{path.replace('/', '-') or 'root'}",
                "type": "leaf",
                "path": path or ".",
                "detail_level": detail_level(node.source_loc, len(node.source_files)),
                "source_files": node.source_files,
                "source_loc": node.source_loc,
                "output": f"{path}/ai_doc.md" if path else "ai_doc.md",
            }
        else:
            child_docs = []
            for child in node.children:
                if child in doc_dirs:
                    child_docs.append(f"{child}/ai_doc.md" if child else "ai_doc.md")
            task = {
                "task_id": f"rollup-{path.replace('/', '-') or 'root'}",
                "type": "rollup",
                "path": path or ".",
                "local_source_files": node.source_files,
                "child_docs": child_docs,
                "output": f"{path}/ai_doc.md" if path else "ai_doc.md",
            }

        lvl = level_for(path)
        levels_map.setdefault(lvl, []).append(task)

    levels = []
    for lvl in sorted(levels_map.keys()):
        levels.append({
            "level": lvl,
            "description": "Leaf and roll-up tasks",
            "tasks": sorted(levels_map[lvl], key=lambda t: t["path"]),
        })

    # Global tasks
    # Skip global docs if only one leaf and it is the scope root with no children having source.
    scope_root = ""
    root_class = classifications.get(scope_root, "skip")
    only_one_doc = len(doc_dirs) == 1 and scope_root in doc_dirs
    if not (only_one_doc and root_class == "leaf"):
        all_docs = [
            f"{path}/ai_doc.md" if path else "ai_doc.md"
            for path in sorted(doc_dirs)
        ]
        global_task = {
            "task_id": "global-001",
            "type": "global",
            "all_docs": all_docs,
            "outputs": [
                ".ai-docs/OVERVIEW.md",
                ".ai-docs/ARCHITECTURE.md",
                ".ai-docs/CONVENTIONS.md",
                ".ai-docs/CONCURRENCY.md",
                ".ai-docs/ENTRY_POINTS.md",
                ".ai-docs/QUICK_REFERENCE.md",
            ],
        }
        levels.append({
            "level": max(levels_map.keys(), default=0) + 1,
            "description": "Global docs",
            "tasks": [global_task],
        })

    plan = {
        "target_path": data.get("target_path"),
        "levels": levels,
    }

    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
