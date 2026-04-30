#!/usr/bin/env python3
"""
render.py — Inject a review JSON into the HTML template to produce a
self-contained review document.

Usage:
    python3 render.py <input.json> <output.html>
    python3 render.py demo/sample_review.json demo/sample_review.html
"""

import json
import sys
import os
from pathlib import Path

PLACEHOLDER = "/*REVIEW_DATA_PLACEHOLDER*/"

def main():
    if len(sys.argv) != 3:
        print("Usage: python3 render.py <input.json> <output.html>", file=sys.stderr)
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])

    if not input_path.exists():
        print(f"Input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    template_path = Path(__file__).parent / "template" / "review.html"
    if not template_path.exists():
        print(f"Template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    # Validate JSON parses
    with open(input_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Read template
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    if PLACEHOLDER not in template:
        print(f"Template missing placeholder: {PLACEHOLDER}", file=sys.stderr)
        sys.exit(1)

    # Inject JSON. Use json.dumps to ensure valid JS literal.
    # ensure_ascii=False keeps Chinese chars readable in the output.
    # Escape any literal "</" so a "</script>" inside JSON content can't
    # close our embedding <script> tag prematurely.
    injected = json.dumps(data, ensure_ascii=False, indent=2)
    injected = injected.replace("</", "<\\/")

    # IMPORTANT: replace only the FIRST occurrence. Some templates may
    # legitimately reference the placeholder string elsewhere (e.g. in an
    # error message); we must not corrupt those.
    if template.count(PLACEHOLDER) == 0:
        print(f"Template missing placeholder: {PLACEHOLDER}", file=sys.stderr)
        sys.exit(1)
    output = template.replace(PLACEHOLDER, injected, 1)

    # Write
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(output)

    size_kb = os.path.getsize(output_path) / 1024
    print(f"Wrote {output_path} ({size_kb:.1f} KB)")
    print(f"  Storylines: {len(data['storylines'])}")
    print(f"  Total steps: {sum(len(s['steps']) for s in data['storylines'])}")

if __name__ == "__main__":
    main()
