---
name: repo-deep-research
description: >
  Deep research and analysis of code repositories using a multi-agent architecture.
  Claude Code acts as orchestrator/planner, spawning Codex CLI subagents for parallel
  module-level research, then synthesizing findings into a comprehensive lecture-style report.
  Use when: user asks to "deeply research", "analyze", "explain", or "study" a code repository;
  user wants to understand a codebase's architecture, design patterns, core ideas, or techniques;
  user wants a comprehensive walkthrough of how a repo works; user says "research this repo",
  "explain this codebase", "deep dive into this project", or similar. NOT for: simple code review,
  bug finding, or quick file inspection — those don't need multi-agent orchestration.
---

# Repo Deep Research

Multi-agent code repository research system. Claude Code orchestrates, Codex CLI subagents
execute parallel research, results are synthesized into a professor-quality lecture report.

## Prerequisites

- `codex` CLI installed and available on PATH (OpenAI Codex CLI)
- Target repo cloned locally
- Sufficient context window for final synthesis

## High-Level Workflow

```
1. RECON         → Gather repo metadata, structure, entry points
2. PLAN          → Create initial research plan with module breakdown
3. RESEARCH LOOP → Spawn subagents, collect results, replan dynamically
4. SYNTHESIZE    → Combine all findings into final report
5. OUTPUT        → Write polished report to file
```

## Quickstart (Automated — USE THIS BY DEFAULT)

**IMPORTANT — read before doing anything else:**

1. **Always use the driver script.** Do NOT follow the manual Phase 1-5 loop below unless
   the user explicitly asks for a manual/interactive run. The driver handles everything.
2. **Run the driver in the background** (`run_in_background: true`). It spawns many
   subagents and takes a long time — you should monitor it while it runs rather than block.
3. **Monitor progress by reading `progress.md`** in the output directory. It is updated
   after every module completes and shows the plan, per-module status, and findings so far.
   Poll it periodically and share intermediate notes with the user.
4. **Do NOT stop or kill the driver.** Even if `progress.md` looks nearly complete, let
   the driver finish all phases including synthesis. Your "I have enough context" feeling
   mid-run is premature — the module reports and final synthesis are not done yet.
5. **Wait for the driver to exit** before presenting the final report. Once it exits,
   read the final `*-deep-research.md` and summarize it for the user.

The driver script:
- runs recon
- asks Codex to generate a module plan
- spawns parallel Codex subagents per module (resumable across runs)
- detects oversized sub-categories and recursively re-runs repo-deep-research on them
- synthesizes a step-by-step lecture-style final report
- writes `progress.md` to the output dir so you can see exactly what was done

```bash
bash <skill-path>/scripts/deep_research.sh <repo-path> \
  --outdir .deep_research \
  --max-agents 4 \
  --max-depth 1
```

If a previous run was interrupted (e.g. usage limit), **just re-run the same command**.
Completed phases and modules are detected automatically and skipped; only the remaining
work is executed. Use `--force` to ignore all prior outputs and start fresh.

Common knobs:
- `--focus <subdir>`: run the full workflow on a sub-category/subtree
- `--max-depth N`: recursion depth for oversized sub-categories
- `--loc-threshold` / `--file-threshold`: what counts as "too large for one subagent"
- `--force`: ignore all cached outputs and re-run every phase from scratch

## Manual Phases (Fallback Only — Skip if using the Automated Quickstart above)

> These phases describe what the driver script does internally. Only follow them manually
> if the user has explicitly asked for an interactive/manual run, or if the driver is
> unavailable. If you are running the driver script, **ignore everything below.**

## Phase 1: Reconnaissance

Run the recon script against the target repo:

```bash
bash <skill-path>/scripts/recon.sh <repo-path>
```

This produces `recon_output.md` in the current directory containing:
- Directory tree (depth 3, respecting .gitignore)
- Language/file-type breakdown
- Top 20 largest files
- README content (first 200 lines)
- Package manager files (package.json, Cargo.toml, go.mod, pyproject.toml, etc.)
- Entry points and build configuration

Also manually read key files the recon surfaces. Pay attention to:
- Architecture docs (`docs/`, `ARCHITECTURE.md`, `DESIGN.md`)
- The main entry point file
- Configuration/build files

## Phase 2: Initial Planning

Based on recon, create a **research plan** as a JSON file `research_plan.json`:

