# LLM Code Index — Prompt Templates

All prompts used by this skill. Read the format spec first for context.

---

## Prompt 1: LLMREADME Generation

Use this to generate the repo-root LLMREADME.md.

**Input required:**
- Repo README (if exists)
- Tree output from gen_tree.sh
- Key config files (package.json, Cargo.toml, CMakeLists.txt, etc.)
- Top-level entry point files (main.*, index.*, app.*)

```
You are generating LLMREADME.md — the entry-point index for an AI agent
navigating this codebase. An AI will read this file FIRST to understand
what this repo is and where to look for specific things.

Repository info:
<tree>
{tree output}
</tree>

<readme>
{existing README content, if any}
</readme>

<config_files>
{content of key config files}
</config_files>

Generate LLMREADME.md with these exact sections:

## Identity
2-3 sentences. What this system is, what problem it solves, who uses it.
No marketing language. Be precise.

## Key Architecture Decisions
3-5 most important design choices. Each MUST include WHY.
Format: "Uses X because Y, which means Z"
Only decisions that affect how an AI would understand/modify the code.

## Structure
Use the tree output provided. Annotate each top-level directory with a
one-phrase description inline as a comment.

## Module Map
Table with columns: Module | Description | Index
Description = one sentence about what the module does.
Index = relative path to that folder's LLMINDEX.md.
Only include directories that will have LLMINDEX.md files.

## Cross-Module Data Flow
Describe the key data flows using arrow notation: A → B → C.
Focus on the primary paths. What does a typical request/operation look like
as it flows through the system?

## Global Constraints
Repo-wide rules that are NOT obvious from individual files.
Things like: lock ordering, error handling conventions, naming rules,
invariants that span modules, performance requirements.
If you violate these, things break. That's what makes them constraints.

Every sentence must carry information. No filler. No "this is a well-structured
codebase" — that's zero information.
```

---

## Prompt 2: LLMINDEX Generation (per folder)

Use this to generate LLMINDEX.md for a specific folder.

**Input required:**
- All file contents in the folder (or headers if files are very large)
- The repo's LLMREADME.md Identity section (for context)
- Parent module's Identity (if this is a nested folder)

```
You are generating LLMINDEX.md for one folder in a codebase.
This file must serve as a complete reference for an AI agent working
with this module. It has TWO sections in ONE file:

TOP (Layer 1): Quick directory — one line per file, scannable.
  An AI reads this to identify which files matter for its task.

BOTTOM (Layer 2): Detailed notes — seekable by line number.
  An AI jumps here (sed) for deeper understanding of specific files.

Context:
<repo_identity>
{LLMREADME.md Identity section}
</repo_identity>

<folder_path>
{relative path of this folder}
</folder_path>

<files>
{content of all files in this folder}
</files>

Generate the LLMINDEX.md following this structure:

# {Folder Name}

## Identity
1-2 sentences: what this module does, its role in the system.

## Dependencies
- depends on: {other modules this imports/uses}
- depended by: {other modules that import/use this}

## Key Concepts
2-5 bullets. Abstractions, patterns, or domain concepts that are NOT
obvious from file names but needed to understand this module.
Skip this section if everything is self-evident.

## File Directory
| File | Description | Details |
|------|-------------|---------|
One line per file (or per .h+.cpp pair). Sort by importance.
Description = one sentence.
Details = L:{N} where N is the line number of that file's detailed notes below.

If more than ~15 files, group under subheadings (Core, Utilities, Tests, etc).

---
## Detailed Notes

For each file listed in the directory, generate a section:

<!-- LINE {N} -->
### {filename}
**{expanded identity}**

Then write notes following these rules:

TAG EVERY NOTE with: [core], [important], [gotcha], [detail], or [constraint]

EVERY NOTE must be a self-contained information unit:
  Bad:  "Uses observer pattern"
  Good: "Event dispatch uses observer pattern because producers and consumers
         need decoupling. Listeners register on EventBus, events dispatched by type."

INCLUDE CAUSATION:
  Bad:  "Buffer size is 4096"
  Good: "Buffer size is 4096 to match page size and avoid cross-page reads"

PRESERVE HARD INFO: type signatures, numbers, sizes, thresholds, enum values.
These cannot be recovered by reasoning — they must be in the notes.

FOR ALGORITHMS: describe key steps and complexity, not every line.
FOR CONSTRAINTS: state what happens if violated.

END EVERY NOTE with a source reference:
  → src: {relative_file_path}:{line_start}-{line_end} `{symbol_name}`

The symbol_name is a grep-friendly anchor (function name, class declaration, etc.)
so if line numbers drift, the AI can relocate with grep.

IMPORTANT LINE NUMBER ACCURACY:
The L:{N} values in the File Directory MUST exactly match the line numbers
where the <!-- LINE {N} --> comments appear. Count your output lines carefully.
The AI will use sed -n '{N},{M}p' to jump to these sections.

IF THE MODULE HAS MANY INTERCONNECTED TYPES, add at the end:

## Symbol Index
| Symbol | Kind | File | Lines | Brief |
Flat lookup table of key symbols. Only include symbols that other files
would need to reference. Skip private/internal helpers.

CALIBRATE DETAIL DEPTH PER FILE:
- Core files with complex logic: full notes with [core]/[important]/[gotcha]
- Simple utility files: 2-3 notes, mostly [detail]
- Test files: just list what's tested, one [detail] note
- Config/build files: one sentence unless they contain non-obvious settings
```

