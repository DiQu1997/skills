# repo-processor: Full Design Document

## 1. Vision & Purpose

### What It Does

`repo-processor` analyzes a code repository (or a subtree of one) and generates **AI-agent-friendly reference documentation** — structured docs that an AI coding agent can consume as context to write correct, idiomatic code against the codebase.

### How It Differs from repo-deep-research

| Aspect | repo-deep-research | repo-processor |
|--------|-------------------|----------------|
| **Audience** | Humans wanting to learn | AI agents needing to code |
| **Output** | One monolithic lecture report | Distributed `ai_doc.md` files co-located with code |
| **Tone** | "Here's why this is clever..." | "To add X, implement Y, call Z with these preconditions" |
| **Focus** | Design insight, patterns, lessons | API contracts, data schemas, concurrency rules, extension guides |
| **Location** | Single file in working directory | In-tree: each directory gets its own doc |
| **Update model** | Full regeneration | Path-scoped: regenerate a subtree only |

### Core Design Principles

1. **Co-location**: Low-level docs live next to the code they describe. An AI agent working in `src/core/engine/` finds `ai_doc.md` right there.
2. **Bottom-up divide-and-conquer**: Leaf directories are analyzed first (fully parallel), then parent directories cross-reference their children, all the way up to the root.
3. **Scope control**: The user can target the entire repo or any subtree path. Only the targeted scope is analyzed.
4. **Structured for machines**: Every `ai_doc.md` follows a strict template so AI agents can reliably parse and extract information.
5. **Adaptive detail**: Small directories get exhaustive per-function docs. Large directories get interface-focused summaries with pointers.

---

## 2. Output Structure

### 2.1 Directory Layout

```
<target-path>/
├── .ai-docs/                          # High-level docs (repo-wide or scope-wide)
│   ├── OVERVIEW.md                    # Purpose, tech stack, build commands, philosophy
│   ├── ARCHITECTURE.md                # Module map, dependency graph, data flows
│   ├── CONVENTIONS.md                 # Coding style, naming, error handling, test patterns
│   ├── CONCURRENCY.md                 # Threading model, lock inventory, async patterns
│   ├── ENTRY_POINTS.md                # "How to add a new X" cookbook guides
│   └── QUICK_REFERENCE.md            # Top types, functions, file→responsibility lookup
│
├── src/
│   ├── core/
│   │   ├── engine/
│   │   │   ├── executor.rs
│   │   │   ├── worker.rs
│   │   │   └── ai_doc.md              # Leaf doc: covers all files in this dir
│   │   ├── scheduler/
│   │   │   ├── queue.rs
│   │   │   └── ai_doc.md              # Leaf doc
│   │   └── ai_doc.md                  # Roll-up: how engine/ and scheduler/ interact
│   ├── api/
│   │   ├── handlers.go
│   │   └── ai_doc.md                  # Leaf doc
│   └── ai_doc.md                      # Roll-up: how core/ and api/ interact
```

### 2.2 Three Tiers of Documentation

**Tier 1 — Leaf `ai_doc.md`** (per leaf directory)
- Analyzes raw source files
- Exhaustive: every type, every public function, every data structure
- No dependencies on other `ai_doc.md` files

**Tier 2 — Roll-up `ai_doc.md`** (per intermediate directory)
- Synthesizes child `ai_doc.md` files
- Focuses on: inter-module relationships, data flow between children, shared patterns
- Does NOT repeat child content — references it

**Tier 3 — `.ai-docs/` global docs** (root-level)
- Synthesizes ALL `ai_doc.md` files across the tree
- Cross-cutting concerns: architecture, conventions, concurrency, extension guides
- The "read this first" docs for an AI agent new to the codebase

---

## 3. ai_doc.md Templates

### 3.1 Leaf ai_doc.md Template

