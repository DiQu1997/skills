#!/usr/bin/env python3
"""
live_server.py — companion server for code-review-narrative skill.

Serves the rendered review HTML and exposes a /ask endpoint that shells
out to `claude -p` or `codex exec` to answer follow-up questions about
a specific step. Answers persist in a sidecar `<basename>.followups.json`
next to the HTML.

The static HTML (rendered by render.py) still works standalone — the
server only enables an opt-in "live mode" where the page detects the
server's presence (via /__alive) and reveals a chat input.

Usage:
    python3 live_server.py <path/to/review.html> \
        [--port 8765] [--cli claude|codex] [--model <id>] \
        [--repo <repo-path>] [--bare]
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# ----- Constants ---------------------------------------------------------

DEFAULT_PORT = 8765
DEFAULT_CLI = "claude"
SUBPROCESS_TIMEOUT_S = 300  # 5 min — claude/codex can take their time

PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "followup_prompt.md"

# Resolved at server startup
_HTML_PATH: Path = None
_JSON_PATH: Path = None
_SIDECAR_PATH: Path = None
_REVIEW_DATA: dict = None
_CLI: str = DEFAULT_CLI
_CLI_BIN: str = None
_MODEL: str = None
_REPO: Path = None
_BARE: bool = False


# ----- Walkthrough key ---------------------------------------------------

def compute_walkthrough_key(metadata: dict) -> str:
    """Stable id that survives re-renders of the same review.

    Mirrors the localStorage key the page uses (djb2 over commit+target),
    but as a plain SHA-1 since we're in Python land and don't need the
    JS-compatible algorithm — the page never reads this key.
    """
    base = (metadata.get("base_commit", "") or "") + "|" \
         + (metadata.get("head_commit", "") or "") + "|" \
         + (metadata.get("title", "") or "")
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


# ----- Sidecar I/O -------------------------------------------------------

def load_sidecar() -> dict:
    if not _SIDECAR_PATH.exists():
        return {
            "schema_version": "1",
            "walkthrough_key": compute_walkthrough_key(_REVIEW_DATA["metadata"]),
            "qa": [],
        }
    try:
        with open(_SIDECAR_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[live_server] WARN: could not read sidecar {_SIDECAR_PATH}: {e}", file=sys.stderr)
        return {
            "schema_version": "1",
            "walkthrough_key": compute_walkthrough_key(_REVIEW_DATA["metadata"]),
            "qa": [],
        }
    # Mismatched key → start fresh, but keep old as .legacy.<ts>
    expected = compute_walkthrough_key(_REVIEW_DATA["metadata"])
    if data.get("walkthrough_key") and data["walkthrough_key"] != expected:
        ts = int(time.time())
        legacy = _SIDECAR_PATH.with_suffix(_SIDECAR_PATH.suffix + f".legacy.{ts}")
        try:
            shutil.move(str(_SIDECAR_PATH), str(legacy))
            print(f"[live_server] sidecar key mismatch — archived to {legacy.name}")
        except OSError:
            pass
        return {"schema_version": "1", "walkthrough_key": expected, "qa": []}
    return data


def save_sidecar_atomic(data: dict) -> None:
    tmp = _SIDECAR_PATH.with_suffix(_SIDECAR_PATH.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, _SIDECAR_PATH)


def append_qa(entry: dict) -> None:
    data = load_sidecar()
    data["qa"].append(entry)
    save_sidecar_atomic(data)


# ----- Prompt building ---------------------------------------------------

def find_step(step_id: str):
    for sl in _REVIEW_DATA.get("storylines", []):
        for st in sl.get("steps", []) or []:
            if st["id"] == step_id:
                return sl, st
    return None, None


def render_code_view(code_view: dict) -> str:
    """Render code_view's primary_changes as a readable text block."""
    parts = []
    for fv in code_view.get("primary_changes", []):
        parts.append(f"--- {fv['file']} (lines {fv['context_start_line']}–{fv['context_end_line']}, {fv['language']}) ---")
        for line in fv.get("lines", []):
            marker = "+" if line["change"] == "added" else ("-" if line["change"] == "removed" else " ")
            parts.append(f"{line['line_num']:5d} {marker} {line['content']}")
        # Walkthrough annotations on this file
        wt = fv.get("walkthrough") or []
        if wt:
            parts.append("")
            parts.append("[walkthrough annotations on this file]")
            for ann in wt:
                rng = f"L{ann['line_start']}" if ann["line_start"] == ann["line_end"] else f"L{ann['line_start']}–{ann['line_end']}"
                parts.append(f"  {rng} ({ann.get('chunk_role','')}): {ann.get('explanation','')}")
        parts.append("")
    return "\n".join(parts)


