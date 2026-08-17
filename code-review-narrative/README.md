# code-review-narrative skill

Skill that produces interactive HTML review documents from git diffs,
organized by **logical groups (storylines)** rather than file-by-file.

**v0.4** adds a top-level `diff_hunks` field listing every +/- line in the
diff, and `render.py` enforces two gates before writing HTML:

1. **Real-diff check** (default ON): `diff_hunks` is verified against the
   actual PR diff — supplied via `--diff pr.patch` or `--repo <clone>`
   (range from `--git-range` or `metadata.base_commit..head_commit`) —
   in both directions and on exact content. A dropped change, a
   fabricated line, or a single character of drift aborts the render.
2. **Coverage check**: every `(file, change, line_num)` triple from
   `diff_hunks` must appear in some step's `code_view`.

Chained: **real diff == diff_hunks ⊆ steps** — every line the PR
actually changed is walked through, verbatim. The agent can no longer
silently summarize a change away, nor review a diff that never existed.

Keeps v0.3 additions (`prior_role`, `function_purpose`, `walkthrough`,
`concerns`) and v0.2 rich factual context (behavior_delta, usage_context,
test_coverage, codebase_patterns, alternative_approaches) plus
storyline-level overview (purpose, architectural_context, change_overview,
reading_roadmap).

## What you get

A single self-contained HTML file. Three-pane layout:

- **Left**: Storyline tree with per-storyline overview link and step list.
- **Center**: Three view modes — PR overview / Storyline overview / Step.
  Step view shows full enclosing-function code context with optional
  `function_purpose` rationale and inline `walkthrough` annotations, plus
  supporting definitions.
- **Right**: Collapsible context + analysis sections per step. Section
  labels honor `metadata.locale` (`"en"` default → Prerequisites /
  Summary / Prior Role / ...; `"zh"` → 前情提要 / 简介 / 前世今生 / ...).
  - *Context* (factual): Prerequisites · Prior Role · Behavior Delta ·
    Usage Context (callers, call patterns, implicit deps) · Test Coverage
    · Codebase Patterns · Alternative Approaches
  - *Analysis* (opinion): Summary · Evaluation · Suggestions · Analysis ·
    Concerns (with severity)

Section collapse state persists across step navigation. Default-collapsed
sections (Test coverage, Codebase patterns, Alternatives) keep the right
pane scannable while still being one click away.

Keyboard: `j` next step, `k` previous step, `o` PR overview.

## Try it

```bash
# The demo PR is fabricated, so its "real diff" ships as a fixture patch:
python3 render.py demo/sample_review.json demo/sample_review.html --diff demo/sample_review.patch

# For a real PR, point at the clone (range from metadata commits) …
python3 render.py review.json review.html --repo /path/to/repo
# … or a saved patch:
git diff base..head > pr.patch
python3 render.py review.json review.html --diff pr.patch

open demo/sample_review.html  # or xdg-open / open in browser manually
```

## Files

```
code-review-narrative/
├── README.md
├── SKILL.md                     ← skill definition
├── render.py                    ← inject JSON → HTML; enforces real-diff + coverage gates
├── prompts/
│   ├── schema.md                ← v0.4 JSON schema
│   └── analyze_diff.md          ← v0.4 analysis prompt
├── template/
│   ├── review_source.html       ← default: continuous diff + margin annotations
│   └── review.html              ← swimlane storyline canvas
└── demo/
    ├── sample_review.json       ← v0.4 demo data (includes diff_hunks)
    ├── sample_review.patch      ← fixture "real diff" for the fabricated demo PR
    ├── sample_review.html       ← rendered output (swimlane)
    └── sample_review_source.html ← rendered output (source view)
```

## Status

v0.4. Schema adds top-level `diff_hunks` (every +/- line in the diff);
`render.py` cross-checks it against each step's `code_view` and refuses to
render uncovered reviews. Keeps v0.3 additions (`prior_role`,
`function_purpose`, `walkthrough`, `concerns`).

NOT backward-compatible with v0.3 by default: `render.py` requires
`diff_hunks` to be present, complete, AND verified against the real
diff (`--diff` / `--repo`). Use `--no-diff-check` / `--no-coverage-check`
as escape hatches when rendering legacy or illustration data.
