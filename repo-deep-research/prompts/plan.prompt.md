You are an expert software architect and codebase researcher.

You are analyzing a local repository at: {REPO_PATH}
Focus area (treat as the root for planning): {FOCUS_PATH}

TASK:
1. Inspect the codebase structure (directories, entry points, build files, docs).
2. Propose a research plan that is deep enough for a large dataset and produces a professor-quality final report.
3. The plan must be actionable for multiple parallel subagents (each subagent owns one module/sub-category).

OUTPUT REQUIREMENTS (VERY IMPORTANT):
- Output ONLY valid JSON. No markdown, no commentary, no prose outside JSON.
- Paths MUST be relative to the focus root (the focus area above).
- Produce between 10 and {MAX_MODULES} modules (prefer 12-18 for large repos).
- Each module should be coherent (one responsibility) and not just a random directory slice.
- Use this exact schema:
{
  "repo_name": "...",
  "repo_purpose": "...",
  "key_technologies": ["..."],
  "focus_path": "{FOCUS_PATH}",
  "modules": [
    {
      "id": "mod-01",
      "name": "...",
      "path": "relative/path",
      "priority": "high|medium|low",
      "estimated_complexity": "high|medium|low",
      "research_questions": ["..."]
    }
  ],
  "cross_cutting_concerns": ["..."]
}

PLANNING HEURISTICS:
- Prioritize: entry points -> core execution model -> key domain logic -> infra (config/logging/errors) -> integrations.
- If a directory is huge, still include it as a module, but craft research_questions that aim to map boundaries and identify sub-areas.
- Add cross_cutting_concerns that matter for understanding end-to-end behavior and correctness.

