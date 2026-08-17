# Handoff: Code Review Narrative Tool

**For**: Claude Code, picking up this project.
**From**: Di + collaborator (Claude in chat).
**Date**: 2026-04-27 (handoff v2 — adds walk-through and function rationale as v0.3 direction)
**Status**: v0.2 of the review skill works end-to-end on real PRs. Schema validated. Two distinct quality gaps identified. Direction confirmed for v0.3 (walk-through annotations + function rationale). Prompt overhaul (Path A from v1 handoff) deprioritized to follow walk-through.

---

## 0. How to use this document

You are taking over a project. Read linearly. Don't skip Section 3 (validated assumptions) — those are conclusions from real experiments, not speculation.

After reading, you should be able to:
1. Explain the vision in one paragraph
2. Run the v0.2 skill on a real PR and produce an HTML review (the existing capability)
3. Understand the v0.3 direction (walk-through + function rationale) and execute Phase 1 of it
4. Know what NOT to do (deferred / deprioritized work)

If anything in this document contradicts the codebase, **trust the codebase and ask the user** before changing direction.

---

## 1. The vision (north star)

### One-paragraph version

Reading, reviewing, and understanding code today happens through tools whose primitive is the file. But the unit of meaning in code is rarely a single file — features, fixes, design choices live across files. Reviewers, readers, and learners are forced to mentally reconstruct logical units from physical layout, every time. We're building a tool whose primitive is the **logical unit** (a storyline, a step within a storyline, a logical change group), where physical layout (which file, which line) is implementation detail. The agent organizes information for the user; the user reads/reviews along logical lines, not file lines.

### Long-term form

A multi-mode AI-native reading/writing surface delivered as a VSCode extension (initially). Modes: reading (understand existing code), reviewing (understand a proposed change), planning (design a change), learning (deep dive into unfamiliar code). The full vision is 5-10 years; the present plan delivers a useful subset much sooner.

### The MVP we're building first

**Review mode skill**: takes a git diff, produces a self-contained interactive HTML review document organized by **logical groups (storylines)** rather than by file. The HTML has three panes: left navigation tree, center code view, right analysis sections.

Why review mode first (not reading mode):
- PR review is occasional → low switching cost for users to try
- GitHub PR view is widely disliked → clear differentiation space
- Review-mode agent task (analyze diff) is more tractable than freeform code understanding
- Validates the core primitive shift on a concrete artifact

The skill is not yet a VSCode extension. It produces a standalone HTML file. Extension comes later, after content quality is validated.

---

## 2. What exists right now (v0.2)

### The skill folder

```
code-review-narrative/
├── README.md                  # User-facing readme
├── SKILL.md                   # Skill definition: when to trigger, workflow
├── render.py                  # Inject JSON into HTML template
├── prompts/
│   ├── schema.md              # JSON schema spec (v0.2)
│   └── analyze_diff.md        # Prompt template for the agent
├── template/
│   └── review.html            # Single-file HTML/CSS/JS template (~45KB)
└── demo/
    ├── sample_review.json     # Hand-crafted reference data
    └── sample_review.html     # Rendered demo output
```

### How v0.2 works end-to-end

1. User has a PR / commit range / git diff to review
2. User invokes the skill (e.g. "use code-review-narrative on this PR")
3. Agent reads the diff and surrounding code, produces JSON conforming to `prompts/schema.md`
4. `render.py` injects JSON into `template/review.html`, producing self-contained HTML
5. User opens HTML in browser. Three panes, keyboard nav (`j`/`k`/`o`/`s`)

### v0.2 schema at a glance

**Storyline** (logical group of changes):
- `id`, `title`, `kind`, `confidence`, `confidence_reasoning`, `summary`, `files_touched`
- `purpose` (stated/evident/discrepancy)
- `architectural_context` (system_role, involved_modules, data_flow, diagram)
- `change_overview`, `reading_roadmap`
- `steps[]`

