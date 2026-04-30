#!/usr/bin/env bash
# recon.sh - Gather repository metadata for research planning
# Usage: bash recon.sh <repo-path> [output-file]
#
# Produces a structured markdown file with repo overview data.

set -euo pipefail

REPO_PATH="${1:?Usage: recon.sh <repo-path> [output-file]}"
OUTPUT="${2:-recon_output.md}"

# Resolve absolute path
REPO_PATH="$(cd "$REPO_PATH" && pwd)"
REPO_NAME="$(basename "$REPO_PATH")"

cat > "$OUTPUT" <<EOF
# Reconnaissance Report: $REPO_NAME

**Path**: $REPO_PATH
**Generated**: $(date -u +"%Y-%m-%d %H:%M:%S UTC")

---

## 1. Directory Structure (depth 3)

\`\`\`
EOF

# Tree with gitignore respect, or fallback to find
if command -v tree &>/dev/null; then
    (cd "$REPO_PATH" && tree -L 3 -I 'node_modules|.git|__pycache__|.venv|venv|dist|build|.tox|.mypy_cache|.pytest_cache|target' --dirsfirst 2>/dev/null || true) >> "$OUTPUT"
else
    (cd "$REPO_PATH" && find . -maxdepth 3 \
        -not -path './.git/*' \
        -not -path '*/node_modules/*' \
        -not -path '*/__pycache__/*' \
        -not -path '*/.venv/*' \
        -not -path '*/target/*' \
        -not -path '*/dist/*' \
        -not -path '*/build/*' \
        | sort) >> "$OUTPUT"
fi

cat >> "$OUTPUT" <<'EOF'
```

## 2. Language / File Type Breakdown

EOF

# Count files by extension
echo '```' >> "$OUTPUT"
(cd "$REPO_PATH" && find . -type f \
    -not -path './.git/*' \
    -not -path '*/node_modules/*' \
    -not -path '*/__pycache__/*' \
    -not -path '*/.venv/*' \
    -not -path '*/target/*' \
    | sed 's/.*\.//' | sort | uniq -c | sort -rn | head -30 || true) >> "$OUTPUT"
echo '```' >> "$OUTPUT"

# Total file count
TOTAL_FILES=$(cd "$REPO_PATH" && find . -type f \
    -not -path './.git/*' \
    -not -path '*/node_modules/*' \
    -not -path '*/__pycache__/*' \
    -not -path '*/.venv/*' \
    -not -path '*/target/*' \
    | wc -l)
echo "" >> "$OUTPUT"
echo "**Total files**: $TOTAL_FILES" >> "$OUTPUT"

# Total lines of code (rough)
echo "" >> "$OUTPUT"
echo "**Approximate lines of code**:" >> "$OUTPUT"
echo '```' >> "$OUTPUT"
if command -v cloc &>/dev/null; then
    (cd "$REPO_PATH" && cloc --quiet --hide-rate . 2>/dev/null | tail -20) >> "$OUTPUT"
else
    # Fallback: count lines in common source extensions
    for ext in py rs go js ts tsx jsx java c cpp h hpp rb php cs swift kt scala; do
        count=$(cd "$REPO_PATH" && find . -type f -name "*.$ext" \
            -not -path './.git/*' \
            -not -path '*/node_modules/*' \
            -not -path '*/target/*' \
            -exec cat {} + 2>/dev/null | wc -l)
        if [ "$count" -gt 0 ]; then
            printf "  .%-8s %s lines\n" "$ext" "$count" >> "$OUTPUT"
        fi
    done
fi
echo '```' >> "$OUTPUT"

cat >> "$OUTPUT" <<'EOF'

## 3. Top 20 Largest Source Files

```
EOF

(cd "$REPO_PATH" && find . -type f \
    -not -path './.git/*' \
    -not -path '*/node_modules/*' \
    -not -path '*/__pycache__/*' \
    -not -path '*/.venv/*' \
    -not -path '*/target/*' \
    -not -path '*/dist/*' \
    \( -name '*.py' -o -name '*.rs' -o -name '*.go' -o -name '*.js' -o -name '*.ts' \
       -o -name '*.tsx' -o -name '*.jsx' -o -name '*.java' -o -name '*.c' -o -name '*.cpp' \
       -o -name '*.h' -o -name '*.hpp' -o -name '*.rb' -o -name '*.php' -o -name '*.cs' \
       -o -name '*.swift' -o -name '*.kt' -o -name '*.scala' -o -name '*.ex' -o -name '*.exs' \) \
    -exec wc -l {} + 2>/dev/null | sort -rn | head -21 || true) >> "$OUTPUT"

cat >> "$OUTPUT" <<'EOF'
```

