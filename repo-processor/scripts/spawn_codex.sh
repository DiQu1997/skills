#!/usr/bin/env bash
set -euo pipefail

REPO_PATH="${1:?Usage: spawn_codex.sh REPO_PATH PROMPT_FILE LOG_FILE}"
PROMPT_PATH="${2:?Missing prompt file}"
LOG_FILE="${3:?Missing log file}"

if [[ ! -f "$PROMPT_PATH" ]]; then
  echo "Prompt file not found: $PROMPT_PATH" >&2
  exit 2
fi

REPO_PATH="$(cd "$REPO_PATH" && pwd)"

mkdir -p "$(dirname "$LOG_FILE")"

run_codex() {
  local -a cmd=("$@")
  if "${cmd[@]}" > "$LOG_FILE.tmp" 2> "$LOG_FILE.stderr"; then
    return 0
  fi
  return 1
}

PROMPT_CONTENT="$(cat "$PROMPT_PATH")"

if run_codex codex exec --dangerously-bypass-approvals-and-sandbox -C "$REPO_PATH" "$PROMPT_CONTENT"; then
  mv "$LOG_FILE.tmp" "$LOG_FILE"
  exit 0
fi

{
  echo "# RESEARCH FAILED"
  echo "Codex subagent failed for this task. See: $LOG_FILE.stderr"
} > "$LOG_FILE"
exit 1
