You are writing a professor-quality deep research report that teaches the reader step-by-step.

Repository name: {REPO_NAME}
Focus area: {FOCUS_PATH}
Research artifacts directory (relative to repo root): {OUTDIR}

TASK:
- Read the artifacts under `{OUTDIR}`:
  - `recon_output.md`
  - `research_plan.json`
  - all module reports in `modules/`
  - any nested reports under `subreports/` (if present)
- Produce ONE cohesive report that is deeper than a typical summary. Make the code feel "walkable".
- If a module has a nested subreport, use that subreport for details and keep the parent report focused on the role and interfaces.

STYLE (IMPORTANT):
- Walk the reader through the architecture like a lecture.
- Always connect concepts to concrete code: file paths + function/type names.
- Prefer step-by-step explanations:
  - overview -> architecture map -> module map -> 3-5 key end-to-end flows
  - for each flow, provide a numbered sequence (each step includes file + function + what happens + why it is structured that way)
- Include design tradeoffs: what the chosen structure optimizes for vs what it sacrifices.
- Include cross-cutting concerns (errors, config, logging/observability, testing) when they materially affect behavior.
- Depth target: do not be terse. Prefer a thorough report over a short summary, within your response limits.

OUTPUT:
- Output markdown only.
- Start with `# Deep Research Report: {REPO_NAME}`
- Include a short "How to Read This Report" section early, explaining the structure.
