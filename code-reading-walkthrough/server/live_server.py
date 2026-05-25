#!/usr/bin/env python3
"""
live_server.py — companion server for code-reading-walkthrough skill.

Serves the rendered walkthrough HTML and exposes a /ask endpoint that
shells out to `codex exec` (or `claude -p` via --cli claude) to answer
follow-up questions about a specific step. Answers persist in a sidecar
`<basename>.followups.json` next to the HTML.

The static HTML (rendered by render.py) still works standalone — the
server only enables an opt-in "live mode" where the page detects the
server's presence (via /__alive) and reveals a chat input.

Concurrency is capped (default 2 in-flight subprocesses, configurable
via --max-concurrent) and at most one question per step can be in
flight at a time. Excess requests get 429.

Usage:
    python3 live_server.py <path/to/walkthrough.html> \\
        [--port 8765] [--cli codex|claude] [--model <id>] \\
        [--repo <repo-path>] [--bare] [--max-concurrent 2]
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

# ----- Constants ---------------------------------------------------------

DEFAULT_PORT = 8765
DEFAULT_CLI = "codex"
DEFAULT_MAX_CONCURRENT = 2
SUBPROCESS_TIMEOUT_S = 300  # 5 min — codex/claude can take their time

PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "followup_prompt.md"

# Resolved at server startup
_HTML_PATH: Path = None
_JSON_PATH: Path = None
_SIDECAR_PATH: Path = None
_WALKTHROUGH_DATA: dict = None
_CLI: str = DEFAULT_CLI
_CLI_BIN: str = None
_MODEL: str = None
_REPO: Path = None
_BARE: bool = False

# Concurrency control for /ask. Initialized in main().
_ask_semaphore: threading.BoundedSemaphore = None
_max_concurrent: int = DEFAULT_MAX_CONCURRENT
_in_flight_lock = threading.Lock()
_in_flight_steps: set = set()


# ----- Walkthrough key ---------------------------------------------------

def compute_walkthrough_key(metadata: dict) -> str:
    """Stable id that survives re-renders of the same walkthrough.

    Reading-mode metadata uses commit + target (vs review-mode's
    base_commit + head_commit + title). Mirrors the localStorage
    key the page derives so the server's sidecar lines up with the
    HTML's persisted view state.
    """
    base = (metadata.get("commit", "") or "") + "|" \
         + (metadata.get("target", "") or "") + "|" \
         + (metadata.get("title", "") or "")
    return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]


# ----- Sidecar I/O -------------------------------------------------------

def load_sidecar() -> dict:
    if not _SIDECAR_PATH.exists():
        return {
            "schema_version": "1",
            "walkthrough_key": compute_walkthrough_key(_WALKTHROUGH_DATA["metadata"]),
            "qa": [],
        }
    try:
        with open(_SIDECAR_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[live_server] WARN: could not read sidecar {_SIDECAR_PATH}: {e}", file=sys.stderr)
        return {
            "schema_version": "1",
            "walkthrough_key": compute_walkthrough_key(_WALKTHROUGH_DATA["metadata"]),
            "qa": [],
        }
    # Mismatched key → start fresh, but keep old as .legacy.<ts>
    expected = compute_walkthrough_key(_WALKTHROUGH_DATA["metadata"])
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
    for sl in _WALKTHROUGH_DATA.get("storylines", []):
        for st in sl.get("steps", []) or []:
            if st["id"] == step_id:
                return sl, st
    return None, None


def _render_file_view(fv: dict, why_included: str = None) -> list:
    """Render a single FileView (primary_changes or supporting_definition).
    Returns lines (no trailing newline) ready to be joined."""
    parts = []
    header = f"--- {fv['file']} (lines {fv['context_start_line']}–{fv['context_end_line']}, {fv['language']}) ---"
    parts.append(header)
    if why_included:
        parts.append(f"[supporting definition — {why_included}]")

    fp = fv.get("function_purpose")
    if fp:
        name = fp.get("function_name") or "(unnamed block)"
        parts.append(f"[function_purpose for {name}]")
        if fp.get("structure") == "multi_section":
            for sec in fp.get("sections", []) or []:
                parts.append(f"  • L{sec.get('line_start')}–{sec.get('line_end')} {sec.get('section_name','')}: "
                             f"problem={sec.get('problem_solved','')} | without_it={sec.get('without_it','')}")
        else:
            if fp.get("problem_solved"):
                parts.append(f"  • problem_solved: {fp['problem_solved']}")
            if fp.get("without_it"):
                parts.append(f"  • without_it:     {fp['without_it']}")

    for line in fv.get("lines", []):
        # Reading mode: all lines are "unchanged" — render as plain code.
        # We still tolerate added/removed in case the same renderer ever
        # gets reused across modes.
        marker = "+" if line.get("change") == "added" else ("-" if line.get("change") == "removed" else " ")
        parts.append(f"{line['line_num']:5d} {marker} {line['content']}")

    wt = fv.get("walkthrough") or []
    if wt:
        parts.append("")
        parts.append("[walkthrough annotations on this file]")
        for ann in wt:
            rng = (f"L{ann['line_start']}" if ann["line_start"] == ann["line_end"]
                   else f"L{ann['line_start']}–{ann['line_end']}")
            parts.append(f"  {rng} ({ann.get('chunk_role','')}): {ann.get('explanation','')}")
    return parts


def render_code_view(code_view: dict) -> str:
    """Render primary_changes + supporting_definitions as a readable text block."""
    parts = []
    for fv in code_view.get("primary_changes", []) or []:
        parts.extend(_render_file_view(fv))
        parts.append("")
    sd = code_view.get("supporting_definitions") or []
    if sd:
        parts.append("## Supporting definitions (referenced by the code, not the focus)")
        for fv in sd:
            parts.extend(_render_file_view(fv, why_included=fv.get("why_included")))
            parts.append("")
    return "\n".join(parts)


def _bullets(items, prefix="- "):
    """Format a list of strings as bullets; returns lines or [] if empty."""
    return [f"{prefix}{x}" for x in items if x]


def _render_storyline_context(storyline: dict) -> list:
    """Storyline-level header: mental model, purpose, architecture,
    overview, roadmap. Reading-mode equivalent of the review version."""
    out = [f"# Storyline: {storyline.get('title','')} ({storyline.get('id','')})"]
    if storyline.get("summary"):
        out.append(f"\n_{storyline['summary']}_")

    if storyline.get("mental_model_anchor"):
        out.append(f"\n## Mental model anchor\n{storyline['mental_model_anchor']}")

    purpose = storyline.get("purpose") or {}
    if purpose.get("stated") or purpose.get("evident") or purpose.get("discrepancy"):
        out.append("\n## Purpose")
        if purpose.get("stated"):      out.append(f"- Stated:      {purpose['stated']}")
        if purpose.get("evident"):     out.append(f"- Evident:     {purpose['evident']}")
        if purpose.get("discrepancy"): out.append(f"- Discrepancy: {purpose['discrepancy']}")

    arch = storyline.get("architectural_context") or {}
    if arch.get("system_role") or arch.get("data_flow") or arch.get("involved_modules"):
        out.append("\n## Architectural context")
        if arch.get("system_role"):
            out.append(f"- System role: {arch['system_role']}")
        if arch.get("involved_modules"):
            out.append("- Involved modules:")
            for m in arch["involved_modules"]:
                out.append(f"  • {m.get('module','?')}: {m.get('role_in_storyline','')}")
        if arch.get("data_flow"):
            out.append(f"- Data flow: {arch['data_flow']}")
        diagram = arch.get("diagram") or {}
        if diagram.get("type") and diagram["type"] != "none" and diagram.get("content"):
            out.append(f"- Diagram ({diagram['type']}):")
            out.append("```")
            out.append(diagram["content"])
            out.append("```")

    if storyline.get("change_overview"):
        out.append(f"\n## Overview\n{storyline['change_overview']}")
    if storyline.get("reading_roadmap"):
        out.append(f"\n## Reading roadmap\n{storyline['reading_roadmap']}")
    return out


def _render_step_factual_context(step: dict) -> list:
    """Step-level factual context (reading-mode research-assistant fields).

    Differs from review mode by using invariants / key_data_structures /
    design_rationale in place of behavior_delta + the analytical fields.
    """
    out = []

    if step.get("invariants"):
        out.append("\n## Invariants (what must always hold here)")
        out.extend(_bullets(step["invariants"]))

    kds = step.get("key_data_structures") or []
    if kds:
        out.append("\n## Key data structures")
        for d in kds:
            name = d.get("name", "?")
            shape = d.get("shape", "")
            role = d.get("role", "")
            out.append(f"- **{name}** — {shape}")
            if role:
                out.append(f"    role: {role}")

    uc = step.get("usage_context") or {}
    has_uc = uc.get("primary_usage_scenario") or uc.get("callers") or uc.get("call_patterns") or uc.get("implicit_dependencies")
    if has_uc:
        out.append("\n## Usage context")
        if uc.get("primary_usage_scenario"):
            out.append(f"- Primary usage scenario: {uc['primary_usage_scenario']}")
        if uc.get("callers"):
            out.append("- Callers:")
            for c in uc["callers"]:
                out.append(f"  • {c.get('file','?')}:{c.get('line','?')} — {c.get('context','')}")
                if c.get("snippet"):
                    out.append(f"      `{c['snippet']}`")
        if uc.get("call_patterns"):
            out.append("- Call patterns:")
            out.extend(_bullets(uc["call_patterns"], prefix="  • "))
        if uc.get("implicit_dependencies"):
            out.append("- Implicit dependencies:")
            out.extend(_bullets(uc["implicit_dependencies"], prefix="  • "))

    cp = step.get("codebase_patterns") or {}
    similar = cp.get("similar_code_elsewhere") or cp.get("similar_changes_elsewhere") or []
    has_cp = cp.get("convention_alignment") or cp.get("deviations") or similar
    if has_cp:
        out.append("\n## Codebase patterns")
        if cp.get("convention_alignment"):
            out.append(f"- Convention alignment: {cp['convention_alignment']}")
        if cp.get("deviations"):
            out.append(f"- Deviations: {cp['deviations']}")
        if similar:
            out.append("- Similar code elsewhere:")
            for s in similar:
                out.append(f"  • {s.get('file','?')}:{s.get('line','?')} — {s.get('note','')}")

    # design_rationale supersedes review-mode's alternative_approaches;
    # tolerate both for forward-compat.
    dr = step.get("design_rationale") or step.get("alternative_approaches") or []
    if dr:
        out.append("\n## Design rationale (alternatives and trade-offs)")
        for a in dr:
            out.append(f"- ({a.get('evidence_kind','?')}) {a.get('approach','')}")
            tr = a.get("tradeoff_vs_chosen_design") or a.get("tradeoff_vs_chosen")
            if tr:
                out.append(f"    tradeoff: {tr}")

    if step.get("analysis"):
        out.append(f"\n## Analysis\n{step['analysis']}")
    return out


def render_step_context(storyline: dict, step: dict, prior_qas: list) -> str:
    """Build the context block fed to the LLM.

    Mirrors what the reader sees in the right pane: storyline-level
    mental_model_anchor/purpose/architecture/overview, step-level
    factual context (invariants, key_data_structures, usage_context,
    codebase_patterns, design_rationale, analysis), then the code block
    with walkthrough + function_purpose annotations.
    """
    out = _render_storyline_context(storyline)

    out.append(f"\n# Step: {step.get('title','')} ({step.get('id','')})")
    if step.get("summary"):
        out.append(f"\n## Step summary\n{step['summary']}")

    out.extend(_render_step_factual_context(step))

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
            "You are answering a follow-up question about a specific step in a code-reading walkthrough.\n"
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
            with _in_flight_lock:
                in_flight = sorted(_in_flight_steps)
            self._send_json(200, {
                "ok": True,
                "cli": _CLI,
                "model": _MODEL,
                "bare": _BARE,
                "html": str(_HTML_PATH),
                "walkthrough_key": compute_walkthrough_key(_WALKTHROUGH_DATA["metadata"]),
                "max_concurrent": _max_concurrent,
                "in_flight_steps": in_flight,
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

        # Gate 1: at most one in-flight question per step. Catches the
        # browser-retry-on-network-blip case and double-clicks without
        # spawning a second subprocess for the same question.
        with _in_flight_lock:
            if step_id in _in_flight_steps:
                self._send_json(429, {
                    "error": "another question is already in flight for this step",
                    "step_id": step_id,
                })
                return
            _in_flight_steps.add(step_id)

        try:
            # Gate 2: global concurrency cap. Non-blocking — excess
            # requests get an immediate 429 rather than queueing behind
            # a multi-minute subprocess.
            if not _ask_semaphore.acquire(blocking=False):
                self._send_json(429, {
                    "error": f"server is at max concurrency ({_max_concurrent}); try again in a moment",
                    "max_concurrent": _max_concurrent,
                })
                return
            try:
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
            finally:
                _ask_semaphore.release()
        finally:
            with _in_flight_lock:
                _in_flight_steps.discard(step_id)


# ----- Bootstrap ---------------------------------------------------------

def extract_embedded_json(html_path: Path) -> dict:
    """Recover WALKTHROUGH_DATA from the HTML itself.

    `render.py` injects the JSON via a literal replacement of
    `/*WALKTHROUGH_DATA_PLACEHOLDER*/` with `json.dumps(data, indent=2)`.
    The resulting block looks like `const WALKTHROUGH_DATA = { ... };` near
    the top of the embedded <script>. We find that block, un-escape the
    `</` → `<\\/` guard the renderer applies, and re-parse it as JSON.

    The closing `}` is anchored on `\n}` (a brace at column 0) because
    `json.dumps(indent=2)` always emits the outermost close-brace at the
    start of its own line, while any `};` appearing inside a JSON string
    value (e.g. a code-line being shown to the reader) is indented and
    therefore won't false-match.

    Returns the parsed dict on success; raises ValueError otherwise.
    """
    import re
    text = html_path.read_text(encoding="utf-8")
    m = re.search(r"const\s+WALKTHROUGH_DATA\s*=\s*(\{[\s\S]*?\n\})\s*;", text)
    if not m:
        raise ValueError("could not locate `const WALKTHROUGH_DATA = {...}` in HTML")
    raw = m.group(1).replace("<\\/", "</")  # un-escape the </script> guard
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"embedded WALKTHROUGH_DATA failed to parse: {e}")


def parse_args():
    p = argparse.ArgumentParser(description="Companion live server for code-reading-walkthrough HTML walkthroughs.")
    p.add_argument("html", type=Path, help="Path to the rendered walkthrough HTML.")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--cli", choices=["codex", "claude"], default=DEFAULT_CLI)
    p.add_argument("--model", default=None, help="Model id passed through to the CLI.")
    p.add_argument("--repo", type=Path, default=None, help="Working dir for the CLI subprocess (defaults to none).")
    p.add_argument("--bare", action="store_true", help="Pass --bare to claude (only meaningful with --cli claude). Requires ANTHROPIC_API_KEY env.")
    p.add_argument("--json", type=Path, default=None, help="Override the sibling JSON path (default: <html>.json).")
    p.add_argument("--max-concurrent", type=int, default=DEFAULT_MAX_CONCURRENT,
                   help=f"Max concurrent /ask subprocess calls (default {DEFAULT_MAX_CONCURRENT}). "
                        f"Excess requests get 429.")
    return p.parse_args()


def main():
    global _HTML_PATH, _JSON_PATH, _SIDECAR_PATH, _WALKTHROUGH_DATA
    global _CLI, _CLI_BIN, _MODEL, _REPO, _BARE
    global _ask_semaphore, _max_concurrent

    args = parse_args()

    _HTML_PATH = args.html.resolve()
    if not _HTML_PATH.exists():
        sys.exit(f"HTML not found: {_HTML_PATH}")

    # Locate the JSON: explicit --json wins, else sibling <name>.json,
    # else extract from the embedded const in the HTML.
    if args.json:
        _JSON_PATH = args.json.resolve()
        with open(_JSON_PATH, "r", encoding="utf-8") as f:
            _WALKTHROUGH_DATA = json.load(f)
    else:
        sibling = _HTML_PATH.with_suffix(".json")
        if sibling.exists():
            _JSON_PATH = sibling.resolve()
            with open(_JSON_PATH, "r", encoding="utf-8") as f:
                _WALKTHROUGH_DATA = json.load(f)
        else:
            try:
                _WALKTHROUGH_DATA = extract_embedded_json(_HTML_PATH)
            except ValueError as e:
                sys.exit(
                    f"No sibling JSON at {sibling}, and could not extract from HTML: {e}\n"
                    f"  Pass --json <path> if the source JSON lives elsewhere."
                )
            _JSON_PATH = None
            print(f"[live_server] no sibling JSON found — recovered WALKTHROUGH_DATA from {_HTML_PATH.name}")

    _SIDECAR_PATH = _HTML_PATH.with_suffix(".followups.json")

    _CLI = args.cli
    _CLI_BIN = shutil.which(_CLI)
    if not _CLI_BIN:
        sys.exit(f"{_CLI} not found on PATH — install it or pass --cli {('claude' if _CLI == 'codex' else 'codex')}.")
    _MODEL = args.model
    _REPO = args.repo.resolve() if args.repo else None
    _BARE = args.bare

    if args.max_concurrent < 1:
        sys.exit(f"--max-concurrent must be >= 1, got {args.max_concurrent}")
    _max_concurrent = args.max_concurrent
    _ask_semaphore = threading.BoundedSemaphore(_max_concurrent)

    print(f"[live_server] HTML:     {_HTML_PATH}")
    print(f"[live_server] JSON:     {_JSON_PATH if _JSON_PATH else '(extracted from HTML)'}")
    print(f"[live_server] sidecar:  {_SIDECAR_PATH}")
    print(f"[live_server] CLI:      {_CLI} ({_CLI_BIN}){' [--bare]' if _BARE else ''}")
    if _MODEL:
        print(f"[live_server] model:    {_MODEL}")
    if _REPO:
        print(f"[live_server] repo cwd: {_REPO}")
    print(f"[live_server] max concurrent /ask: {_max_concurrent}")
    print(f"[live_server] storylines: {len(_WALKTHROUGH_DATA.get('storylines', []))}, steps: {sum(len(s.get('steps') or []) for s in _WALKTHROUGH_DATA.get('storylines', []))}")
    print(f"[live_server] listening on http://127.0.0.1:{args.port}/   (Ctrl-C to stop)")
    print(f"[live_server] WARNING: binds loopback only — do NOT change the bind address. "
          f"/ask runs the CLI on arbitrary input; exposing this beyond 127.0.0.1 is a cost/exec risk.")

    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[live_server] shutting down")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
