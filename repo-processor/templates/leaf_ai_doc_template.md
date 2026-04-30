Leaf ai_doc.md format rules:

Required heading order:
1) Top-level heading with the directory path
2) Blockquote with a 2-3 sentence purpose statement
3) ## Files Overview
4) ## Key Types
5) ## Functions
6) ## Internal Logic
7) ## Concurrency Details
8) ## Dependencies
9) ## Usage Guide
10) ## Extension Guide

Files Overview:
- Table columns: File, Purpose, LOC

Key Types:
- Document every public type.
- For each type include a fields table and bullets:
  - Invariants
  - Construction
  - Thread safety
  - Serialization

Functions:
- Document every public function.
- For each function include bullets:
  - Preconditions
  - Postconditions
  - Side effects
  - Thread safety
  - Error conditions
  - Performance

Internal Logic:
- Explain non-trivial logic step-by-step.
- Include at least one 5-15 line code snippet per major algorithm.

Concurrency Details:
- Locks, lock ordering, atomics, async boundaries, shared state, hot paths.

Dependencies:
- Imports from, exported to, external dependencies.

Usage Guide:
- At least one example.

Extension Guide:
- At least two concrete workflows with numbered steps.

Global rules:
- Output Markdown only.
- No placeholders or ellipses in the final document.
- If a section has no content, write "None" on a single line.
