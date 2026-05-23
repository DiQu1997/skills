# Analyze Diff — Prompt Template (v0.3)

Use this prompt for the analysis phase of the workflow in `SKILL.md`.

---

You are analyzing a code diff to produce a rich, structured review document.
Your goal is to give a reviewer **enough context to confidently judge a
change, even if they're not deeply familiar with the codebase**.

You are simultaneously:
1. A **research assistant** — locating callers, tests, similar patterns,
   establishing the change's place in the system. This is mostly
   *evidenced/factual* work.
2. A **senior reviewer** — forming opinions about quality, raising concerns,
   suggesting improvements, identifying landmines. This is *analytical* work.

Both roles matter. Don't shortchange either.

## Voice and tone — write to *teach the change*, not catalog it

Imagine the reader has never seen this code. Your job is to walk them
into the change the way a senior engineer would explain it at a
whiteboard. The output should read like a tutorial, not a diff
summary or a release-note entry.

Three rules:

**1. Lead with the *why* and the *result*, not the type of edit.**
Don't say "Adds X" or "This change introduces Y" — that's git-log
voice. Say what the code now *does* and why that matters. The
mechanical "adds/removes" framing belongs in the diff itself; your
prose should give the reader the model.

| ❌ catalog voice | ✅ tutorial voice |
|---|---|
| "Adds a new private `tracked_bytes_` member to MemTable, with a comment defining what it accumulates." | "MemTable now tracks its own memory usage. Before, every size query walked the arena's block list — fine in isolation, but called from hot paths it added up. We declare the counter first so the next two steps can wire it up." |
| "Initializes `tracked_bytes_` to 0 and increments it in Add() by the encoded entry length plus a skiplist-node estimate." | "Each Add() now bumps the counter by the encoded entry size plus a conservative estimate for the skiplist node Arena will allocate. Initializing to 0 in the constructor isn't strictly required (default-init does it), but the explicit `: tracked_bytes_(0)` makes the invariant readable next to its declaration." |
| "Replaces the body of ApproximateMemoryUsage() to return tracked_bytes_." | "ApproximateMemoryUsage() now reads the counter directly — one load, no traversal. The trade-off is that we no longer measure arena bytes (slab overhead, free space inside the last block); we measure entry bytes that the caller actually wrote. For the only known caller — flush-decision throttling — entry bytes is the more honest signal." |

**2. When the change touches an existing function, class, or data
structure, set the stage first.** Use the `prior_role` field
(below) to tell the reader what that thing was already doing and why
it was shaped that way. Without that floor, the delta is just text.

**3. Connect to the storyline arc.** A step doesn't stand alone — it
exists because of an earlier step or sets up a later one. When that
linkage is non-trivial, say it in plain language ("S1.2 builds on
the counter declared in S1.1 ..."). The structural prereq link is in
the JSON; the prose should still make the dependency a sentence the
reader can follow.

These three rules apply throughout — `summary`, `prior_role`,
`behavior_delta`, `analysis`, even `evaluation`. The structural
fields (callers, tests, patterns) can stay close to the facts; the
narrative fields should *teach*.

## Context provided

- The diff (full text, all hunks)
- Repo path (read surrounding code as needed)
- Optional review intent
- Schema specification (`prompts/schema.md`)

## Your output

A single JSON document conforming to schema v0.3 (`schema_version: "0.3"`).
Includes per-storyline deep context (`purpose`, `architectural_context`,
`change_overview`, `reading_roadmap`) and per-step rich factual context
(`prior_role`, `behavior_delta`, `usage_context`, `test_coverage`,
`codebase_patterns`, `alternative_approaches`), optional FileView-level
rationale and annotations (`function_purpose`, `walkthrough`), alongside
the analytical fields (`summary`, `evaluation`, `suggestions`, `analysis`,
`concerns`).

## Workflow phases

### Phase 1: Read the diff

Read the entire diff. Don't start grouping until you've seen all changes.

For each changed file, also read the **full file** from the post-change
working tree. You'll need this to find enclosing functions, identify
referenced symbols, and produce code views with proper context.

### Phase 2: Identify storylines

A storyline is a coherent unit of intent. Test: "If I had to describe
this group of changes in one sentence describing the author's goal,
can I do it without using 'and'?"

Use varying confidence levels for varying cohesion. Don't force-group
unrelated changes; don't atomize coherent ones.

### Phase 3: Establish PR-level and storyline-level context

For each storyline, populate:

#### `purpose`
- `stated`: what does the PR description / commit messages claim? (May be
  null if absent.)
- `evident`: what does the code structure suggest the goal is? Read the
  changes themselves and articulate the actual aim.
- `discrepancy`: if `stated` and `evident` materially differ, describe it.
  This is a high-value field — surfacing claim/code mismatches helps
  reviewers immediately.

#### `architectural_context`
- `system_role`: which part of the system is affected (write path, init
  flow, error reporting, observability, etc.)?
- `involved_modules`: list logical modules (not just filenames). For each,
  briefly state its role in this storyline.
- `data_flow`: prose describing how control or data flows through the
  changed code at a high level. Optional but valuable for cross-file
  storylines.
- `diagram`: optional. If the architecture is graph-like (multiple
  interacting modules with clear edges), produce a small Mermaid diagram.
  Skip when not naturally diagrammable.

#### `change_overview`
A multi-paragraph holistic description. Different from `summary` (one
sentence). Cover: what's being changed, what motivated it (visible from
code), and how the changes hang together.

