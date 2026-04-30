# Research Prompt Templates

Use these templates when constructing prompts for Codex subagents.
Replace `{placeholders}` with actual values. Combine templates as needed.

## Module Deep Dive (default)

```
Analyze the module at {path}.

Research questions:
{numbered_questions}

Read all relevant source files in this module (not just the obvious ones). For each significant file, explain:
1. What it does and why it exists
2. Its key types/functions with signatures
3. How it connects to other files in this module

Then trace 2-3 primary code flows through this module from entry to exit.
Explain each flow step-by-step with file + function references, and include annotated code snippets for the most important logic (5-20 lines each).

Finally, assess size/complexity and (if needed) recommend a breakdown into sub-areas that deserve their own deep research runs.
```

## Code Flow Trace

```
Trace the complete execution flow for: {operation_description}

Starting from: {entry_point_file}:{function_name}
Expected endpoint: {where_it_ends}

For each step in the flow:
1. File and function name
2. What happens (2-3 sentences)
3. Key code snippet if the logic is non-trivial
4. What gets passed to the next step

Produce a numbered sequence showing the complete path.
Note any branching points, error handling paths, or async boundaries.
```

## Cross-Cutting Concern

```
Analyze how {concern} is handled across the codebase.

Search for all files related to {concern}. Look for:
- Centralized configuration or utilities for {concern}
- How individual modules implement/use {concern}
- Consistency or inconsistency in approach
- Any abstraction layers or middleware

Produce a summary that covers:
1. The overall strategy/pattern used
2. Key files that implement the infrastructure
3. How modules consume/integrate with it
4. Any notable deviations from the main pattern
```

## Data Model Analysis

```
Analyze the data model defined in {path}.

For each significant type/struct/class:
1. Full definition with field types
2. What real-world concept it represents
3. Invariants or constraints (validation, required fields)
4. How it's constructed (builders, constructors, factories)
5. How it's serialized/deserialized if applicable
6. Key methods and what they do

Then map the relationships between types (ownership, references, composition).
```

## API / Interface Analysis

```
Analyze the public API surface of {module_path}.

Document:
1. All exported functions/methods with signatures and brief descriptions
2. All exported types with their purpose
3. Configuration options and defaults
4. Error types and when they occur
5. Example usage patterns (from tests or docs if available)

Focus on what a consumer of this module needs to know.
```

## Architecture Comparison

```
Compare the architecture of {module_a} and {module_b}.

Analyze:
1. What problem each solves
2. The approach/pattern each uses
3. How they interact (shared dependencies, data flow)
4. Design tradeoffs: what each optimizes for
5. Any duplication or shared abstractions between them
```

## Sub-Module Identification

Use when a module is too large and needs splitting:

```
The module at {path} is large and complex. Identify its internal sub-modules.

For each distinct area of responsibility:
1. Name and purpose (2 sentences)
2. Key files belonging to this sub-area
3. Internal dependencies (which sub-areas depend on which)
4. Estimated complexity (high/medium/low)
5. Whether it deserves its own deep-dive research (full repo-deep-research rerun on that subpath)

Produce a recommended breakdown for further research.
```

## Recursive Deep Research Trigger (Orchestrator Hint)

Use when the sub-category is too large for a single subagent:

```
This area is too large for a single subagent deep dive. Propose 3-8 subpaths that each deserve a full repo-deep-research run.

For each proposed subpath:
1. Path (relative)
2. Purpose (2-4 sentences)
3. 3-5 research questions tailored to that subpath
4. What the parent report should cover vs what the nested report should cover
```

## Follow-Up Investigation

Use when initial research left gaps:

```
Previous research on {module_name} found:
{summary_of_previous_findings}

But these questions remain:
{unanswered_questions}

Investigate these specific gaps. Read the relevant source files and provide
concrete answers with code evidence. Don't repeat what's already known —
focus only on the gaps listed above.
```
