# Notes / 未来方向备忘

Open ideas that came out of working sessions — not yet scheduled, recorded
so they don't get lost. One section per idea; delete when shipped.

## Review quality layer: adversarial verification (2026-07-03)

**Context.** The render gates in `code-review-narrative` now give a hard
*completeness* guarantee: `real diff == diff_hunks ⊆ steps` — every line
the PR changed appears in the walkthrough verbatim (PR #19). What the
gates cannot check is *judgment quality*: whether the conclusion written
next to each line is correct.

**The gap, concretely:**

- **漏报 (false negative)** — a step covers the changed line, agent marks
  it ✓ CLEAN, but the line has a real bug (e.g. a race on a bare
  `size_t +=` in what will become multi-writer code). Line covered, bug
  missed. The validator confirms "the line appears," not "the line was
  understood."
- **误报 (false positive)** — HIGH concern on a perfectly normal pattern
  because the agent misread the context.
- **严重度错标 (severity misgrading)** — real bug marked LOW, style nit
  marked HIGH; reviewer attention gets steered wrong.
- **证据错误 (bad evidence)** — a concern's `evidence` field cites
  `util/arena.h:35` but that line doesn't support the claim. Nothing
  re-reads the cited file to check.

One line: **gates guarantee "every line was looked at," not "every line
was judged correctly."** Completeness is mechanical; correctness needs a
stronger review process.

**Design sketch (multi-agent adversarial verify, complementary layer):**

1. **误报过滤 — refuters.** For each emitted concern, spawn N independent
   "skeptic" agents prompted to REFUTE it (read the cited evidence file,
   check the claim against actual code). Concern survives only if a
   majority fail to refute. Kills plausible-but-wrong findings.
2. **漏报补捞 — re-scan of CLEAN steps.** Spawn independent reviewers with
   *distinct lenses* (concurrency, boundary/overflow, error paths, test
   blind spots, API contract) over steps marked CLEAN or LOW. Diversity
   catches what redundancy can't. New findings feed back through step 1.
3. **证据核查 — evidence checker.** Mechanical-ish middle ground: an agent
   (or script + agent) that opens every `evidence` citation and verifies
   the cited line actually exists and plausibly supports the concern text.
   Cheapest of the three; could even become a render.py warning gate.
4. **严重度仲裁 — severity panel.** For surviving concerns, a small judge
   panel re-grades severity independently; disagreement beyond one level
   flags the concern for human attention rather than silently averaging.

**Where it would live:** a post-analysis phase in
`code-review-narrative` (after Phase 9 validation, before render), likely
orchestrated via the Workflow tool's fan-out patterns (adversarial verify,
perspective-diverse verify, loop-until-dry). Output: same JSON, with
concerns annotated `verified: refuted|confirmed|panel-flagged` — the
template could then render confidence styling.

**Relation to existing gates:** 完整性 (mechanical gates, shipped) vs
正确性 (adversarial layer, this note). They compose; neither replaces the
other.
