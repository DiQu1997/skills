#!/usr/bin/env python3
"""diff_map.py — mechanically compute a card's `diff` field from base/head files.

Given the base (old) and head (new) versions of a file, and the head-side
line range of a card's code excerpt, emits the card.diff JSON: `added`
(card-relative head line numbers) and `removed` (deleted base lines anchored
after the card-relative head line they precede). This removes the error-prone
manual step of eyeballing a git diff into card coordinates.

Usage:
    python3 diff_map.py BASE_FILE HEAD_FILE --head-start N [--head-count M]

    BASE_FILE   旧版文件（如 `git show BASE_SHA:path > /tmp/old.py`）
    HEAD_FILE   新版文件（工作区或 `git show HEAD_SHA:path`）
    --head-start  卡片摘选在 HEAD 文件里的起始行（1 起）
    --head-count  摘选行数（省略 = 到文件尾）

Output: {"added": [...], "removed": [{"after": ..., "code": ...}, ...]}
行号均为卡片内 1 起的相对行号；removed.after=0 表示显示在卡首之前。
"""
import argparse
import difflib
import json
import sys
from pathlib import Path


def compute(base_lines, head_lines, head_start, head_count):
    """head_start is 1-based; returns card.diff dict with card-relative lines."""
    head_end = head_start + head_count - 1  # inclusive, 1-based
    added, removed = [], []
    sm = difflib.SequenceMatcher(a=base_lines, b=head_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("insert", "replace"):
            for j in range(j1, j2):                    # head lines (0-based)
                ln = j + 1
                if head_start <= ln <= head_end:
                    added.append(ln - head_start + 1)
        if tag in ("delete", "replace"):
            # deleted base lines anchor just after head position j1 (0-based),
            # i.e. after 1-based head line j1
            anchor_head = j1                            # 1-based head line they follow
            if head_start - 1 <= anchor_head <= head_end:
                after = max(0, anchor_head - head_start + 1)
                for i in range(i1, i2):
                    removed.append({"after": after, "code": base_lines[i]})
    return {"added": added, "removed": removed}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("base", type=Path)
    p.add_argument("head", type=Path)
    p.add_argument("--head-start", type=int, required=True)
    p.add_argument("--head-count", type=int, default=None)
    a = p.parse_args()
    base_lines = a.base.read_text(encoding="utf-8", errors="replace").split("\n")
    head_lines = a.head.read_text(encoding="utf-8", errors="replace").split("\n")
    count = a.head_count if a.head_count is not None else len(head_lines) - a.head_start + 1
    if not (1 <= a.head_start <= len(head_lines)):
        sys.exit(f"--head-start {a.head_start} 越界（head 共 {len(head_lines)} 行）")
    print(json.dumps(compute(base_lines, head_lines, a.head_start, count),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
