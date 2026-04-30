#!/usr/bin/env python3
"""
update_line_refs.py — Mechanically update source line references in LLMINDEX.md
based on git diff output. No LLM needed for this operation.

Usage:
  python3 update_line_refs.py <llmindex_path> <source_file> [--diff <diff_file>]

If --diff is not provided, reads from stdin. Expects unified diff format.

What it does:
  1. Parses diff hunks to build a line-number offset map
  2. Reads LLMINDEX.md and finds all "→ src: <source_file>:X-Y `anchor`" references
  3. Shifts X and Y according to the offset map
  4. If a reference falls INSIDE a changed hunk, tries to grep for the anchor
  5. Marks references as STALE if anchor can't be found
"""

import re
import sys
import subprocess
from pathlib import Path


def parse_hunks(diff_text: str) -> list[dict]:
    """Parse unified diff hunks into structured data."""
    hunks = []
    for match in re.finditer(
        r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@',
        diff_text
    ):
        old_start = int(match.group(1))
        old_count = int(match.group(2) or 1)
        new_start = int(match.group(3))
        new_count = int(match.group(4) or 1)
        hunks.append({
            'old_start': old_start,
            'old_end': old_start + old_count - 1,
            'new_start': new_start,
            'new_end': new_start + new_count - 1,
            'old_count': old_count,
            'new_count': new_count,
            'delta': new_count - old_count,
        })
    return hunks


def compute_new_line(old_line: int, hunks: list[dict]) -> tuple[int | None, bool]:
    """
    Compute new line number for an old line number given diff hunks.
    Returns (new_line, inside_changed_hunk).
    If inside_changed_hunk=True, new_line is best-guess and needs anchor verification.
    """
    offset = 0
    for hunk in hunks:
        if old_line < hunk['old_start']:
            # Line is before this hunk, no more offsets to accumulate
            break
        elif old_line <= hunk['old_end']:
            # Line is inside this hunk — content may have changed
            # Best guess: map proportionally into new hunk
            relative = old_line - hunk['old_start']
            if hunk['old_count'] > 0:
                ratio = relative / hunk['old_count']
            else:
                ratio = 0
            guess = hunk['new_start'] + int(ratio * hunk['new_count'])
            return guess, True
        else:
            # Line is after this hunk, accumulate offset
            offset += hunk['delta']

    return old_line + offset, False


def grep_anchor(source_file: str, anchor: str) -> int | None:
    """Try to find anchor text in source file, return line number or None."""
    try:
        result = subprocess.run(
            ['grep', '-n', '-F', anchor, source_file],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            # Take first match
            first_line = result.stdout.strip().split('\n')[0]
            return int(first_line.split(':')[0])
    except (subprocess.TimeoutExpired, ValueError):
        pass
    return None


def update_refs(llmindex_path: str, source_file: str, diff_text: str) -> str:
    """Update source references in LLMINDEX.md based on diff."""
    hunks = parse_hunks(diff_text)
    if not hunks:
        return Path(llmindex_path).read_text()

    content = Path(llmindex_path).read_text()
    lines = content.split('\n')

    # Pattern: → src: path/to/file.cpp:112-158 `SymbolName`
    ref_pattern = re.compile(
        r'(→ src: '
        + re.escape(source_file)
        + r'):(\d+)-(\d+)(\s+`[^`]+`)?'
    )

    updated_lines = []
    stale_count = 0

    for line in lines:
        match = ref_pattern.search(line)
        if match:
            prefix = match.group(1)
            old_start = int(match.group(2))
            old_end = int(match.group(3))
            anchor_part = match.group(4) or ''
            anchor = anchor_part.strip().strip('`') if anchor_part else None

            new_start, start_changed = compute_new_line(old_start, hunks)
            new_end, end_changed = compute_new_line(old_end, hunks)

            # If lines fell inside a changed hunk, try anchor verification
            if (start_changed or end_changed) and anchor and Path(source_file).exists():
                anchor_line = grep_anchor(source_file, anchor)
                if anchor_line is not None:
                    span = old_end - old_start
                    new_start = anchor_line
                    new_end = anchor_line + span
                    start_changed = False
                    end_changed = False

            # If still uncertain after anchor search, mark stale
            if start_changed or end_changed:
                stale_marker = '  <!-- STALE: verify line numbers -->'
                stale_count += 1
            else:
                stale_marker = ''

            new_ref = f'{prefix}:{new_start}-{new_end}{anchor_part}{stale_marker}'
            line = ref_pattern.sub(new_ref, line)

        updated_lines.append(line)

    result = '\n'.join(updated_lines)

    if stale_count > 0:
        print(f"Warning: {stale_count} references marked STALE — anchor not found, "
              f"line numbers are best-guess. Regenerate notes for these files.",
              file=sys.stderr)

    return result


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 update_line_refs.py <llmindex.md> <source_file> [--diff <diff_file>]",
              file=sys.stderr)
        sys.exit(1)

    llmindex_path = sys.argv[1]
    source_file = sys.argv[2]

    if '--diff' in sys.argv:
        diff_idx = sys.argv.index('--diff')
        diff_text = Path(sys.argv[diff_idx + 1]).read_text()
    else:
        diff_text = sys.stdin.read()

    updated = update_refs(llmindex_path, source_file, diff_text)

    # Write back
    Path(llmindex_path).write_text(updated)
    print(f"Updated: {llmindex_path}", file=sys.stderr)


if __name__ == '__main__':
    main()
