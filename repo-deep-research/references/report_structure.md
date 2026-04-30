# Report Structure Guide

The final report should read like a professor's lecture: it teaches the reader how the
codebase works, why decisions were made, and what they can learn from it. Adapt sections
as needed — not every repo needs every section.

## Template

```markdown
# Deep Research Report: {repo_name}

> {One-paragraph executive summary: what this project does, its core insight,
> and why it's worth studying. Written for someone who has never seen the repo.}

## How to Read This Report
{Explain the structure in 5-8 sentences. Tell the reader:
- Where the architecture map is
- Where the module map is
- Where the key end-to-end flows are
- How to use nested subreports (if present) for deep dives on large subsystems}

## Table of Contents
{Auto-generated from sections}

---

## 1. Project Overview

### What It Does
{2-3 paragraphs explaining the project's purpose in plain language.
What problem does it solve? Who uses it? What's the core value proposition?}

### Key Insight / Core Idea
{The fundamental architectural or algorithmic insight that makes this project
work. This is the "aha moment" — the thing that, once understood, makes
everything else click. 1-2 paragraphs.}

### Technology Stack
{Table or brief list: languages, frameworks, key dependencies, and WHY
each was chosen if apparent.}

---

## 2. Architecture Overview

### High-Level Architecture
{Describe the system's major components and how they interact.
Include an ASCII diagram if it helps:}

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│  Client   │────▶│  Router  │────▶│  Engine  │
└──────────┘     └──────────┘     └─────┬────┘
                                        │
                                   ┌────▼────┐
                                   │  Store  │
                                   └─────────┘
```

### Module Map
{List each major module with 1-2 sentence description and its role
in the overall architecture. This is the reader's navigation guide.}

### Data Flow
{How data moves through the system from input to output.
Trace the "happy path" for the most common operation, step-by-step, with file/function anchors.}

---

## 3. Core Modules (Deep Dives)

{One subsection per major module. Order by importance, not alphabetically.}

### 3.x {Module Name}

#### Purpose & Responsibility
{What this module owns. What it does NOT do (boundaries).}

#### Key Files
| File | Purpose |
|------|---------|
| `path/to/file.rs` | Brief description |

#### Core Data Structures
{The types that define this module's domain. Include actual definitions
with annotations:}

```{lang}
// The central type that represents {concept}.
// Fields are ordered by {rationale}.
struct Widget {
    id: WidgetId,          // Globally unique, assigned at creation
    state: WidgetState,    // FSM: Created → Active → Retired
    config: Arc<Config>,   // Shared config, never mutated after init
}
```

#### How It Works
{Prose explanation of the module's core logic. Walk through the algorithm
or processing pipeline step by step. Include code snippets for non-obvious
parts, annotated with explanations.}

#### Design Decisions & Tradeoffs
{Why was it built this way? What alternatives exist? What does this
approach optimize for, and what does it sacrifice?}

---

## 4. Key Code Flows

{For the 3-5 most important operations, trace the complete path.}

### 4.x {Operation Name} (e.g., "Processing an Incoming Request")

**Entry point**: `file.rs:handle_request()` (line ~42)

**Step-by-step flow:**

1. **Request parsing** (`router/parse.rs:parse()`)
   - Deserializes the raw bytes into a `Request` struct
   - Validates required fields, returns `ParseError` on failure
   ```{lang}
   // Key validation logic
   {annotated snippet}
   ```

2. **Routing** (`router/dispatch.rs:dispatch()`)
   - Matches request type to handler using {pattern}
   - {explanation}

3. **Processing** (`engine/process.rs:execute()`)
   - {explanation with snippets}

4. **Response** (`router/respond.rs:build_response()`)
   - {explanation}

**Error paths**: {Brief description of what happens when things go wrong}

**Why this flow is structured this way**: {Explain the design decisions that create this flow: boundaries, ownership, async model, layering.}

---

## 5. Design Patterns & Techniques

{Catalog of notable patterns found in the codebase. Explain each in
terms of: what it is, where it's used, and what benefit it provides.}

### 5.x {Pattern Name}

**Where**: {files/modules where this pattern appears}
**What**: {Brief explanation of the pattern}
**Why**: {What problem it solves in this codebase}
**Example**:
```{lang}
{Representative code snippet}
```

---

## 6. Cross-Cutting Concerns

{How the codebase handles infrastructure-level concerns.}

### Error Handling
{Strategy, error types, propagation patterns}

### Configuration
{How config is loaded, structured, and distributed}

### Testing Strategy
{Test organization, key testing patterns, coverage approach}

### Performance Considerations
{Optimizations, caching strategies, hot paths}

---

## 7. Lessons & Takeaways

### What Makes This Codebase Good
{Specific strengths worth emulating in other projects}

### Techniques Worth Learning
{Specific techniques a developer could adopt from studying this code}

### Potential Improvements
{Constructive observations about areas that could be stronger.
Frame diplomatically — this is educational, not a code review.}

---

## Appendix: Nested Subreports (Optional)
{If the repo is large, list any nested deep research reports for huge sub-systems, and explain in 2-3 sentences each what extra detail the nested report provides.}

---

## Appendix: File Reference

{Quick-reference table of all significant files discussed in the report.}

| File | Module | Purpose |
|------|--------|---------|
| `src/main.rs` | entry | Application entry point |
| ... | ... | ... |
```

## Adaptation Guidelines

- **Small repos (<20 files)**: Collapse modules section, focus on code flows
- **Library repos**: Emphasize API surface, usage patterns, and design philosophy
- **Framework repos**: Focus on extension points, plugin architecture, lifecycle
- **Infrastructure repos**: Emphasize operational aspects, deployment, reliability patterns
- **Algorithm-heavy repos**: Expand technique section, include complexity analysis
- **Multi-service repos**: Add service interaction diagrams, API contracts between services
