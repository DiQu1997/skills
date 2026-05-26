# Walkthrough JSON Schema (v0.5-reading)

This is the JSON contract between the analysis prompt and the HTML template
for the `code-reading-walkthrough` skill — the reading-oriented sibling of
`code-review-narrative`.

## What changed from v0.4

v0.5 replaces the linear `steps[]` model with a **flow inspector**: each
full-depth storyline is rendered as a swimlane-style canvas where columns
are functions / lanes, blocks are small chunks within a column (3–10 lines
each), and edges between blocks visualize control flow (calls, catches,
finally branches). Clicking a block expands its code inline; a right-side
dock surfaces what / why / touches / failure-mode for the selected block.

Storyline-level fields (`mental_model_anchor`, `purpose`,
`architectural_context`, `change_overview`) carry over unchanged. The
`code_view` shape, `function_purpose`, and `walkthrough` annotation
structures from v0.4 carry over as building blocks for per-block content.

## Top level

```jsonc
{
  "schema_version": "0.5-reading",
  "metadata":   { ... },
  "summary":    { ... },
  "scope":      { ... },
  "storylines": [ ... ]
}
```

## metadata

```jsonc
{
  "repo":         "string (path or repo name)",
  "commit":       "string (HEAD commit SHA at the time of reading)",
  "target":       "string (Mode A: file/folder paths read; Mode B: the topic question)",
  "title":        "string (display title for the walkthrough)",
  "generated_at": "ISO8601 timestamp"
}
```

`metadata.commit` + `metadata.target` together form the localStorage key
prefix the template uses to persist view state per walkthrough.

## summary

```jsonc
{
  "one_line":    "string (one-sentence pitch for the walkthrough)",
  "description": "string (paragraph: what's covered, who it's for, what the reader will know after)"
}
```

## scope

Records the actual code that was read and why. In Mode B the agent presents
this as a *proposal* to the user before reading; only the confirmed scope
appears in the final JSON.

```jsonc
{
  "mode":  "files | topic",
  "input": "string (raw user input — file paths, folder, or topic question)",
  "discovered_scope": [
    {
      "path":   "string (file path, repo-relative)",
      "reason": "entry-point | type-def | core-flow | dependency | tests | other",
      "note":   "string | null (optional one-line on why this file is in-scope)"
    }
  ],
  "excluded": [
    {
      "path":   "string",
      "reason": "string (why deliberately excluded — 'tests skipped on user request', 'generated code', etc.)"
    }
  ],
  "importance_criteria": "string (paragraph: how N was chosen, what 'important' meant for this run, any user overrides)"
}
```

## storylines

```jsonc
{
  "id":     "S1",
  "title":  "string",
  "kind":   "core_flow | data_model | entry_point | algorithm | extension_point | utility | glue | config | mixed",
  "depth":  "full | summary",

  "importance_scores": {
    "centrality":        1 | 2 | 3,
    "conceptual_weight": 1 | 2 | 3,
    "entry_point":       1 | 2 | 3,
    "novelty":           1 | 2 | 3,
    "total":             "int (sum 4–12, used for ranking)",
    "rationale":         "string | null (one short sentence per non-default sub-score; required when any sub-score is 3 OR total ≤ 5)"
  },

  "summary":       "string (one paragraph for summary-depth, one sentence for full-depth)",
  "files_touched": ["string (paths)"],

  // Full-depth only — omit or set null on summary-depth storylines.
  "mental_model_anchor": "string (one analogy / picture / metaphor, 1–3 sentences — the thing the reader should remember)",

  "purpose": {
    "stated":      "string | null (what existing docs/comments claim about this code's purpose)",
    "evident":     "string (what the code structure actually shows the purpose to be)",
    "discrepancy": "string | null (if stated and evident differ; null if aligned or no docs)"
  },

  "architectural_context": {
    "system_role":     "string (which part of the system this storyline lives in)",
    "involved_modules": [
      { "module": "string", "role_in_storyline": "string" }
    ],
    "data_flow":       "string | null (high-level prose — input → transformation → output)"
  },

  "change_overview": "string (multiple paragraphs OK — what this storyline does as a whole, told as a reading)",

  // The flow inspector — replaces v0.4 `steps[]` + `reading_roadmap`.
  "diagram": { ... }
}
```

### Summary-depth storyline minimum

When `depth === "summary"`, only these fields are required:
- `id`, `title`, `kind`, `depth`, `importance_scores`, `summary`, `files_touched`

`diagram` is omitted. `mental_model_anchor`, `purpose`,
`architectural_context`, `change_overview` are omitted.

The template renders summary-depth storylines as cards with a "Summary only"
pill and a "Promote to full" button.

## diagram

The flow canvas for one full-depth storyline.

