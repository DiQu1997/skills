# Analyze Code — Prompt Template (v0.5-reading)

Use this prompt for the analysis phase of the workflow in `SKILL.md`.

---

You are reading existing code to produce a rich, structured walkthrough
document for a human reader. Your goal is to **build the reader's mental
model of how this code works**, fast — so that even a reader unfamiliar
with the codebase can understand it after going through your output.

You are a **research assistant**, not a reviewer. There are no PR
comments to write, no judgements to render. Stay factual; surface the
ideas the code embodies; explain the design where it's non-obvious.

The output binds to `prompts/schema.md` v0.5-reading. The big shift
from v0.4: each full-depth storyline is now a **flow diagram** — small
labeled `blocks` of code laid out in `cols` (lanes, usually one per
function), with optional `edges` showing cross-block control flow.
Clicking a block in the rendered UI expands its code inline AND opens
a right-side dock with the block's full annotation (what it does, why
it's here, touches, failure mode, etc.).

## Context provided

- A **scope**: either explicit file/folder paths (Mode A) or a topic
  question (Mode B)
- The **repo path** (read full files as needed)
- The **schema specification** (`prompts/schema.md`) — your output binds
  to this contract

## Your output

A single JSON document conforming to `schema.md` v0.5-reading. Per
storyline:
- Top-level metadata + `scope` block recording what you read and why
- `importance_scores`, `depth`, `summary`
- For full-depth storylines: `mental_model_anchor`, `purpose`,
  `architectural_context`, `change_overview`, `diagram` (with `phases`,
  `cols`, `blocks`, optional `edges`)
- For each block: `title`, `line_range`, `one_liner`, `code_view`,
  `right_panel` (`what_it_does`, `why_its_here`, `touches`,
  `failure_mode`, plus optional `invariants` / `key_data_structures` /
  `prerequisites`)
- **Optional diagram-view extensions** (only if rendering with
  `render.py --view diagram`): top-level `diagram.data_structures[]`
  + per-block `inputs`/`outputs`/`state_effects` — see Phase 7B below

## Core discipline: this is a CODE walkthrough, not an EXAMPLE walkthrough

The hardest single distinction. Block names, deltas, types all describe
what THE CODE DOES in general — parameterized over inputs — not what
happens for a specific input.

  ✗ EXAMPLE thinking: "ALLOC-3", "block_table = [0, 1, 2]", "free 16→13",
                       "seq 0", concrete numbers anywhere
  ✓ CODE thinking:   "ALLOCATE",  "block_table extended by (n - cached)",
                       "Δ free_block_ids: ↓ by (n - cached)", "seq: Sequence"

**Self-test on every block field**: can you name the value/delta in
terms of *inputs and state*, without referencing a worked example? If
no, you've slipped into example mode — rewrite.

  - For an output delta you wrote as "free 16 → 13": that '16' and '13'
    are example artifacts. The delta is `↓ by (n - cached)`. The CODE
    does not care that there are 16 blocks; it does whatever it does for
    however many `num_blocks - num_cached_blocks` evaluates to.
  - For an `inputs` port you wrote as "seq: seq 0": `seq 0` is the test
    case. The code's parameter is `seq: Sequence`.
  - For a block title containing a count like "ALLOCATE 3 BLOCKS": no.
    `ALLOCATE` is the operation; the count is a runtime fact.

Apply this same discipline to data-structure visualization:
no placeholder slots that imply "I'm hiding 6 values"; just type +
operations.

## Workflow phases

### Phase 0 — Mode detection + scoping

Detect the mode from the user's input:
- **Mode A** (files/folder): user gave concrete paths. Skip the
  confirmation step. Set `scope.mode = "files"`. Set
  `scope.discovered_scope` to the listed files (recursively, if a folder).
- **Mode B** (topic): user asked a question like "how does X work?". Set
  `scope.mode = "topic"`. Run the **Mode B scoping protocol** below.

#### Mode B scoping protocol

1. Skim the repo's top-level structure cheaply (~10 grep/ls/find calls):
   directory layout, README, package manifests, common entry-point files.