**Step**:
- `id`, `title`, `track` (core/supporting/test/config)
- `code_view`: `primary_changes[]` + `supporting_definitions[]`
- `summary`
- `behavior_delta` (before / after / diff)
- `usage_context` (primary_usage_scenario, callers, call_patterns, implicit_dependencies)
- `test_coverage` (covered_by, added_in_this_pr, not_covered)
- `codebase_patterns` (similar_changes_elsewhere, convention_alignment, deviations)
- `alternative_approaches[]`
- `evaluation`, `suggestions[]`, `analysis`
- `concerns[]` (with severity)
- `prerequisites[]`

### v0.2 UI

**Left pane**: nav tree (PR overview link → storyline collapsibles → steps)

**Center pane**: depends on view state
- PR Overview: title, summary, list of storylines
- Storyline Overview: title, purpose (stated/evident/discrepancy), architectural context with diagram, change overview, reading roadmap, steps roadmap, "Start reading" button
- Step view: breadcrumb, title, badges, Changes, Supporting context, prev/up/next nav

**Right pane**: 9 collapsible analysis sections per step. Default-expanded: Prerequisites, Summary, Behavior Delta, Evaluation, Suggestions, Concerns. Default-collapsed: Usage Context, Test Coverage, Codebase Patterns, Alternative Approaches, Analysis.

---

## 3. What has been validated (don't re-litigate)

These are conclusions from real experiments. Take them as given unless you have new evidence:

### V1: Logical grouping is meaningful on real PRs

Agent successfully identified coherent storylines on a real ~4-commit codex PR. Hand-crafted demo also broke into clean storylines. **Conclusion**: storylines are not fictional — agents can produce them, real PRs have such structure.

### V2: Three-pane UI shape works

PR / storyline / step views; nav / code / analysis panes; keyboard nav. UI doesn't get in the way. **Conclusion**: don't redesign the layout.

### V3: Self-contained HTML is the right delivery format (for now)

No build, no server, no deps. Easy to share, archive, version. Fast iteration. **Conclusion**: don't migrate to SPA / web app / VSCode extension yet. Stay with HTML.

### V4: Schema v0.2 captures the right "around the code" context

Behavior delta, usage context, test coverage, codebase patterns, alternatives, concerns, plus storyline purpose / architecture / overview. After running on a real PR, no v0.2 field was identified as missing. **Conclusion**: don't redesign the existing v0.2 fields. (v0.3 ADDS new fields; doesn't restructure existing ones.)

### V5: Template + injected JSON architecture is right

UI iterates independently of analysis quality. Token-efficient. Multiple reviews share one template. **Conclusion**: don't have agent generate HTML/JS directly.

### V6: Render pipeline bug (fixed)

Earlier: `render.py` used `str.replace()` replacing all occurrences, including a self-reference inside an error message. Result: JSON injected into wrong place too, breaking JS. Fixed by using `replace(..., 1)` and removing self-reference. Don't reintroduce.

---

## 4. The two quality gaps (v0.2 → v0.3)

After v0.2 reviews on real PRs, two distinct gaps in user experience emerged:

### Gap A: Content depth is shallower than hand-crafted reference

Numerical comparison (avg per step, real PR vs hand-crafted demo):

| Field | Real PR | Demo | Ratio |
|---|---|---|---|
| step.summary | 174 chars | 135 chars | 1.3× |
| step.behavior_delta.diff | 123 chars | 204 chars | 0.6× |
| step.evaluation | 163 chars | 200 chars | 0.8× |
| step.analysis | 240 chars | 387 chars | **0.6×** |
| Total alternatives across all steps | 8 | 15 | 0.5× |
| Total concerns across all steps | **3** | **9** | **0.3×** |
| Total suggestions | 8 | 15 | 0.5× |

**Diagnosis**: schema is fine; UI is fine; bottleneck is in `prompts/analyze_diff.md`. Agent stops at one paragraph for `analysis`, raises few concerns (default-helpful, not default-skeptical), populates exactly 1 alternative per step regardless of complexity.

