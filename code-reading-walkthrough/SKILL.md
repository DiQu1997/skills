---
name: code-reading-walkthrough
description: Reads existing source code and produces an interactive HTML walkthrough document organized by logical groups (storylines) rather than alphabetically by file. Two modes — Mode A (user gives files/folder; agent identifies storylines and selects the top-N most important to walk through deeply, with the rest as summary cards) and Mode B (user gives a topic question like "how does X work"; agent first proposes a scope, gets user confirmation, then runs the same pipeline). Each full-depth storyline contains step-by-step explanations with full code context, line-attached walkthrough annotations, function-level rationale (problem_solved / without_it), invariants, key data structures, prerequisites, and the design rationale for non-obvious choices. Use when a user wants to understand an unfamiliar codebase by reading rather than reviewing changes. Triggers include "explain this code", "walk me through", "how does X work", "help me read this", or being given a folder and asked to make sense of it.
---

# code-reading-walkthrough skill (v0.4-reading)

Schema v0.4-reading — see `prompts/schema.md` for full spec.

This skill is the reading-oriented sibling of `code-review-narrative`. It
reuses that skill's storyline / step / walkthrough-annotation structure
(including v0.3 `function_purpose` and `walkthrough[]`) and replaces the
review-specific fields with reading-oriented ones (mental_model_anchor,
invariants, key_data_structures, design_rationale).

## Purpose

Take a body of existing code (a few files, a folder, or the slice of a
repo that answers a topic question) and produce a self-contained
interactive HTML walkthrough. The document organizes code by **logical
groups (storylines)** rather than by filename, ranks them by
importance, walks the top-N deeply, and surfaces the rest as summary
cards the reader can ask the agent to promote later.

Output is a single HTML file the user can open in any browser. No build
tools, no dependencies, no servers. View state (which step, which
sections collapsed) persists in localStorage per-walkthrough so the
reader can close the tab and resume later.

## When to use

Trigger this skill when the user:
- Asks to "explain this code" / "walk me through" / "help me read this"
- Asks "how does X work" about a known codebase
- Provides a folder or list of files and asks for an overview / understanding
- Wants to understand an unfamiliar codebase by reading rather than reviewing

Do NOT trigger this skill for:
- PR or diff review (use `code-review-narrative` instead)
- AI-agent navigation indexes (use `llm-index-skill` for LLMINDEX.md, or `repo-processor` for ai_doc.md)
- A comprehensive lecture-style markdown report (use `repo-deep-research`)
- Quick file lookups, bug fixing, code generation

## The two modes

### Mode A — files given

The user names files or a folder. The agent reads them, identifies
storylines, scores each on four importance lenses (centrality,
conceptual_weight, entry_point, novelty), and picks the top-N (default
`N = clamp(ceil(0.4 * total_storylines), 4, 12)`) for full-depth
walkthrough. The remaining storylines render as summary cards.

No scope confirmation step — the user gave concrete paths.

### Mode B — topic given

The user asks a topic question like *"how does memory management work?"*
The agent must first *find* the relevant code:

1. Skim the repo (~10 grep/ls/find calls): top-level structure, README,
   package manifests, common entry points
2. Form a scope proposal — a list of in-bounds files (each tagged with a
   reason: entry-point / type-def / core-flow / dependency / tests) and
   a list of considered-but-excluded files (each with a reason)
3. **Stop and present the scope to the user.** Don't go deep until the
   user confirms or adjusts.
4. After confirmation, run the same pipeline as Mode A on the confirmed
   scope.

The stop-and-confirm step is non-negotiable. Going deep on the wrong
slice of code wastes 15+ minutes; one extra round trip prevents it.

## Inputs

The skill needs:
1. **The scope** — either explicit file/folder paths (Mode A) or a topic
   question (Mode B)
2. **Repo path** — the local clone, so the skill can read source and
   grep for callers
3. **Optional reading intent** — what the reader cares about (e.g.
   "focus on the write path", "I want to understand the threading model")

If any input is unclear, ask before proceeding. If the user says "in
this repo, walk me through X", treat as Mode B unless the user names
specific files.

## Workflow

The full prompt is in `prompts/analyze_code.md`. In summary:

### Phase 0: Mode detection + scoping
- Mode A: scope = user-listed files; skip confirmation
- Mode B: produce scope proposal, **stop**, ask user to confirm, then proceed

### Phase 1: Read in-scope files
Read the *full* file for each entry in `discovered_scope`. You'll need
the full content to find function/class boundaries, identify referenced
symbols, and produce code views with proper context.

### Phase 2: Identify storylines
A storyline is a *conceptual thread* — a coherent idea the code
embodies. Common shapes: a flow through layers, a lifecycle of one
object, a layer (parsing / type-checking / codegen), a subsystem, a
shared invariant, a data structure with operations.

Test: "If I had to describe this group of code in one sentence about
the *idea* it embodies, can I do it without 'and'?"

