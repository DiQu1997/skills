You are extending an existing code-reading walkthrough. The reader has decided that one of its SUMMARY-only storylines deserves a full **flow inspector** — not just the one-paragraph summary card. Your job: produce that full storyline as a single JSON object.

The server will validate your output against the v0.5-reading schema and slot it into the walkthrough.

## Tool access

You can read files in the repo. The server has set your working directory to the repo root. Start with the files in `files_touched`; expand as needed to follow type definitions, callers, callees, or any other code that helps you build the mental model. Be specific with line numbers — your code_view blocks must contain the **exact** source text.

## Your output

Emit ONE JSON object. **No surrounding prose. No markdown code fences. No `Here's the JSON:` preamble.** The server parses your stdout as JSON directly.

The object is a single STORYLINE conforming to the schema below.

```jsonc
{
  "id":      "<keep the original storyline id verbatim>",
  "title":   "<keep or lightly refine the original title>",
  "kind":    "<keep the original kind>",
  "depth":   "full",
  "promoted": true,
  "importance_scores": { /* keep the original sub-scores + total + rationale */ },

  "summary":       "<one tight sentence — drop everything that the full diagram now says better>",
  "files_touched": [ /* keep, extend if you discovered more in-scope files */ ],

  "mental_model_anchor": "<1-3 sentence vivid analogy / picture / structural shape the reader should walk away with>",

  "purpose": {
    "stated":      "<what comments/docs claim about this code's purpose, or null>",
    "evident":     "<what the code structure actually shows>",
    "discrepancy": "<only if stated and evident differ materially, else null>"
  },

  "architectural_context": {
    "system_role":     "<which part of the system this storyline lives in>",
    "involved_modules": [
      { "module": "<name>", "role_in_storyline": "<role>" }
    ],
    "data_flow":       "<input → transformation → output, or null>"
  },

  "change_overview": "<2-4 paragraphs: the IDEA of this storyline as a whole, why it earns its place, how its pieces hang together>",

  "diagram": {
    "file_badge":     "<dominant filename when one file truly dominates, else null>",
    "subtitle":       "<tight tagline like 'four functions, one lifecycle', else null>",
    "phases":         [ <PhaseDef>, ... ],
    "cols":           [ <Col>, ... ],
    "edges":          [ <Edge>, ... ]
  }
}
```

### PhaseDef

3–7 entries. Color tags applied to blocks; the legend appears in the diagram header.

```jsonc
{
  "id":    "<lowercase identifier>",
  "label": "<display name, e.g. 'Guard'>",
  "color": "<one of the named tokens below, or a CSS hex>"
}
```