```markdown
# {directory_path}

> {2-3 sentence purpose statement. What this directory owns and why it exists.}

## Files Overview

| File | Purpose | LOC |
|------|---------|-----|
| `executor.rs` | Main executor logic, thread pool management | 342 |
| `worker.rs` | Individual worker thread implementation | 187 |

## Key Types

### `TypeName`
{What real-world concept it represents. 1-2 sentences.}

| Field | Type | Description |
|-------|------|-------------|
| `field1` | `Type` | What this stores and why |
| `field2` | `Type` | What this stores and why |

- **Invariants**: {field constraints, mutual exclusions, ordering requirements}
- **Construction**: {how instances are created — builder, constructor, factory}
- **Thread safety**: {Send? Sync? Requires lock? Interior mutability?}
- **Serialization**: {JSON? Protobuf? Not serialized?}

### `AnotherType`
...

## Functions

### `module::function_name(param1: Type, param2: Type) -> ReturnType`
{What it does. 1-2 sentences.}
- **Preconditions**: {what must be true before calling}
- **Postconditions**: {what is guaranteed after return}
- **Side effects**: {IO, state mutation, logging, network calls}
- **Thread safety**: {safe to call concurrently? Requires lock?}
- **Error conditions**: {when and why it fails}
- **Performance**: {O(n)? Hot path? Acquires locks?}

### `module::another_function(...)`
...

## Internal Logic

{For non-trivial algorithms or processing pipelines, explain the logic step by step.
Include annotated code snippets (5-15 lines) for the most important parts.}

```{lang}
// Key algorithm: how tasks are scheduled
// This is a work-stealing deque — each worker has a local queue
// but can steal from other workers when idle.
fn steal_task(&self) -> Option<Task> {
    // Try local queue first (fast path, no contention)
    if let Some(task) = self.local_queue.pop() {
        return Some(task);
    }
    // Steal from random peer (slow path, CAS contention possible)
    self.steal_from_random_peer()
}
```

## Concurrency Details

- **Locks**: {what locks exist in this module, what they protect}
- **Lock ordering**: {if multiple locks, required acquisition order}
- **Atomic operations**: {what atomics are used and why}
- **Async boundaries**: {where async/await is used, what runtime}
- **Shared state**: {what mutable state is shared across threads}
- **Hot paths**: {which functions are performance-critical, lock duration}

## Dependencies

- **Imports from**: {list of other modules this depends on, with what it uses from each}
- **Exported to**: {list of modules that depend on this, with what they use}
- **External crates/packages**: {third-party dependencies specific to this module}

## Usage Guide

{Concrete examples of how to use this module's public API.
Extracted from tests if available, otherwise synthesized.}

```{lang}
// Example: submitting a task to the executor
let executor = TaskExecutor::new(config);
executor.start();
let id = executor.submit(Task::new(|| {
    process_data(input)
}))?;
let result = executor.wait(id).await?;
```

## Extension Guide

{Step-by-step instructions for common modifications.}

**To add a new scheduling policy:**
1. Create a new file in this directory implementing the `SchedulingPolicy` trait
2. Implement `fn next_task(&self, queue: &TaskQueue) -> Option<Task>`
3. Register it in `ExecutorConfig::with_policy()`
4. The executor calls `policy.next_task()` instead of default FIFO `pop_front()`
5. Test requirement: must pass `test_scheduling_fairness` with your policy

**To add a new task type:**
1. ...
```

### 3.2 Roll-up ai_doc.md Template

```markdown
# {directory_path}

> {2-3 sentence summary of what this directory group represents as a whole.}

## Sub-modules

| Directory | Purpose | Key Type |
|-----------|---------|----------|
| `engine/` | Task execution and thread pool | `TaskExecutor` |
| `scheduler/` | Task prioritization and ordering | `PriorityQueue` |

## Module Relationships

{Describe how the sub-modules interact. This is the primary value of the roll-up.}

### Dependency Graph
```
scheduler/ ──provides-policy──▶ engine/
engine/ ──notifies-completion──▶ scheduler/
```

### Data Flow
{Trace the primary data flow through these sub-modules.}

1. External caller submits `Task` to `engine/TaskExecutor::submit()`
2. Engine enqueues to internal `TaskQueue`
3. `scheduler/PriorityQueue` orders tasks by priority + dependency resolution
4. Engine workers pull next task via `scheduler/policy.next_task()`
5. Worker executes task, notifies scheduler of completion for dependency tracking

### Shared Patterns
{Patterns that are consistent across sub-modules.}
- All sub-modules use `Result<T, ModuleError>` for error handling
- Logging follows `tracing` crate conventions with `#[instrument]`