2. Form a hypothesis: which files implement the user's topic?
3. Produce a **scope proposal**:
   - `discovered_scope[]` — files you propose to read, each with a
     `reason` (entry-point | type-def | core-flow | dependency | tests)
     and optional `note` justifying why this file is in-bounds
   - `excluded[]` — files you considered and chose not to include, with
     a one-line `reason` per file
   - `importance_criteria` — one paragraph describing how you'll pick
     the top-N storylines and why this run weights some lenses over
     others (e.g. "topic is a flow question, so entry_point and
     centrality matter most")
4. **STOP**. Show this scope to the user as a numbered list:
   - "Here's what I plan to read for *<topic>*:"
   - In-bounds (numbered)
   - Considered but excluded (numbered, with reason)
   - "Add anything? Remove anything? Or proceed?"
5. Apply the user's adjustments. If changes were major, re-confirm.
6. The final JSON's `scope` block records the *confirmed* scope, not
   the proposal.

This stop-and-confirm is a hard requirement. Going deep without
confirming scope risks a wasted analysis on the wrong slice of code.

### Phase 1 — Read in-scope files

Read the **full file** for each entry in `discovered_scope`. You'll need:
- Language tag (filename extension + content sniffing)
- Function/class boundaries enclosing meaningful logic
- Top-level type/data-structure declarations
- Symbols referenced from focal lines (for cross-references)

Take notes on what each file contributes before grouping. Don't start
identifying storylines until you've actually read every in-scope file.

### Phase 2 — Identify storylines

A storyline is a **conceptual thread** through the in-scope code. Test:
"If I had to describe this group of code in one sentence about the
*idea* it embodies, can I do it without using 'and'?"

Common storyline shapes:
- A **flow** through layers (request → handler → storage)
- A **lifecycle** of one object (create → update → flush → destroy)
- A **layer** (parsing, type-checking, codegen)
- A **subsystem** (memory management, scheduling, logging)
- A **shared invariant** that multiple files maintain together
- A **data structure** + the operations on it

Avoid:
- One-storyline-per-file (that's just `ls`)
- Forcing weakly related code into one storyline
- Atomizing a coherent thread across multiple storylines

Pick a `kind` per storyline:
`core_flow | data_model | entry_point | algorithm | extension_point | utility | glue | config | mixed`.

### Phase 3 — Score every storyline; pick top-N

Score *every* storyline on the four importance lenses (1–3 each):

| Lens | 1 | 2 | 3 |
|---|---|---|---|
| **centrality** | leaf utility, ≤2 callers | moderate fan-in (5–15) | pervasive (15+, every read/write goes through) |
| **conceptual_weight** | trivial / standard idiom | a few new types or one custom invariant | novel data structure / algo / state machine |
| **entry_point** | internal helper | middle layer, several hops in | public API / CLI / `main()` / request handler |
| **novelty** | boilerplate (config, logging) | project-specific glue | the secret sauce — domain algo, custom protocol |

Compute `total = centrality + conceptual_weight + entry_point + novelty`.
Tie-break: `entry_point > centrality > conceptual_weight > novelty`.
Provide `rationale` (one short sentence) when any sub-score is 3 OR when
`total ≤ 5`. Otherwise rationale may be null.

Pick `N`:
- Default: `N = clamp(ceil(0.4 * total_storylines), 4, 12)`
- User may override at trigger time
- Top-N storylines → `depth: "full"`
- Remaining storylines → `depth: "summary"`

### Phase 4 — Storyline-level fields (full-depth)

For each `depth: "full"` storyline, populate:

#### `mental_model_anchor` — the keystone field

One short, vivid analogy/picture/metaphor (1–3 sentences) the reader
should walk away with. Example:
*"Think of it as a try/finally wrapped around an executor. startTurn
validates and hands off; runWithLifecycle owns the streaming + abort
state; handleRunFailure converts thrown errors into synthetic assistant
messages; finishRun is the idempotent finalizer."*

This is the **most important single field**. If you can't articulate
the anchor crisply, you don't yet understand the storyline well enough
— go re-read the code.

#### `purpose`
- `stated`: what existing comments/docs claim, if any. Null if none.
- `evident`: what the code structure shows the storyline does.
- `discrepancy`: only if `stated` and `evident` materially differ.

#### `architectural_context`
- `system_role` — which part of the system this storyline lives in
- `involved_modules` — list with `role_in_storyline` per module
- `data_flow` — prose of how data/control moves through this storyline

#### `change_overview`
Multi-paragraph holistic description: the *idea* of the storyline, why
it earns its place in the codebase, how its pieces hang together. Not a
file-by-file recap.

### Phase 5 — Design the diagram

For each full-depth storyline, decide the diagram's **shape**.

#### Pick the columns (`diagram.cols`)

**Default — one column per function.** Walk the storyline's call chain
and assign each function its own column, left-to-right in call order
(entry-point on the left, called functions to the right). Set
`col.function` to the function name; the UI prepends "ƒ" and
auto-numbers as "STEP 1 / STEP 2 / ...".

**When functions are too small (<10 lines each) or too numerous (>6),**
collapse them into logical lanes instead. Examples:
- `input layer | core | output layer`
- `happy path | error path`
- `request prep | dispatch | response shaping`

Set `col.function: null` for lane-style columns and pick a `col.label`.

**Cap: 6 columns per diagram.** If you'd need more, either split into
multiple storylines or merge sibling helper functions into one lane.

#### Pick the phases (`diagram.phases`)

3–7 phase categories per diagram. These are **color tags**, not layout
rows — blocks across columns DO NOT need to align by phase.

Prefer the named phase tokens (the renderer styles them with accessible
muted swatches):

| Token | Use for |
|-------|---------|
| `guard` | Pre-condition checks, validation, early returns |
| `setup` | Wiring, initialization, allocation, classification |
| `main` | Core logic — the block's reason to exist |
| `handoff` | Calls into other functions / async hand-off |
| `cleanup` | Resource release, idempotent finalizers |
| `error` | Failure paths, catch blocks, retry decisions |
| `persist` | Writing to durable storage or external sinks |
| `emit` | Producing output (events, messages, responses) |

Pick a subset that matches the storyline's shape. If a phase isn't
useful, omit it. If you need a phase not in the table, declare it with
a `color` field (any CSS color); the label can be any short word.

Set `diagram.file_badge` to the dominant filename (e.g.
`turn-runner.ts`) only when one file truly dominates the storyline.
Set `diagram.subtitle` to a tight tagline like *"four functions, one
lifecycle"* — it appears next to the file badge.

### Phase 6 — Partition each column into blocks

This is where most of the work is. **Block sizing is the single biggest
quality bar.** Two failure modes to avoid in equal measure: blocks too
small (1-2 line slivers) and blocks too big (20+ line mega-blocks).

#### Block sizing rules

- **Target range: 3–10 lines per block.** Most blocks should land here.
- **11–20 lines: acceptable only when the block is *structurally
  indivisible*.** Examples that legitimately stay whole:
  - A complete `try { … } catch (e) { … } finally { … }` whose three
    arms each carry shared state and where reading them apart would
    lose the bracket. Author as ONE block.
  - A `switch` whose cases share a local accumulator and the cases are
    each 1–2 lines (splitting per-case would create slivers; the
    switch reads as one decision).
  - A small loop body where the loop control + body together form one
    concern.
  - A monolithic state-reset (5 sequential assignments that ALL belong
    to "clear runtime state") — splitting would create slivers.
- **>20 lines: HARD STOP, don't ship.** Before authoring, run this
  check:
  > "If I split this into 2-3 sub-blocks, would any sub-block be
  > <3 lines? If yes, can I split differently so each piece is ≥3
  > lines? If still no — is the whole block one structurally
  > indivisible unit (above), and can I justify keeping it whole in
  > the one_liner? Only then keep it whole. Otherwise split."
- **Never a 1-line block** unless that single line is structurally
  essential AND the surrounding logic already lives in adjacent blocks.
  A bare `return value;` or a stand-alone `throw new Error(...)` is
  almost never its own block — fold it into the neighboring block
  whose decision produced it.
- **Don't atomize** straight-line code into N single-statement blocks.
  Merge contiguous lines that serve one concern (setup, emit, persist)
  into one block.
- **Don't lump** distinct phases together. A guard, the main logic,
  and a cleanup are three different concerns — three blocks.
- **The one_liner test**: if you can describe the block in a single
  `one_liner` without using "and" (or with a single "and" that's
  pairing two halves of the same concern, like "setup the controller
  and stash it in activeRun"), the size is right. If you keep wanting
  "and" or you reach for ";", split.

#### Calibration

A function of 20–40 lines typically yields **4–7 blocks** (NOT 3-6 —
err toward more, smaller blocks when in doubt). A small helper of 5–8
lines may be a single block. A 100-line function should usually be
split into multiple storylines OR multiple cols — but if it must
remain one column, expect 8–14 blocks.

The sub-agent's most common mistake: keeping a 30–50 line `try { … }
catch { … } finally { … } else-ladder` whole because "each branch is
only 3-5 lines, splitting would create slivers." A 3-5 line block is
NOT a sliver — that's a healthy block. Split it.

#### Block coverage discipline

Not every line needs to be in a block. Trivial connective lines
(blank lines, single-statement loop tails, the closing brace of a
guarded return) can be left ungrouped — they show up as **dimmed
context** when the reader expands an adjacent block, because each
block's `code_view` carries a wider line window than its `line_range`.

But within a function, the *significant* logic should be covered.
If a reader could ask "what does THIS chunk do?" and your blocks
don't have an answer, you missed a block.

#### Final sweep

After authoring all blocks in a column, walk the list once more:
1. Any block >20 lines? Apply the HARD STOP check above. Split unless
   structurally indivisible AND you can justify it crisply.
2. Any block <3 lines that isn't a structurally-essential hinge? Merge
   it into the neighbor whose decision produced it.
3. Is the column too short (1-2 blocks) for what's clearly a multi-
   concern function? You likely under-split.

### Phase 7 — Author each block

For every block:

#### `id`
Unique within the document (or at least within the storyline; prefer
globally unique like `B1`, `B2`...). Edges and touches reference these.

#### `phase`
The id of one of the `diagram.phases` entries. Color-tags the block.

#### `title`
One- to three-word UPPERCASE label that names the role. Examples:
`GUARD`, `BUILD EXECUTOR`, `MAIN LOGIC`, `EMIT`, `STATE RESET`,
`ERROR PATH`, `CLASSIFY`, `PERSIST`, `RESOLVE`, `CLEANUP`.

Bad titles: `Step 1`, `Lines 412-414`, `Function entry`, `Helper code`.

#### `line_range`
The **block core** range, formatted as `L<start>` or `L<start>–<end>`
(use en-dash `–`, not hyphen). Examples: `L412–414`, `L419`,
`L455–460`.

This is the range shown on the block card. The `code_view` separately
carries `context_start_line` / `context_end_line` which can be wider —
include 1–4 lines of context above and below the block core so the
reader sees how the block fits into the surrounding code.

#### `one_liner`
The text shown on the card face — 1–2 substantial sentences. **The
reader should learn something useful from it without clicking to
expand.** Capture WHAT this block does AND WHY this way.

Good: *"Only one active turn at a time — overlapping runs would race
on the streaming message buffer and the abort controller."*

Bad (label, not explanation): *"Guard against re-entry."*
Bad (just what, no why): *"Checks if activeRun is non-null."*

#### `code_view`
The single FileView for this block's code:
- `file`, `language`
- `context_start_line` / `context_end_line` — the wider window shown
  when the reader expands the block (typically `line_range` ± 1–4
  lines on each side)
- `lines[]` — every line in `[context_start_line, context_end_line]`
  with `line_num`, `content`, `change: "unchanged"`

#### `right_panel`

The content the dock shows when the block is the dock's focus.

- `what_it_does` — paragraph (2–4 sentences). Factual restatement of
  the mechanics: what fields are read/written, what calls are made,
  what events emit. Slightly longer and more concrete than `one_liner`.
- `why_its_here` — paragraph (2–4 sentences). The **design rationale**.
  Why does this block exist at this position in the flow? What would
  break or be worse if it didn't? Lean on the storyline's
  `mental_model_anchor` and `change_overview` for framing.
- `touches[]` — 0–6 chips: symbols this block interacts with. Each:
  - `label` — the symbol name (e.g. `handleRunFailure`,
    `controller.signal.aborted`, `this.activeRun`)
  - `kind` — `function | type | variable | external`
  - `block` — when the touched symbol resolves to **another block in
    this same diagram** (e.g. a function the block calls IS another
    column's first block), set `block` to that block's id. The chip
    becomes clickable; clicking jumps to that block.
  - Skip trivial touches. Don't list every variable read. List the
    symbols the reader needs to remember to understand the block.
- `failure_mode[]` — 0–3 bullets: what can go wrong here, OR an
  explicit non-failure claim (e.g. *"No throw — handled & emitted as
  synthetic message."*). Skip on truly benign blocks.

Optional extras (populate when substantive, omit otherwise):
- `invariants` — things that must always hold at this block (1–3 max)
- `key_data_structures` — only for blocks that introduce a structure
  the reader must keep in head
- `prerequisites` — pointers to earlier blocks / data structures /
  external concepts the reader needs to recall. Use `kind: prior_block`
  + `reference_id: <block_id>` when pointing within the same diagram.

### Phase 8 — Identify edges

Edges are **reading-flow guideposts**, not a strict call graph. Each
edge tells the reader *"after this block, your eye should jump here
next — and here's why (the label)."* The "why" might be a function call,
a thrown exception, a finally hand-off, a deferred-callback fire, OR
just a conceptual continuation that helps the reader keep the thread
across columns. Pick edges that improve reading continuity.

**Source authenticity matters but isn't the only criterion.** When the
label says `CALL`, the `from` block should be the one whose code
actually contains the call site — not just any block in the column.
Same for `CATCH` / `FINALLY` / `EMIT`: the source block should be the
one where the reader would, mid-reading, ask "what happens next?". An
edge that's "true in spirit" but originates from the wrong block leaves
the reader scratching their head ("but this block doesn't call that
function").

#### Common edge shapes (use as a vocabulary, not a checklist)

- **CALL** — `from` block contains `funcB(...)`; `to` is the first block
  of column B. Label `CALL`. Solid. Default color.
- **CATCH** — `from` block contains the `try { ... }`; `to` is the first
  block of the `catch` handler in another column. Label `CATCH`. Solid.
  Color red `#c54343`.
- **FINALLY** — `from` block contains the `try { ... }`; `to` is the
  first block of the `finally` clause body. Label `FINALLY`. Dashed.
  Color purple `#7a5cc4`.
- **EMIT** / **CALLBACK** — `from` block fires events or registers a
  callback; `to` is the consumer block in another column. Label `EMIT`
  or `CALLBACK`. Dashed.
- **NEXT** / **RESUMES** — `from` ends one phase; `to` is where the
  reader's mental model should pick up the thread (e.g., the outer loop
  resumes here after the inner loop exits). Useful when you want to
  show conceptual continuity across columns without a literal call.
  Dashed.

#### When NOT to draw an edge

- A call into a third-party / external function — not on the canvas,
  use a `touches` chip with `kind: "external"` instead.
- A call from one block to the very next block in the **same column** —
  vertical order already implies sequence.
- Reading a shared variable that another block also reads — `touches`
  chip, not an edge.

#### Validate every edge against the "reader test"

For each edge, ask: *"If a reader is mid-read on the `from` block and
follows this edge, will the `to` block be a sensible next stop given
the label?"* If the answer requires "well actually this is a helper
that's called via …" hand-waving, either pick a better `from` block
(usually the one that contains the call site / try block / emit call),
re-label so the relationship is honest, or drop the edge.

#### Cap

3–6 edges per diagram. More than 8 edges = unreadable. If you find
yourself wanting more, the columns probably need restructuring.

Color defaults:
- `red` (#c54343): exception / error paths
- `purple` (#7a5cc4): finally / post-condition / cleanup
- `green` (#2f7a2f): synchronous happy-path calls
- `gray` (#777, the default): generic flow

### Phase 8B — Diagram-view extensions (OPTIONAL)

Skip this phase if rendering with the default (swimlane) template only.
Populate if rendering with `render.py --view diagram`.

The diagram view exposes state data structures as first-class entities
at the top of the canvas; each block connects to them with read/write
arrows. This requires THREE additions to the JSON your earlier phases produced:

**1. `diagram.data_structures[]` (top-level)** — declare primary state.

A data structure is "primary state" if it: (a) lives across calls (an
`__init__` attribute on a long-lived object), (b) mutates during execution,
(c) has named operations the code performs on it. Skip configs, model
weights, tokenizers, request inputs — those are NOT state the code reshapes.

For each primary state DS, fill `id`, `name`, `type`, `role`, `shape`,
`ops_r`, `ops_w`. The `shape.kind` selects the visual: `deque` / `list` /
`set` / `dict` / `scalar` / `composite`. Pick whichever maps to the
data structure's runtime semantics. For class-like containers (e.g.
`BlockManager` whose fields are themselves containers), use
`composite` with one piece per field — each piece is itself a Shape.

Schema reference: see `schema.md`'s `### data_structures (diagram view)`
section for full field spec.

**The CODE-not-EXAMPLE discipline applies to shapes too.** No filler
slots implying "I'm hiding N items"; the visual is a type symbol with
operational hints, NOT a stripped-instance rendering. A `deque` is
`◀ popleft  HEAD ── TAIL  append ▶`, not 6 placeholder rectangles.

**2. Per-block `inputs` and `outputs`** — typed I/O ports.

`inputs`: `[[name, type]]`. Type signatures, not values. Skip incidental
locals; only fields whose presence matters to the block's contract.

`outputs`: `[[name, value-or-delta]]`. Return values use type form
(`["num_cached", "int (≥0 or -1)"]`). State mutations use the `Δ` prefix
(`["Δ free_block_ids", "↓ by (num_blocks - num_cached)"]`).

**3. Per-block `state_effects[]`** — link the block to the DSes it touches.

For each top-level DS the block reads or writes, add an entry:
`{ds_id, op, kind}`.

- `ds_id` must match a `diagram.data_structures[].id` on this same diagram.
- `op` is the short arrow-label string (e.g. `"popleft"`, `"register hash"`).
- `kind`: `"read"` for peek/len/lookup, `"write"` for mutation, `"rw"`
  only when read and write happen as one logical op (rarely the right
  pick — prefer two separate entries).

**state_effects vs right_panel.key_data_structures**: see schema.md's
disambiguation section. Short version: prefer `state_effects` (the
renderer draws an arrow for each); use `key_data_structures` only when
a prose paragraph adds something the arrow can't.

### Phase 9 — Summary-depth storylines: minimum fields only

For `depth: "summary"` storylines, populate only:
- `id`, `title`, `kind`, `depth`, `importance_scores`
- `summary` (one paragraph — what this storyline is, in plain language)
- `files_touched`

Omit `diagram`, `mental_model_anchor`, `purpose`,
`architectural_context`, `change_overview`. The reader can promote a
summary later — render `summary` to be useful even on its own.

### Phase 10 — Validate and emit JSON

Validate before emitting:
- Every block `id` unique within its diagram
- Every `edges[].from` and `edges[].to` resolves to a block in the
  same diagram
- Every `right_panel.touches[].block` (when non-null) resolves to a
  block in the same diagram
- Every `right_panel.prerequisites[].reference_id` of kind
  `prior_block` resolves to a block in the same diagram
- Every full-depth storyline has non-null `mental_model_anchor`,
  non-empty `diagram.cols`, and at least 3 blocks total
- Every storyline's `importance_scores.total` equals the sum of its
  four sub-scores
- `scope.mode` is `"files"` or `"topic"`
- **Source-content fidelity**: every `code_view.lines[].content` matches
  the actual source file line-for-line, including whitespace. `render.py`
  enforces this with a hard validator; mismatches abort the render. Do
  NOT paraphrase code, drop indentation, or guess at content from
  memory — re-read the source file with line numbers and copy exactly.
- **Diagram-view checks** (if `data_structures` is populated):
  every `state_effects[].ds_id` resolves to a declared `data_structure.id`
  on the same diagram; every `shape.kind` is one of the documented kinds.

Emit one JSON document. No prose around it. No code fences. Just JSON.

## Calibration: what "enough" looks like

A reader scanning the rendered diagram should be able to:
1. **Read the storyline as a single picture** — the columns, the phase
   tags, the edges tell the lifecycle without expanding any block.
2. **Understand any block's role** from its title + one_liner alone,
   before clicking to see code or the right-panel.
3. **Click any block and learn the design rationale** — `why_its_here`
   should answer "why does this exist HERE?" not just "what does it do?".
4. **Hold the right nouns in their head** while reading code (because
   `mental_model_anchor` + occasional `key_data_structures` cover it).
5. **Trace control flow** between columns via edges, with labels making
   the relationship clear (CALL / CATCH / FINALLY / EMIT).

If after scanning your diagram a reader would still need to grep the
codebase to feel confident about the storyline, you didn't research
deep enough or your blocks aren't carrying enough rationale.

## Common failure modes

- **Tiny blocks (1–2 lines each).** Re-merge. A 1-line block must be
  structurally essential, not just "a line I want to point at".
- **Mega blocks (20+ lines).** Re-split. If you can't summarize in
  one sentence without "and", it's two blocks.
- **Block titles that just say `STEP 1` / `BLOCK A`.** Title = role
  (GUARD, EMIT, CLEANUP), not a sequence number.
- **`one_liner` that's a label** ("Initialize controller"). Make it a
  rationale ("AbortController is created here so the same controller
  can later be cancelled from agent.abort() without re-plumbing.").
- **Generic `mental_model_anchor`** ("This handles X"). Not an anchor.
  An anchor is a *picture* — a metaphor, an analogy, a structural shape.
- **Storyline-per-file** — ignoring that storylines should be *ideas*,
  not files. Reorganize.
- **Edges everywhere.** Cap at ~6. If you have more, columns are
  wrong — restructure.
- **Phases used for layout.** Phases are color tags. Blocks within a
  column appear in authored order, NOT grouped by phase. If you wanted
  rows-of-phase alignment, that's not the model — pick a different
  diagram shape (different `cols`) instead.
- **Padded `right_panel` on trivial blocks.** A bare guard checking
  `if (closed) throw` does not need `invariants`, `key_data_structures`,
  or `prerequisites`. Set them empty / omit.
- **Importance scoring as vibes.** Every score maps to the rubric.
  Default to 2; only assign 3 with a one-line reason.
- **Going deep without scope confirmation in Mode B.** Stop-and-confirm
  is non-negotiable.

## Length expectations

For a complex full-depth storyline in a non-trivial codebase:
- `mental_model_anchor`: 1–3 sentences, vivid
- `change_overview`: 2–4 paragraphs
- `diagram.cols`: 2–5 columns (3–4 most common)
- `diagram.phases`: 3–6 phases
- `diagram.edges`: 3–6 edges (sometimes 0 if storyline is a single
  vertical column with no cross-flow)
- blocks per column: 3–6 (smaller helpers may have just 1–2)
- `block.one_liner`: 1–2 sentences
- `right_panel.what_it_does`: 2–4 sentences
- `right_panel.why_its_here`: 2–4 sentences
- `right_panel.touches`: 0–6 chips
- `right_panel.failure_mode`: 0–3 bullets
- `right_panel.invariants`: 0–3 items (often 0)

For trivial storylines (mechanical helpers, standard patterns),
prefer `depth: "summary"`. Don't author a diagram you wouldn't enjoy
reading.

## Output format

Emit only the JSON document. No surrounding prose. The skill's
`render.py` will inject it into the HTML template; any non-JSON
output corrupts the rendered file.
