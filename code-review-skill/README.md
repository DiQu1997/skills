# code-review-narrative skill

Skill that produces interactive HTML review documents from git diffs,
organized by **logical groups (storylines)** rather than file-by-file.

**v0.2** adds rich factual context (behavior delta, callers, test coverage,
codebase patterns, alternative approaches) plus storyline-level overview
(purpose, architectural context, change overview, reading roadmap) so a
reviewer can confidently judge changes even without prior familiarity with
the codebase.

## What you get

A single self-contained HTML file. Three-pane layout:

- **Left**: Storyline tree with per-storyline overview link and step list.
- **Center**: Three view modes — PR overview / Storyline overview / Step.
  Step view shows full enclosing-function code context plus supporting
  definitions.
- **Right**: Collapsible context + analysis sections per step.
  - *Context* (factual): 前情提要 · Behavior delta · Usage context (callers,
    call patterns, implicit deps) · Test coverage · Codebase patterns ·
    Alternative approaches
  - *Analysis* (opinion): 简介 · 评价 · 建议 · 分析

Section collapse state persists across step navigation. Default-collapsed
sections (Test coverage, Codebase patterns, Alternatives) keep the right
pane scannable while still being one click away.

Keyboard: `j` next step, `k` previous step, `o` PR overview.

## Try it

```bash
python3 render.py demo/sample_review.json demo/sample_review.html
open demo/sample_review.html  # or xdg-open / open in browser manually
```

## Files

```
code-review-skill/
├── README.md
├── SKILL.md                     ← skill definition
├── render.py                    ← inject JSON → HTML
├── prompts/
│   ├── schema.md                ← v0.2 JSON schema
│   └── analyze_diff.md          ← v0.2 analysis prompt
├── template/
│   └── review.html              ← single-file HTML/CSS/JS template
└── demo/
    ├── sample_review.json       ← v0.2 demo data (rich context)
    └── sample_review.html       ← rendered output
```

## Status

v0.2. Schema enriched with storyline-level overview and step-level
factual context. Template supports collapsible sections, storyline view,
PR view. Agent integration (auto-generation from git diff) not yet wired.

Backward-compatible with v0.2 data: old documents render with empty
context sections.
