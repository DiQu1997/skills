# Review JSON Schema (v0.2)

This is the JSON contract between the analysis prompt and the HTML template.
v0.2 adds rich context fields (behavior delta, usage context, test coverage,
codebase patterns, alternative approaches) at the step level, and architectural
+ purpose context at the storyline level.

## Top level

```jsonc
{
  "schema_version": "0.2",
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
  "generated_at": "ISO8601 timestamp"
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
  ]
}
```

### FileViewWithReason

Same as FileView, plus `why_included: "string"`.

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
- code_view.supporting_definitions
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
