# code-reading-walkthrough skill

Skill that produces interactive HTML walkthroughs of existing source code,
organized by **logical groups (storylines)** ranked by importance. One JSON
schema (`v0.5-reading`), three render targets — pick the view that fits the
storyline:

| View | Best for | `render.py` flag |
|------|----------|------------------|
| **source** (default) | "read this code with me" — continuous file display with each block as a colored highlight band and a 1–2 sentence margin annotation; click → detail panel | (no flag) |
| **diagram** | state-centric stories — data structures sit at the top of the canvas as persistent glyphs (queue, dict, set…), each block draws read/write arrows | `--view diagram` |
| **swimlane** | flow-inspector layout — phase-tagged block cards in horizontal swim lanes with CALL/CATCH/FINALLY edges | `--view swimlane` |

The reading-oriented sibling of `code-review-narrative`. Storyline
selection and importance scoring are shared with that skill; the per-
storyline UI is different — code with annotations / flow diagram / state
canvas, rather than a linear step walk.

## Two modes

- **Mode A — files given.** User points at files/folder. Agent identifies
  storylines, scores each on four importance lenses, builds a flow
  diagram for the top-N, and renders the rest as summary cards.
- **Mode B — topic given.** User asks "how does X work?". Agent first
  proposes a scope (in-bounds + considered-but-excluded files), gets
  user confirmation, then runs the same pipeline on the confirmed slice.

## What you get

A single self-contained HTML file with a tab per storyline.

**Source view (default)** opens each storyline with a prologue card —
the `mental_model_anchor` (keystone framing) as a hero quote, the
storyline's role / involved modules / data flow as structured context,
and ◀ Previously / Coming up ▶ bridges to adjacent storylines (前情提要
pattern, no schema change). Below the prologue: the source file rendered
continuously with real line numbers, each block as a colored highlight
band over its `line_range`, a 1–2 sentence annotation chip in the right
margin, and a detail panel on click with `What it does` / `Why it's
here` / inputs / outputs / state effects / failure mode / full code.
`←/→` walks the next/prev block in narrative order (follows edges first,
falls back to source order).

**Diagram view** promotes state to first-class: queues drawn as queues,
dicts as `key→value`, composites as schema tables. Each block carries
typed I/O ports and draws SVG arrows to the data structures it
reads/writes. Cross-block CALL / SUCCESS / ERROR / ASYNC edges connect
blocks across columns. Use when "what state does this touch" matters
more than "what's the source say."

**Swimlane view** keeps the original flow-inspector layout: phase-tagged
block cards in horizontal columns, multi-block expansion, slide-in
right dock. Best when the cross-function control flow is the main story.

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
# Source view (default) — continuous code with margin annotations:
python3 render.py demo/kafka_consumer_group.json /tmp/kafka.html
open /tmp/kafka.html

# Diagram view — state-centric canvas:
python3 render.py demo/kafka_consumer_group.json /tmp/kafka_diag.html --view diagram

# Swimlane view — original flow inspector:
python3 render.py demo/kafka_consumer_group.json /tmp/kafka_swim.html --view swimlane

# OR live mode (swimlane only currently) — companion server enables per-block Q&A:
python3 server/live_walkthrough.py /tmp/kafka.html
#   Stop with: python3 server/live_walkthrough.py --stop /tmp/kafka.html
```

`demo/kafka_consumer_group.json` is a fresh-agent run on kafka-python's
consumer coordinator (8 storylines, 40 blocks, 16 data structures) —
useful as a real-world reference output. `demo/toy.json` is a smaller
hand-authored fixture exercising every schema feature.

## Live mode

The static HTML works standalone. Live mode is an opt-in layer: the
page detects the companion `server/live_server.py` via `/__alive` and
enables two features:

- **Per-block Q&A in the dock** — questions go to `POST /ask` with
  `{storyline_id, col_id, block_id, question}`. The server shells out
  to `codex exec` (default) or `claude -p` (`--cli claude`). Answers
  persist in `<basename>.followups.json`.
- **Promote-to-full on summary cards** — the previously-disabled
  "Promote to full" button on summary-only storyline cards now calls
  `POST /promote { storyline_id }`. The server shells out to author a
  full-depth diagram for that storyline (1-3 min typical). The card
  shows a pending spinner during the wait, then flips to the
  full-depth card with a green "Promoted" badge. Result persists in
  `<basename>.promotions.json` and rehydrates on reload. A small
  "↺ Revert to summary" affordance drops the promotion back to the
  original card.

Concurrency is capped (default 2 in-flight CLI calls, shared between
`/ask` and `/promote`; per-block and per-storyline in-flight gates).
The server binds 127.0.0.1 only — both endpoints run the CLI on
user-supplied input, do not expose beyond loopback.

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
│   ├── walkthrough_source.html     ← default: continuous code + margin annotations
│   ├── walkthrough_diagram.html    ← state-centric canvas (data structures as glyphs)
│   └── walkthrough.html            ← original swimlane flow inspector (live-mode Q&A baked in)
├── server/
│   ├── live_server.py              ← live-mode HTTP server (/__alive, /followups, /ask, /promotions, /promote, /promote/revert)
│   ├── live_walkthrough.py         ← wrapper: starts/reuses server, opens browser
│   └── prompts/
│       ├── followup_prompt.md      ← reading-mode follow-up prompt template
│       └── promote_prompt.md       ← promote-to-full prompt (ships schema + Phase 6 rules inline)
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