### Gap B (NEW — discovered after v0.2 dogfooding): summaries are too far from code

This is the **bigger gap** and the priority for v0.3.

User feedback verbatim: *"代码和summary直接联系不够紧密, summary太抽象, 我还是需要一些类似于hand holding 级别的walk through... 这个不是summary, 而是walk through, 就像那种有人做code walk through, 他不会给你介绍这个函数是干嘛的, 一段summary就结束了, 你需要一些更细节的介绍, 尤其是那些很长的function, 你一眼过去都不想看, 他里面是可以拆分, 像段落, 第一段是干嘛的, 第二段是干嘛的"*

Translation: code review is detail-grained work. v0.2's `summary` is **distance reading** — agent stands outside and describes the change in one paragraph, leaving the reader to map abstract description to concrete lines. What's needed is **walk-through reading** — annotation interleaved with code, paragraph-by-paragraph corresponding to chunks of code.

**Two distinct things the user wants** that v0.2 lacks:

1. **Code-attached walk-through annotations**. Long functions get broken into chunks (e.g. "validation block", "main loop", "cleanup"); each chunk gets a paragraph of explanation tied to specific line ranges. Inline with the code, not in the right pane.

2. **Function-level rationale (motivation, not description)**. For each function/code-block being modified or shown, an explanation of *why this exists* and *what problem it solves*. Not "this function does X" (description) but "this function exists to solve problem Y; without it, callers would have to do Z" (motivation). For long messy functions where one rationale doesn't fit, the rationale itself can be split into multiple sub-sections.

**Diagnosis**: v0.2 schema doesn't model "annotation tied to specific line ranges within a code block". `summary` is one string per step, far from the code. Walk-through annotations need first-class schema support.

### Decision: v0.3 priority

Close Gap B first (walk-through + function rationale), then Gap A (prompt overhaul). 

Rationale: Gap B is structural (schema + UI), Gap A is prompt-tuning. Doing Gap A first means re-doing prompt work after Gap B changes the schema. Gap B is also the user-articulated need most likely to differentiate the tool — close-reading hand-holding is uniquely valuable, deeper analytical commentary is "nice to have."

---

## 5. v0.3 design: walk-through and function rationale

### Schema additions

Two new fields on each `FileView` entry inside `code_view.primary_changes[]` and `code_view.supporting_definitions[]`:

```jsonc
{
  "file": "string",
  "language": "string",
  "context_start_line": "int",
  "context_end_line":   "int",
  "lines": [...],          // existing

  // NEW in v0.3 — function-level rationale
  "function_purpose": {
    "function_name": "string | null",   // e.g. "MemTable::Add"; null if not function-scoped
    "structure":     "single | multi_section",

    // when structure == "single" — function has coherent single purpose
    "problem_solved": "string (what problem does this function exist to solve)",
    "without_it":     "string (what would happen / what would callers do differently if this function didn't exist)",

    // when structure == "multi_section" — function does multiple things
    "sections": [
      {
        "line_start":    "int",
        "line_end":      "int",
        "section_name":  "string (e.g. 'input validation', 'main execution loop')",
        "problem_solved":"string",
        "without_it":    "string"
      }
    ]
  },

  // NEW in v0.3 — code-attached walk-through annotations
  "walkthrough": [
    {
      "line_start":  "int",
      "line_end":    "int",
      "chunk_role":  "string (e.g. 'validation', 'main logic', 'error handling', 'cleanup', 'state transition')",
      "explanation": "string (a paragraph: what this chunk does AND why; bond to specific code mechanics)"
    }
  ]
}
```

### Walk-through scope (important — the heuristic agents must follow)

Walk-through annotations should be **change-centric, with related unchanged code included**. Concretely, for each candidate chunk in the displayed code, the agent asks:

> Does understanding this chunk help the reader understand the change?