### Cross-Cutting Concerns
{Concurrency, error handling, or other concerns that span sub-modules.}
- Lock ordering: scheduler locks must be acquired BEFORE engine locks
- Shared state: `Arc<SchedulerState>` is passed from scheduler to engine at init

## Interface Contract

{The "API" that this directory group exposes to the outside world.
What do modules OUTSIDE this directory need to know?}

### Public API Surface
- `TaskExecutor::new(config) -> Self`
- `TaskExecutor::submit(task) -> TaskId`
- `TaskExecutor::shutdown() -> JoinHandle`

### Assumptions Made by External Callers
- Executor is initialized once, shared via `Arc`
- All task IDs are valid for the lifetime of the executor
- Shutdown is called exactly once
```

### 3.3 Global Document Templates

#### .ai-docs/OVERVIEW.md
```markdown
# {Project Name} — AI Agent Overview

## Purpose
{What this project does. 3-5 sentences.}

## Tech Stack
| Component | Technology | Version | Notes |
|-----------|-----------|---------|-------|
| Language | Rust | 1.75+ | Edition 2021 |
| Async | Tokio | 1.x | Multi-threaded runtime |
| ...

## Build & Run
```bash
# Build
cargo build --release

# Test
cargo test

# Run
cargo run -- --config config.toml
```