```jsonc
{
  // Header shown above the canvas. Optional badge appears when a single
  // file dominates the storyline (e.g. "turn-runner.ts").
  "file_badge":     "string | null",
  "subtitle":       "string | null (e.g. 'four functions, one lifecycle')",

  // Phase legend — LLM picks 3-7 phase categories per storyline. Phases
  // are NOT used for layout (blocks don't align across columns by phase).
  // They're color tags shown on each block and in a top-right legend.
  "phases": [
    {
      "id":    "string (lowercase identifier, e.g. 'guard')",
      "label": "string (display name, e.g. 'Guard')",
      "color": "string (CSS color OR one of the named tokens below)"
    }
  ],

  // Columns — left-to-right, auto-numbered STEP 1, STEP 2... in the UI.
  // Usually one column per function but the LLM can choose other lanes
  // (e.g. 'happy path' / 'error path', 'request' / 'response').
  "cols": [
    {
      "id":          "string (stable identifier referenced by blocks)",
      "function":    "string | null (when col == a function, e.g. 'startTurn'; null for non-function lanes)",
      "label":       "string (display label; defaults to `function` if function is set)",
      "description": "string (one paragraph: what this function/lane does)",
      "blocks":      [ Block ]
    }
  ],

  // Edges between blocks. Drawn as bezier curves on an SVG overlay above
  // the canvas. Omit / empty array for storylines without cross-block flow.
  "edges": [
    {
      "from":  "string (block id)",
      "to":    "string (block id, in any column)",
      "label": "string | null (short, e.g. 'CALL', 'CATCH', 'FINALLY')",
      "style": "solid | dashed",
      "color": "string | null (CSS color; defaults to a neutral tone)"
    }
  ]
}
```

### Named phase color tokens

These pre-defined tokens render to muted, accessible swatches. LLMs should
prefer tokens to literal hex values unless a custom palette is needed.

| Token        | Use for                                  |
|--------------|------------------------------------------|
| `guard`      | Pre-condition checks, validation         |
| `setup`      | Wiring, initialization, allocation       |
| `main`       | Core logic, the function's reason to be  |
| `handoff`    | Calls into other functions / async hand-off |
| `cleanup`    | Resource release, idempotent finalizers  |
| `error`      | Failure paths, catch blocks              |
| `persist`    | Writing to durable storage or external sinks |
| `emit`       | Producing output (events, messages, responses) |

A custom token can be declared inline by providing a hex `color`.

## Block

A small chunk of code within a column (typically 3–10 lines).

```jsonc
{
  "id":         "string (unique within the diagram, e.g. 'B1', 'B2')",
  "phase":      "string (id from diagram.phases)",
  "title":      "string (uppercase short label, e.g. 'GUARD', 'BUILD EXECUTOR')",
  "line_range": "string (display label, e.g. 'L412–414' or 'L419')",

  "one_liner": "string (the rationale shown directly on the block face — 1-2 sentences explaining what this block does AND why)",

  "code_view": FileView,   // shown when the block is expanded (clicked)

  "right_panel": {
    "what_it_does":    "string (paragraph — factual mechanics)",
    "why_its_here":    "string (paragraph — design rationale: why this exists in the flow, what would break without it)",

    "touches": [
      // Chips shown in the right-panel TOUCHES section. Each is a symbol
      // (function, variable, type) this block interacts with. The block id
      // is optional — when present and resolvable, clicking the chip
      // navigates to that block.
      {
        "label":   "string (e.g. 'handleRunFailure', 'AbortController.abort')",
        "kind":    "function | type | variable | external",
        "block":   "string | null (block id if the touch resolves to another block in this diagram)"
      }
    ],

    "failure_mode": [
      // Bullet items shown in the right-panel FAILURE MODE section.
      "string (each item is one bullet — what can go wrong here OR an explicit non-failure claim)"
    ],

    // Optional extra sections — render below the four primary sections if present.
    "invariants":          [ "string" ],
    "key_data_structures": [
      { "name": "string", "shape": "string", "role": "string" }
    ],
    "prerequisites":       [ Prerequisite ]
  }
}
```

### Block sizing guidance

- A block should be one coherent concern. If you can describe it in a
  single `one_liner` without "and", the size is right.
- **Target 3–10 lines per block.** 11–20 acceptable only when
  structurally indivisible (a complete try/catch/finally bracket whose
  arms share state; a switch whose cases collectively form one
  decision). **>20 lines is almost always a sign to split** — see the
  full authoring rules in `prompts/analyze_code.md` Phase 6.
- 1-line blocks are tolerated only when the line is a structurally
  essential hinge (e.g. a `return`, a `throw`, a `break` from a guard);
  prefer folding into the neighbor whose decision produced it.
- Lines within a function don't need to be exhaustively partitioned —
  trivial connective lines can be left ungrouped.
- Blocks within a column appear in **authored order** (top-down).

### FileView

