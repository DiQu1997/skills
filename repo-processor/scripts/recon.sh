#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $# -lt 2 ]]; then
  echo "Usage: recon.sh TARGET_PATH OUTPUT_JSON [--skip-dirs DIRS] [--skip-generated true|false]" >&2
  exit 2
fi

exec python3 "$SCRIPT_DIR/recon.py" "$@"
