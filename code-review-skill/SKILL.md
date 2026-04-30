---
name: code-review-narrative
description: Analyzes a git diff or PR and produces an interactive HTML review document organized by logical groups (storylines) rather than alphabetically by file. Each storyline contains step-by-step changes with full code context, prerequisite reminders, factual context (behavior delta, callers, test coverage, codebase patterns, alternative approaches), and analytical commentary (summary/evaluation/suggestions/analysis). Use when a user wants help reviewing a PR, commit range, or git diff in a structured way that surfaces logical units of change rather than file-by-file. Triggers include "review this PR", "analyze this diff", "help me review", or being given a diff and asked to walk through it.
---

# code-review-narrative skill (v0.2)

Schema v0.2 — see `prompts/schema.md` for full spec. Adds rich factual context per step (behavior delta, callers, test coverage, codebase patterns, alternatives) and storyline-level overview (purpose, architectural context, change overview, reading roadmap).


## Purpose

This skill takes a git diff (representing a PR, commit range, or change set) and produces a self-contained interactive HTML review document. The document organizes changes by **logical groups (storylines)** rather than by filename, helping reviewers follow the *intent* of a change instead of fighting alphabetical file order.

Output is a single HTML file the user can open in any browser. No build tools, no dependencies, no servers.

## When to use

Trigger this skill when the user:
- Asks to "review this PR" or "review this diff"
- Provides a git diff and asks for analysis or walkthrough
- Mentions wanting to "go through" or "walk through" a change set
- Has a mid-sized change (3-15 files, ~50-1000 lines) — too small doesn't benefit from grouping; too large strains the analysis

Do NOT trigger this skill for:
- Single-file or single-line changes (file-by-file is fine for these)
- Reading existing code (use code-narrative-trace skill instead)
- Generating commit messages or PR descriptions
- Writing code

## Inputs

The skill needs:
1. **The diff** — either a git diff text the user paste, or a commit range in the user's local repo (e.g. `main..feature-branch`), or a path to a diff file
2. **Repo context** — the local clone path, so the skill can read surrounding code for "supporting definitions" in each step
3. **Review intent** (optional) — a sentence about what the reviewer cares about (e.g. "focus on correctness", "I'm worried about the locking changes")

If any input is unclear, ask the user before proceeding.

## Workflow

The skill executes these steps:

### 1. Read the diff fully

Read the entire diff into memory. For each changed file, parse hunks into structured form:
- file path
- old_start, old_count, new_start, new_count for each hunk
- the actual changed lines with +/- markers

### 2. Read repo context as needed

For each changed file, also read the *full* file from the working tree (post-change state). This is needed to:
- Determine the language for syntax tagging
- Find function/class boundaries enclosing each hunk (so the code view can show the full enclosing function, not just the +/- lines)
- Identify symbols referenced in the change to populate `supporting_definitions`

### 3. Identify logical groups (storylines)

Read the diff as a whole and identify coherent groups of changes. A storyline is:
- A coherent unit of intent (one feature, one fix, one refactor, one test addition)
- Possibly spanning multiple files
- Possibly multiple steps in sequence within itself

Heuristics for grouping:
- Changes touching related code paths (same call chain, same data structure)
- Changes that obviously enable each other (defining a thing, then using it)
- Test files for a change usually belong to the same storyline as the change being tested
- Truly unrelated changes in the same PR (drive-by fixes, bundled refactors) get their own storyline, marked with appropriate confidence

For each storyline, decide:
- `kind`: feature | fix | refactor | test | config | doc | mixed
- `confidence`: high | medium | low — how cohesive is this grouping?
- `confidence_reasoning`: why this confidence level

### 4. Order steps within each storyline

Steps within a storyline should be in *logical reading order*, which is usually:
- Definitions before uses (introduce a concept, then use it)
- Core changes before supporting (mainline before tests, before config)
- Earlier dependencies before later

This may differ from chronological commit order or file-alphabetical order. That's the point.

### 5. For each step, build the code view

For each step:

**primary_changes**: the actual diff for this step. Include enough surrounding unchanged lines to show the full enclosing function or natural code block. Don't show only the +/- lines — that's GitHub's failure mode that we're correcting. Aim for showing 5-30 lines of context surrounding each hunk, capturing the full enclosing function when reasonable.

**supporting_definitions**: code that the reader needs to fully understand `primary_changes`, but isn't itself changed. Examples:
- Definition of a function being called by changed lines
- Field declaration referenced by an updated method
- Constant being used

