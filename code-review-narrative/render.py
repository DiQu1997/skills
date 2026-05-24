#!/usr/bin/env python3
"""
render.py — Inject a review JSON into the HTML template to produce a
self-contained review document.

Also verifies that every +/- line declared in `diff_hunks` appears in
at least one step's `code_view.primary_changes` (coverage check). Bypass
with --no-coverage-check.

Usage:
    python3 render.py <input.json> <output.html>
    python3 render.py demo/sample_review.json demo/sample_review.html
    python3 render.py review.json review.html --no-coverage-check
"""

import argparse
import json
import os
import sys
from pathlib import Path

PLACEHOLDER = "/*REVIEW_DATA_PLACEHOLDER*/"


# ----- Coverage check ---------------------------------------------------

def compute_coverage(data):
    """Return (covered_count, total_count, uncovered_list).

    Iterates `diff_hunks` for every line where change is added/removed.
    Matches against (file, change, line_num) tuples collected from all
    `code_view.primary_changes[].lines` across the document.

    uncovered_list items: (file, change, line_num, content).
    """
    hunks = data.get("diff_hunks") or []

    # Build the set of covered keys from every step's code_view.
    covered = set()
    for sl in data.get("storylines") or []:
        for st in sl.get("steps") or []:
            cv = st.get("code_view") or {}
            for fv in cv.get("primary_changes") or []:
                file = fv.get("file")
                for line in fv.get("lines") or []:
                    ch = line.get("change")
                    if ch in ("added", "removed") and "line_num" in line:
                        covered.add((file, ch, line["line_num"]))

    # Walk diff_hunks; collect what's missing.
    uncovered = []
    total = 0
    covered_count = 0
    for hunk in hunks:
        file = hunk.get("file")
        for line in hunk.get("lines") or []:
            ch = line.get("change")
            if ch not in ("added", "removed"):
                continue  # unchanged context lines in diff_hunks (if any) are not counted
            total += 1
            key = (file, ch, line.get("line_num"))
            if key in covered:
                covered_count += 1
            else:
                uncovered.append((file, ch, line.get("line_num"), line.get("content", "")))

    return covered_count, total, uncovered


def report_coverage(covered, total, uncovered, has_hunks):
    """Print a coverage report. Returns True if coverage is OK to proceed."""
    if not has_hunks:
        print("[coverage] FAIL: no `diff_hunks` field in JSON; cannot verify coverage.", file=sys.stderr)
        print("[coverage] Either populate `diff_hunks` (one entry per changed file with all +/- lines)", file=sys.stderr)
        print("[coverage] or pass --no-coverage-check to bypass.", file=sys.stderr)
        return False

    if total == 0:
        print("[coverage] WARN: `diff_hunks` is present but contains no added/removed lines.", file=sys.stderr)
        return True

    pct = 100.0 * covered / total
    if uncovered:
        print(f"[coverage] FAIL: {covered}/{total} lines covered ({pct:.1f}%); "
              f"{len(uncovered)} uncovered:", file=sys.stderr)
        # Group by file for readability
        by_file = {}
        for file, change, line_num, content in uncovered:
            by_file.setdefault(file, []).append((change, line_num, content))
        for file in sorted(by_file):
            print(f"  {file}:", file=sys.stderr)
            for change, line_num, content in sorted(by_file[file], key=lambda x: (x[1] or 0, x[0])):
                marker = "+" if change == "added" else "-"
                snippet = content[:80] + ("…" if len(content) > 80 else "")
                print(f"    L{line_num} {marker} {snippet}", file=sys.stderr)
        print("[coverage] To fix: add each uncovered line to some step's "
              "code_view.primary_changes[].lines with the matching `change`.", file=sys.stderr)
        return False

    print(f"[coverage] OK: {covered}/{total} lines covered (100%)")
    return True


# ----- Main -------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__.strip(),
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", type=Path, help="Review JSON input file.")
    p.add_argument("output", type=Path, help="Rendered HTML output file.")
    p.add_argument("--no-coverage-check", action="store_true",
                   help="Skip the diff_hunks ↔ code_view coverage check. "
                        "Use only as an escape hatch; the default behavior "
                        "is to refuse rendering if any +/- line is uncovered.")
    return p.parse_args()


def main():
    args = parse_args()

    if not args.input.exists():
        print(f"Input file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    template_path = Path(__file__).parent / "template" / "review.html"
    if not template_path.exists():
        print(f"Template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    # Load and validate JSON parses.
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Coverage check (before rendering, so a failing review never produces an HTML).
    if not args.no_coverage_check:
        has_hunks = bool(data.get("diff_hunks"))
        covered, total, uncovered = compute_coverage(data)
        ok = report_coverage(covered, total, uncovered, has_hunks)
        if not ok:
            sys.exit(2)

    # Read template.
    with open(template_path, "r", encoding="utf-8") as f:
        template = f.read()

    if PLACEHOLDER not in template:
        print(f"Template missing placeholder: {PLACEHOLDER}", file=sys.stderr)
        sys.exit(1)

    # Inject JSON. json.dumps yields a valid JS literal; ensure_ascii=False
    # keeps CJK readable; the </ → <\/ escape prevents any "</script>" inside
    # JSON content from closing the embedding <script> tag prematurely.
    injected = json.dumps(data, ensure_ascii=False, indent=2)
    injected = injected.replace("</", "<\\/")

    # Replace only the FIRST occurrence; placeholder may appear in error
    # messages elsewhere in the template.
    output = template.replace(PLACEHOLDER, injected, 1)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(output)

    size_kb = os.path.getsize(args.output) / 1024
    print(f"Wrote {args.output} ({size_kb:.1f} KB)")
    print(f"  Storylines: {len(data.get('storylines', []))}")
    print(f"  Total steps: {sum(len(s.get('steps') or []) for s in data.get('storylines', []))}")


if __name__ == "__main__":
    main()
