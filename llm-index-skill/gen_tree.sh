#!/bin/bash
# gen_tree.sh — Generate depth-appropriate tree for a repo
# Usage: bash gen_tree.sh <repo-path>

set -e

REPO="${1:-.}"

if [ ! -d "$REPO" ]; then
  echo "Error: $REPO is not a directory" >&2
  exit 1
fi

cd "$REPO"

# Count source files (exclude common non-source directories)
FILE_COUNT=$(find . -type f \
  -not -path '*/.git/*' \
  -not -path '*/node_modules/*' \
  -not -path '*/vendor/*' \
  -not -path '*/build/*' \
  -not -path '*/dist/*' \
  -not -path '*/__pycache__/*' \
  -not -path '*/.cache/*' \
  -not -path '*/target/*' \
  -not -name '*.pyc' \
  -not -name '.DS_Store' \
  2>/dev/null | wc -l)

# Select depth
if [ "$FILE_COUNT" -lt 50 ]; then
  DEPTH=99
elif [ "$FILE_COUNT" -lt 200 ]; then
  DEPTH=3
elif [ "$FILE_COUNT" -lt 500 ]; then
  DEPTH=2
else
  DEPTH=2
fi

echo "# File count: $FILE_COUNT → tree depth: $DEPTH"
echo ""

# Generate tree, excluding common non-source directories
if command -v tree &>/dev/null; then
  tree -L "$DEPTH" --dirsfirst \
    -I 'node_modules|vendor|build|dist|__pycache__|.cache|target|.git|.idea|.vscode' \
    --charset=ascii
else
  # Fallback: use find + sed to approximate tree output
  find . -maxdepth "$DEPTH" \
    -not -path '*/.git/*' \
    -not -path '*/node_modules/*' \
    -not -path '*/vendor/*' \
    -not -path '*/build/*' \
    -not -path '*/dist/*' \
    -not -path '*/__pycache__/*' \
    -not -path '*/.cache/*' \
    -not -path '*/target/*' \
    -not -name '.DS_Store' \
    | sort \
    | sed 's|[^/]*/|  |g'
fi

echo ""
echo "# Total source files: $FILE_COUNT"

if [ "$FILE_COUNT" -gt 500 ]; then
  OMITTED=$(find . -type d \
    \( -name 'test*' -o -name 'tests' -o -name 'spec' -o -name 'specs' \
       -o -name 'fixtures' -o -name 'testdata' -o -name '__tests__' \
       -o -name 'vendor' -o -name 'generated' -o -name 'build' \) \
    -not -path '*/.git/*' 2>/dev/null | wc -l)
  echo "# Note: $OMITTED test/vendor/build directories omitted. See per-module LLMINDEX.md."
fi
