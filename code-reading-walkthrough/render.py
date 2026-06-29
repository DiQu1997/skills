#!/usr/bin/env python3
"""
render.py — Inject a walkthrough JSON into the HTML template to produce
a self-contained code-reading walkthrough document.

Usage:
    python3 render.py <input.json> <output.html>                 # default = swimlane view
    python3 render.py <input.json> <output.html> --view diagram  # data-structure-centric view
"""

import json
import sys
import os
from pathlib import Path

PLACEHOLDER = "/*WALKTHROUGH_DATA_PLACEHOLDER*/"

TEMPLATES = {
    "swimlane": "walkthrough.html",
    "diagram":  "walkthrough_diagram.html",
}

def main():
    raw = sys.argv[1:]
    view = "swimlane"
    args = []
    i = 0
    while i < len(raw):
        if raw[i] == "--view" and i + 1 < len(raw):
            view = raw[i + 1]
            i += 2
        else:
            args.append(raw[i])
            i += 1
    if len(args) != 2:
        print("Usage: python3 render.py <input.json> <output.html> [--view swimlane|diagram]", file=sys.stderr)
        sys.exit(1)
    if view not in TEMPLATES:
        print(f"Unknown view: {view}. Choose from: {list(TEMPLATES)}", file=sys.stderr)
        sys.exit(1)

    input_path = Path(args[0])
    output_path = Path(args[1])

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    template_path = Path(__file__).parent / "template" / TEMPLATES[view]
    if not template_path.exists():
        print(f"Template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    if PLACEHOLDER not in template:
        print(f"Template missing placeholder: {PLACEHOLDER}", file=sys.stderr)
        sys.exit(1)

    injected = json.dumps(data, ensure_ascii=False, indent=2)
    injected = injected.replace("</", "<\\/")

    output = template.replace(PLACEHOLDER, injected, 1)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output)

    size_kb = os.path.getsize(output_path) / 1024
    storylines = data.get("storylines", [])
    full_count = sum(1 for s in storylines if s.get("depth", "full") == "full")
    summary_count = sum(1 for s in storylines if s.get("depth") == "summary")
    total_blocks = sum(
        sum(len(col.get("blocks", []) or []) for col in (s.get("diagram") or {}).get("cols", []) or [])
        for s in storylines
    )
    total_edges = sum(
        len((s.get("diagram") or {}).get("edges", []) or [])
        for s in storylines
    )
    total_ds = sum(
        len((s.get("diagram") or {}).get("data_structures", []) or [])
        for s in storylines
    )
    print(f"Wrote {output_path} ({size_kb:.1f} KB) [view={view}]")
    print(f"  Storylines: {len(storylines)} ({full_count} full, {summary_count} summary)")
    print(f"  Total blocks: {total_blocks}, edges: {total_edges}, data_structures: {total_ds}")

if __name__ == "__main__":
    main()
