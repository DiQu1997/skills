# code-review-narrative skill

Skill that produces interactive HTML review documents from git diffs,
organized by **logical groups (storylines)** rather than file-by-file.

**v0.3** keeps the v0.2 rich factual context (behavior_delta, usage_context,
test_coverage, codebase_patterns, alternative_approaches) and storyline-level
overview (purpose, architectural_context, change_overview, reading_roadmap),
and adds:

- `prior_role` — what an existing function/class/struct was doing before this
  change, so the delta is readable
- `function_purpose` on FileView — function-level motivation
  (`problem_solved` / `without_it`), single- or multi-section
- `walkthrough` on FileView — sparse code-attached annotations that connect
  the +/- lines to the surrounding logic
- `concerns` on each step — explicit issues with `{concern, evidence, severity}`

## What you get

A single self-contained HTML file. Three-pane layout:

- **Left**: Storyline tree with per-storyline overview link and step list.
- **Center**: Three view modes — PR overview / Storyline overview / Step.
  Step view shows full enclosing-function code context with optional
  `function_purpose` rationale and inline `walkthrough` annotations, plus
  supporting definitions.
- **Right**: Collapsible context + analysis sections per step.
  - *Context* (factual): 前情提要 · Prior role · Behavior delta · Usage context
    (callers, call patterns, implicit deps) · Test coverage · Codebase patterns
    · Alternative approaches
  - *Analysis* (opinion): 简介 · 评价 · 建议 · 分析 · Concerns (with severity)

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
code-review-narrative/
├── README.md
├── SKILL.md                     ← skill definition
├── render.py                    ← inject JSON → HTML
├── prompts/
│   ├── schema.md                ← v0.3 JSON schema
│   └── analyze_diff.md          ← v0.3 analysis prompt
├── template/
│   └── review.html              ← single-file HTML/CSS/JS template
└── demo/
    ├── sample_review.json       ← v0.3 demo data (rich context + walkthrough)
    └── sample_review.html       ← rendered output
```

## Status

v0.3. Schema enriched with `prior_role`, FileView-level `function_purpose`
and `walkthrough`, and structured `concerns`. Template supports collapsible
sections, storyline view, PR view, inline walkthrough annotations.

Backward-compatible with v0.2 data: documents without v0.3 fields render
with those sections omitted.