## 4. README Content (first 200 lines)

```markdown
EOF

# Find README (case insensitive)
README_FILE=$(cd "$REPO_PATH" && find . -maxdepth 1 -iname 'readme*' -type f | head -1)
if [ -n "$README_FILE" ]; then
    (cd "$REPO_PATH" && head -200 "$README_FILE") >> "$OUTPUT"
else
    echo "(No README found)" >> "$OUTPUT"
fi

cat >> "$OUTPUT" <<'EOF'
```

## 5. Package / Dependency Configuration

EOF

# Check for common package manager files
PKG_FILES=(
    "package.json"
    "Cargo.toml"
    "go.mod"
    "pyproject.toml"
    "setup.py"
    "setup.cfg"
    "requirements.txt"
    "Pipfile"
    "pom.xml"
    "build.gradle"
    "build.gradle.kts"
    "Gemfile"
    "mix.exs"
    "composer.json"
    "CMakeLists.txt"
    "Makefile"
)

found_any=false
for pf in "${PKG_FILES[@]}"; do
    if [ -f "$REPO_PATH/$pf" ]; then
        found_any=true
        echo "### $pf" >> "$OUTPUT"
        echo '```' >> "$OUTPUT"
        head -80 "$REPO_PATH/$pf" >> "$OUTPUT"
        echo '```' >> "$OUTPUT"
        echo "" >> "$OUTPUT"
    fi
done

if [ "$found_any" = false ]; then
    echo "(No standard package manager files found)" >> "$OUTPUT"
fi

cat >> "$OUTPUT" <<'EOF'

## 6. Entry Points and Configuration

EOF

# Look for common entry point patterns
ENTRY_PATTERNS=(
    "main.py" "app.py" "server.py" "index.py" "__main__.py"
    "main.rs" "lib.rs"
    "main.go" "cmd/"
    "index.js" "index.ts" "app.js" "app.ts" "server.js" "server.ts"
    "Main.java" "Application.java"
    "Program.cs"
)

echo "**Detected entry points:**" >> "$OUTPUT"
echo '```' >> "$OUTPUT"
for pattern in "${ENTRY_PATTERNS[@]}"; do
    results=$(cd "$REPO_PATH" && find . -name "$pattern" \
        -not -path './.git/*' \
        -not -path '*/node_modules/*' \
        -not -path '*/target/*' \
        -not -path '*/__pycache__/*' \
        2>/dev/null)
    if [ -n "$results" ]; then
        echo "$results" >> "$OUTPUT"
    fi
done
echo '```' >> "$OUTPUT"

# Look for CI/CD config
echo "" >> "$OUTPUT"
echo "**CI/CD Configuration:**" >> "$OUTPUT"
echo '```' >> "$OUTPUT"
CI_FILES=(
    ".github/workflows"
    ".gitlab-ci.yml"
    "Jenkinsfile"
    ".circleci"
    ".travis.yml"
    "Dockerfile"
    "docker-compose.yml"
    "docker-compose.yaml"
)
for cf in "${CI_FILES[@]}"; do
    if [ -e "$REPO_PATH/$cf" ]; then
        echo "  Found: $cf" >> "$OUTPUT"
    fi
done
echo '```' >> "$OUTPUT"

cat >> "$OUTPUT" <<'EOF'

## 7. Top-Level Module Summary

EOF

# List top-level directories with file counts
echo '```' >> "$OUTPUT"
(cd "$REPO_PATH" && for dir in */; do
    if [[ "$dir" != ".git/" && "$dir" != "node_modules/" && "$dir" != "__pycache__/" && "$dir" != "target/" && "$dir" != ".venv/" && "$dir" != "venv/" ]]; then
        count=$(find "$dir" -type f \
            -not -path '*/.git/*' \
            -not -path '*/node_modules/*' \
            -not -path '*/__pycache__/*' \
            2>/dev/null | wc -l)
        printf "  %-40s %4d files\n" "$dir" "$count"
    fi
done) >> "$OUTPUT"
echo '```' >> "$OUTPUT"

echo "" >> "$OUTPUT"
echo "---" >> "$OUTPUT"
echo "*Recon complete. Use this data to create the initial research plan.*" >> "$OUTPUT"

echo "✅ Recon report written to: $OUTPUT"