Named color tokens (use these when semantics fit — they're pre-styled muted swatches):

| Token | Use for |
|-------|---------|
| `guard` | Pre-condition checks, validation, early returns |
| `setup` | Wiring, initialization, allocation, classification |
| `main` | Core logic — the function's reason to be |
| `handoff` | Calls into other functions / async hand-off |
| `cleanup` | Resource release, idempotent finalizers |
| `error` | Failure paths, catch blocks, retry decisions |
| `persist` | Writing to durable storage / external sinks |
| `emit` | Producing output (events, messages, responses) |

### Col

2–6 cols (cap 6). Default: one col per function in call order. Fallback to logical lanes (`input | core | output`, `happy path | error path`) when functions are too small or too numerous.

```jsonc
{
  "id":          "<stable id, e.g. 'col-startTurn'>",
  "function":    "<function name when col == a function, else null>",
  "label":       "<display label; defaults to `function` if set>",
  "description": "<one paragraph: what this function/lane does>",
  "blocks":      [ <Block>, ... ]
}
```

### Block

```jsonc
{
  "id":         "<unique within the diagram, e.g. 'B1'>",
  "phase":      "<id of one of diagram.phases>",
  "title":      "<UPPERCASE 1-3 word role, e.g. 'GUARD' / 'BUILD EXECUTOR' / 'EMIT'>",
  "line_range": "L<start>–<end>   (en-dash, NOT hyphen; or just 'L<n>' for a single line)",
  "one_liner":  "<1-2 substantial sentences: WHAT this block does AND WHY this way. Reader should learn something from the card face without expanding>",
  "code_view": {
    "file":               "<repo-relative path>",
    "language":           "<typescript|python|go|rust|...>",
    "context_start_line": <int — typically line_range start minus 1-3>,
    "context_end_line":   <int — typically line_range end plus 1-3>,
    "lines": [
      { "line_num": <int>, "content": "<EXACT line text from the source>", "change": "unchanged" }
    ]
  },
  "right_panel": {
    "what_it_does":  "<2-4 factual sentences: mechanics, what fields/calls are involved>",
    "why_its_here":  "<2-4 sentences: design rationale, WHY this exists AT THIS POSITION, what would break without it>",
    "touches":       [ { "label": "<symbol>", "kind": "function|type|variable|external", "block": "<other block id in this diagram, or null>" } ],
    "failure_mode":  [ "<bullet — what can go wrong here, or an explicit non-failure claim>" ],
    "invariants":          [ "<optional, only when substantive>" ],
    "key_data_structures": [ { "name": "?", "shape": "?", "role": "?" } ],
    "prerequisites":       [ { "kind": "prior_block|data_structure|external_concept", "reference_id": "<block_id or free identifier>", "summary": "?" } ]
  }
}
```

### Edge

```jsonc
{
  "from":  "<block id>",
  "to":    "<block id, in any col>",
  "label": "CALL|CATCH|FINALLY|EMIT|CALLBACK|NEXT|RESUMES|...",
  "style": "solid | dashed",
  "color": "#c54343 (red for exceptions) | #7a5cc4 (purple for finally/cleanup) | #777 (default gray)"
}
```

## Block sizing discipline — HARD RULE

The single biggest quality bar.

- **Target 3–10 lines per block.** Most blocks land here.
- **11–20 lines: acceptable only when structurally indivisible.** Examples:
  - A complete `try { … } catch (e) { … } finally { … }` whose three arms share state and reading them apart would lose the bracket.
  - A `switch` whose cases share a local accumulator and the cases are each 1-2 lines (splitting per-case creates slivers; the switch reads as one decision).
  - A small loop body where loop control + body together form one concern.
  - A monolithic state-reset (contiguous assignments that all serve "clear this thing").
- **>20 lines: HARD STOP, don't ship.** Before authoring, run:
  > "If I split this into 2-3 sub-blocks, would any be <3 lines? If so, can I split differently so each piece is ≥3 lines? If still no — is this truly indivisible (above), and can I justify keeping it whole in the one_liner? Only then keep whole. Otherwise split."
- **Never a 1-line block** unless that single line is structurally essential AND the surrounding logic already lives in adjacent blocks. A bare `return value;` or stand-alone `throw new Error(...)` is almost never its own block — fold it into the neighbor whose decision produced it.
- **A 3-5 line block is NOT a sliver.** It's a healthy block. Don't keep a 30-50 line ladder whole because the resulting children would each be 3-5 lines.

A function of 20–40 lines typically yields **4–7 blocks**. Don't undershoot.

## Edge discipline

- Edges are **reading-flow guideposts**, not strict call graphs. Each edge tells the reader: "after this block, your eye should jump here next — and here's why (the label)."
- **Source authenticity**: when the label says `CALL`, the `from` block should be the one whose code actually contains the call site. Don't edge from a block "in the same column" if it's not the actual call. An edge that's true in spirit but originates from the wrong block leaves the reader scratching their head.
- Common edge shapes:
  - `CALL` — `from` contains `funcB(...)`, `to` is the first block of col B
  - `CATCH` — `from` contains `try { ... }`, `to` is the catch handler. Red, solid.
  - `FINALLY` — `from` contains `try { ... }`, `to` is the finally body. Purple, dashed.
  - `EMIT` / `CALLBACK` — `from` fires events, `to` is the consumer
  - `NEXT` / `RESUMES` — conceptual continuation across cols when no literal call but reader needs to follow the thread
- Don't draw edges for: third-party calls (use a `touches` chip with `kind: "external"`), next-block-in-same-col (vertical order implies sequence), shared variable reads (use a `touches` chip).
- **Cap: 3–6 edges per diagram.** More than 6 is unreadable.

## Voice consistency

Other storylines in this walkthrough are listed below (with their `mental_model_anchor` snippets when available). Match their reading voice — same kind of metaphors / framings. Don't introduce a competing framing.

## Final validation (run this before emitting)

- Every `block.id` is unique within this storyline's diagram.
- Every `edges[].from` and `edges[].to` resolves to a block id you defined.
- Every `touches[].block` (when non-null) resolves to a block id you defined.
- Every `prerequisites[].reference_id` of kind `prior_block` resolves.
- `diagram.cols` is non-empty and total blocks ≥ 3.
- `mental_model_anchor` is non-null and not generic ("This handles X" is a description, not an anchor — re-read the code if you can't articulate the anchor crisply).
- `importance_scores.total` equals the sum of the four sub-scores.
- Every `code_view.lines` entry contains EXACT source text (you read the file to get content and line numbers — don't paraphrase).
- No block exceeds 20 lines unless you've explicitly justified it via the structurally-indivisible carve-out above.

---

{{CONTEXT}}

---

Emit only the JSON object. No prose. No markdown fences. The server parses stdout as JSON.
