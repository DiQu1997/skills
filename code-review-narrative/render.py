#!/usr/bin/env python3
"""
render.py — Inject a review JSON into the HTML template to produce a
self-contained review document.

Two validation gates run before rendering (both on by default):

1. REAL-DIFF CHECK — the JSON's `diff_hunks` are verified against the
   actual PR diff, in both directions AND on content:
     - every +/- line in the real diff must appear in `diff_hunks`
       (nothing the PR changed can be silently dropped),
     - every +/- line in `diff_hunks` must exist in the real diff
       (nothing can be fabricated),
     - the `content` string must match exactly at every line.
   The real diff comes from `--diff <file.patch>` (a saved unified
   diff) or `--repo <path>` (runs `git diff base..head` using
   `--git-range` or, if omitted, `metadata.base_commit..head_commit`).
   Rendering without a diff source is an error; bypass ONLY with
   --no-diff-check (e.g. for hand-authored illustration data).

2. COVERAGE CHECK — every +/- line in `diff_hunks` must appear in at
   least one step's `code_view.primary_changes` (no reviewed line is
   left out of the walkthrough). Bypass with --no-coverage-check.

Chained, the two checks guarantee: real diff == diff_hunks ⊆ steps —
i.e. every line the PR actually changed is walked through, verbatim.

Usage:
    python3 render.py review.json review.html --diff pr.patch
    python3 render.py review.json review.html --repo /path/to/repo
    python3 render.py review.json review.html --repo /path/to/repo --git-range main..feature
    python3 render.py review.json review.html --view swimlane --diff pr.patch
    python3 render.py review.json review.html --no-diff-check          # escape hatch

Two views on the same schema:
    source   — continuous diff top-to-bottom (file-by-file, +/- coloring)
               with each step as a colored highlight band (severity-tinted)
               and a margin annotation showing the step title + concern
               preview. Click → detail panel with concerns, evidence,
               behavior_delta, suggestions, tests, alternatives.
               Best for "walk me through this PR."
    swimlane — original storyline canvas + slide-in dock. Steps as
               phase-tagged block cards in horizontal columns.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

PLACEHOLDER = "/*REVIEW_DATA_PLACEHOLDER*/"

TEMPLATES = {
    "source":   "review_source.html",
    "swimlane": "review.html",
}


# ----- Real-diff check ---------------------------------------------------
# Parses the ACTUAL PR diff and compares it against the JSON's diff_hunks.
# This is the gate that makes diff_hunks trustworthy: without it, the
# coverage check below only proves internal consistency (steps cover
# whatever the agent CLAIMED the diff was), not fidelity to the real PR.

HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_unified_diff(text):
    """Parse unified diff text into {(file, change, line_num): content}.

    Line-number convention matches the schema: `added` lines carry the
    NEW-file line number, `removed` lines carry the OLD-file line number
    (the same convention `git diff` hunk counters walk).
    """
    entries = {}
    old_path = None
    file = None
    old_ln = new_ln = None
    old_left = new_left = 0  # +/-/context lines still expected in current hunk

    for raw in text.splitlines():
        in_hunk = (old_left > 0 or new_left > 0)
        if not in_hunk:
            if raw.startswith("--- "):
                p = raw[4:].split("\t")[0].strip()
                old_path = None if p == "/dev/null" else (p[2:] if p.startswith("a/") else p)
                continue
            if raw.startswith("+++ "):
                p = raw[4:].split("\t")[0].strip()
                if p == "/dev/null":
                    file = old_path  # file deletion: key lines by the old path
                else:
                    file = p[2:] if p.startswith("b/") else p
                continue
            m = HUNK_RE.match(raw)
            if m:
                old_ln = int(m.group(1))
                old_left = int(m.group(2)) if m.group(2) is not None else 1
                new_ln = int(m.group(3))
                new_left = int(m.group(4)) if m.group(4) is not None else 1
            continue

        # Inside a hunk: consume exactly old_left+new_left line slots.
        if raw.startswith("\\"):
            continue  # "\ No newline at end of file"
        if raw.startswith("+"):
            entries[(file, "added", new_ln)] = raw[1:]
            new_ln += 1
            new_left -= 1
        elif raw.startswith("-"):
            entries[(file, "removed", old_ln)] = raw[1:]
            old_ln += 1
            old_left -= 1
        else:
            # context line (starts with ' ' — or is empty for blank context)
            old_ln += 1
            new_ln += 1
            old_left -= 1
            new_left -= 1
    return entries


def load_real_diff(args, data):
    """Resolve the real diff text from --diff or --repo. Returns (text, label)
    or exits with an explanatory error."""
    if args.diff:
        if not args.diff.exists():
            print(f"[diff-check] Diff file not found: {args.diff}", file=sys.stderr)
            sys.exit(1)
        return args.diff.read_text(encoding="utf-8", errors="replace"), str(args.diff)
    if args.repo:
        md = data.get("metadata") or {}
        if args.git_range:
            rng = args.git_range
        else:
            base, head = md.get("base_commit"), md.get("head_commit")
            if not base or not head:
                print("[diff-check] --repo given but no --git-range, and metadata lacks "
                      "base_commit/head_commit to derive one.", file=sys.stderr)
                sys.exit(1)
            rng = f"{base}..{head}"
        cmd = ["git", "-C", str(args.repo), "diff", "--no-color", "--no-ext-diff", rng]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"[diff-check] git diff failed: {' '.join(cmd)}", file=sys.stderr)
            print(e.stderr.strip(), file=sys.stderr)
            sys.exit(1)
        return out.stdout, f"git -C {args.repo} diff {rng}"
    return None, None


def validate_against_real_diff(data, real_entries):
    """Compare diff_hunks against the parsed real diff.

    Returns dict with three problem lists:
      missing    — real +/- lines absent from diff_hunks (dropped changes)
      fabricated — diff_hunks +/- lines absent from the real diff
      content    — matched (file, change, line_num) but content differs
    """
    json_entries = {}
    for hunk in data.get("diff_hunks") or []:
        f = hunk.get("file")
        for line in hunk.get("lines") or []:
            ch = line.get("change")
            if ch in ("added", "removed") and "line_num" in line:
                json_entries[(f, ch, line["line_num"])] = line.get("content", "")

    problems = {"missing": [], "fabricated": [], "content": []}
    for key, content in real_entries.items():
        if key not in json_entries:
            problems["missing"].append((key, content))
        elif json_entries[key] != content:
            problems["content"].append((key, content, json_entries[key]))
    for key, content in json_entries.items():
        if key not in real_entries:
            problems["fabricated"].append((key, content))
    return problems


def report_diff_check(problems, n_real, source_label):
    """Print the real-diff report. Returns True if OK to proceed."""
    bad = sum(len(v) for v in problems.values())
    if not bad:
        print(f"[diff-check] OK: diff_hunks match the real diff exactly "
              f"({n_real} +/- lines, source: {source_label}).")
        return True
    print(f"[diff-check] FAIL: diff_hunks do not match the real diff "
          f"({source_label}):", file=sys.stderr)
    if problems["missing"]:
        print(f"  {len(problems['missing'])} real change line(s) MISSING from diff_hunks "
              f"(the review silently drops them):", file=sys.stderr)
        for (file, ch, ln), content in sorted(problems["missing"])[:15]:
            sign = "+" if ch == "added" else "-"
            print(f"    {file}:{ln}  {sign} {content!r}", file=sys.stderr)
        if len(problems["missing"]) > 15:
            print(f"    … +{len(problems['missing']) - 15} more", file=sys.stderr)
    if problems["fabricated"]:
        print(f"  {len(problems['fabricated'])} diff_hunks line(s) NOT in the real diff "
              f"(fabricated or mis-numbered):", file=sys.stderr)
        for (file, ch, ln), content in sorted(problems["fabricated"])[:15]:
            sign = "+" if ch == "added" else "-"
            print(f"    {file}:{ln}  {sign} {content!r}", file=sys.stderr)
        if len(problems["fabricated"]) > 15:
            print(f"    … +{len(problems['fabricated']) - 15} more", file=sys.stderr)
    if problems["content"]:
        print(f"  {len(problems['content'])} line(s) with CONTENT drift:", file=sys.stderr)
        for (file, ch, ln), real, claimed in sorted(problems["content"])[:15]:
            print(f"    {file}:{ln} ({ch})", file=sys.stderr)
            print(f"      real:    {real!r}", file=sys.stderr)
            print(f"      claimed: {claimed!r}", file=sys.stderr)
        if len(problems["content"]) > 15:
            print(f"    … +{len(problems['content']) - 15} more", file=sys.stderr)
    print("[diff-check] Fix diff_hunks to mirror the real diff exactly "
          "(lift lines verbatim from `git diff`), OR pass --no-diff-check "
          "to bypass (not recommended).", file=sys.stderr)
    return False


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
    p.add_argument("--view", choices=list(TEMPLATES.keys()), default="source",
                   help="Which render template to use. 'source' (default) is "
                        "the continuous-diff-with-margin-annotations view; "
                        "'swimlane' is the original storyline canvas + dock.")
    p.add_argument("--diff", type=Path, default=None,
                   help="Path to the PR's unified diff (a .patch file, e.g. "
                        "saved via `git diff base..head > pr.patch`). The "
                        "JSON's diff_hunks are verified against it exactly.")
    p.add_argument("--repo", type=Path, default=None,
                   help="Path to the repo clone; the real diff is produced by "
                        "running `git diff` there, over --git-range or "
                        "metadata.base_commit..head_commit.")
    p.add_argument("--git-range", default=None,
                   help="Git range for --repo mode, e.g. 'main..feature' or "
                        "'abc123..def456'. Defaults to metadata commits.")
    p.add_argument("--no-diff-check", action="store_true",
                   help="Skip verifying diff_hunks against the real PR diff. "
                        "Escape hatch for hand-authored illustration data — "
                        "with this set, nothing guarantees diff_hunks reflect "
                        "an actual diff.")
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

    template_path = Path(__file__).parent / "template" / TEMPLATES[args.view]
    if not template_path.exists():
        print(f"Template not found: {template_path}", file=sys.stderr)
        sys.exit(1)

    # Load and validate JSON parses.
    with open(args.input, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Real-diff check FIRST: makes diff_hunks trustworthy before the
    # coverage check builds on it.
    if not args.no_diff_check:
        diff_text, source_label = load_real_diff(args, data)
        if diff_text is None:
            print("[diff-check] FAIL: no diff source given; cannot verify diff_hunks "
                  "against the real PR.", file=sys.stderr)
            print("[diff-check] Provide one of:", file=sys.stderr)
            print("  --diff <pr.patch>       a saved unified diff "
                  "(git diff base..head > pr.patch)", file=sys.stderr)
            print("  --repo <path>           run git diff there over "
                  "--git-range or metadata commits", file=sys.stderr)
            print("[diff-check] or pass --no-diff-check to bypass "
                  "(illustration data only).", file=sys.stderr)
            sys.exit(3)
        real_entries = parse_unified_diff(diff_text)
        problems = validate_against_real_diff(data, real_entries)
        if not report_diff_check(problems, len(real_entries), source_label):
            sys.exit(3)

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
    print(f"Wrote {args.output} ({size_kb:.1f} KB) [view={args.view}]")
    print(f"  Storylines: {len(data.get('storylines', []))}")
    print(f"  Total steps: {sum(len(s.get('steps') or []) for s in data.get('storylines', []))}")


if __name__ == "__main__":
    main()