def render_step_context(storyline: dict, step: dict, prior_qas: list) -> str:
    """Build the context block fed to the LLM."""
    bd = step.get("behavior_delta") or {}
    out = []
    out.append(f"# Storyline: {storyline.get('title','')}")
    if storyline.get("change_overview"):
        out.append(f"\n## Storyline overview\n{storyline['change_overview']}")
    out.append(f"\n# Step: {step.get('title','')} ({step.get('id','')})")
    if step.get("summary"):
        out.append(f"\n## Step summary\n{step['summary']}")
    if bd.get("before") or bd.get("after") or bd.get("diff"):
        out.append("\n## Behavior delta")
        if bd.get("before"):  out.append(f"- Before: {bd['before']}")
        if bd.get("after"):   out.append(f"- After:  {bd['after']}")
        if bd.get("diff"):    out.append(f"- Diff:   {bd['diff']}")
    if step.get("evaluation"):
        out.append(f"\n## Existing evaluation\n{step['evaluation']}")
    out.append("\n## Code under discussion")
    out.append(render_code_view(step.get("code_view", {})))
    if prior_qas:
        out.append("## Prior follow-up Q&A on this step (most recent last)")
        for qa in prior_qas[-5:]:  # cap the trailing context at 5
            out.append(f"\nQ: {qa.get('question','')}")
            out.append(f"A: {qa.get('answer_markdown','')}")
    return "\n".join(out)


def load_prompt_template() -> str:
    if not PROMPT_TEMPLATE_PATH.exists():
        # Fallback inline template — keeps the server runnable even if
        # the file got deleted.
        return (
            "You are answering a follow-up question about a specific step in a code-review walkthrough.\n"
            "Answer in markdown. Be concise. Cite line numbers when relevant.\n"
            "If the question is about general syntax/grammar, answer that directly.\n\n"
            "{{CONTEXT}}\n\n"
            "## Reader's question\n{{QUESTION}}\n"
        )
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def build_prompt(step_id: str, question: str, prior_qas: list) -> str:
    storyline, step = find_step(step_id)
    if step is None:
        raise ValueError(f"unknown step_id: {step_id}")
    template = load_prompt_template()
    context = render_step_context(storyline, step, prior_qas)
    return template.replace("{{CONTEXT}}", context).replace("{{QUESTION}}", question.strip())


# ----- CLI invocation ----------------------------------------------------

def run_cli(prompt: str) -> dict:
    """Returns {ok, answer, stderr, elapsed_s}."""
    if _CLI == "claude":
        cmd = [_CLI_BIN, "-p"]
        if _BARE:
            cmd.append("--bare")
        if _MODEL:
            cmd.extend(["--model", _MODEL])
        cmd.append(prompt)
    elif _CLI == "codex":
        cmd = [_CLI_BIN, "exec"]
        if _MODEL:
            cmd.extend(["-m", _MODEL])
        cmd.append(prompt)
    else:
        return {"ok": False, "stderr": f"unknown cli: {_CLI}", "answer": "", "elapsed_s": 0}

    t0 = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT_S,
            cwd=str(_REPO) if _REPO else None,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "stderr": "subprocess timed out", "answer": "", "elapsed_s": SUBPROCESS_TIMEOUT_S}
    except (OSError, FileNotFoundError) as e:
        return {"ok": False, "stderr": f"failed to invoke {_CLI}: {e}", "answer": "", "elapsed_s": time.time() - t0}

    elapsed = time.time() - t0
    stdout = (proc.stdout or "").strip()
    stderr = (proc.stderr or "").strip()
    # Some CLI failure modes exit 0 with an error message on stdout (e.g.
    # `claude --bare` without ANTHROPIC_API_KEY prints "Not logged in" and
    # exits 0). Treat short answers that look like login errors as failures.
    KNOWN_ERROR_NEEDLES = ("Not logged in", "Please run /login", "API key not", "rate limit", "401 Unauthorized")
    if proc.returncode != 0 or (stdout and any(n.lower() in stdout.lower() for n in KNOWN_ERROR_NEEDLES) and len(stdout) < 400):
        msg = stderr if stderr else stdout
        return {"ok": False, "stderr": msg[:4000], "answer": stdout, "elapsed_s": elapsed}
    if not stdout:
        return {"ok": False, "stderr": "CLI returned empty stdout" + (f" (stderr: {stderr[:200]})" if stderr else ""), "answer": "", "elapsed_s": elapsed}
    return {"ok": True, "stderr": "", "answer": stdout, "elapsed_s": elapsed}


