# Walkthrough JSON Schema (v0.4-reading)

This is the JSON contract between the analysis prompt and the HTML template
for the `code-reading-walkthrough` skill — the reading-oriented sibling of
`code-review-narrative`'s v0.3 schema.

The schema reuses v0.3's storyline/step/code-view structure (including
`function_purpose` and `walkthrough` annotations) and replaces the
review-specific fields (behavior_delta, evaluation, suggestions, concerns)
with reading-specific ones (mental_model_anchor, invariants,
key_data_structures, design_rationale).

## Top level

```jsonc
{
  "schema_version": "0.4-reading",
  "metadata": { ... },
  "summary":  { ... },
  "scope":    { ... },
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
    "data_flow":       "string | null (high-level prose — input → transformation → output)",
    "diagram":         { "type": "mermaid | ascii | none", "content": "string" }
  },

  "change_overview": "string (multiple paragraphs OK — what this storyline does as a whole, told as a reading)",
  "reading_roadmap": "string (each step's role and how they connect)",

  "steps": [ ... ]
}
```

### Summary-depth storyline minimum

When `depth === "summary"`, only these fields are required:
- `id`, `title`, `kind`, `depth`, `importance_scores`, `summary`, `files_touched`

`steps[]` is omitted (or empty array). `mental_model_anchor`, `purpose`,
`architectural_context`, `change_overview`, `reading_roadmap` are omitted.

The template renders summary-depth storylines as cards with a "Summary only"
pill and a "Promote to full" button (button is signaling-only in v1 — clicking
it does not auto-rerun the agent).

## steps

```jsonc
{
  "id":    "S1.1",
  "title": "string",
  "track": "core | supporting | utility | data | extension",

  "code_view": {
    "primary_changes":       [ FileView ],            // for reading: this is just the code to read; "changes" is a misnomer kept for schema compatibility, all lines have change="unchanged"
    "supporting_definitions":[ FileViewWithReason ]   // 0–3 entries
  },

  "summary": "string (factual: what this step shows, 1–3 sentences)",

  "invariants": [ "string (what must always hold here — pre/post-conditions, structural guarantees, ordering)" ],

  "key_data_structures": [
    {
      "name":  "string (e.g. 'MemTable')",
      "shape": "string (brief — 'sorted skiplist of (key, seq, value) entries')",
      "role":  "string (why the reader needs to keep it in head)"
    }
  ],

  "usage_context": {
    "primary_usage_scenario": "string (narrative: when this code is hit and what's typically happening upstream)",
    "callers": [
      {
        "file":    "string",
        "line":    "int",
        "snippet": "string",
        "context": "string (what this caller is doing, why it reaches into this code)"
      }
    ],
    "call_patterns": [
      "string (e.g. 'always invoked with non-empty input', 'called once per request from the hot path')"
    ],
    "implicit_dependencies": [
      "string (e.g. 'callers assume sorted output', 'relies on side-effect of incrementing seq number')"
    ]
  },

  "codebase_patterns": {
    "similar_code_elsewhere": [
      { "file": "string", "line": "int", "note": "string (how it's analogous)" }
    ],
    "convention_alignment": "string (does this follow established patterns in the codebase?)",
    "deviations":           "string | null"
  },

  "design_rationale": [
    {
      "approach":               "string (description of an alternative the design could have taken)",
      "evidence_kind":          "evidenced | analytical",
      "tradeoff_vs_chosen_design": "string (what's gained / lost vs the chosen design)"
    }
  ],

  "analysis": "string | null (deeper technical reasoning — performance, edge cases, system-wide ripples; null when nothing notable)",

  "prerequisites": [ Prerequisite ]
}
```

### FileView