Limit to 0-3 supporting definitions per step. More is noise.

For both, fill in `lines` with `{line_num, content, change}` for each line, where `change` is `added | removed | unchanged`.

### 6. For each step, write the analytical content

Each step gets four pieces of meta-content:

**summary** (factual, required): One or two sentences describing what this step does. Should be uncontroversial — describes the change without judgment.

**evaluation** (opinion, optional): Quality assessment. Is the change well-implemented? Are there code smells? Is the abstraction right? May be null if no notable evaluation.

**suggestions** (action items, optional): Concrete things the reviewer should check or consider. Each item is one bullet. Examples: "Verify the new constant is consistent with similar constants nearby", "This loop runs in O(n) — confirm it's not on a hot path", "Consider adding a test for the empty-input case". May be empty array.

**analysis** (deep technical, optional): Deeper reasoning about implications — performance, edge cases, interaction with other systems, alternative approaches. May be null. This is where you raise concerns the reviewer might miss without thinking carefully.

The separation matters for **trust calibration**: readers can take `summary` at face value but should treat `evaluation`/`suggestions`/`analysis` as analytical claims to be checked.

Write in the language the user is using (English or 中文). The template renders Chinese section labels (前情提要/简介/评价/建议/分析) but content can be in either language.

### 7. Identify prerequisites

For each step, identify whether the reader needs to recall something from earlier to understand the current step. Common cases:
- A symbol introduced in an earlier step is now being used
- A data structure modified in an earlier step is now relied on
- A pre-existing concept (not from this PR) is critical to understanding

For each prerequisite, populate:
- `kind`: prior_step | data_structure | external_concept
- `reference_id`: the step ID being referenced (for `prior_step`) or any identifier
- `summary`: the actual reminder text shown to the reviewer

Aim for prerequisites to be informative without being patronizing. Don't explain things the reviewer obviously knows. Do remind them of specifics they might have read 5 minutes ago and forgotten.

### 8. Validate and emit JSON

Construct the final JSON conforming to the schema in `prompts/schema.md`. Validate that:
- Every `id` is unique
- Every `prerequisite.reference_id` of kind `prior_step` resolves to an actual step
- Every `code_view.primary_changes` has at least one entry (otherwise the step has no code, which is suspicious)
- All required fields are present

### 9. Render to HTML

Read `template/review.html`. Find the placeholder `/*REVIEW_DATA_PLACEHOLDER*/` and replace it with the JSON (formatted as a JS object literal — `JSON.stringify(data, null, 2)` is fine).

Write the final HTML to a path the user specified, or to `review.html` in the current directory.

Tell the user where the file was written and suggest they open it in a browser.

## Constraints

- **No fabrication**: don't invent author intent. If a change's purpose is unclear, mark the storyline confidence as `medium` or `low` and explain in `confidence_reasoning`.
- **Trust calibration**: be honest in `evaluation` and `analysis`. If something looks wrong, say so. If something looks fine, don't pad with vague concerns.
- **Conciseness**: each `summary` should be 1-3 sentences. `evaluation` and `analysis` can be longer but should still be focused. The reviewer will read this in flow; long-windedness wastes their attention.
- **Single output file**: produce one HTML file. Don't split into multiple files; don't reference external resources; don't require a server.
- **Schema compliance**: the JSON must conform to `prompts/schema.md` exactly. The template depends on this contract.

## Failure modes to avoid

- **Over-grouping**: forcing weakly related changes into one storyline. If you're stretching to find a connection, they probably belong in separate storylines. Use medium/low confidence groups for genuinely mixed PRs.
- **Under-grouping**: making every file its own storyline. That's just GitHub PR view. The value of this tool is logical grouping; if you can't find logical groups, the PR may be too small for this skill (tell the user).
- **Generic suggestions**: "Add tests" / "Consider edge cases" without specifics. If you can't make a concrete suggestion, leave the suggestions array empty.
- **Padded analysis**: if a step is mechanical (rename, comment fix), don't manufacture deep analysis. Set `analysis: null` and move on.
- **Ignoring the diff**: don't review based on commit messages or PR description alone. Read the actual diff.

## Files in this skill

- `SKILL.md` — this file
- `prompts/analyze_diff.md` — detailed prompt for the analysis phase (used during step 3-7)
- `prompts/schema.md` — full JSON schema specification
- `template/review.html` — the HTML/CSS/JS template
- `render.py` — helper script to inject JSON into template
- `demo/sample_review.json` — reference example of valid JSON
- `demo/sample_review.html` — reference example of rendered output
