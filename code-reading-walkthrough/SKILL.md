---
name: code-reading-walkthrough
description: Reads existing source code and produces an interactive HTML walkthrough document organized by logical groups (storylines) rather than alphabetically by file. Each full-depth storyline is rendered as a flow inspector — a canvas of phase-tagged code blocks laid out in columns (one per function by default), with cross-block control-flow edges (CALL / CATCH / FINALLY / EMIT). Clicking a block expands its code inline and opens a right-side dock with rationale (what it does, why it's here, touches, failure mode). Two modes — Mode A (user gives files/folder; agent identifies storylines and selects the top-N most important to walk through deeply, the rest as summary cards) and Mode B (user gives a topic question like "how does X work"; agent first proposes a scope, gets user confirmation, then runs the same pipeline). Use when a user wants to understand an unfamiliar codebase by reading rather than reviewing changes. Triggers include "explain this code", "walk me through", "how does X work", "help me read this", or being given a folder and asked to make sense of it.
---

# code-reading-walkthrough skill (v0.5-reading)

Schema v0.5-reading — see `prompts/schema.md` for full spec.

This skill is the reading-oriented sibling of `code-review-narrative`.
It shares storyline grouping and importance scoring with that skill,
but the per-storyline UI is fundamentally different: instead of a
linear step-by-step walk, each full-depth storyline becomes a **flow
inspector** — a left-to-right canvas of phase-tagged code blocks with
optional cross-block control-flow edges.

## Purpose

Take a body of existing code (a few files, a folder, or the slice of a
repo that answers a topic question) and produce a self-contained
interactive HTML walkthrough. The document organizes code by **logical
groups (storylines)** rather than by filename, ranks them by
importance, builds a flow diagram for the top-N, and surfaces the rest
as summary cards the reader can ask the agent to promote later.

Output is a single HTML file the user can open in any browser. No build
tools, no dependencies, no servers. View state (which storyline, which
blocks expanded, which block is focused) persists in localStorage
per-walkthrough so the reader can close the tab and resume later.

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
diagram. The remaining storylines render as summary cards.

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

The full analysis prompt lives in `prompts/analyze_code.md`. Summary:

### Phase 0: Mode detection + scoping
- Mode A: scope = user-listed files; skip confirmation.
- Mode B: produce scope proposal, **stop**, ask user to confirm, then proceed.

### Phase 1: Read in-scope files
Read the *full* file for each entry in `discovered_scope`. Function/class
boundaries and referenced symbols are inputs to storyline grouping and
block authoring.

### Phase 2: Identify storylines
A storyline is a *conceptual thread* — a coherent idea the code embodies.
Common shapes: a flow through layers, a lifecycle, a layer, a subsystem,
a shared invariant, a data structure with operations. One-storyline-per-
file is the wrong signal — that's just `ls`.

### Phase 3: Score every storyline; pick top-N
Rubric below. Top-N → `depth: "full"`. Rest → `depth: "summary"`.

### Phase 4: Storyline-level fields (full-depth only)
`mental_model_anchor` (the keystone field — vivid analogy, 1–3 sentences),
`purpose` (stated / evident / discrepancy), `architectural_context`
(system role, involved modules, data flow), `change_overview`.

### Phase 5: Design the diagram
For each full-depth storyline:
- **Pick cols**: default = one per function in call order. Fallback to
  logical lanes (`happy path | error path`, `input | core | output`)
  when functions are too small/numerous. Cap 6 columns.
- **Pick phases**: 3–7 color tags from the named palette
  (`guard / setup / main / handoff / cleanup / error / persist / emit`)
  or custom; phases are NOT layout rows, just color tags.
- Set `diagram.file_badge` and `diagram.subtitle` for the header.

### Phase 6: Partition each column into blocks
**The single biggest quality bar.** Block sizing:
- 3–15 lines per block (5–10 sweet spot)
- Never a 1-line block unless structurally essential
- Don't atomize straight-line code; don't lump distinct phases
- A 20–40 line function → typically 3–6 blocks

### Phase 7: Author each block
- `title` UPPERCASE role label (GUARD / BUILD EXECUTOR / EMIT / ...)
- `line_range` the block CORE (the wider context window is in `code_view`)
- `one_liner` substantial rationale shown on the card face (1–2 sentences,
  reader should learn something WITHOUT clicking to expand)
- `code_view` with context_start_line/context_end_line ± 1–4 lines
  around the block core
- `right_panel`:
  - `what_it_does` — paragraph, factual mechanics (2–4 sentences)
  - `why_its_here` — paragraph, design rationale (2–4 sentences)
  - `touches[]` — 0–6 chips (label, kind, optional block-id linking)
  - `failure_mode[]` — 0–3 bullets
  - Optional: `invariants`, `key_data_structures`, `prerequisites`

### Phase 8: Identify edges
Draw cross-block control flow that matters: `CALL`, `CATCH`, `FINALLY`,
`EMIT`, `CALLBACK`. Cap ~6 edges per diagram. Solid for sync flow,
dashed for error/finally/async. Color conventions: red for exceptions,
purple for finally/cleanup, green for sync happy-path.

### Phase 9: Summary-depth storylines
Just `id`, `title`, `kind`, `depth`, `importance_scores`, `summary`,
`files_touched`. Render as cards with a "Promote to full" affordance.

### Phase 10: Validate and emit JSON
- Every block `id` unique within its diagram
- Every `edges[].from` / `edges[].to` / `touches[].block` resolves
- Every `prerequisites[].reference_id` of kind `prior_block` resolves
- Every full-depth storyline has non-null `mental_model_anchor` and
  non-empty diagram (≥3 blocks)
- `importance_scores.total` equals sum of four sub-scores

### Phase 11: Render to HTML
```bash
python3 render.py walkthrough.json output.html
```
The renderer finds the `/*WALKTHROUGH_DATA_PLACEHOLDER*/` in
`template/walkthrough.html`, injects the JSON via `json.dumps()` with
`</` → `<\/` escaping, and writes the output.

### Phase 12: Open in live mode (default behavior)

Immediately after rendering, run:

```bash
python3 server/live_walkthrough.py <walkthrough.html>
```

This wrapper detects whether a companion `live_server.py` is already
serving this HTML on a port in `8765–8775`. If yes, it just opens the
browser. If no, it starts the server in the background (detached,
survives this script exiting) and then opens the browser. The server
enables a per-block Q&A section in the right-side dock; answers are
written to a sidecar `<basename>.followups.json` next to the HTML
(keyed by `storyline_id/col_id/block_id`) and persist across runs.

Tell the user the URL (e.g. `http://127.0.0.1:8765/`) and that the
"live" badge in the top-right confirms live mode is active. If they
prefer a static-only file with no Q&A, they can skip this step and
open the HTML directly via `file://`.

To stop the server later: `python3 server/live_walkthrough.py --stop`
(kills all live-walkthrough servers) or `--stop <html>` (just one).

The server defaults to `codex exec` (use `--cli claude` for `claude -p`
instead). The chosen CLI must be on PATH; if neither is available, fall
back to telling the user to open the HTML directly.

The server caps concurrent `/ask` subprocesses (default 2) and rejects
duplicate questions for the same block with a 429. It binds 127.0.0.1
only and **must not** be exposed beyond loopback — `/ask` runs the CLI
on user-supplied input, so external exposure is a cost/exec risk.

The follow-up prompt template at `server/prompts/followup_prompt.md`
instructs the CLI to ground answers in the established
`mental_model_anchor` / invariants / key_data_structures rather than
introducing a competing framing — reading-mode questions are about
building understanding, not evaluating changes.

## Importance scoring rubric

Each lens scored 1–3, summed for `total` (range 4–12).

| Lens | 1 | 2 | 3 |
|---|---|---|---|
| **centrality** | leaf utility, ≤2 callers | moderate fan-in (5–15) | pervasive (15+, every read/write goes through) |
| **conceptual_weight** | trivial / standard idiom | a few new types or one custom invariant | novel data structure / algo / state machine |
| **entry_point** | internal helper | middle layer, several hops in | public API / CLI / `main()` / request handler |
| **novelty** | boilerplate (config, logging) | project-specific glue | the secret sauce — domain algo, custom protocol |

`importance_scores.rationale` is required when any sub-score is 3 OR
when `total ≤ 5`. Score every storyline (full and summary).

## Constraints

- **No fabrication**: don't invent design intent. If a storyline's
  `mental_model_anchor` doesn't come crisp, you don't yet understand
  the storyline — re-read the code.
- **Block sizing discipline**: 1-line blocks are almost always a smell.
  3–15 lines per block, 5–10 sweet spot.
- **Show importance scores**: every storyline carries `importance_scores`
  in the JSON; the UI renders them as badges.
- **Single output file**: one self-contained HTML, no external resources.
- **Schema compliance**: the JSON must conform to `prompts/schema.md`
  exactly. The template depends on this contract.

## Failure modes to avoid

- **Tiny blocks (1–2 lines).** Re-merge or fold into an adjacent block.
- **Mega blocks (20+ lines).** Re-split. If you can't summarize in
  one sentence without "and", it's two blocks.
- **Generic mental_model_anchor.** Must be a *picture* — metaphor,
  analogy, structural shape — not a description.
- **Storyline-per-file**: storylines should be *ideas*, not files.
- **Edges everywhere**: cap ~6. More usually means cols are wrong.
- **Phases used for layout**: phases are color tags, NOT rows.
- **Importance scoring as vibes**: every score maps to the rubric.
- **Going deep without scope confirmation in Mode B**: non-negotiable.
- **Padded right_panel on trivial blocks**: a bare guard does not need
  invariants / key_data_structures / prerequisites.

## Files in this skill

- `SKILL.md` — this file
- `README.md` — short user-facing intro
- `prompts/schema.md` — full JSON schema specification (v0.5-reading)
- `prompts/analyze_code.md` — detailed analysis prompt (used during phases 0–10)
- `template/walkthrough.html` — single-file HTML/CSS/JS template (flow inspector + live-mode Q&A baked in)
- `render.py` — helper script: injects JSON into template
- `server/live_server.py` — companion HTTP server (`/__alive`, `/followups`, `/ask` → `codex exec` by default, or `claude -p` via `--cli claude`); per-block in-flight gate + global concurrency cap; falls back to extracting `WALKTHROUGH_DATA` from the HTML if no sibling JSON is found
- `server/live_walkthrough.py` — wrapper that starts (or reuses) `live_server.py` in the background and opens the browser; supports `--status` and `--stop`
- `server/prompts/followup_prompt.md` — prompt template fed to the CLI for each follow-up question
- `demo/toy.json` — hand-authored fixture exercising every schema feature; useful for template/server smoke-testing, not a real codebase walkthrough

## Relationship to sibling skills

- **`code-review-narrative`** (sibling): same architecture spirit, but for
  git diffs. If the user gave a diff or asked to review a PR, use that.
- **`repo-deep-research`**: produces a comprehensive lecture-style
  markdown report via multi-agent orchestration. Use when the user
  wants depth and breadth in markdown form — this skill is for
  interactive HTML walkthroughs at a chosen scope.
- **`llm-index-skill`** / **`repo-processor`**: produce navigation
  indexes for *AI agents*, not human-readable walkthroughs.
