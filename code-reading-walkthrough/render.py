#!/usr/bin/env python3
"""
render.py — Inject a walkthrough JSON into the HTML template to produce
a self-contained code-reading walkthrough document.

Usage:
    python3 render.py <input.json> <output.html>                       # swimlane view (default)
    python3 render.py <input.json> <output.html> --view diagram
    python3 render.py <in.json> <out.html> --source-root /path/to/repo # validate code_view content
    python3 render.py <in.json> <out.html> --no-source-check           # skip content validation
"""

import json
import sys
import os
from pathlib import Path

PLACEHOLDER = "/*WALKTHROUGH_DATA_PLACEHOLDER*/"

TEMPLATES = {
    "swimlane": "walkthrough.html",
    "diagram":  "walkthrough_diagram.html",
    "source":   "walkthrough_source.html",
}


# ============================================================
# Source-content validator
# ============================================================
# Diffs every block's code_view.lines[].content against the actual
# source file. Catches the class of bug where the agent transcribes
# code incorrectly (indent off, line shift, paraphrased pseudocode).
# Same shape as code-review-narrative's coverage gate.

def validate_source_content(data, source_root):
    """Returns (n_blocks_checked, mismatches) where mismatches is a
    list of dicts: {block_id, file, line_num, claimed, actual_or_marker}."""
    n_checked = 0
    mismatches = []
    src_cache = {}

    def load(rel_path):
        if rel_path in src_cache:
            return src_cache[rel_path]
        full = source_root / rel_path
        if not full.exists():
            src_cache[rel_path] = None
            return None
        src_cache[rel_path] = full.read_text(encoding="utf-8", errors="replace").splitlines()
        return src_cache[rel_path]

    for sl in data.get("storylines") or []:
        diag = sl.get("diagram") or {}
        for col in diag.get("cols") or []:
            for b in col.get("blocks") or []:
                cv = b.get("code_view") or {}
                file_rel = cv.get("file")
                lines = cv.get("lines") or []
                if not file_rel or not lines:
                    continue
                src = load(file_rel)
                if src is None:
                    mismatches.append({
                        "block_id": b.get("id"),
                        "file": file_rel,
                        "line_num": None,
                        "claimed": None,
                        "actual": "<source file not found>",
                    })
                    continue
                n_checked += 1
                for line in lines:
                    ln = line.get("line_num")
                    claimed = line.get("content", "")
                    if not isinstance(ln, int) or ln < 1 or ln > len(src):
                        mismatches.append({
                            "block_id": b.get("id"),
                            "file": file_rel,
                            "line_num": ln,
                            "claimed": claimed,
                            "actual": f"<out of range; source has {len(src)} lines>",
                        })
                        continue
                    actual = src[ln - 1]
                    if actual != claimed:
                        mismatches.append({
                            "block_id": b.get("id"),
                            "file": file_rel,
                            "line_num": ln,
                            "claimed": claimed,
                            "actual": actual,
                        })
    return n_checked, mismatches


def report_source_mismatches(n_checked, mismatches):
    if not mismatches:
        print(f"[source-check] OK: {n_checked} block(s) verified against source.")
        return True
    by_block = {}
    for m in mismatches:
        by_block.setdefault(m["block_id"], []).append(m)
    print(f"[source-check] FAIL: {len(mismatches)} content mismatch(es) across "
          f"{len(by_block)} block(s) ({n_checked} block(s) checked):", file=sys.stderr)
    for bid, ms in by_block.items():
        for m in ms[:6]:  # cap per-block report
            ln = m["line_num"]
            ln_str = f"L{ln}" if ln else "(no line)"
            print(f"  ✗ {bid}  {m['file']}:{ln_str}", file=sys.stderr)
            if m["claimed"] is not None:
                print(f"     claimed: {m['claimed']!r}", file=sys.stderr)
            print(f"     actual:  {m['actual']!r}", file=sys.stderr)
        if len(ms) > 6:
            print(f"  … +{len(ms) - 6} more in {bid}", file=sys.stderr)
    print("[source-check] Fix the code_view.lines[].content fields to match the source file "
          "exactly, OR pass --no-source-check to bypass (not recommended).", file=sys.stderr)
    return False


def main():
    raw = sys.argv[1:]
    view = "swimlane"
    source_root = Path(".")
    no_source_check = False
    args = []
    i = 0
    while i < len(raw):
        if raw[i] == "--view" and i + 1 < len(raw):
            view = raw[i + 1]; i += 2
        elif raw[i] == "--source-root" and i + 1 < len(raw):
            source_root = Path(raw[i + 1]); i += 2
        elif raw[i] == "--no-source-check":
            no_source_check = True; i += 1
        else:
            args.append(raw[i]); i += 1
    if len(args) != 2:
        print("Usage: python3 render.py <input.json> <output.html> "
              "[--view swimlane|diagram] [--source-root PATH] [--no-source-check]", file=sys.stderr)
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

    # Source-content validation (refuse render if code_view content drifts)
    if not no_source_check:
        n_checked, mismatches = validate_source_content(data, source_root)
        if not report_source_mismatches(n_checked, mismatches):
            sys.exit(2)

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