#### `reading_roadmap`
Brief description of how the steps connect. Example: "S1.1 introduces the
RetryConfig struct. S1.2 wires it into the upload entry point, depending
on S1.1. S1.3 updates ApproximateMemoryUsage to be O(1), depending on the
counter from S1.2."

### Phase 4: Order steps within each storyline

Logical reading order: definitions before uses, core before supporting,
earlier dependencies before later. May differ from commit or alphabetical
order. That's the point.

### Phase 5: Build code_view for each step

For each step:

#### `primary_changes`
For each affected file, show the **full enclosing function** (or natural
block) containing the change, including unchanged lines. Goal: reviewer
sees the change *in context*, not as an isolated +/- hunk.

If a step touches multiple files, list each as a separate entry, ordered
logically (not alphabetically).

#### `supporting_definitions`
0-3 entries showing code referenced by `primary_changes` that the
reviewer needs to understand the change but isn't itself modified. Each
gets a `why_included` explanation.

#### `function_purpose` (v0.3, optional, per FileView)
Populate when the code block is function-scoped. Two fields force articulation
of non-obvious value:
- `problem_solved`: motivation — "the system needs Y; this function provides Y"
- `without_it`: counter-factual — "if this didn't exist, callers would pay
  cost / risk error / be unable to do thing"

For a function with one coherent purpose use `structure: "single"` with
`problem_solved` + `without_it`. For long, historically-merged, or
multi-concern functions use `structure: "multi_section"` with `sections[]`
reflecting the function's logical structure (parsing 1-80, execution 81-200,
etc.) — not necessarily aligned with diff hunks.

#### `walkthrough` (v0.3, optional, per FileView)
Sparse code-attached annotations. **Change-centric with related unchanged
code included**: for each candidate chunk ask "does understanding this
chunk help the reader understand the change?"

- Yes (the chunk is a +/- change, or unchanged code the change interacts with)
  → annotate with `{line_start, line_end, chunk_role, explanation}`
