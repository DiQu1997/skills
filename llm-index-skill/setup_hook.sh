#!/bin/bash
# setup_hook.sh — Install a post-commit hook that flags stale LLMINDEX.md files
# Usage: bash setup_hook.sh <repo-path>
#
# The hook does NOT auto-regenerate (that needs an LLM).
# It prints which LLMINDEX.md files need updating so you can run the skill.

set -e

REPO="${1:-.}"

if [ ! -d "$REPO/.git" ]; then
  echo "Error: $REPO is not a git repository" >&2
  exit 1
fi

HOOK_PATH="$REPO/.git/hooks/post-commit"

# Backup existing hook if present
if [ -f "$HOOK_PATH" ]; then
  echo "Backing up existing post-commit hook to $HOOK_PATH.bak"
  cp "$HOOK_PATH" "$HOOK_PATH.bak"
fi

cat > "$HOOK_PATH" << 'HOOK'
#!/bin/bash
# LLM Code Index — post-commit staleness detector
# Installed by llm-code-index skill

# Get changed files in this commit
CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null)

if [ -z "$CHANGED_FILES" ]; then
  exit 0
fi

STALE_INDEXES=()

while IFS= read -r file; do
  # Skip if the changed file is itself an LLMINDEX or LLMREADME
  if [[ "$file" == *"LLMINDEX.md" ]] || [[ "$file" == "LLMREADME.md" ]]; then
    continue
  fi

  # Find the nearest LLMINDEX.md in the file's directory or parent
  dir=$(dirname "$file")
  while [ "$dir" != "." ] && [ "$dir" != "/" ]; do
    if [ -f "$dir/LLMINDEX.md" ]; then
      # Check if this index is already in our stale list
      if [[ ! " ${STALE_INDEXES[*]} " =~ " $dir/LLMINDEX.md " ]]; then
        STALE_INDEXES+=("$dir/LLMINDEX.md")
      fi
      break
    fi
    dir=$(dirname "$dir")
  done
done <<< "$CHANGED_FILES"

# Report stale indexes
if [ ${#STALE_INDEXES[@]} -gt 0 ]; then
  echo ""
  echo "╔══════════════════════════════════════════════╗"
  echo "║  LLM Code Index: stale indexes detected     ║"
  echo "╠══════════════════════════════════════════════╣"
  for idx in "${STALE_INDEXES[@]}"; do
    echo "║  → $idx"
  done
  echo "╠══════════════════════════════════════════════╣"
  echo "║  Run: llm-code-index update                 ║"
  echo "╚══════════════════════════════════════════════╝"
  echo ""
fi
HOOK

chmod +x "$HOOK_PATH"
echo "Installed post-commit hook at $HOOK_PATH"
echo "The hook will report stale LLMINDEX.md files after each commit."