## Design Philosophy
{3-5 bullet points capturing the project's core values.}
- Favor correctness over performance — all shared state is explicitly locked
- Zero-copy where possible — uses `Bytes` and `Arc<[u8]>` for buffer sharing
- Fail fast — invalid state panics in debug, returns error in release

## Project Structure
{High-level directory map with purpose annotations.}
```
src/
├── core/       # Execution engine and scheduling
├── api/        # HTTP/gRPC interface layer
├── storage/    # Persistence and caching
└── util/       # Shared utilities, no business logic
```
```

#### .ai-docs/ARCHITECTURE.md
```markdown
# Architecture

## System Diagram
{Mermaid or ASCII diagram showing major components and data flow.}

## Module Dependency Graph
{Which modules depend on which. Directed graph.}

## Key Data Flows
{For the 3-5 most important operations, trace the full path.}

### Flow 1: {Operation Name}
Entry: `api/handlers.rs:handle_request()`
1. API layer validates and deserializes → `Request`
2. Core engine receives `Request`, creates `Task`
3. Scheduler orders task, engine worker executes
4. Storage layer persists result
5. API layer serializes `Response`

## Layer Rules
{What can depend on what.}
- `api/` → `core/` ✅
- `core/` → `storage/` ✅
- `api/` → `storage/` ❌ (must go through core)
- `util/` → nothing (leaf dependency)
```

#### .ai-docs/CONVENTIONS.md
```markdown
# Coding Conventions

## Naming
- Types: PascalCase
- Functions: snake_case
- Constants: SCREAMING_SNAKE_CASE
- File names: snake_case, one primary type per file

## Error Handling
- All fallible functions return `Result<T, Error>`
- Module-level error enums in `error.rs`
- Use `thiserror` for error definitions
- Use `anyhow` only at application boundaries

## Testing
- Unit tests in `#[cfg(test)] mod tests` within each file
- Integration tests in `tests/` directory
- Test naming: `test_{function}_{scenario}_{expected}`
- Mocking: use `mockall` crate for trait-based mocks

## Logging
- Use `tracing` crate, not `log`
- Every public function has `#[instrument]`
- Log levels: ERROR (user-facing failures), WARN (recoverable), INFO (state changes), DEBUG (internal flow)

## Code Style
- Max line length: 100
- Imports grouped: std → external crates → internal modules
- No `unwrap()` in production code, `expect()` only with descriptive message
```

#### .ai-docs/CONCURRENCY.md
```markdown
# Concurrency Model

## Threading Architecture
{Thread pool? Actor model? Single-threaded event loop?}

## Lock Inventory
| Lock | Type | Protects | Held By | Duration |
|------|------|----------|---------|----------|
| `task_queue_lock` | `Mutex` | `VecDeque<Task>` | submit(), steal() | Brief (push/pop) |
| `state_lock` | `RwLock` | `SchedulerState` | Multiple | Read-heavy |

## Lock Ordering (MUST follow)
1. `state_lock` (outermost)
2. `task_queue_lock`
3. `worker_lock` (innermost)

**Violating this order WILL deadlock.**

## Async Model
- Runtime: Tokio multi-threaded
- CPU-bound work: `spawn_blocking()`
- IO-bound work: direct `.await`
- Never hold a Mutex across `.await` — use `tokio::sync::Mutex` if needed

## Shared State Catalog
| State | Owner | Access Pattern | Sync Mechanism |
|-------|-------|----------------|----------------|
| `TaskQueue` | Engine | Write: submit, Read: workers | `Arc<Mutex<>>` |
| `Config` | Main | Read-only after init | `Arc<>` |

## Gotchas & Rules
- Never allocate while holding `task_queue_lock`
- `shutdown` flag is `AtomicBool` — check it AFTER releasing locks, not while held
- Worker threads must not panic — wrap task execution in `catch_unwind`
```

#### .ai-docs/ENTRY_POINTS.md
```markdown
# Extension Guide

## How to Add a New API Endpoint
1. Define request/response types in `api/types.rs`
2. Add handler function in `api/handlers.rs`
3. Register route in `api/router.rs:build_routes()`
4. Add integration test in `tests/api_test.rs`
5. **Concurrency**: handlers receive `Arc<AppState>` — read-only access to shared state

## How to Add a New Storage Backend
1. Implement `StorageBackend` trait in `storage/backends/`
2. Required methods: `get()`, `put()`, `delete()`, `list()`
3. Register in `storage/mod.rs:create_backend(config)`
4. **Precondition**: backend must be thread-safe (`Send + Sync`)
5. **Testing**: must pass `storage/tests/backend_conformance.rs`

## How to Add a New Task Type
1. ...
```

#### .ai-docs/QUICK_REFERENCE.md
```markdown
# Quick Reference

## Key Types
| Type | Module | One-liner |
|------|--------|-----------|
| `TaskExecutor` | core/engine | Main executor, owns thread pool |
| `PriorityQueue` | core/scheduler | Orders tasks by priority + deps |
| `Request` | api/types | Incoming API request |

## Key Functions
| Function | Signature | One-liner |
|----------|-----------|-----------|
| `TaskExecutor::submit` | `(&self, Task) -> Result<TaskId>` | Enqueue a task |
| `PriorityQueue::next` | `(&self) -> Option<Task>` | Get highest-priority ready task |

## File → Responsibility Map
| File | What It Does |
|------|-------------|
| `src/core/engine/executor.rs` | Thread pool and task lifecycle |
| `src/core/engine/worker.rs` | Individual worker thread loop |
| `src/core/scheduler/queue.rs` | Priority queue implementation |
| `src/api/handlers.rs` | HTTP request handlers |

## Glossary
| Term | Meaning |
|------|---------|
| Extent | A contiguous block of storage, typically 64MB |
| Cell | An isolated failure domain within the storage cluster |
```

---

## 4. Multi-Agent Architecture

### 4.1 Overall Pipeline

```
┌─────────────────────────────────────────────────────────────────┐
│                        ORCHESTRATOR (Claude Code)                │
│                                                                  │
│  Phase 1: RECON ──▶ Phase 2: PLAN ──▶ Phase 3: GENERATE ──▶ Phase 4: SYNTHESIZE  │
│                                          │                       │
│                              ┌───────────┼───────────┐           │
│                              ▼           ▼           ▼           │
│                          [Codex 1]   [Codex 2]   [Codex 3]      │
│                          leaf dir    leaf dir    leaf dir         │
│                              │           │           │           │
│                              ▼           ▼           ▼           │
│                          ai_doc.md   ai_doc.md   ai_doc.md      │
│                              │           │           │           │
│                              └─────┬─────┘           │           │
│                                    ▼                 │           │
│                                [Codex 4]             │           │
│                              roll-up dir             │           │
│                                    │                 │           │
│                                    ▼                 │           │
│                                ai_doc.md             │           │
│                                    └────────┬────────┘           │
│                                             ▼                    │
│                                    GLOBAL SYNTHESIS              │
│                                    .ai-docs/*.md                 │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Phase 1: Reconnaissance

**Input**: Target path (repo root or subtree)
**Output**: `recon_output.json` containing:

```json
{
  "target_path": "/path/to/repo/src/core",
  "is_full_repo": false,
  "languages": {"rust": 85, "toml": 10, "markdown": 5},
  "total_files": 47,
  "total_loc": 12500,
  "directory_tree": [
    {
      "path": "src/core",
      "source_files": ["mod.rs"],
      "source_loc": 45,
      "subdirs": ["engine", "scheduler"]
    },
    {
      "path": "src/core/engine",
      "source_files": ["mod.rs", "executor.rs", "worker.rs"],
      "source_loc": 892,
      "subdirs": []
    },
    {
      "path": "src/core/scheduler",
      "source_files": ["mod.rs", "queue.rs", "priority.rs"],
      "source_loc": 634,
      "subdirs": []
    }
  ],
  "entry_points": ["src/main.rs", "src/lib.rs"],
  "build_files": ["Cargo.toml", "Cargo.lock"],
  "existing_docs": ["README.md", "docs/architecture.md"]
}
```

**Implementation**: Enhanced version of existing `recon.sh` that outputs JSON + collects LOC per directory.

### 4.3 Phase 2: Planning

The orchestrator reads `recon_output.json` and builds an **execution plan** — a DAG of tasks organized by tree level.

#### Directory Classification

```
classify(dir):
  has_source = dir.source_files.length > 0
  has_children = dir.subdirs.length > 0
  children_with_source = subdirs that have source files (recursive)

  if has_source and not has_children:
    → LEAF (analyze source files, produce ai_doc.md)
  
  if has_source and has_children:
    → LEAF + ROLLUP (analyze local source files AND cross-reference children)
  
  if not has_source and children_with_source >= 2:
    → ROLLUP (cross-reference children only)
  
  if not has_source and children_with_source == 1:
    → SKIP (pass-through directory, no doc needed)
  
  if not has_source and children_with_source == 0:
    → SKIP (empty directory tree)
```

#### Detail Level Assignment

```
detail_level(dir):
  if dir.source_loc < 500 and dir.source_files.length <= 5:
    → EXHAUSTIVE
    Every function documented. Every field annotated.
    Full usage examples. Complete concurrency analysis.
  
  if dir.source_loc < 2000 and dir.source_files.length <= 15:
    → STANDARD
    Public API fully documented. Internal helpers summarized.
    Key types fully annotated. Concurrency notes for shared state.
  
  if dir.source_loc >= 2000 or dir.source_files.length > 15:
    → OVERVIEW
    Interface-focused. Public types and functions only.
    Point to individual files for implementation details.
    Note: orchestrator should consider if this dir should be split.
```

#### Execution Plan Output

```json
{
  "target_path": "/path/to/repo/src/core",
  "levels": [
    {
      "level": 0,
      "description": "Leaf directories — no dependencies",
      "tasks": [
        {
          "task_id": "leaf-001",
          "type": "leaf",
          "path": "src/core/engine",
          "detail_level": "standard",
          "source_files": ["mod.rs", "executor.rs", "worker.rs"],
          "source_loc": 892,
          "output": "src/core/engine/ai_doc.md"
        },
        {
          "task_id": "leaf-002",
          "type": "leaf",
          "path": "src/core/scheduler",
          "detail_level": "standard",
          "source_files": ["mod.rs", "queue.rs", "priority.rs"],
          "source_loc": 634,
          "output": "src/core/scheduler/ai_doc.md"
        }
      ]
    },
    {
      "level": 1,
      "description": "Roll-up — depends on level 0",
      "tasks": [
        {
          "task_id": "rollup-001",
          "type": "rollup",
          "path": "src/core",
          "local_source_files": ["mod.rs"],
          "child_docs": ["src/core/engine/ai_doc.md", "src/core/scheduler/ai_doc.md"],
          "output": "src/core/ai_doc.md"
        }
      ]
    },
    {
      "level": 2,
      "description": "Global synthesis — depends on all",
      "tasks": [
        {
          "task_id": "global-001",
          "type": "global",
          "all_docs": ["src/core/engine/ai_doc.md", "src/core/scheduler/ai_doc.md", "src/core/ai_doc.md"],
          "outputs": [
            ".ai-docs/OVERVIEW.md",
            ".ai-docs/ARCHITECTURE.md",
            ".ai-docs/CONVENTIONS.md",
            ".ai-docs/CONCURRENCY.md",
            ".ai-docs/ENTRY_POINTS.md",
            ".ai-docs/QUICK_REFERENCE.md"
          ]
        }
      ]
    }
  ]
}
```

### 4.4 Phase 3: Bottom-Up Generation

Execute the plan level by level. Within each level, tasks are independent and run in parallel.

#### Parallelism Rules

- **Max concurrent subagents**: 5 (more causes context/resource issues)
- **Batch within a level**: if level has >5 tasks, batch them 5 at a time
- **Cross-level**: strictly sequential — level N+1 waits for all of level N

#### Subagent Spawn

Each task is dispatched to a Codex subagent using `spawn_codex.sh` (adapted from repo-deep-research). The prompt varies by task type.

**Leaf task prompt:**
```
You are analyzing source code to produce AI-agent-friendly documentation.

TARGET DIRECTORY: {path}
FILES TO ANALYZE: {file_list}
DETAIL LEVEL: {exhaustive|standard|overview}
LANGUAGE: {detected_language}

Read every source file in this directory. Produce an `ai_doc.md` following this EXACT structure:

{leaf_ai_doc_template}

CRITICAL RULES:
- Read actual source code. Do not guess from file names.
- Document EVERY public type and function (for exhaustive/standard levels).
- For each function: preconditions, postconditions, side effects, thread safety.
- For each type: all fields with descriptions, invariants, construction patterns.
- Include real code snippets (5-15 lines) for non-trivial logic. Annotate them.
- Note all concurrency concerns: locks, atomics, shared state, ordering requirements.
- Note all error conditions and how they propagate.
- End with concrete usage examples and extension guides.

Write the output to: {output_path}
```

**Roll-up task prompt:**
```
You are synthesizing AI-agent-friendly documentation from child module docs.

TARGET DIRECTORY: {path}
CHILD DOCS TO READ: {child_doc_paths}
LOCAL SOURCE FILES (if any): {local_source_files}

Read all child ai_doc.md files. {If local source files exist: Also read the local source files.}

Produce a ROLL-UP `ai_doc.md` following this EXACT structure:

{rollup_ai_doc_template}

CRITICAL RULES:
- Do NOT repeat content from child docs. Reference them instead.
- Focus on RELATIONSHIPS between children: data flow, dependency direction, shared state.
- Identify cross-cutting patterns shared by children.
- Document the interface contract this directory exposes to the outside world.
- Note any lock ordering or concurrency rules that span children.

Write the output to: {output_path}
```

**Global synthesis task prompt:**
```
You are producing high-level AI-agent-friendly documentation for a codebase.

ALL ai_doc.md FILES: {all_doc_paths}
EXISTING PROJECT DOCS: {readme_path, architecture_docs, etc.}
BUILD FILES: {cargo_toml, package_json, etc.}

Read ALL ai_doc.md files and any existing project documentation.

Produce the following files:

1. .ai-docs/OVERVIEW.md — {overview_template}
2. .ai-docs/ARCHITECTURE.md — {architecture_template}
3. .ai-docs/CONVENTIONS.md — {conventions_template}
4. .ai-docs/CONCURRENCY.md — {concurrency_template}
5. .ai-docs/ENTRY_POINTS.md — {entry_points_template}
6. .ai-docs/QUICK_REFERENCE.md — {quick_reference_template}

CRITICAL RULES:
- Synthesize across ALL modules. Find system-wide patterns.
- ARCHITECTURE.md must include a complete dependency graph and top data flows.
- CONVENTIONS.md: detect actual patterns from the code, don't assume.
- CONCURRENCY.md: compile ALL locks, ALL shared state, define lock ordering.
- ENTRY_POINTS.md: concrete step-by-step guides for common extension tasks.
- QUICK_REFERENCE.md: the cheat sheet an AI agent reads first.

Write each file to its specified path.
```

#### Validation and Retry

After each batch completes:

```
for each task in batch:
  output_file = task.output
  
  if not exists(output_file):
    → RETRY (re-spawn subagent once)
  
  if file_size(output_file) < 200 bytes:
    → RETRY (output too small, likely failed)
  
  if contains(output_file, "# RESEARCH FAILED"):
    → RETRY with simplified prompt
  
  if RETRY also fails:
    → MANUAL: orchestrator analyzes the directory itself
    → Flag in execution log for user review
```

### 4.5 Phase 4: Post-Processing (Orchestrator)

After all subagents complete, the orchestrator does a final pass:

1. **Verify completeness**: Every planned `ai_doc.md` exists and has reasonable content.
2. **Fix cross-references**: Scan for broken references to sibling `ai_doc.md` files. (Can happen if a dir was SKIPped but a sibling references it.)
3. **Generate index**: Optionally produce a `.ai-docs/INDEX.md` listing all generated docs with their paths.
4. **Summary report**: Print a summary to the console:
   ```
   repo-processor complete:
     Target: /path/to/repo/src/core
     Generated: 12 leaf docs, 4 roll-up docs, 6 global docs
     Total subagent calls: 18 (16 succeeded, 2 retried)
     Coverage: 47/47 source files documented
     Time: 3m 42s
   ```

---

## 5. Scope Control (Path Targeting)

### 5.1 Usage

```bash
# Full repo
repo-processor /path/to/repo

# Subtree only
repo-processor /path/to/repo/src/core

# Single directory
repo-processor /path/to/repo/src/core/engine
```

### 5.2 Behavior by Scope

**Full repo** (`/path/to/repo`):
- Recon covers entire repo
- All directories classified and documented
- Full `.ai-docs/` generated at repo root

**Subtree** (`/path/to/repo/src/core`):
- Recon limited to the subtree
- Only directories under `src/core/` get `ai_doc.md`
- `.ai-docs/` generated at `src/core/.ai-docs/` (scope root)
- Note: cross-references to modules outside the scope are marked as `[external: path/to/module]` without full docs

**Single directory** (`/path/to/repo/src/core/engine`):
- No subagents needed — orchestrator does it directly (or single subagent)
- Only one leaf `ai_doc.md` generated
- No roll-ups, no `.ai-docs/` (too narrow for global docs)
- Useful for incremental regeneration of one module

### 5.3 Incremental Regeneration

When targeting a subtree that already has `ai_doc.md` files:
- Leaf docs are **regenerated** (source may have changed)
- Roll-up docs are **regenerated** (children may have changed)
- Sibling `ai_doc.md` outside the scope are **left untouched**
- Parent roll-ups above the scope are **NOT regenerated** (user must explicitly target the parent to update)

This is a simple, predictable model. No diffing or staleness detection needed.

---

## 6. Orchestrator Decision Logic

### 6.1 Small Repo Optimization

```
if total_source_files <= 20 and total_loc <= 3000:
  → SMALL REPO MODE
  → Skip subagents entirely
  → Orchestrator reads all source files directly
  → Produces all ai_doc.md and .ai-docs/ in one pass
  → Reason: subagent overhead not worth it for small codebases
```

### 6.2 Single-Dir Optimization

```
if target_path is a leaf directory (no subdirs with source):
  → SINGLE DIR MODE
  → One subagent (or orchestrator directly) produces one ai_doc.md
  → No roll-ups, no .ai-docs/
```

### 6.3 Large Directory Handling

```
if any leaf directory has source_loc > 3000 or source_files > 20:
  → Orchestrator tries to split it into logical groups:
    1. Look for sub-namespaces (e.g., files sharing a prefix)
    2. Look for class hierarchies (base class + derived classes)
    3. Look for functional grouping (all *_handler.go files)
  → Create virtual sub-tasks, each analyzing a file group
  → Combine into one ai_doc.md with sections per group
```

---

## 7. File Structure of the Skill

```
/mnt/skills/user/repo-processor/
├── SKILL.md                              # Skill entry point and instructions
├── scripts/
│   ├── recon.sh                          # Phase 1: reconnaissance (enhanced from repo-deep-research)
│   ├── plan.py                           # Phase 2: build execution plan from recon
│   ├── spawn_codex.sh                    # Subagent spawner (adapted)
│   └── validate.sh                       # Post-processing: verify outputs, fix refs
├── templates/
│   ├── leaf_prompt.md                    # Prompt template for leaf directory analysis
│   ├── rollup_prompt.md                  # Prompt template for roll-up synthesis
│   ├── global_prompt.md                  # Prompt template for .ai-docs/ synthesis
│   ├── leaf_ai_doc_template.md           # Structure template for leaf ai_doc.md
│   ├── rollup_ai_doc_template.md         # Structure template for roll-up ai_doc.md
│   └── global_docs/
│       ├── overview_template.md
│       ├── architecture_template.md
│       ├── conventions_template.md
│       ├── concurrency_template.md
│       ├── entry_points_template.md
│       └── quick_reference_template.md
└── references/
    └── design.md                         # This document
```

### 7.1 SKILL.md Responsibilities

The SKILL.md tells the orchestrator (Claude Code) how to:

1. Parse user input (target path, options)
2. Run recon
3. Run planning (or do it inline for small repos)
4. Execute the level-by-level generation loop
5. Handle errors and retries
6. Run post-processing
7. Report results

### 7.2 plan.py

A Python script that:
- Reads `recon_output.json`
- Walks the directory tree
- Classifies each directory (leaf / rollup / skip)
- Assigns detail levels
- Computes tree depth and level assignments
- Outputs `execution_plan.json`

Why Python: JSON handling, tree traversal, and the classification logic are easier in Python than bash. The orchestrator calls it once and reads the output.

---

## 8. Error Handling & Edge Cases

### 8.1 Subagent Failures
- **Timeout**: If codex hangs >5 min per task → kill and retry once
- **Empty output**: Retry with simplified prompt (fewer template sections)
- **Garbage output**: Orchestrator inspects for required headings; if missing → retry
- **Persistent failure**: Orchestrator handles the directory manually or skips with warning

### 8.2 Edge Cases
- **Symlinks**: Follow symlinks but track visited paths to avoid cycles
- **Generated code**: Detect common generated file markers (`// Code generated`, `@generated`). Document as "generated — do not modify" rather than full analysis
- **Vendored dependencies**: Detect `vendor/`, `third_party/`, `node_modules/`. Skip by default; document as external dependency
- **Binary files**: Skip (`.o`, `.so`, `.wasm`, images, etc.)
- **Very deep nesting**: Collapse pass-through directories (single-child with no source)
- **Mixed languages**: Each ai_doc.md notes the language. Templates adapt (e.g., "concurrency" section differs for Rust vs. Python)
- **Existing ai_doc.md**: Overwrite. These are generated artifacts, not hand-written docs
- **Empty directories**: Skip entirely

---

## 9. Future Enhancements (Out of Scope for V1)

- **Watch mode**: Monitor file changes, regenerate affected `ai_doc.md` files automatically
- **Diff mode**: Show what changed in `ai_doc.md` when source changes
- **Confidence scores**: Each section gets a confidence rating (high/medium/low) based on how well the subagent understood the code
- **Interactive refinement**: User can mark sections as "needs more detail" and trigger targeted regeneration
- **Multi-repo support**: Generate docs across multiple repos with cross-repo references
- **Custom templates**: User provides their own `ai_doc.md` template for project-specific sections
- **Integration with IDE**: VSCode extension that shows `ai_doc.md` alongside source files
- **.gitignore integration**: Option to auto-add generated files to .gitignore

---

## 10. Summary

`repo-processor` transforms a codebase into a hierarchy of AI-agent-friendly reference documents. The divide-and-conquer architecture ensures:

- **Scalability**: Leaf analysis parallelizes perfectly; tree depth determines total rounds
- **Quality**: Each level builds on verified child docs, not raw source code
- **Flexibility**: Target any subtree for scoped or incremental analysis
- **Usability**: An AI agent starting work in any directory immediately finds relevant, structured documentation co-located with the code

The key innovation over `repo-deep-research` is the **distributed, co-located output** combined with **bottom-up cross-referencing** — treating documentation generation as a tree reduction problem.