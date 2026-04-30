Roll-up ai_doc.md format rules:

Required heading order:
1) Top-level heading with the directory path
2) Blockquote with a 2-3 sentence summary
3) ## Sub-modules
4) ## Module Relationships
5) ## Interface Contract

Sub-modules:
- Table columns: Directory, Purpose, Key Type

Module Relationships must include these subsections in order:
- ### Dependency Graph
- ### Data Flow
- ### Shared Patterns
- ### Cross-Cutting Concerns

Interface Contract must include:
- ### Public API Surface
- ### Assumptions Made by External Callers

If local source files exist:
- Summarize local public API in the Interface Contract section.

Global rules:
- Output Markdown only.
- No placeholders or ellipses in the final document.
- If a section has no content, write "None" on a single line.
