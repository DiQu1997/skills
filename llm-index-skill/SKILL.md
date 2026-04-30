---
name: llm-code-index
description: >
  Generate AI-navigable semantic indexes for code repositories. Creates LLMREADME.md (repo-level)
  and LLMINDEX.md (per-folder) files that let AI agents understand a codebase with minimum token
  reads and maximum information density. Supports incremental updates via git hooks.
  Use when: user asks to "index a repo", "generate code index", "create LLMREADME", "make this
  repo AI-navigable", "generate semantic index", "index this codebase for AI", "create code notes",
  or wants to make a codebase easy for LLMs to navigate. Also use when user asks to "update index"
  or "refresh index" for an already-indexed repo. Trigger even if user just says "index this" while
  in a repo directory.
---

# LLM Code Index

Generate progressive-disclosure semantic indexes for code repositories.
AI agents read LLMREADME.md → folder LLMINDEX.md → seek to detail lines → sed source code.
Each layer is self-contained. Most tasks complete without reading actual source.

## Quick Reference

| Command | What it does |
|---------|-------------|
| Full index | Generate LLMREADME.md + all LLMINDEX.md files for a repo |
| Single folder | Generate LLMINDEX.md for one folder |
| Update | Incremental update based on git diff |
| Setup hook | Install post-commit git hook for auto-updates |

## Before Starting

1. Read `references/format-spec.md` for the complete format specification
2. Read `references/prompts.md` for all prompt templates
3. Identify the repo root and get a sense of repo size

## Workflow: Full Index Generation

### Step 1: Reconnaissance

```bash
# Count files to determine tree depth
find <repo> -type f -not -path '*/.git/*' -not -path '*/node_modules/*' \
  -not -path '*/vendor/*' -not -path '*/build/*' | wc -l

# Generate appropriately-depth tree
bash <skill-path>/scripts/gen_tree.sh <repo-path>
```

Tree depth rules (from format spec):
- < 50 files: full tree
- 50-200: depth 3
- 200-500: depth 2
- 500+: depth 2, omit test/vendor/build/generated

### Step 2: Generate LLMREADME.md (repo root)

Read the repo's existing README, key config files, and top-level structure.
Then use the **LLMREADME Prompt** from `references/prompts.md` to generate.

The LLMREADME.md must include:
- Identity (2-3 sentences)
- Key Architecture Decisions (with WHY)
- Structure (tree output from Step 1)
- Module Map (table with links to each LLMINDEX.md)
- Cross-Module Data Flow
- Global Constraints

Write to `<repo-root>/LLMREADME.md`.

### Step 3: Generate LLMINDEX.md files (per folder)

Process folders in dependency order when possible (leaf modules first,
so parent modules can reference children's identities).

For each folder containing source code:

1. Read all files in the folder (or if too large, read headers/interfaces first)
2. Use the **LLMINDEX Prompt** from `references/prompts.md`
3. Write to `<folder>/LLMINDEX.md`

**Critical format requirements:**
- Top section (Layer 1): File Directory with one-line-per-file + detail line numbers
- Bottom section (Layer 2): Detailed notes, each starting at the line number referenced above
- Line markers: `<!-- LINE {N} -->` comments before each file's detail section
- Source refs: `→ src: file:lines \`symbol\`` format on every note

**Grouping rules for files:**
- `.h + .cpp` pairs: treat as one unit in File Directory, but note both files in refs
- `.ts + .test.ts`: list separately, test file gets minimal notes
- Small utility files: can share a detail section if they're closely related

**Skip LLMINDEX.md for:**
- Directories with only generated/build files
- Test fixture directories (just data)
- Vendor/third-party code
- Directories with 1-2 trivial files (describe in parent's LLMINDEX.md instead)

### Step 4: Verify line numbers

After generating each LLMINDEX.md, verify that `L:XX` references in the File Directory
actually correspond to the `<!-- LINE XX -->` markers. Off-by-one errors break navigation.

```bash
# Quick verification: extract all L: references and LINE markers
grep -n 'L:' <folder>/LLMINDEX.md
grep -n '<!-- LINE' <folder>/LLMINDEX.md
```

### Step 5: Add metadata comment

Add freshness tracking at the top of each LLMINDEX.md:

```markdown
<!-- LLMINDEX_META
generated_at: {ISO timestamp}
source_commit: {git rev-parse HEAD}
prompt_version: v1
files:
  {filename}: {sha256 hash of file content}
  ...
-->
```

## Workflow: Incremental Update

When user asks to update an existing index after code changes:

### Step 1: Identify changes

```bash
# What changed since last index?
git diff --name-only $(grep 'source_commit' LLMREADME.md | head -1 | awk '{print $2}') HEAD
```

### Step 2: Classify changes per file

For each changed file, determine impact level:

**(a) Implementation-only change** (bug fix, refactor, perf optimization)
→ Update line numbers mechanically using `scripts/update_line_refs.py`
→ Optionally update detail notes if behavior description changed

**(b) Interface change** (new/removed/renamed symbols, changed signatures)
→ Regenerate that file's detailed notes in LLMINDEX.md
→ Update File Directory one-liner if identity changed
→ Check if module-level Identity or Key Concepts need update

**(c) Structural change** (new file, deleted file, moved file)
→ Regenerate the folder's LLMINDEX.md
→ If module role changed, update parent LLMREADME.md Module Map

**(d) Architecture change** (new module, changed data flow)
→ Regenerate LLMREADME.md

### Step 3: Mechanical line number update

For type (a) changes, use the helper script:

```bash
python3 <skill-path>/scripts/update_line_refs.py <folder>/LLMINDEX.md <git-diff-output>
```

This parses diff hunks and shifts line numbers without needing LLM calls.
If anchor text no longer matches, it marks refs as stale for regeneration.

### Step 4: Update metadata

Update the `LLMINDEX_META` comment with new commit hash and file hashes.

## Workflow: Setup Git Hook

To auto-update index on every commit:

```bash
bash <skill-path>/scripts/setup_hook.sh <repo-path>
```

This installs a post-commit hook that identifies changed files and
prints which LLMINDEX.md files need updating. Full auto-regeneration
requires the LLM, so the hook just flags what's stale — the user
runs the actual update manually or via CI.

## Quality Checklist

After generating index files, verify:

- [ ] LLMREADME.md exists at repo root with all required sections
- [ ] Every source folder has LLMINDEX.md (except skipped directories)
- [ ] File Directory `L:XX` numbers match `<!-- LINE XX -->` markers
- [ ] Every note has a source reference (`→ src:` line)
- [ ] Source reference anchors can be found with grep in actual files
- [ ] No filler text — every sentence carries information
- [ ] Causation included — notes say WHY, not just WHAT
- [ ] [gotcha] and [constraint] tags used where applicable
- [ ] Cross-file relationships noted in Dependencies sections
- [ ] Module Map in LLMREADME.md links to all LLMINDEX.md files

## Important Notes

- **Line numbers will drift** — this is expected. Anchors (symbol names after backtick)
  are the stable fallback. Both are provided so AI can try line number first, grep anchor second.
- **Don't over-index** — a 10-line utility file needs one sentence, not a full note section.
  Let the LLM judge how much detail each file deserves.
- **Test files get minimal notes** — just list what's tested, not how. Tests are self-documenting.
- **The format is markdown** — not JSON, not YAML. Markdown is LLM-native and human-readable.
  No parsing step needed.
- **Repo-specific conventions matter** — if the repo uses specific patterns (error handling,
  logging, DI), capture these in LLMREADME.md Global Constraints so every module inherits them.
