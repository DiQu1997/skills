#!/usr/bin/env bash
# spawn_codex.sh - Spawn a Codex CLI subagent for module-level research
#
# Usage: bash spawn_codex.sh <repo-path> <prompt> <output-file> [focus-path]
#
# Arguments:
#   repo-path   - Path to the repository root
#   prompt      - Research prompt/instructions for the subagent
#   output-file - Where to write the subagent's research output
#   focus-path  - (Optional) Subdirectory to focus on within the repo
#
# The script wraps the prompt with structured output instructions and
# invokes codex CLI in non-interactive mode.

set -euo pipefail

REPO_PATH="${1:?Usage: spawn_codex.sh <repo-path> <prompt> <output-file> [focus-path]}"
PROMPT_RAW="${2:?Missing research prompt}"
OUTPUT_FILE="${3:?Missing output file path}"
FOCUS_PATH="${4:-}"

# Resolve paths
REPO_PATH="$(cd "$REPO_PATH" && pwd)"

# Allow passing a prompt file by prefixing with "@", e.g. "@/path/to/prompt.txt"
PROMPT="$PROMPT_RAW"
if [[ "$PROMPT_RAW" == @* ]]; then
    PROMPT_PATH="${PROMPT_RAW#@}"
    if [[ -f "$PROMPT_PATH" ]]; then
        PROMPT="$(cat "$PROMPT_PATH")"
    else
        echo "Prompt file not found: $PROMPT_PATH" >&2
        exit 2
    fi
fi

# Build the full prompt with structured output instructions
FULL_PROMPT="You are a code research analyst. You are researching a code repository located at: $REPO_PATH
$([ -n "$FOCUS_PATH" ] && echo "Focus your analysis on: $FOCUS_PATH")

RESEARCH TASK:
$PROMPT

OUTPUT FORMAT - Structure your response EXACTLY as follows:

## Module Overview
Brief 4-6 sentence summary of what this module/component does, why it exists, and what it is responsible for (and NOT responsible for).

## Key Files
List the 8-15 most important files with one-line descriptions (include paths).

## Core Data Structures
Describe the primary types, structs, classes, or interfaces.
Include actual type definitions (or key fields/method signatures) where they are central to understanding.
Explain invariants and how instances are created/validated.

## Core Logic & Algorithms
Explain the main algorithms, processing pipelines, or business logic.
Include annotated code snippets for non-obvious logic and include the surrounding function signature.

## Code Flow
Trace 2-3 primary execution path(s) through this module. Show how data enters, transforms, and exits.
Prefer a numbered, step-by-step walkthrough with file/function references per step.

## Edge Cases & Failure Modes
List important edge cases, validation points, and error-handling paths. Include at least 2 concrete examples (with code evidence).

## Tests & Guarantees
Explain what tests exist for this area (unit/integration/e2e), what they assert, and what behavior is implicitly relied upon but not tested.

## Design Patterns & Techniques
Identify specific patterns used (e.g., visitor, builder, actor model, event sourcing). Explain WHY they were chosen.

## Dependencies & Interfaces
How this module connects to other parts of the codebase. What it exports, what it imports.

## Interesting Implementation Details
Non-obvious tricks, optimizations, or clever solutions. Things a developer would say 'oh that's neat' about.

## Size & Complexity Assessment
Estimate: number of relevant source files, approximate LOC, and the main reasons this area is complex.
Explicitly answer: is this too large for a single subagent deep dive?

## Suggested Recursive Deep Research
If this is too large, propose 3-8 sub-areas (subpaths) that deserve their own *full* repo-deep-research run.
For each suggested sub-area: path, purpose, and 3-5 research questions tailored to that sub-area.

## Open Questions
Anything unclear that would benefit from further investigation.

## AUTOPLAN
Emit a machine-readable JSON block wrapped in tags EXACTLY like this:
<AUTOPLAN_JSON>
{...}
</AUTOPLAN_JSON>

GUIDELINES:
- Read actual source files, don't guess from names alone
- Include real code snippets (5-20 lines) for key logic, annotated with comments
- Explain the WHY behind design decisions, not just the WHAT, and make the reasoning explicit
- If you find something surprising or non-obvious, highlight it
- Be specific: use actual function names, type names, and file paths
- If the module is large, prioritize mapping responsibilities, boundaries, and the most important flows; then propose a research breakdown
- Depth target: aim for a comprehensive sub-report (often 1,200-2,500+ words) rather than a short summary

**Extra points(include but not limited to these points)**
For AI agents:
- You should find the code flow for the agent, and key prompt it's using and analyze the pattern of prompt
- You should find how it managed the context, how it does the context engineer
- How does the agent manage its memory if there is any memory management system

For Server:
- Understand the key business or key services that the server provides.
- Based on the main goal it provided, trace down the requests and reply code path end to end
- Decompose the server structure and explain the key components in detail"

# Create output directory if needed
mkdir -p "$(dirname "$OUTPUT_FILE")"

echo "Researching: ${FOCUS_PATH:-$REPO_PATH} -> $OUTPUT_FILE"

run_codex() {
    local -a cmd=("$@")
    local run_log="${OUTPUT_FILE}.run.log"

    if "${cmd[@]}" > "$run_log" 2> "$OUTPUT_FILE.stderr"; then
        if [ ! -s "$OUTPUT_FILE.tmp" ]; then
            echo "Codex did not write output file: $OUTPUT_FILE.tmp" >&2
            return 1
        fi
        return 0
    else
        local exit_code=$?
        echo "Codex command failed with exit code $exit_code: ${cmd[*]}" >&2
        if [ -s "$OUTPUT_FILE.stderr" ]; then
            echo "--- codex stderr (first 160 lines) ---" >&2
            sed -n '1,160p' "$OUTPUT_FILE.stderr" >&2
            echo "--- end codex stderr ---" >&2
        fi
        return "$exit_code"
    fi
}

# Prefer modern non-interactive invocation. Keep a fallback without --full-auto.
if run_codex codex exec --dangerously-bypass-approvals-and-sandbox -o "$OUTPUT_FILE.tmp" -C "$REPO_PATH" "$FULL_PROMPT"; then
    mv "$OUTPUT_FILE.tmp" "$OUTPUT_FILE"
    echo "Complete: $OUTPUT_FILE"
elif run_codex codex exec --dangerously-bypass-approvals-and-sandbox -o "$OUTPUT_FILE.tmp" -C "$REPO_PATH" "$FULL_PROMPT"; then
    mv "$OUTPUT_FILE.tmp" "$OUTPUT_FILE"
    echo "Complete: $OUTPUT_FILE"
else
    echo "Failed: $OUTPUT_FILE (codex subagent returned non-zero)"
    echo "# RESEARCH FAILED" > "$OUTPUT_FILE"
    echo "Codex subagent failed for this module. Needs manual research or retry." >> "$OUTPUT_FILE"
    echo "See $OUTPUT_FILE.stderr for command stderr." >> "$OUTPUT_FILE"
    exit 1
fi