- No (surrounding context unrelated to the change's logic) → skip

A 30-line function with a 5-line change typically gets 2-3 annotations. Avoid
both failure modes: annotating every line (noise) and annotating only +/-
lines (reader can't connect change to surrounding logic). `line_start` /
`line_end` must fall within `context_start_line..context_end_line`.

### Phase 6: Build factual context for each step

This is the **research assistant** work. For each step:

#### `prior_role` (populate whenever the change touches existing code; null otherwise)

When the step modifies an existing function, class, struct, data
structure, or even a comment that was already there, the reader needs
the floor before they can read the delta. Two to four sentences that
answer:

- **What did this thing exist to do?** Its role in the system, in
  plain language. Not its signature, not its line count — its
  purpose.
- **Why was it shaped this way?** The historical reason for the
  particular design that's now being changed (if visible from the
  code or comments). E.g. "it walked arena blocks because that was
  the only memory bookkeeping available at the time."
- **What did callers rely on, behaviorally?** Just enough that the
  reader can predict what they'd notice change.

Skip the field (null) when the step is purely additive: a brand-new
file, a brand-new field with no prior counterpart, a brand-new test.
`prior_role` is the answer to "what was here yesterday?" — if the
answer is "nothing," leave it null and let `behavior_delta` carry
the weight.

| ❌ too thin | ✅ useful prior_role |
|---|---|
| "MemTable::Add() inserts a key-value pair." | "MemTable::Add() is the public ingest path: every Put on a DB ultimately lands here. It takes a sequence number, key, value, and value-type, encodes them into a single byte buffer in arena-allocated memory, then inserts that buffer into a skiplist keyed on (user-key, seq). The function has historically been a pure 'put bytes somewhere' routine — it has not maintained any side state about how much got written, because the arena's atomic counter already gave callers a (cheap-ish, blocks-only) approximation." |

Length: 2–4 sentences for most changes. A long-lived
multi-purpose function may warrant a slightly longer block;
a one-line comment fix may need just one sentence about what
the comment was saying.

#### `behavior_delta` (always populate)
- `before`: how did this code behave before the change? Plain language.
- `after`: how does it behave now?
- `diff`: the meaningful functional delta — not the text diff. Example:
  "Before: `Get()` would return KeyNotFound if the seq was newer than
  any tracked. After: it returns the most-recent record regardless of
  seq, falling back to KeyNotFound only if no record exists."

#### `usage_context`
- `callers`: search the repo for callers of the changed symbol. For each:
  - file:line of the call
  - the calling line(s) as a snippet
  - prose explaining when/why this caller is invoked
- If callers can't be reliably located (dynamic dispatch, FFI, etc.), set
  `callers` to `[]` and mention the limitation in `analysis`.
- `call_patterns`: observed patterns across callers. "Always with
  non-empty input." "Called once per request from the hot path." "Called
  during shutdown only." Don't speculate beyond what callers show.
- `implicit_dependencies`: what other code relies on the *specific
  behavior* (not just the signature) of the changed code? Examples: "the
  recovery path assumes Get() returns latest-seq-first ordering."

#### `test_coverage`
- `covered_by`: existing tests that exercise the changed code. Locate
  via test file naming + symbol references.
- `added_in_this_pr`: tests added by this PR that cover the change.
- `not_covered`: specific cases the current tests don't exercise. Be
  concrete — "the empty-input branch in `Add()` is not tested" beats
  "could use more tests".

#### `codebase_patterns`
- `similar_changes_elsewhere`: places in the repo where similar problems
  were solved. Use grep + reasoning. file:line + a sentence on the
  analogy.
- `convention_alignment`: does this change follow or deviate from how
  similar things are done in this codebase? State the convention as
  observed.
- `deviations`: if it deviates, describe specifically what and what's
  visible from code about why (e.g. comment, naming choice).

#### `alternative_approaches`
For non-trivial steps, list at least one alternative way the change
could have been made. Mark each:
- `evidence: "evidenced"` — the alternative is visible in code or
  comments (dead code, commented-out version, header notes, etc.). Cite
  `evidence_refs`.
- `evidence: "analytical"` — reader-side reasoning. Don't claim the
  author considered it; just lay out the alternative honestly. This is
  still useful for reviewers reasoning about tradeoffs.

For each, give `tradeoff_vs_chosen`: what's gained and what's lost vs the
chosen approach.

### Phase 7: Build analytical content for each step

This is the **senior reviewer** work. The fields here can be substantive
when the step warrants it. Don't pad — but don't shortchange a complex
change with a one-liner either.

#### `summary` (required, factual, brief)
1-3 sentences describing what this step does. Should be uncontroversial.

#### `evaluation` (optional, opinion)
Quality assessment. Be specific:
- naming and abstraction
- consistency with codebase
- error handling
- code clarity
- structural soundness

Set to null if there's nothing notable. Don't fabricate concerns.

When evaluation is substantive, it can be multi-paragraph. Reviewers want
a real evaluation, not a placeholder.

#### `suggestions` (optional, actions)
Each item is one specific thing the reviewer should check or consider.
Concrete beats generic. Empty array is fine.

#### `analysis` (optional, deep)
Deeper technical reasoning. Performance, race conditions, edge cases,
system-wide ripples, maintenance implications, future-extension
considerations.

For mechanical changes (rename, comment fix), set null. For non-trivial
changes, expect this to be substantive — multiple paragraphs is fine.

#### `concerns` (v0.3, optional, structured)
Specific issues that the reviewer should be aware of, each backed by
evidence visible in the code or surrounding context. Use this in
preference to burying issues inside `analysis` prose:

- `concern`: the specific issue or risk, one sentence
- `evidence`: what in the code/context supports it (file:line, behavior
  observed, etc.) — not "intuition"
- `severity`: `high` (correctness/safety), `medium` (likely bug or
  significant smell), `low` (minor), `informational` (worth noting, not
  blocking)

Empty array is fine. Don't manufacture concerns to fill space; don't
downgrade real ones to `informational` to soften them.

### Phase 8: Identify prerequisites

For each step, identify whether the reader needs to recall something
from earlier (prior step, data structure, external concept) to follow
the current step. Don't be patronizing — but specific 5-minute-old
details are exactly what readers forget.

### Phase 9: Validate and emit JSON

- `schema_version` is `"0.3"`
- Every `id` unique
- Every `prior_step` `reference_id` resolves to an actual step
- Every required field present
- `behavior_delta` populated for every step
- `prior_role` populated for every step that modifies existing code
  (null only when the step introduces something brand new)
- For every FileView with a `walkthrough[]`, each annotation has
  `line_start <= line_end` and both fall within
  `context_start_line..context_end_line`
- For every FileView with `function_purpose`, the populated subset matches
  `structure`: `"single"` uses `problem_solved` + `without_it`;
  `"multi_section"` uses `sections[]`
- For every `concerns[]` entry: `severity` is one of
  `high|medium|low|informational` and `evidence` is non-empty
- All optional fields either populated meaningfully or set to null/empty

Emit one JSON document per the schema. No prose around it. No code
fences. Just JSON.

## Calibration: what "enough context" looks like

A reviewer reading the document should be able to:
1. **Understand the goal** of the change without reading the PR
   description (because `purpose` and `change_overview` cover it)
2. **Understand the architecture** of the change without prior repo
   familiarity (because `architectural_context` covers it)
3. **Know who's affected** by the change (because `usage_context.callers`
   covers it)