---

## Prompt 3: Change Classification (for incremental updates)

Use this when a file has changed and you need to decide what to update.

```
A file in an indexed codebase has been modified. Classify this change
to determine what index updates are needed.

<file_path>{path}</file_path>

<diff>
{git diff output for this file}
</diff>

<current_notes>
{the existing detailed notes for this file from LLMINDEX.md}
</current_notes>

Classify this change into ONE of:

(a) IMPLEMENTATION_ONLY — Internal logic changed but interfaces, behavior
    semantics, and public API are identical. Examples: bug fix, performance
    optimization, refactoring internals, adding comments.
    → Action: shift line numbers, maybe update detail notes if behavior description changed.

(b) INTERFACE_CHANGE — Public symbols added/removed/renamed, function signatures
    changed, type definitions changed, or observable behavior semantics changed.
    → Action: regenerate this file's detailed notes. Update File Directory if identity changed.

(c) STRUCTURAL_CHANGE — File added, deleted, or moved. Or fundamental role
    of the file has changed.
    → Action: regenerate folder's LLMINDEX.md.

(d) ARCHITECTURE_CHANGE — Module boundaries shifted, new module created,
    cross-module data flow changed.
    → Action: regenerate LLMREADME.md.

Output:
classification: (a|b|c|d)
reason: {one sentence explaining why}
stale_notes: {list any specific notes that are now inaccurate, by quoting their first few words}
new_info: {any new information that should be captured in notes}
```

---

## Prompt 4: Detailed Notes Regeneration (single file)

Use this to regenerate notes for one specific file after a change.

```
Regenerate the detailed notes section for a single file in an LLMINDEX.md.

<file_path>{path}</file_path>

<file_content>
{current file content with line numbers}
</file_content>

<module_context>
{LLMINDEX.md Identity and Key Concepts sections for this module}
</module_context>

<previous_notes>
{the old detailed notes for this file, if they exist}
</previous_notes>

Generate updated notes following these rules:

- Tag: [core], [important], [gotcha], [detail], [constraint]
- Self-contained information units with causation
- Source references: → src: {file}:{lines} `{symbol}`
- Preserve previously identified [gotcha] and [constraint] items
  unless the code change explicitly resolved them
- If the change introduced new constraints or gotchas, add them
- Calibrate depth: not every function needs notes. Focus on what matters
  for someone using or modifying this code.

Output ONLY the notes section (from ### {filename} to just before the next ###).
Include the <!-- LINE {N} --> marker. The caller will splice this into the LLMINDEX.md.
```

---

## Prompt 5: Module-Level Aggregation Check

Use after updating file-level notes to decide if module-level sections need updating.

```
File-level notes in a module have been updated. Determine if the
module-level sections of LLMINDEX.md need updating.

<module_identity>
{current Identity section}
</module_identity>

<module_key_concepts>
{current Key Concepts section}
</module_key_concepts>

<module_dependencies>
{current Dependencies section}
</module_dependencies>

<updated_file_notes>
{the new/changed file notes}
</updated_file_notes>

<change_summary>
{what changed and why}
</change_summary>

For each module-level section, answer:
1. Identity — still accurate? If not, provide replacement.
2. Key Concepts — any new concepts introduced? Any old ones invalidated?
3. Dependencies — any new deps? Any removed?

Output ONLY the sections that need changing, with their replacements.
Output "NO_CHANGES" if everything is still accurate.
```
