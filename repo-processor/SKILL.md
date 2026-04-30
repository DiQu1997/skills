---
name: repo-processor
description: Generate AI-agent-friendly `ai_doc.md` files and `.ai-docs` global docs for a code repository or subtree using a bottom-up pipeline (recon, plan, generation, validation). Use when asked to document a repo for AI agents, produce co-located `ai_doc.md` files, or create strict, machine-readable reference docs from source code.
---

# Repo Processor

Create structured documentation that AI coding agents can use directly. Follow the pipeline exactly and keep outputs strict and predictable.

## Quick Start

Run the end-to-end pipeline:

```
scripts/repo_processor.sh /abs/path/to/target
```

Common options:

- `--max-agents 5`
- `--small-repo-files 20`
- `--small-repo-loc 3000`
- `--skip-dirs vendor,third_party,node_modules,.git`
- `--skip-generated true`
- `--work-dir /tmp/repo-processor-work`

## Required Workflow (Imperative)

1. Parse the user request and resolve the target path to an absolute path.
2. Decide scope mode.
3. Run recon to collect tree metadata.
4. Build an execution plan.
5. Generate docs bottom-up with strict prompts.
6. Validate outputs and retry failures once.
7. Report a concise summary.

## Scope Mode Rules

- Single directory with no child directories containing source: generate only one `ai_doc.md` and skip `.ai-docs`.
- Subtree or full repo: generate `ai_doc.md` files plus `.ai-docs` at the scope root.

## Recon

Command:

```
scripts/recon.sh /abs/path/to/target /path/to/recon_output.json
```

Rules:

- Skip vendor directories and binary files.
- Detect generated files and exclude them from source analysis if `--skip-generated true`.
- Produce `recon_output.json` matching the schema in `references/design.md`.

## Plan

Command:

```
python3 scripts/plan.py /path/to/recon_output.json /path/to/execution_plan.json
```

Rules:

- Classify directories using the design rules.
- Compute bottom-up levels for leaf and roll-up tasks.
- Do not emit global tasks if the scope root is a single leaf directory.

## Generation

Use prompt templates from `templates/` and spawn subagents with `scripts/spawn_codex.sh`.

Templates:

- `templates/leaf_prompt.md`
- `templates/rollup_prompt.md`
- `templates/global_prompt.md`
- `templates/small_repo_prompt.md` (use when small-repo mode triggers)

Token replacement rules are listed at the top of each prompt template.

Hard requirements for every output:

- Output Markdown only.
- No placeholders or ellipses in the final docs.
- If a section has no content, write `None` on a single line.
- Follow the exact headings and ordering described in `templates/leaf_ai_doc_template.md`, `templates/rollup_ai_doc_template.md`, and `templates/global_docs/*`.

## Validation

Command:

```
scripts/validate.sh /path/to/execution_plan.json
```

Validation rules:

- All planned output files must exist.
- Each file must be at least 200 bytes.
- Required headings must be present for the file type.

If validation fails, retry the failed task once with a simplified prompt. If it fails again, generate the file manually and note the failure in the summary.

## References

- `references/design.md` contains the full design and output rules.
- Do not modify the design document during normal use of this skill.