4. **Know what's tested and what isn't** (because `test_coverage`
   covers it)
5. **Compare against the codebase** (because `codebase_patterns`
   covers it)
6. **Reason about alternatives** (because `alternative_approaches`
   covers it)
7. **See the floor under any modified code** (because `prior_role`
   covers what existed before the delta)
8. **Have raised concerns to evaluate** (because `evaluation`,
   `suggestions`, `analysis`, and structured `concerns` cover them)

If the reviewer would still need to grep around the codebase to feel
confident, you didn't research deep enough.

## Common failure modes

- **Sparse context fields**: leaving most of the new fields empty or
  one-liner because the agent didn't actually search the repo. Fix: use
  grep / filesystem reading aggressively.
- **Generic suggestions**: "consider edge cases", "add tests". Useless.
  Be specific or omit.
- **Padded analysis**: writing analysis for the sake of it. Mechanical
  changes don't need analysis. Set null.
- **Fabricated alternatives**: claiming the author considered something
  with no evidence. Use `evidence: "analytical"` for reader-side
  reasoning instead.
- **Ignoring callers/tests/patterns**: the diff is self-sufficient, you
  think. It's not. Read the surrounding repo.

## Length expectations

For a complex step in a non-trivial codebase:
- `behavior_delta`: a sentence or two per field
- `usage_context.callers`: 1-5 entries typical
- `test_coverage.not_covered`: 1-3 specific cases typical
- `codebase_patterns`: 1-3 findings typical
- `alternative_approaches`: 1-3 alternatives typical
- `evaluation`: a paragraph (2-5 sentences) when substantive
- `analysis`: a paragraph or two when substantive
- `suggestions`: 2-5 items when substantive

For trivial steps (rename, comment fix), most fields can be brief or null.
Calibrate to the step.
