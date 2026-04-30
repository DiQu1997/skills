CONCURRENCY.md format rules:

Required headings:
- # Concurrency Model
- ## Threading Architecture
- ## Lock Inventory
- ## Lock Ordering
- ## Async Model
- ## Shared State Catalog
- ## Gotchas & Rules

Content requirements:
- Lock Inventory: table with Lock, Type, Protects, Held By, Duration.
- Lock Ordering: numbered list.
- Async Model: runtime and rules for CPU-bound vs IO-bound work.
- Shared State Catalog: table with State, Owner, Access Pattern, Sync Mechanism.

Global rules:
- Output Markdown only.
- No placeholders or ellipses in the final document.
- If a section has no content, write "None" on a single line.