```json
{
  "repo_name": "example-repo",
  "repo_purpose": "One-line summary of what this repo does",
  "key_technologies": ["rust", "tokio", "grpc"],
  "modules": [
    {
      "id": "mod-01",
      "name": "core/engine",
      "path": "src/core/engine",
      "priority": "high",
      "estimated_complexity": "high",
      "research_questions": [
        "What is the main execution model?",
        "How does it handle concurrency?",
        "What are the key data structures?"
      ],
      "status": "pending"
    }
  ],
  "cross_cutting_concerns": [
    "error handling strategy",
    "configuration management",
    "logging/observability"
  ],
  "research_queue": ["mod-01", "mod-02", "mod-03"]
}
```

**Planning heuristics:**
- Identify 5-15 top-level modules based on directory structure
- Prioritize: entry points > core logic > utilities > tests
- Mark modules as `high`/`medium`/`low` complexity
- For `high` complexity modules, note they may need splitting later
- Identify cross-cutting concerns that span multiple modules

## Phase 3: Dynamic Research Loop

This is the core of the system. Execute iteratively until all modules are researched.

### 3a. Spawn Subagent Batch

For each module in the research queue (batch 3-5 at a time), use the spawn script:

```bash
bash <skill-path>/scripts/spawn_codex.sh \
  "<repo-path>" \
  "<research-prompt>" \
  "<output-file>" \
  "<focus-path>"
```

See `references/research_prompts.md` for prompt templates per research type.

### 3b. Collect and Review Results

After each batch completes, read ALL output files and assess:

1. **Completeness** — Did the subagent answer all research questions?
2. **Depth** — Is the analysis surface-level or does it explain WHY?
3. **New discoveries** — Did findings reveal:
   - Sub-modules that need their own deep dive?
   - Cross-module dependencies not visible from structure alone?
   - Interesting design patterns or techniques worth highlighting?
   - Unexpected complexity that changes priorities?

### 3c. Dynamic Replanning

Based on the review, update `research_plan.json`:

- **Split** large modules into sub-modules if findings show internal complexity
- **Add** new research tasks for discovered cross-cutting concerns
- **Reprioritize** queue based on what's been learned
- **Add follow-up questions** for modules that need deeper investigation
- **Mark completed** modules and track coverage

**Decision framework for splitting:**
- Module has 3+ distinct responsibilities → Split
- Module has >500 lines of core logic → Consider splitting
- Subagent output is superficial despite good prompting → Split and re-research
- Module contains an embedded subsystem → Split

**Decision framework for recursive deep research (oversized sub-categories):**
- Sub-category has ~60+ code files or ~6k+ LOC of relevant code → Prefer a nested repo-deep-research run on that subpath
- Subagent report contains large "unknown" areas or only high-level mapping → Trigger a nested run to get a full, self-contained subreport
- The sub-category is effectively a subsystem (its own lifecycle, config, APIs, persistence, jobs) → Nested run

**Decision framework for follow-up research:**
- Subagent mentioned a pattern but didn't explain the mechanism → Follow up
- Critical code flow only partially traced → Follow up with flow-tracing prompt
- Module interfaces with external systems in non-obvious ways → Follow up

### 3d. Repeat

Continue the loop (3a → 3b → 3c → 3d) until:
- All modules in the queue are completed
- No new splits or follow-ups are needed
- Coverage is sufficient for a comprehensive report

Typical repos need 2-4 iterations. Very large repos may need more.

## Phase 4: Synthesis

Once all research is collected, synthesize into the final report.
See `references/report_structure.md` for the full report template.

**Synthesis principles:**
- **Denoise**: Remove redundant observations across module reports.
  Keep the clearest explanation, cite it once.
- **Connect**: Explicitly trace how modules interact. Don't describe each in isolation.
- **Layer**: Present both the 10,000-foot view AND the line-by-line detail.
  A reader should be able to read just the overview and get value,
  or dive into any section for implementation details.
- **Teach**: Use step-by-step explanations. Frame as:
  "here's what the authors were trying to solve → here's the approach they chose → here's why it works → here's what to watch for."
- **Code flows**: For the 3-5 most important operations, trace the complete code path
  from entry point to result. Include actual code snippets with annotations.

## Phase 5: Output

Write the final report to `<repo-name>-deep-research.md` in the working directory.
The report should be self-contained and readable without access to the source code,
though it should reference file paths for readers who want to follow along.

## Important Notes

- **Parallelism**: Spawn up to 5 Codex subagents concurrently. More causes context issues.
- **Subagent scope**: Each subagent should focus on ONE module or concern. Don't overload.
- **Token budget**: Subagent prompts should request structured output to stay focused.
- **Error handling**: If a subagent fails or produces garbage, retry once with a simpler prompt.
  If it fails again, research that module manually.
- **Progress tracking**: Update `research_plan.json` after every batch.
  This is your source of truth for what's done and what's left.
