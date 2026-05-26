# code-reading-walkthrough skill

Skill that produces interactive HTML walkthroughs of existing source code,
organized by **logical groups (storylines)** ranked by importance. Each
full-depth storyline becomes an interactive **flow inspector** — a
left-to-right canvas of small phase-tagged code blocks the reader clicks
to expand inline. The rest land as summary cards the reader can promote
later.

The reading-oriented sibling of `code-review-narrative`. Storyline
selection and importance scoring are shared with that skill; the per-
storyline UI is different — flow diagram + clickable blocks + slide-in
right dock, rather than a linear step walk.

## Two modes

- **Mode A — files given.** User points at files/folder. Agent identifies
  storylines, scores each on four importance lenses, builds a flow
  diagram for the top-N, and renders the rest as summary cards.
- **Mode B — topic given.** User asks "how does X work?". Agent first
  proposes a scope (in-bounds + considered-but-excluded files), gets
  user confirmation, then runs the same pipeline on the confirmed slice.

## What you get

A single self-contained HTML file with two views:

- **Reading overview**: storyline cards with importance badges, scope
  panel showing what was read and why.
- **Flow inspector (per storyline)**: a top header (file badge +
  subtitle + color legend), a canvas of left-to-right columns
  (auto-numbered STEP 1 / STEP 2 / ... — one column per function by
  default), each column a vertical stack of phase-tagged block cards.
  Click any block to expand its code inline. Click any block to also
  open the right-side dock with `What it does` / `Why it's here` /
  `Touches` (chips) / `Failure mode` (bullets), plus optional
  `Invariants` / `Key data structures` / `Prerequisites` / per-block
  Q&A. SVG overlay draws control-flow edges between blocks
  (CALL / CATCH / FINALLY / EMIT) with labeled bezier curves.

Multiple blocks can be expanded simultaneously — each toggles
independently. The dock follows the most recently expanded block; its
× button closes the dock without collapsing anything.

State (view, expanded blocks, focused block) persists in
localStorage per-walkthrough.

Keyboard: `j` next block, `k` previous block, `o` reading overview,
`Esc` cascades (close dock → collapse all → back to overview).

## Importance scoring (1–3 each, sum 4–12)

| Lens | 1 | 2 | 3 |
|---|---|---|---|
| **centrality** | leaf utility, ≤2 callers | moderate fan-in (5–15) | pervasive (15+) |
| **conceptual_weight** | trivial / standard idiom | a few new types or one custom invariant | novel data structure / algo / state machine |
| **entry_point** | internal helper | middle layer, several hops in | public API / CLI / `main()` / request handler |
| **novelty** | boilerplate (config, logging) | project-specific glue | the secret sauce |

Top-N = `clamp(ceil(0.4 * total_storylines), 4, 12)`. Tiebreaker:
`entry_point > centrality > conceptual_weight > novelty`. Scores are
stored in the JSON and rendered in the UI.

## Try it

```bash
python3 render.py demo/toy.json /tmp/toy.html

# Static — open the file directly, no Q&A:
open /tmp/toy.html

# OR live — companion server enables a per-block Q&A section:
python3 server/live_walkthrough.py /tmp/toy.html
# Detached server stays up after this script exits. Stop with:
#   python3 server/live_walkthrough.py --stop /tmp/toy.html
```

`demo/toy.json` is a hand-authored fixture (a fake `turn-runner.ts`
lifecycle) that exercises every schema feature — phases, cols, blocks,
edges, full right-panel content. It's a developer-facing example, not
a real codebase walkthrough.

## Live mode

The static HTML works standalone. Live mode is an opt-in layer: the
page detects the companion `server/live_server.py` via `/__alive` and
reveals a per-block chat input in the dock. Questions go to
`POST /ask` with `{storyline_id, col_id, block_id, question}` and the
server shells out to `codex exec` (default) or `claude -p`
(`--cli claude`). Answers persist in a sidecar
`<basename>.followups.json` keyed by `storyline_id/col_id/block_id`
and re-load on revisit. Concurrency is capped (default 2 in-flight
calls; per-block in-flight gate); the server binds 127.0.0.1 only —
do not expose beyond loopback.

## Files

```
code-reading-walkthrough/
├── README.md                       ← this file
├── SKILL.md                        ← skill definition + workflow
├── render.py                       ← inject JSON → HTML
├── prompts/
│   ├── schema.md                   ← v0.5-reading JSON schema
│   └── analyze_code.md             ← analysis prompt (diagram-centric)
├── template/
│   └── walkthrough.html            ← single-file HTML/CSS/JS template (live-mode Q&A baked in)
├── server/
│   ├── live_server.py              ← Q&A HTTP server (/__alive, /followups, /ask)
│   ├── live_walkthrough.py         ← wrapper: starts/reuses server, opens browser
│   └── prompts/
│       └── followup_prompt.md      ← reading-mode follow-up prompt template
└── demo/
    └── toy.json                    ← hand-authored v0.5 fixture
```

## Status

v0.5-reading. Replaces v0.4's linear step model with a flow inspector
(phases / cols / blocks / edges). Storyline grouping, importance
scoring, Mode A/B scoping, live-mode Q&A, and localStorage persistence
all carry over from v0.4. The schema does not preserve v0.4's
`steps[]` / `walkthrough[]` / `function_purpose` — v0.4 walkthrough
JSON files need re-analysis to render.