```jsonc
{
  "file":               "string",
  "language":           "string",
  "context_start_line": "int",
  "context_end_line":   "int",
  "lines": [
    { "line_num": "int", "content": "string", "change": "unchanged" }
  ]
}
```

For reading walkthroughs all `change` values are `"unchanged"` (the schema
keeps the field for compatibility with the template's rendering code, which
already handles `unchanged` as plain code lines).

`code_view.lines` should cover exactly the block's `line_range` plus a few
lines of surrounding context (typically ±1–2 lines) so the reader can see
where the block sits in the function. The renderer highlights the block's
own line range; surrounding context lines render dimmer.

v0.4's per-FileView `function_purpose` and `walkthrough[]` annotations
are dropped from v0.5 — block-level `one_liner` + right-panel `what_it_does`
replace them, and function-level purpose lives on the **column**
(`cols[].description`) instead.

### Prerequisite

```jsonc
{
  "kind":         "prior_block | data_structure | external_concept",
  "reference_id": "string (block ID for prior_block, otherwise free identifier)",
  "summary":      "string (the actual reminder text shown to the reader)"
}
```

## Field rationale

The schema serves a single role for reading mode — **research assistant** —
rather than the dual research-assistant + senior-reviewer role in
`code-review-narrative`. There is no judgement layer:

- `one_liner` (block-face): factual + a touch of why
- `right_panel.what_it_does`: factual mechanics
- `right_panel.why_its_here`: design rationale (no preference, just trade-offs)
- `right_panel.touches`: factual cross-references
- `right_panel.failure_mode`: factual edge-case enumeration (or explicit non-failure claim)
- `right_panel.invariants` / `key_data_structures` / `prerequisites`:
  optional mental-model scaffolding when relevant
- Storyline-level `mental_model_anchor`: the picture to remember

Empty/null fields render as nothing. Don't pad.

## Always populate vs. populate when relevant

**Always populate** (every block in a full-depth diagram):
- `id`, `phase`, `title`, `line_range`, `one_liner`
- `code_view` (full `FileView` covering the block's lines)
- `right_panel.what_it_does`
- `right_panel.why_its_here`

**Populate when relevant** (may be empty/null):
- `right_panel.touches` (chips for cross-block / external references)
- `right_panel.failure_mode` (bullets — or explicit "No failure mode" sentence)
- `right_panel.invariants`
- `right_panel.key_data_structures`
- `right_panel.prerequisites`

A trivial guard block may have just `what_it_does` + `why_its_here`. A
core-algorithm block likely populates `touches` + `failure_mode` +
`invariants` substantively.

## Edges — when to author them

Author an edge when there's a control-flow or causal relationship that
spans columns and isn't obvious from reading left-to-right. Examples:

- `from: caller-block, to: callee's first block, label: "CALL"`
- `from: try-block, to: catch-block in another function, label: "CATCH"`
- `from: try-block, to: finally-block (often in a sibling function), label: "FINALLY"`
- `from: event-emit, to: handler's entry block, label: "EMITS"`

Don't author edges for purely linear flow within a column (the visual
stacking already conveys order). Don't author edges for distant or
purely informational relationships — put those in `touches` chips instead.

## Importance scoring rubric

Each lens scored 1–3, summed for `importance_scores.total` (range 4–12).

| Lens | 1 | 2 | 3 |
|---|---|---|---|
| **centrality** | leaf utility, ≤2 callers | moderate fan-in (5–15) | pervasive (15+; every read/write goes through) |
| **conceptual_weight** | trivial / standard idiom | a few new types or one custom invariant | novel data structure / algo / state machine |
| **entry_point** | internal helper | middle layer, several hops in | public API / CLI / `main()` / request handler |
| **novelty** | boilerplate (config, logging) | project-specific glue | the secret sauce — domain algo, custom protocol |

Top-N selection: rank by `total`, break ties by `entry_point > centrality > conceptual_weight > novelty`.
Default `N = clamp(ceil(0.4 * total_storylines), 4, 12)`.
`rationale` required when any sub-score is 3 OR `total ≤ 5`.

## Validation

In addition to JSON-shape validation:
- All block `id`s unique within a diagram
- All `edges[].from` and `edges[].to` reference block IDs that exist in
  the same diagram
- All `right_panel.touches[].block` references resolve when non-null
- All `prerequisites[].reference_id` of kind `prior_block` resolve to actual block IDs
- Every block has non-empty `code_view.lines`
- `code_view.lines[].line_num` falls within (or adjacent to) `block.line_range`
- Every full-depth storyline has non-null `mental_model_anchor` and a `diagram`
- Every storyline has `importance_scores.total === sum of four sub-scores`
- Exactly one storyline of any given `id`
- `scope.mode` is `"files"` or `"topic"`
- Each `block.phase` resolves to one of `diagram.phases[].id`