- **Yes** (chunk is a +/- change, OR chunk is unchanged but the change interacts with or depends on it) → annotate
- **No** (chunk is just surrounding context unrelated to the change's logic) → don't annotate, just show code

This means walk-through is **sparse**, not exhaustive. A 30-line function with a 5-line change might have 2 annotations (one for the change region, one for the unchanged validation that the change relies on). The remaining 20 lines render plain.

This avoids two failure modes:
- "Annotate every line" → noise, dilutes attention
- "Annotate only +/- lines" → reader still has to mentally connect the change to surrounding logic

### `function_purpose` design notes

- A function may not perfectly serve a single purpose. Long, historically-merged, or messy functions exist. The schema accommodates this with `multi_section`.
- For `multi_section`, sections are the agent's reading of the function's structure (not necessarily aligned with diff hunks). E.g. a 200-line function with parsing in lines 1-80 and execution in lines 81-200 gets two sections, even if the change only touches lines 150-160.
- `problem_solved` is **motivation** ("the system needs Y; this function provides Y"). `without_it` is **counter-factual** ("if this didn't exist, callers would [pay cost / risk error / be unable to do thing]"). These two together force agent to articulate non-obvious value.

### How walk-through differs from existing fields

| Field | Scope | What it answers |
|---|---|---|
| `step.summary` | Whole step, distant | "What does this step do at a high level?" |
| `step.behavior_delta` | Whole step | "What's the runtime behavior change?" |
| `function_purpose` (new) | Function/section | "Why does this function/section exist?" |
| `walkthrough` (new) | Code chunks within file | "What is this chunk doing in detail, and why this way?" |

Walk-through is the most fine-grained. Together with the existing fields, the reader gets four levels of zoom: PR → storyline → step → chunk.

### UI rendering: inline annotations

User confirmed inline (not side-by-side, not hover-reveal). Approximate layout for a `FileView` block:

```
┌─ db/memtable.cc · lines 76-99 · cpp ─────────────────────────┐
│                                                                │
│ ── Function: MemTable::Add() ──                                │
│ Why it exists: ...                                             │
│ Without it: ...                                                │
│                                                                │
│ ── Walk-through ── [Hide all]                                  │
│                                                                │
│ 76 │ void MemTable::Add(SequenceNumber s, ValueType type,      │
│ 77 │                   const Slice& key, const Slice& value) { │
│ 78 │   size_t key_size = key.size();                           │
│ 79 │   size_t val_size = value.size();                         │
│ 80 │   size_t internal_key_size = key_size + 8;                │
│ 81 │   const size_t encoded_len = VarintLength(...) +          │
│ 82 │                              internal_key_size + ...;     │
│ 83 │                                                            │
│   ▾ Lines 78-83 · sizing                                      │
│      Compute total bytes needed (varint key size + key + 8     │
│      byte tag + varint value size + value) before allocation,  │
│      so the arena returns one contiguous buffer.               │
│                                                                │
│ 84 │   char* buf = arena_.Allocate(encoded_len);               │
│                                                                │
│   ▾ Line 84 · single allocation                                │
│      Arena gives one contiguous buffer for the whole entry.    │
│      SkipList nodes are allocated separately inside            │
│      table_.Insert(buf), which is why the size accounting in   │
│      this PR adds an estimate for node overhead.               │
│                                                                │
│ 85 │   char* p = EncodeVarint32(buf, internal_key_size);       │
│ 86 │   std::memcpy(p, key.data(), key_size);                   │
│ ...                                                            │
│ 94 │ + // Track size: entry bytes + node-overhead estimate.    │
│ 95 │ + tracked_bytes_ += encoded_len + kApproxSkipListNode...; │
│                                                                │
│   ▾ Lines 94-95 · the change · accumulator update             │
│      The change adds bookkeeping after a successful insert.    │
│      Note placement: after table_.Insert(), so a hypothetical  │
│      future Insert that can fail wouldn't desync the counter.  │
│      Uses += not atomic — relies on single-writer assumption.  │
│                                                                │
│ 96 │ }                                                         │
└────────────────────────────────────────────────────────────────┘
```

Annotations are visually subordinate to code (smaller font or muted background), but distinct enough to scan. Each annotation has a `▾` toggle for individual collapse. File-block top has `[Hide all]` / `[Show all]` master toggle.

Function purpose block sits at the top of the file-block, before any code. For `multi_section`, render as multiple stacked rationale blocks (one per section), each with their `line_start–line_end` range marked.

### Default state (collapse / expand)

- **Function purpose**: default expanded (high-level motivation, helpful at a glance)
- **Walk-through annotations**: default expanded (point of v0.3 is to provide hand-holding by default)
- User can hide all annotations to scan code cleanly when wanted

State doesn't persist across reload (acceptable for MVP; localStorage polish later).

---

## 6. Recommended path forward

### Phase 1: v0.3 schema + template + render — UI work first

This is the structural foundation. Before changing prompts, get the rendering right with hand-crafted data.

1. Update `prompts/schema.md` to v0.3:
   - Bump schema_version to "0.3"
   - Add `function_purpose` and `walkthrough` to `FileView` and `FileViewWithReason`
   - Document the change-centric walk-through scope heuristic
2. Update `template/review.html`:
   - Render `function_purpose` block at top of each file-block (single or multi_section)
   - Render `walkthrough` annotations interleaved with code lines, in line-number order
   - Add `[Hide all]` / `[Show all]` master toggle per file-block
   - Add per-annotation `▾` collapse toggle
   - Style annotations distinctly (muted background, smaller-font, perhaps left-margin indicator)
3. Update `demo/sample_review.json` to v0.3:
   - Add `function_purpose` and `walkthrough` to selected file-views
   - Hand-craft for at least one step with a single-purpose function and one step with a multi-section function, to exercise both paths
4. Re-render demo, verify UI renders correctly. **Run JS through node to catch errors before pronouncing it done** (we hit a render bug earlier by skipping this — see V6).
5. Show user; iterate UI feel before moving to Phase 2.

**Time estimate**: 4-8 hours (mostly UI work; schema is small).

### Phase 2: Update analyze_diff.md prompt for v0.3 fields

After UI is good with hand-crafted data:

1. Add walk-through generation guidance to the prompt:
   - The change-centric scope heuristic
   - Length expectation per annotation (1 substantial paragraph, not a sentence)
   - Bond to mechanics — explain *what code does and why this way*, not abstract restatement
2. Add function_purpose guidance:
   - Distinguish single vs multi_section by reading function structure
   - `problem_solved` is motivation; `without_it` is counter-factual
   - Both should make non-obvious value visible
3. Test on the same real PR used for v0.2 validation
4. Compare agent output to demo's hand-crafted v0.3 walk-through quality
5. Iterate prompt until the gap closes

**Time estimate**: 4-6 hours (prompt work + iteration).

### Phase 3: Address Gap A (analysis depth) — old "Path A"

Now that walk-through is in place, return to the original quality gap:
- Multi-paragraph `analysis` with multiple angles
- Encourage skepticism for `concerns`
- Calibrate `alternative_approaches` count to step complexity
- Tighten `test_coverage.added_in_this_pr` semantics

**Time estimate**: 4-6 hours.

### Phase 4: Validate on a different PR

Run v0.3 on a real PR Di hasn't seen this tool's output for. Confirm prompt improvements generalize.

**Time estimate**: 2-3 hours.

### Phase 5: Dogfood

Di uses the tool for several real reviews over 1-2 weeks. Surface real workflow friction. Iterate.

### Critical path

Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5. No phases parallel-able since each builds on the previous.

Total to v0.3 dogfood-ready: 14-23 hours of focused work, plus 1-2 weeks intermittent dogfooding.

---

## 7. What NOT to do (deferred / deprioritized)

- **VSCode extension**: HTML file is the deliverable for now. Don't port until content quality is validated.
- **Reading mode skill**: shares 80% of schema/UI; not the MVP. Build review mode first.
- **Other modes** (planning, learn): same reasoning.
- **PR platform integration** (push comments back to GitHub/etc.): v0.2+ feature. v0.1 has manual export.
- **Re-grouping interaction** (drag steps between storylines): not yet built. Decide based on dogfooding.
- **Local state persistence**: section collapse states, scroll positions don't persist. localStorage would fix; not yet built.
- **Reviewer notes / annotations**: schema implicitly has space; no UI yet.
- **Don't redesign existing v0.2 schema fields**: v0.3 *adds* fields; don't restructure existing ones.
- **Don't redesign UI layout**: three panes, three views. Until you have evidence layout is broken (vs. content thin), stick with what works.
- **Don't introduce a build step**: vanilla HTML/CSS/JS. No webpack/React/TS for the template.
- **Don't have agent generate HTML directly**: template + JSON injection.

---

## 8. Quick start for Claude Code

### Setup

```bash
cd /path/to/code-review-narrative
ls -la   # README.md, SKILL.md, render.py, prompts/, template/, demo/
python3 render.py demo/sample_review.json demo/sample_review.html
# Open demo/sample_review.html in browser to see v0.2 reference output
```

### v0.3 development workflow

```bash
# 1. Edit prompts/schema.md to v0.3
# 2. Hand-craft additions to demo/sample_review.json (function_purpose + walkthrough)
# 3. Edit template/review.html to render new fields
# 4. Render: python3 render.py demo/sample_review.json demo/sample_review.html
# 5. CRITICAL: actually open the HTML in a browser AND run JS through node to catch errors
#    (see V6 — we hit a render bug earlier by skipping JS validation)
# 6. Iterate
```

### Files to study before starting

In order:
1. `SKILL.md` — what the skill is and when to use it
2. `prompts/schema.md` — v0.2 contract (you'll extend to v0.3)
3. `prompts/analyze_diff.md` — current prompt (extend in Phase 2)
4. `demo/sample_review.json` — v0.2 reference; you'll extend to v0.3
5. `demo/sample_review.html` — v0.2 rendered; you'll regenerate after v0.3 changes
6. `template/review.html` — v0.2 template; you'll edit for v0.3 rendering

---

## 9. Decision log (key choices made and why)

| Decision | Rationale |
|---|---|
| Review mode first, not reading mode | PR review is occasional → low switching cost; GitHub PR view is widely disliked → clear differentiation |
| Self-contained HTML, not extension | Fast iteration; no extension infra distraction; product-shape questions answer themselves before infrastructure investment |
| Template + injected JSON | UI iterates independently of analysis quality; consistent across runs; token-efficient |
| Three-pane UI | Logical nav + code + analysis maps to three classes of information naturally |
| Three-level zoom (PR / storyline / step) | Matches how reviewers navigate: see whole, choose part, dive in |
| Collapsible right-pane sections (v0.2) | Density without overwhelm; user controls focus |
| Both research-assistant AND senior-reviewer roles | Two roles aren't conflicting; reviewer benefits from rich context AND substantive opinion |
| Schema v0.2 (added behavior_delta, usage_context, test_coverage, codebase_patterns, alternative_approaches, concerns, plus storyline-level purpose, architectural_context, change_overview, reading_roadmap) | Reviewer with little familiarity needs all this to form independent judgment |
| **v0.3 adds walk-through and function_purpose to FileView** | v0.2's `summary` is distance reading; PR review is detail work; long functions need chunked annotation tied to specific lines; functions need "why does this exist" not "what does this do" |
| **Walk-through is change-centric with related unchanged included** | Avoids both "annotate every line" (noise) and "annotate only +/- lines" (still no help understanding the surrounding logic the change interacts with) |
| **function_purpose supports single OR multi_section** | Real functions aren't always single-purpose; long messy functions need section-level rationale |
| **Walk-through inline (not side-by-side, not hover)** | Hand-holding feel requires interleaving; side-by-side adds another column to already-3-pane layout; hover defeats walk-through |
| **Close Gap B (walk-through) before Gap A (prompt depth)** | Gap B is structural; doing prompt work first means re-doing it after schema changes |

---

## 10. Open questions for the user (Di)

Surface to Di when relevant; don't decide unilaterally:

1. **Confirm v0.3 priority order** (Gap B first, then Gap A). Recommended in Section 6 but can be overridden.
2. **Real PRs for iteration**: same codex repo last 4 commits as v0.2? a different PR? 
3. **Eventual delivery form**: HTML file in v0.1, extension in v0.2 — confirm still fits.
4. **Open-source / private**: at what point does this become public? Affects how prompts are documented, demo data is chosen.

---

## 11. Brief context on Di

Background relevant to this project:
- Mid-level systems engineer (storage / distributed systems background)
- Hands-on with ML/AI infrastructure, agentic frameworks
- Strong preference for clean, principled designs over over-engineering
- Iterative, scope-controlled development style
- Communicates fluidly in English and Chinese; UI labels include Chinese (前情提要, 简介, etc.) intentionally — keep this
- Has been tracking this project across many conversations; expects continuity
- Values honest critique and willingness to push back; doesn't want sycophancy

When in doubt: ask Di. When responding: be direct, structured, evidence-based, willing to disagree.

---

## 12. Final note

This project is at v0.2 (works on real PRs end-to-end) and has a clear v0.3 direction (walk-through + function rationale). The next phase is structural (schema + UI) before prompt-tuning, because doing prompt-tuning first means redoing it after schema changes.

Don't restart. Pick up at v0.3 Phase 1 (Section 6). The artifacts in the skill folder and this document together contain everything needed.

If you find yourself disagreeing with a foundational choice (delivery form, schema shape, UI layout, mode priority, v0.3 direction), surface to Di explicitly with evidence — don't change direction silently.

---

## Appendix A: v0.2 sample of agent output (current state)

For calibration of where we are:

```json
{
  "id": "S2.2",
  "title": "Add lifecycle to HTTP SSE streams",
  "summary": "Wires the lifecycle recorder into the HTTP SSE stream path...",
  "behavior_delta": {
    "before": "HTTP SSE terminal failures produced plain stream errors such as idle timeout or stream closed before response.completed.",
    "after":  "When codex-core supplies lifecycle options, those same errors can include lifecycle context and emit structured warning logs.",
    "diff":   "The public behavior changes only for opt-in callers and mostly in diagnostics; non-lifecycle callers still pass None through the compatibility methods."
  },
  "analysis": "The response_error path finalizes on the parser error and then sends that same error after the stream ends. That avoids reclassifying a response.failed event as a closed-before-completion transport problem."
}
```

Note `analysis` stops at one paragraph stating one observation. A senior reviewer would naturally continue: "This means [implication]. In workloads where [Y], this could lead to [Z]. The alternative would have been [W], with tradeoff [V]." Closing this is Phase 3 (Gap A).

## Appendix B: v0.2 hand-crafted reference (Gap A target)

```json
{
  "id": "S1.2",
  "analysis": "The conservative-overhead approach trades accuracy for cost. Actual node height in SkipList::Insert() is determined by RandomHeight() which most often returns 1 (50% probability) but can go up to kMaxHeight (12). A node with height h occupies sizeof(Node) + (h-1)*sizeof(void*) bytes. The 96-byte estimate roughly corresponds to height 12 (max), which is conservative but on average overcounts by a factor of 2-3x for small entries.\n\nThis matters because callers (DBImpl::MakeRoomForWrite) compare tracked_bytes_ against `options_.write_buffer_size` to decide when to rotate. Overestimating means rotation happens earlier than it would have with a precise count, leading to slightly smaller MemTables in practice. Whether this is desirable depends on whether write_buffer_size is interpreted as 'soft target' or 'hard cap'. Header docs are silent on this; commits historically treat it as a soft target."
}
```

Two paragraphs: first is technical mechanism with concrete numbers from code; second is implication for callers + open question. Depth target for Phase 3.

## Appendix C: v0.3 example — what walk-through + function_purpose should look like

This is for hand-crafting `demo/sample_review.json` in Phase 1.

```jsonc
{
  "file": "db/memtable.cc",
  "language": "cpp",
  "context_start_line": 76,
  "context_end_line": 99,
  "lines": [/* ... existing line entries with line_num, content, change ... */],

  "function_purpose": {
    "function_name": "MemTable::Add",
    "structure": "single",
    "problem_solved": "Inserts a single key/value entry into the in-memory write buffer. This is the only path by which writes land in the MemTable; everything else (DBImpl::Write, WriteBatchInternal) ultimately routes here. The function is responsible for encoding the entry into a single contiguous arena allocation and inserting a pointer into the SkipList.",
    "without_it": "Without MemTable::Add, callers would either need to manually encode the entry layout (varint sizes + key + tag + value) and manage arena allocation themselves, or the SkipList would have to expose a richer Insert API that handled encoding. Either route would leak MemTable's internal layout to callers, breaking the abstraction that lets MemTable evolve its on-disk-equivalent format independently."
  },

  "walkthrough": [
    {
      "line_start": 78,
      "line_end": 83,
      "chunk_role": "sizing",
      "explanation": "Compute the total encoded length for the entry — varint(internal_key_size) + internal_key_size + varint(val_size) + val_size — before allocating. Doing it in one pass avoids a copy or realloc later. internal_key_size is key_size + 8 because the trailing 8 bytes pack sequence number and value type."
    },
    {
      "line_start": 84,
      "line_end": 84,
      "chunk_role": "allocation",
      "explanation": "Single contiguous arena allocation for the whole entry. Note the SkipList node itself is allocated separately inside table_.Insert(buf) below — this is why the size-accounting change in this PR (line 96) adds an explicit estimate for node overhead rather than relying on encoded_len alone."
    },
    {
      "line_start": 85,
      "line_end": 92,
      "chunk_role": "encoding",
      "explanation": "Lay out the bytes into the buffer: varint internal_key_size, then the user key, then the 8-byte (seq << 8) | type tag, then varint val_size, then the value. The assert at line 92 checks the encoder consumed exactly the budgeted space."
    },
    {
      "line_start": 93,
      "line_end": 93,
      "chunk_role": "insertion",
      "explanation": "Hand the buffer off to the SkipList. Insert takes the buffer pointer; the comparator embedded in the SkipList knows how to decode it for ordering."
    },
    {
      "line_start": 94,
      "line_end": 95,
      "chunk_role": "the change · accumulator update",
      "explanation": "The change in this PR. Increment tracked_bytes_ by encoded entry bytes plus a fixed conservative skiplist-node overhead estimate. Three things to notice: (1) placement is *after* table_.Insert(), so failure paths wouldn't desync the counter (Insert is currently infallible, but this is correct anyway); (2) += is non-atomic — relies on the single-writer property of the DB write lock; (3) the overhead constant is a magic number (96), not derived from sizeof(Node) + kMaxHeight*sizeof(void*) — see concerns section for the implication."
    }
  ]
}
```

Note how walk-through is **sparse** (only 5 annotations for ~24 lines), each annotation is **substantial** (1 paragraph with mechanics + reasoning, not just description), and the change region (lines 94-95) gets the deepest annotation because it's the focus of the review. The unchanged lines 85-92 get an annotation because the encoding layout is what the new tracking is counting bytes of — relevant. Lines 76-77 (function signature) get no annotation — agent decided they don't need hand-holding.

This is the depth and granularity to aim for in Phase 1 demo and Phase 2 prompt.

— end of handoff document —