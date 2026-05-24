# Review JSON Schema (v0.3)

This is the JSON contract between the analysis prompt and the HTML template.
v0.3 adds `function_purpose` and `walkthrough` to FileView, enabling
inline code-attached annotations and function-level rationale.
(v0.2 added rich context fields and storyline-level context; those are unchanged.)

## Top level

```jsonc
{
  "schema_version": "0.3",
  "metadata": { ... },
  "summary": { ... },
  "storylines": [ ... ]
}
```

## metadata

```jsonc
{
  "repo": "string",
  "base_commit": "string",
  "head_commit": "string",
  "title": "string",
  "generated_at": "ISO8601 timestamp",
  "locale": "en | zh"   // optional, default "en" — controls right-pane section labels only (Prerequisites/Summary/... vs 前情提要/简介/...); content language is free
}
```

## summary

```jsonc
{
  "one_line": "string",
  "description": "string"
}
```

## storylines

```jsonc
{
  "id": "S1",
  "title": "string",
  "kind": "feature | fix | refactor | test | config | doc | mixed",
  "confidence": "high | medium | low",
  "confidence_reasoning": "string",
  "summary": "string (one sentence)",
  "files_touched": ["paths"],

  // NEW in v0.2 — storyline-level context
  "purpose": {
    "stated":      "string | null (what PR description / commit messages claim)",
    "evident":     "string (what the code structure actually shows the change does)",
    "discrepancy": "string | null (if stated and evident differ; null if aligned)"
  },

  "architectural_context": {
    "system_role":     "string (what part of the system this change touches)",
    "involved_modules": [
      { "module": "string", "role_in_storyline": "string" }
    ],
    "data_flow":       "string | null (high-level prose describing flow through this change)",
    "diagram":         { "type": "mermaid | ascii | none", "content": "string" }
  },

  "change_overview":  "string (multiple paragraphs OK — what the storyline does as a whole)",
  "reading_roadmap":  "string (each step's role and how they connect)",

  "steps": [ ... ]
}
```

## steps

```jsonc
{
  "id": "S1.1",
  "title": "string",
  "track": "core | supporting | test | config",

  "code_view": {
    "primary_changes":      [ FileView ],
    "supporting_definitions":[ FileViewWithReason ]
  },

  "summary": "string (factual: what this step does, 1-3 sentences)",

  // NEW in v0.3 — background context for changes that touch existing code
  "prior_role": "string | null (2-4 sentences: what the function/class/data structure being modified existed to do, and why it was shaped this way, BEFORE this change — the floor the reader needs before the delta makes sense; null when the step introduces something brand new)",

  // NEW in v0.2 — rich context fields
  "behavior_delta": {
    "before": "string (how the code behaved before this change, in plain language)",
    "after":  "string (how it behaves after this change)",
    "diff":   "string (the meaningful behavior difference, not just text diff)"
  },

  "usage_context": {
    "primary_usage_scenario": "string (narrative: when this is called and what's typically happening)",
    "callers": [
      {
        "file":    "string",
        "line":    "int",
        "snippet": "string (the actual calling code in context)",
        "context": "string (what this caller is doing, why it calls into the changed code)"
      }
    ],
    "call_patterns": [
      "string (e.g. 'always called with non-empty input', 'invoked from hot path during writes')"
    ],
    "implicit_dependencies": [
      "string (e.g. 'callers assume sorted output', 'relies on side-effect of incrementing seq number')"
    ]
  },

  "test_coverage": {
    "covered_by":      [
      { "file": "string", "test_name": "string", "what_it_tests": "string" }
    ],
    "added_in_this_pr":[
      { "file": "string", "test_name": "string", "what_it_tests": "string" }
    ],
    "not_covered":     [
      "string (use cases / edge cases not currently tested)"
    ]
  },

  "codebase_patterns": {
    "similar_changes_elsewhere": [
      { "file": "string", "line": "int", "note": "string (how it's analogous)" }
    ],
    "convention_alignment": "string (does this change follow established patterns in the codebase?)",
    "deviations":           "string | null (if it deviates from convention, what and why visible from code)"
  },

  "alternative_approaches": [
    {
      "approach":           "string (description of an alternative)",
      "evidence_kind":      "evidenced | analytical",
      "tradeoff_vs_chosen": "string (why this alternative was/wasn't chosen, or what it would trade off)"
    }
  ],

  // EXISTING analytical fields (kept; agent populates when substantive)
  "evaluation":  "string | null (quality assessment, opinion)",
  "suggestions":[ "string (concrete action item for reviewer)" ],
  "analysis":   "string | null (deeper technical reasoning)",

  // NEW in v0.2 — explicit concerns with severity
  "concerns": [
    {
      "concern":  "string (specific issue or risk)",
      "evidence": "string (what in the code/context supports this concern)",
      "severity": "high | medium | low | informational"
    }
  ],

  "prerequisites": [ Prerequisite ]
}
```

