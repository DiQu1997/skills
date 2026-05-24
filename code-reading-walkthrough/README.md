# code-reading-walkthrough skill

Skill that produces interactive HTML walkthroughs of existing source code,
organized by **logical groups (storylines)** ranked by importance — top-N
walked deeply with line-attached annotations, the rest as summary cards
the reader can promote later.

The reading-oriented sibling of `code-review-narrative`. Same architecture
(3-pane layout, code-attached walkthrough annotations, function-level
rationale), reading-oriented schema (mental_model_anchor, invariants,
key_data_structures, design_rationale instead of behavior_delta /
evaluation / suggestions / concerns).

## Two modes

- **Mode A — files given.** User points at files/folder. Agent identifies
  storylines, scores each on four importance lenses, walks the top-N
  deeply, summarizes the rest.
- **Mode B — topic given.** User asks "how does X work?". Agent first
  proposes a scope (in-bounds + considered-but-excluded files), gets
  user confirmation, then runs the same pipeline on the confirmed slice.

## What you get

A single self-contained HTML file. Three-pane layout:

- **Left**: Storyline tree with importance badges (numeric total, hover
  tooltip shows the four sub-scores), per-storyline overview link,
  step list. Summary-only storylines have a "summary only" pill.
- **Center**: Three view modes — Reading overview (lists all storylines
  + scope panel) / Storyline overview (mental model anchor + purpose +
  architecture + step roadmap) / Step (full enclosing-function code
  with inline walkthrough annotations + supporting definitions).
- **Right**: Collapsible context sections per step.
  - 前情提要 Prerequisites · 心智模型 Mental Model (the anchor for the
    current storyline) · 简介 Summary · 不变量 Invariants · Key Data
    Structures · Where This Is Called From · Codebase Patterns · 设计取舍
    Design Rationale · 分析 Analysis

Section collapse state, current view, and current step persist in
localStorage per-walkthrough so the reader can close the tab and resume
later. A "↺ Reset view" button in the left header clears persisted state.

Keyboard: `j` next step, `k` previous step, `o` reading overview, `s`
storyline overview.

## Importance scoring (1–3 each, sum 4–12)

| Lens | 1 | 2 | 3 |
|---|---|---|---|
| **centrality** | leaf utility, ≤2 callers | moderate fan-in (5–15) | pervasive (15+) |
| **conceptual_weight** | trivial / standard idiom | a few new types or one custom invariant | novel data structure / algo / state machine |
| **entry_point** | internal helper | middle layer, several hops in | public API / CLI / `main()` / request handler |
| **novelty** | boilerplate (config, logging) | project-specific glue | the secret sauce |

Top-N = `clamp(ceil(0.4 * total_storylines), 4, 12)`. Tiebreaker:
`entry_point > centrality > conceptual_weight > novelty`. Scores are
stored in the JSON and rendered in the UI so the reader can see and
challenge the picks.

## Try it

```bash
python3 render.py demo/sample_walkthrough.json demo/sample_walkthrough.html
open demo/sample_walkthrough.html  # or xdg-open / open in browser manually
```

The demo is a Mode A walkthrough of `code-review-narrative` itself —
storyline-grouping the JSON contract, the analysis prompt, the render
pipeline, the template architecture, and the v0.3 walkthrough-annotation
system. Four full-depth storylines + three summary cards.

## Files

```
code-reading-walkthrough/
├── README.md                       ← this file
├── SKILL.md                        ← skill definition + workflow
├── render.py                       ← inject JSON → HTML
├── prompts/
│   ├── schema.md                   ← v0.4-reading JSON schema
│   └── analyze_code.md             ← analysis prompt with two-mode scoping
├── template/
│   └── walkthrough.html            ← single-file HTML/CSS/JS template
└── demo/
    ├── sample_walkthrough.json     ← v0.4-reading demo data
    └── sample_walkthrough.html     ← rendered output
```

## Status

v0.4-reading. Forked from code-review-narrative v0.3 with reading-oriented
schema changes, two-mode scoping front-end, importance-based top-N
selection with summary-card fallback, localStorage view persistence.
Backward-compatible with v0.3 field names where reused (`function_purpose`,
`walkthrough`, `code_view`, `prerequisites`, `usage_context`,
`codebase_patterns`).