### Phase 3: Score every storyline; pick top-N
Score each storyline 1–3 on the four lenses (rubric below). Compute
total. Pick top-N by total, tiebreaker `entry_point > centrality >
conceptual_weight > novelty`. Top-N → `depth: "full"`. Rest → `depth: "summary"`.

### Phase 4–9: For full-depth storylines
- Phase 4: storyline-level fields (`mental_model_anchor`, `purpose`,
  `architectural_context`, `change_overview`, `reading_roadmap`)
- Phase 5: order steps logically (definitions before uses)
- Phase 6: build `code_view` (whole enclosing function/block)
- Phase 7: per-step `walkthrough[]`, `function_purpose`, `invariants`,
  `key_data_structures`
- Phase 8: `usage_context`, `codebase_patterns`, `design_rationale`,
  `prerequisites`
- Phase 9: trivia → `analysis: null`; substantive concerns → paragraph

### Phase 10: Summary-depth storylines
Just `id`, `title`, `kind`, `depth`, `importance_scores`, `summary`,
`files_touched`. Render as cards with a "Promote to full" affordance.

### Phase 11: Validate and emit JSON
- Step IDs unique
- All `prior_step` reference IDs resolve
- Every full-depth step has `code_view.primary_changes` non-empty
- Every full-depth storyline has non-null `mental_model_anchor`
- `importance_scores.total` equals sum of four sub-scores

### Phase 12: Render to HTML
```bash
python3 render.py walkthrough.json output.html
```
The renderer finds the `/*WALKTHROUGH_DATA_PLACEHOLDER*/` in
`template/walkthrough.html`, injects the JSON via `json.dumps()` with
`</` → `<\/` escaping, and writes the output. Tell the user where it
went and suggest opening it in a browser.

## Importance scoring rubric

Each lens scored 1–3, summed for `total` (range 4–12).

| Lens | 1 | 2 | 3 |
|---|---|---|---|
| **centrality** | leaf utility, ≤2 callers | moderate fan-in (5–15) | pervasive (15+, every read/write goes through) |
| **conceptual_weight** | trivial / standard idiom | a few new types or one custom invariant | novel data structure / algo / state machine |
| **entry_point** | internal helper | middle layer, several hops in | public API / CLI / `main()` / request handler |
| **novelty** | boilerplate (config, logging) | project-specific glue | the secret sauce — domain algo, custom protocol |

`importance_scores.rationale` is required when any sub-score is 3 OR
when `total ≤ 5`. Score every storyline (full and summary) so the user
can see and challenge the picks.

## Constraints

- **No fabrication**: don't invent design intent. If a storyline's
  `mental_model_anchor` doesn't come crisp, you don't yet understand
  the storyline — re-read the code, don't generate vague prose.
- **Sparse walkthroughs**: line-attached annotations are mental-model
  anchors, not narration. A 30-line function gets 2–4 annotations.
- **Show importance scores**: every storyline carries `importance_scores`
  in the JSON; the UI renders them as badges so the reader can see and
  challenge the agent's picks.
- **Single output file**: one self-contained HTML, no external resources.
- **Schema compliance**: the JSON must conform to `prompts/schema.md`
  exactly. The template depends on this contract.

## Failure modes to avoid

- **Generic mental_model_anchor**: "This handles X" is a description,
  not an anchor. The anchor must be a *picture* the reader can hold.
- **Storyline-per-file**: storylines should be *ideas*, not files. If
  every storyline maps 1:1 to a file, you've under-grouped.
- **Walkthrough as line-by-line narration**: if every line is annotated,
  attention is diluted. The heuristic is "does this build the reader's
  mental model?"
- **Importance scoring as vibes**: every score must map to the rubric.
  When in doubt, default to 2 and only assign 3 with a one-line reason.
- **Going deep without scope confirmation in Mode B**: Phase 0's stop-
  and-confirm is non-negotiable. Skipping it risks wasting a long
  analysis on the wrong slice.
- **Padded analysis on trivial code**: getter functions don't need
  invariants, design_rationale, or analysis. Set them empty/null.
- **Missing the why**: `design_rationale` answers "why this and not the
  obvious other thing?" — without it, the reader is stuck wondering.

## Files in this skill

- `SKILL.md` — this file
- `README.md` — short user-facing intro
- `prompts/schema.md` — full JSON schema specification
- `prompts/analyze_code.md` — detailed analysis prompt (used during phases 0–11)
- `template/walkthrough.html` — single-file HTML/CSS/JS template
- `render.py` — helper script: injects JSON into template
- `demo/sample_walkthrough.json` — reference example (Mode A on this skill's sibling)
- `demo/sample_walkthrough.html` — rendered demo

## Relationship to sibling skills

- **`code-review-narrative`** (sibling): same architecture, but for git
  diffs. If the user gave a diff or asked to review a PR, use that one.
- **`repo-deep-research`**: produces a comprehensive lecture-style
  markdown report via multi-agent orchestration. Use when the user
  wants depth and breadth in markdown form — this skill is for
  interactive HTML walkthroughs at a chosen scope.
- **`llm-index-skill`** / **`repo-processor`**: produce navigation
  indexes for *AI agents*, not human-readable walkthroughs.