### FileView

```jsonc
{
  "file": "string",
  "language": "string",
  "context_start_line": "int",
  "context_end_line":   "int",
  "lines": [
    { "line_num": "int", "content": "string", "change": "added | removed | unchanged" }
  ],

  // NEW in v0.3 — function-level rationale (optional; omit if not function-scoped)
  "function_purpose": {
    "function_name": "string | null",   // e.g. "MemTable::Add"; null if not function-scoped
    "structure":     "single | multi_section",

    // when structure == "single"
    "problem_solved": "string (what problem this function exists to solve — motivation, not description)",
    "without_it":     "string (what would happen / what callers would do if this didn't exist)",

    // when structure == "multi_section" — function does multiple things
    "sections": [
      {
        "line_start":     "int",
        "line_end":       "int",
        "section_name":   "string (e.g. 'input validation', 'main execution loop')",
        "problem_solved": "string",
        "without_it":     "string"
      }
    ]
  },

  // NEW in v0.3 — code-attached walk-through annotations (optional)
  "walkthrough": [
    {
      "line_start":  "int",
      "line_end":    "int",
      "chunk_role":  "string (e.g. 'validation', 'main logic', 'error handling', 'the change')",
      "explanation": "string (substantial paragraph: what this chunk does AND why this way)"
    }
  ]
}
```

#### Walk-through scope heuristic

Walk-through annotations are **change-centric with related unchanged code included**.
For each candidate chunk, the agent asks: "Does understanding this chunk help the
reader understand the change?"

- **Yes** (chunk is a +/- change, OR unchanged code the change interacts with) → annotate
- **No** (surrounding context unrelated to the change's logic) → skip

This makes walk-through **sparse**, not exhaustive. A 30-line function with a 5-line
change might have 2-3 annotations. Avoid both failure modes:
- "Annotate every line" → noise, dilutes attention
- "Annotate only +/- lines" → reader still can't connect change to surrounding logic

#### `function_purpose` design notes

- `problem_solved` is **motivation** ("the system needs Y; this function provides Y").
  `without_it` is **counter-factual** ("if this didn't exist, callers would pay cost /
  risk error / be unable to do thing"). Together they force articulation of non-obvious value.
- For `multi_section`, sections reflect the agent's reading of the function's logical
  structure (not necessarily aligned with diff hunks). E.g. a 200-line function with
  parsing in lines 1-80 and execution in 81-200 gets two sections.
- Use `single` when the function has one coherent purpose. Use `multi_section` for
  long, historically-merged, or multi-concern functions.

### FileViewWithReason

Same as FileView (including optional `function_purpose` and `walkthrough`),
plus `why_included: "string"`.

### Prerequisite

```jsonc
{
  "kind":         "prior_step | data_structure | external_concept",
  "reference_id": "string",
  "summary":      "string"
}
```

## Field rationale

The schema balances two roles the tool plays:

- **Research assistant** (factual context): behavior_delta, usage_context, test_coverage,
  codebase_patterns, alternative_approaches, prerequisites. These deliver context the
  reviewer needs to form independent judgment, especially when unfamiliar with the codebase.

- **Senior reviewer** (analytical opinion): evaluation, suggestions, analysis, concerns.
  These offer substantive opinion when agent has evidence-grounded things to say. Both
  roles coexist; one does not shrink the other.

Empty/null fields render as nothing (not "no concerns" placeholder). Agent populates
only what's substantive for each step.

## What an agent should always populate vs. populate when relevant

**Always populate** (every step):
- id, title, track
- code_view.primary_changes (must have ≥1 entry)
- summary
- behavior_delta
- usage_context (at least primary_usage_scenario)

**Populate when relevant** (may be empty/null):
- prior_role — populate whenever the change modifies an existing function, class, data structure, or comment; null for steps that introduce something brand new (a new file, a new field with no prior counterpart, etc.)
- code_view.supporting_definitions
- FileView.function_purpose (when the code block is function-scoped)
- FileView.walkthrough (when the code is non-trivial and annotations aid understanding)
- test_coverage
- codebase_patterns
- alternative_approaches
- evaluation, suggestions, analysis, concerns
- prerequisites

A comment-fix step may have summary + behavior_delta only. A step introducing a new
core abstraction may populate everything substantively. Don't pad.

## Validation

In addition to JSON-schema validation:
- All step IDs unique within the document
- All `prerequisites[].reference_id` of kind `prior_step` resolve to actual step IDs
- `behavior_delta` is required
