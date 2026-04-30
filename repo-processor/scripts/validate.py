#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List
import sys


LEAF_HEADINGS = [
    "## Files Overview",
    "## Key Types",
    "## Functions",
    "## Internal Logic",
    "## Concurrency Details",
    "## Dependencies",
    "## Usage Guide",
    "## Extension Guide",
]

ROLLUP_HEADINGS = [
    "## Sub-modules",
    "## Module Relationships",
    "### Dependency Graph",
    "### Data Flow",
    "### Shared Patterns",
    "### Cross-Cutting Concerns",
    "## Interface Contract",
    "### Public API Surface",
    "### Assumptions Made by External Callers",
]

GLOBAL_HEADINGS: Dict[str, List[str]] = {
    "OVERVIEW.md": [
        "## Purpose",
        "## Tech Stack",
        "## Build & Run",
        "## Design Philosophy",
        "## Project Structure",
    ],
    "ARCHITECTURE.md": [
        "## System Diagram",
        "## Module Dependency Graph",
        "## Key Data Flows",
        "## Layer Rules",
    ],
    "CONVENTIONS.md": [
        "## Naming",
        "## Error Handling",
        "## Testing",
        "## Logging",
        "## Code Style",
    ],
    "CONCURRENCY.md": [
        "## Threading Architecture",
        "## Lock Inventory",
        "## Lock Ordering",
        "## Async Model",
        "## Shared State Catalog",
        "## Gotchas & Rules",
    ],
    "ENTRY_POINTS.md": [
        "## How to Add a New API Endpoint",
        "## How to Add a New Storage Backend",
    ],
    "QUICK_REFERENCE.md": [
        "## Key Types",
        "## Key Functions",
        "## File → Responsibility Map",
        "## Glossary",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="repo-processor validate")
    parser.add_argument("plan_json", help="Path to execution_plan.json")
    return parser.parse_args()


def check_headings(path: Path, headings: List[str]) -> List[str]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ["file unreadable"]

    missing = []
    for h in headings:
        if h not in text:
            missing.append(h)
    return missing


def resolve_output(plan_target: str, output: str) -> Path:
    out_path = Path(output)
    if out_path.is_absolute():
        return out_path
    return Path(plan_target) / out_path


def main() -> int:
    args = parse_args()
    plan = json.loads(Path(args.plan_json).read_text(encoding="utf-8"))
    plan_target = plan.get("target_path") or ""

    failures: List[str] = []

    for level in plan.get("levels", []):
        for task in level.get("tasks", []):
            ttype = task.get("type")
            if ttype in {"leaf", "rollup"}:
                output = resolve_output(plan_target, task.get("output"))
                if not output.exists():
                    failures.append(f"missing file: {output}")
                    continue
                if output.stat().st_size < 200:
                    failures.append(f"file too small: {output}")
                headings = LEAF_HEADINGS if ttype == "leaf" else ROLLUP_HEADINGS
                missing = check_headings(output, headings)
                for h in missing:
                    failures.append(f"missing heading in {output}: {h}")
            elif ttype == "global":
                for output in task.get("outputs", []):
                    out_path = resolve_output(plan_target, output)
                    if not out_path.exists():
                        failures.append(f"missing file: {out_path}")
                        continue
                    if out_path.stat().st_size < 200:
                        failures.append(f"file too small: {out_path}")
                    heading_list = GLOBAL_HEADINGS.get(out_path.name, [])
                    missing = check_headings(out_path, heading_list)
                    for h in missing:
                        failures.append(f"missing heading in {out_path}: {h}")

    if failures:
        for f in failures:
            print(f, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