```jsonc
{
  "file":               "string",
  "language":           "string",
  "context_start_line": "int",
  "context_end_line":   "int",
  "lines": [
    { "line_num": "int", "content": "string", "change": "unchanged" }
  ],

  // Optional — function-level rationale (omit if not function-scoped)
  "function_purpose": {
    "function_name": "string | null",
    "structure":     "single | multi_section",

    // when structure == "single"
    "problem_solved": "string (the problem this function exists to solve)",
    "without_it":     "string (what callers / the system would do if this didn't exist)",

    // when structure == "multi_section"
    "sections": [
      {
        "line_start":     "int",
        "line_end":       "int",
        "section_name":   "string",
        "problem_solved": "string",
        "without_it":     "string"
      }
    ]
  },

  // Optional — code-attached walkthrough annotations (sparse, mental-model-centric)
  "walkthrough": [
    {
      "line_start":  "int",
      "line_end":    "int",
      "chunk_role":  "string (e.g. 'the public entrypoint', 'main logic', 'invariant guard', 'error path')",
      "explanation": "string (substantial paragraph: what this chunk does AND why this way)"
    }
  ]
}
```

For reading walkthroughs all `change` values are `"unchanged"` (the schema
keeps the field for compatibility with the template's rendering code, which
already handles `unchanged` as plain code lines).

#### Walkthrough scope heuristic — reading mode

For each candidate chunk, ask: *"Does understanding this chunk help the
reader build a mental model of how this code works?"* Annotate when yes,
skip when no. Aim for sparse, high-signal annotations — typically 2–4 per
non-trivial function, not line-by-line narration.

#### `function_purpose` design notes

- `problem_solved` = motivation ("the system needs Y; this function provides Y").
- `without_it` = counter-factual ("if this didn't exist, callers would pay X cost / risk Y / be unable to do Z").
- For reading mode these articulate why the function earns its keep —
  exactly what a new reader needs to anchor on.

### FileViewWithReason

Same as FileView (including optional `function_purpose` and `walkthrough`),
plus `why_included: "string"` explaining why this supporting definition is
needed to follow the primary code.

### Prerequisite

```jsonc
{
  "kind":         "prior_step | data_structure | external_concept",
  "reference_id": "string (step ID for prior_step, otherwise free identifier)",
  "summary":      "string (the actual reminder text shown to the reader)"
}
```

## Field rationale

The schema serves a single role for reading mode — **research assistant** —
rather than the dual research-assistant + senior-reviewer role in
`code-review-narrative`. There is no judgement layer:

- `summary` (factual)
- `invariants`, `key_data_structures` (factual mental-model scaffolding)
- `mental_model_anchor` (factual + pedagogical — the picture to remember)
- `usage_context`, `codebase_patterns` (factual context)
- `design_rationale` (factual + analytical — why this design over others, tradeoffs only, no preference)
- `analysis` (deeper technical reasoning, kept for cases where a step's
  implications warrant a paragraph; null when nothing notable)

Empty/null fields render as nothing. Don't pad.

## Always populate vs. populate when relevant

**Always populate** (every full-depth step):
- `id`, `title`, `track`
- `code_view.primary_changes` (≥1 entry)
- `summary`
- `usage_context.primary_usage_scenario`

**Populate when relevant** (may be empty/null):
- `invariants` (substantive code only — null/[] for trivial steps)
- `key_data_structures` (only the nouns the reader must hold in head)
- `code_view.supporting_definitions`
- `FileView.function_purpose` (when function-scoped)
- `FileView.walkthrough` (when annotations aid understanding)
- `usage_context.callers / call_patterns / implicit_dependencies`
- `codebase_patterns`
- `design_rationale`
- `analysis`
- `prerequisites`

A trivial helper-function step may have just `summary` + `code_view`. A
core-algorithm step likely populates everything substantively.

## Importance scoring rubric (mirrored here for self-containedness)

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
- All step `id`s unique within the document
- All `prerequisites[].reference_id` of kind `prior_step` resolve to actual step IDs
- Every full-depth step has non-empty `code_view.primary_changes`
- Every full-depth storyline has non-null `mental_model_anchor`
- Every storyline has `importance_scores.total === sum of four sub-scores`
- Exactly one storyline of any given `id`
- `scope.mode` is `"files"` or `"topic"`
