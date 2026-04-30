# LLM Code Index — Format Specification

## Design Principle

**Progressive disclosure: minimum tokens, maximum necessary information, zero information loss.**

An AI agent navigates like this:
```
LLMREADME.md (repo-level)     → what is this, where to look
  ↓
LLMINDEX.md (folder-level)    → top section: one-line per file
  ↓ seek by line number          bottom section: detailed notes
  ↓
sed -n 'X,Yp' source.cpp     → actual code, only when needed
```

Most tasks complete at LLMINDEX.md. Source code is last resort.

---

## Layer 0: LLMREADME.md

**Location**: `<repo-root>/LLMREADME.md`
**Purpose**: Entry point. AI reads this first, always.

### Required Sections

```markdown
# {Repository Name}

<!-- LLMINDEX_META
generated_at: {ISO timestamp}
source_commit: {short hash}
prompt_version: v1
-->

## Identity
{2-3 sentences: what this is, what problem it solves, who uses it}

## Key Architecture Decisions
{3-5 bullets, each with WHY not just WHAT}
{Example: "Uses X because Y, which means Z"}

## Structure
{tree output, depth-limited per rules below}
{annotate top-level dirs with one-phrase descriptions}

## Module Map
| Module | Description | Index |
|--------|-------------|-------|
| {dir}/ | {one sentence} | [LLMINDEX.md]({dir}/LLMINDEX.md) |

## Cross-Module Data Flow
{key data flows in the system — what you'd draw on a whiteboard}
{use arrows: A → B → C format}

## Global Constraints
{repo-wide invariants, conventions, rules}
{things NOT obvious from individual files}
```

### Tree Depth Rules

| Total files in repo | Tree depth | Notes |
|---------------------|-----------|-------|
| < 50 | full | Show everything |
| 50-200 | 3 | |
| 200-500 | 2 | |
| > 500 | 2 | Omit test/vendor/build/generated, note omissions |

---

## Layer 1+2: LLMINDEX.md

**Location**: `<folder>/LLMINDEX.md`
**Purpose**: Everything an AI needs to know about this folder.
Layer 1 (top) = quick scan. Layer 2 (bottom) = detailed notes, same file.

### Structure

```markdown
# {Module/Folder Name}

<!-- LLMINDEX_META
generated_at: {ISO timestamp}
source_commit: {short hash}
prompt_version: v1
files:
  {filename}: {sha256 hash}
  ...
-->

## Identity
{1-2 sentences: what this module does and its role in the system}

## Dependencies
- depends on: {modules this imports/uses}
- depended by: {modules that import/use this}

## Key Concepts
{2-5 bullets: abstractions, patterns, or domain concepts needed
 to understand this module. Only non-obvious things.}

## File Directory
| File | Description | Details |
|------|-------------|---------|
| {file} | {one sentence} | L:{line_number} |

{If > 15 files, group under subheadings:}
### Core Implementation
| File | Description | Details |
...
### Utilities
| File | Description | Details |
...
### Tests & Benchmarks
| File | Description | Details |
...

{If folder has subdirectories with their own LLMINDEX.md:}
## Subdirectories
| Subfolder | Description | Index |
|-----------|-------------|-------|
| {subdir}/ | {one sentence} | [LLMINDEX.md]({subdir}/LLMINDEX.md) |

---
## Detailed Notes

<!-- LINE {N} -->
### {filename}
**{expanded one-sentence identity}**

{tagged notes with source references}

<!-- LINE {M} -->
### {next filename}
...

## Symbol Index
| Symbol | Kind | File | Lines | Brief |
|--------|------|------|-------|-------|
| {name} | {class/struct/enum/method/function} | {file} | {start-end} | {one phrase} |
```

### File Directory Rules

- **L:{N}** = line number in THIS file where detailed notes for that file start
- One line per file, sorted by importance (not alphabetically)
- `.h + .cpp` pairs listed as single entry: `block_allocator.h + .cpp`
- Test files listed but with minimal detail notes

### Detailed Notes Rules

Each file's section starts with `<!-- LINE {N} -->` matching its `L:{N}` in the directory.

**Note format:**
```
[tag] {self-contained information unit with causation}
  → src: {relative/path/to/file}:{line_start}-{line_end} `{symbol_or_anchor}`
```

**Tags:**
- `[core]` — Without this, you will misunderstand or misuse this code
- `[important]` — Significantly aids understanding
- `[gotcha]` — Counter-intuitive behavior, common mistake, subtle bug risk
- `[detail]` — Useful specifics; safe to skip for high-level understanding
- `[constraint]` — Invariant, precondition, rule that MUST be respected

**Information unit rules:**
- Self-contained: includes necessary context, not just bare facts
- Causal: "X because Y" not just "X"
- Preserves hard info: numbers, type signatures, sizes, thresholds
- Algorithms: key steps + complexity, not every line
- Constraints: state what happens if violated

**Source reference format:**
```
→ src: relative/path/to/file.cpp:112-158 `ClassName::method_name`
```
- Line numbers = range where this info lives in source
- Symbol = anchor for grep fallback if lines drift
- AI retrieves with: `sed -n '112,158p' relative/path/to/file.cpp`

### Symbol Index (optional, recommended for complex modules)

Flat lookup table at end of LLMINDEX.md.
AI scans this when it needs to locate a specific type or function.

```markdown
## Symbol Index
| Symbol | Kind | File | Lines | Brief |
|--------|------|------|-------|-------|
| BlockAllocator | class | block_allocator.h | 23-78 | Main allocator interface |
| BlockHandle | struct | block_allocator.h | 12-20 | 64-bit block address encoding |
```

---

## AI Navigation Protocol

When an AI agent gets a task against an indexed codebase:

```
STEP 1: cat LLMREADME.md
  → Understand repo, identify relevant modules
  → Check Global Constraints

STEP 2: head -N <module>/LLMINDEX.md
  → Read Identity, Dependencies, File Directory
  → Identify relevant files and their detail line numbers

STEP 3: sed -n 'X,Yp' <module>/LLMINDEX.md
  → Read detailed notes for specific files
  → Get source references

STEP 4 (only if needed): sed -n 'X,Yp' <source_file>
  → Read actual code for implementation work
```

Most tasks complete at Step 3.

---

## Files to Skip

Do NOT generate LLMINDEX.md for:
- Test fixture / test data directories
- Generated / build output directories
- vendor / node_modules / third-party
- Directories with only 1-2 trivial files (describe in parent instead)
- Assets directories (images, fonts)

---

## Incremental Update Triggers

| What changed | What to update |
|-------------|----------------|
| File internals only | Shift line numbers in LLMINDEX.md, optionally refresh detail notes |
| File interface (new/changed symbols) | Regenerate file's detail notes, check File Directory one-liner |
| File added/removed | Regenerate folder's LLMINDEX.md |
| Module structure (new subfolder) | Regenerate LLMINDEX.md + update parent LLMREADME.md |
| Architecture change | Regenerate LLMREADME.md |