# ----- HTTP handler ------------------------------------------------------

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        # quieter access log
        sys.stderr.write(f"[live_server] {self.address_string()} {fmt % args}\n")

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_html(self) -> None:
        try:
            body = _HTML_PATH.read_bytes()
        except OSError as e:
            self._send_json(500, {"error": f"cannot read HTML: {e}"})
            return
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            self._send_html()
        elif path == "/__alive":
            self._send_json(200, {
                "ok": True,
                "cli": _CLI,
                "model": _MODEL,
                "bare": _BARE,
                "html": str(_HTML_PATH),
                "walkthrough_key": compute_walkthrough_key(_REVIEW_DATA["metadata"]),
            })
        elif path == "/followups":
            self._send_json(200, load_sidecar())
        else:
            self._send_json(404, {"error": "not found", "path": path})

    def do_POST(self):
        path = urlparse(self.path).path
        if path != "/ask":
            self._send_json(404, {"error": "not found", "path": path})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length > 0 else b""
            body = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError) as e:
            self._send_json(400, {"error": f"bad request body: {e}"})
            return

        step_id = body.get("step_id")
        question = (body.get("question") or "").strip()
        if not step_id or not question:
            self._send_json(400, {"error": "step_id and question are required"})
            return
        storyline, step = find_step(step_id)
        if step is None:
            self._send_json(404, {"error": f"unknown step_id: {step_id}"})
            return

        sidecar = load_sidecar()
        prior_qas = [q for q in sidecar["qa"] if q["step_id"] == step_id]
        try:
            prompt = build_prompt(step_id, question, prior_qas)
        except ValueError as e:
            self._send_json(400, {"error": str(e)})
            return

        result = run_cli(prompt)
        if not result["ok"]:
            self._send_json(502, {
                "error": "cli call failed",
                "stderr": result["stderr"],
                "elapsed_s": result["elapsed_s"],
            })
            return

        entry = {
            "id": "qa-" + uuid.uuid4().hex[:12],
            "step_id": step_id,
            "storyline_id": storyline["id"],
            "question": question,
            "answer_markdown": result["answer"],
            "asked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "cli": _CLI,
            "model": _MODEL,
            "elapsed_s": round(result["elapsed_s"], 2),
        }
        append_qa(entry)
        self._send_json(200, entry)


# ----- Bootstrap ---------------------------------------------------------

def find_review_json(html_path: Path) -> Path:
    """Convention: <name>.json next to <name>.html."""
    candidate = html_path.with_suffix(".json")
    if not candidate.exists():
        raise FileNotFoundError(
            f"expected sibling JSON next to HTML: {candidate} (the rendered HTML must "
            f"be paired with the source review JSON for the server to bundle prompt context)"
        )
    return candidate


def parse_args():
    p = argparse.ArgumentParser(description="Companion live server for code-review-narrative HTML reviews.")
    p.add_argument("html", type=Path, help="Path to the rendered review HTML.")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--cli", choices=["claude", "codex"], default=DEFAULT_CLI)
    p.add_argument("--model", default=None, help="Model id passed through to the CLI.")
    p.add_argument("--repo", type=Path, default=None, help="Working dir for the CLI subprocess (defaults to none).")
    p.add_argument("--bare", action="store_true", help="Pass --bare to claude. Requires ANTHROPIC_API_KEY env (claude --bare does not read OAuth/keychain).")
    p.add_argument("--json", type=Path, default=None, help="Override the sibling JSON path (default: <html>.json).")
    return p.parse_args()


def main():
    global _HTML_PATH, _JSON_PATH, _SIDECAR_PATH, _REVIEW_DATA
    global _CLI, _CLI_BIN, _MODEL, _REPO, _BARE

    args = parse_args()

    _HTML_PATH = args.html.resolve()
    if not _HTML_PATH.exists():
        sys.exit(f"HTML not found: {_HTML_PATH}")

    _JSON_PATH = (args.json or find_review_json(_HTML_PATH)).resolve()
    with open(_JSON_PATH, "r", encoding="utf-8") as f:
        _REVIEW_DATA = json.load(f)

    _SIDECAR_PATH = _HTML_PATH.with_suffix(".followups.json")

    _CLI = args.cli
    _CLI_BIN = shutil.which(_CLI)
    if not _CLI_BIN:
        sys.exit(f"{_CLI} not found on PATH — install it or pass --cli {('codex' if _CLI == 'claude' else 'claude')}.")
    _MODEL = args.model
    _REPO = args.repo.resolve() if args.repo else None
    _BARE = args.bare

    print(f"[live_server] HTML:     {_HTML_PATH}")
    print(f"[live_server] JSON:     {_JSON_PATH}")
    print(f"[live_server] sidecar:  {_SIDECAR_PATH}")
    print(f"[live_server] CLI:      {_CLI} ({_CLI_BIN}){' [--bare]' if _BARE else ''}")
    if _MODEL:
        print(f"[live_server] model:    {_MODEL}")
    if _REPO:
        print(f"[live_server] repo cwd: {_REPO}")
    print(f"[live_server] storylines: {len(_REVIEW_DATA.get('storylines', []))}, steps: {sum(len(s.get('steps') or []) for s in _REVIEW_DATA.get('storylines', []))}")
    print(f"[live_server] listening on http://127.0.0.1:{args.port}/   (Ctrl-C to stop)")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[live_server] shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
