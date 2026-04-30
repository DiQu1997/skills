#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -lt 1 ]]; then
  echo "Usage: repo_processor.sh TARGET_PATH [options]" >&2
  exit 2
fi

exec python3 "$SCRIPT_DIR/repo_processor.py" "$@"
