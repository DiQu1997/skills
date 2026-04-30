TOKEN RULES:
- Replace {{TARGET_DIR}} with the directory path relative to the scope root.
- Replace {{CHILD_DOCS}} with a newline list of child ai_doc.md paths.
- Replace {{LOCAL_SOURCE_FILES}} with a newline list of local source file names, or the word None.
- Replace {{OUTPUT_PATH}} with the absolute output path for ai_doc.md.

PROMPT:
You are a synthesis agent. Your job is to read child ai_doc.md files and produce a roll-up ai_doc.md for their parent directory.

TARGET DIRECTORY: {{TARGET_DIR}}
CHILD DOCS:
{{CHILD_DOCS}}
LOCAL SOURCE FILES:
{{LOCAL_SOURCE_FILES}}
OUTPUT PATH: {{OUTPUT_PATH}}

Read every child doc. If local source files are listed, read them as well.

You MUST write a roll-up ai_doc.md that follows this exact heading order:
1) Top-level heading containing the directory path (example: # src/core)
2) A blockquote with a 2-3 sentence summary
3) ## Sub-modules
4) ## Module Relationships
5) ## Interface Contract

Module Relationships must include these subsections in order:
- ### Dependency Graph
- ### Data Flow
- ### Shared Patterns
- ### Cross-Cutting Concerns

Interface Contract must include these subsections:
- ### Public API Surface
- ### Assumptions Made by External Callers

Required content rules:
- Do not repeat child content. Reference child docs for details.
- If local source files are present, summarize their public API in the Interface Contract section.
- Focus on interactions, dependency direction, and shared assumptions.
- Describe lock ordering or concurrency rules that span sub-modules.
- If a section has no content, write "None" on a single line.

Prohibited:
- Placeholders or ellipses in the final document.
- HTML output.

Example dependency graph format:
child-a/ --> child-b/
child-b/ --> child-c/

IMPORTANT: You must write the file using a shell command.
Use this pattern (replace content):
/bin/bash -lc 'cat <<\"EOF\" > \"{{OUTPUT_PATH}}\"
<content here>
EOF'
After writing, run: /bin/bash -lc 'ls -l \"{{OUTPUT_PATH}}\"'
