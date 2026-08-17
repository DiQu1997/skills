#!/usr/bin/env python3
"""
live_server.py — companion server for code-reading-walkthrough skill.

Serves the rendered walkthrough HTML (v0.5 flow-inspector schema) and
exposes a /ask endpoint that shells out to `codex exec` (or `claude -p`
via --cli claude) to answer follow-up questions about a specific block
inside a storyline's diagram. Answers persist in a sidecar
`<basename>.followups.json` next to the HTML.

The static HTML (rendered by render.py) still works standalone — the
server only enables an opt-in "live mode" where the page detects the
server's presence (via /__alive) and reveals a chat input.

Concurrency is capped (default 2 in-flight subprocesses, configurable
via --max-concurrent) and at most one question per (storyline,block)
can be in flight at a time. Excess requests get 429.

Usage:
    python3 live_server.py <path/to/walkthrough.html> \\
        [--port 8765] [--cli codex|claude] [--model <id>] \\
        [--repo <repo-path>] [--bare] [--max-concurrent 2]
"""

import argparse
import hashlib
import json
import os
import re
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
PROMOTE_PROMPT_TEMPLATE_PATH = Path(__file__).parent / "prompts" / "promote_prompt.md"

# Resolved at server startup
_HTML_PATH: Path = None
_JSON_PATH: Path = None
_SIDECAR_PATH: Path = None
_PROMOTIONS_PATH: Path = None
_WALKTHROUGH_DATA: dict = None
_CLI: str = DEFAULT_CLI
_CLI_BIN: str = None
_MODEL: str = None
_REPO: Path = None
_BARE: bool = False

# Concurrency control. /promote shares the global semaphore with /ask
# but has its own per-storyline in-flight gate so a promotion in progress
# rejects duplicate kicks for the same storyline.
_ask_semaphore: threading.BoundedSemaphore = None
_max_concurrent: int = DEFAULT_MAX_CONCURRENT
_in_flight_lock = threading.Lock()
_in_flight_blocks: set = set()        # "storyline_id/block_id" keys (for /ask)
_in_flight_promotions: set = set()    # storyline_id keys (for /promote)


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


def _grouped_followups() -> dict:
    """Reshape sidecar's qa[] into the per-block grouped form the template
    expects: { followups: { "<storyline_id>/<col_id>/<block_id>": [ ... ] } }.
    Each entry carries (question, answer, ts) — the minimum the template
    renders. The full record stays in sidecar.qa for later inspection."""
    data = load_sidecar()
    grouped: dict = {}
    for q in data.get("qa", []) or []:
        sid = q.get("storyline_id", "")
        cid = q.get("col_id", "")
        bid = q.get("block_id", "")
        if not (sid and bid):
            continue
        key = f"{sid}/{cid}/{bid}"
        grouped.setdefault(key, []).append({
            "question": q.get("question", ""),
            "answer": q.get("answer_markdown", ""),
            "ts": q.get("asked_at", ""),
        })
    return {
        "schema_version": data.get("schema_version", "1"),
        "walkthrough_key": data.get("walkthrough_key", ""),
        "followups": grouped,
    }


# ----- Promotions sidecar -----------------------------------------------

def load_promotions() -> dict:
    """Returns { schema_version, walkthrough_key, promotions: { storyline_id: storyline } }."""
    expected = compute_walkthrough_key(_WALKTHROUGH_DATA["metadata"])
    if not _PROMOTIONS_PATH.exists():
        return {"schema_version": "1", "walkthrough_key": expected, "promotions": {}}
    try:
        with open(_PROMOTIONS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[live_server] WARN: could not read promotions {_PROMOTIONS_PATH}: {e}", file=sys.stderr)
        return {"schema_version": "1", "walkthrough_key": expected, "promotions": {}}
    if data.get("walkthrough_key") and data["walkthrough_key"] != expected:
        ts = int(time.time())
        legacy = _PROMOTIONS_PATH.with_suffix(_PROMOTIONS_PATH.suffix + f".legacy.{ts}")
        try:
            shutil.move(str(_PROMOTIONS_PATH), str(legacy))
            print(f"[live_server] promotions key mismatch — archived to {legacy.name}")
        except OSError:
            pass
        return {"schema_version": "1", "walkthrough_key": expected, "promotions": {}}
    if "promotions" not in data or not isinstance(data["promotions"], dict):
        data["promotions"] = {}
    return data


def save_promotions_atomic(data: dict) -> None:
    tmp = _PROMOTIONS_PATH.with_suffix(_PROMOTIONS_PATH.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")
    os.replace(tmp, _PROMOTIONS_PATH)


def upsert_promotion(storyline_id: str, storyline: dict) -> None:
    data = load_promotions()
    data["promotions"][storyline_id] = storyline
    save_promotions_atomic(data)


def delete_promotion(storyline_id: str) -> bool:
    data = load_promotions()
    if storyline_id not in data.get("promotions", {}):
        return False
    del data["promotions"][storyline_id]
    save_promotions_atomic(data)
    return True


def validate_promoted_storyline(s: dict, expected_id: str) -> tuple:
    """Cheap structural check. Returns (ok, error_message)."""
    if not isinstance(s, dict):
        return False, "not a JSON object"
    if s.get("id") != expected_id:
        return False, f"id mismatch: expected {expected_id!r}, got {s.get('id')!r}"
    if s.get("depth") not in (None, "full"):
        return False, f"depth must be 'full' (or omitted), got {s.get('depth')!r}"
    if not s.get("mental_model_anchor"):
        return False, "mental_model_anchor is required for full-depth storylines"
    diagram = s.get("diagram") or {}
    cols = diagram.get("cols") or []
    if not cols:
        return False, "diagram.cols must be non-empty"
    block_ids = set()
    total_blocks = 0
    for col in cols:
        if not isinstance(col, dict):
            return False, "every col must be a JSON object"
        if not col.get("id"):
            return False, "every col must have an id"
        for b in col.get("blocks") or []:
            bid = b.get("id")
            if not bid:
                return False, "every block must have an id"
            if bid in block_ids:
                return False, f"duplicate block id: {bid!r}"
            block_ids.add(bid)
            total_blocks += 1
            if not b.get("code_view") or not (b["code_view"].get("lines") or []):
                return False, f"block {bid!r} missing code_view.lines"
    if total_blocks < 3:
        return False, f"diagram must have at least 3 blocks total, got {total_blocks}"
    for e in diagram.get("edges") or []:
        if e.get("from") not in block_ids:
            return False, f"edge 'from' references unknown block: {e.get('from')!r}"
        if e.get("to") not in block_ids:
            return False, f"edge 'to' references unknown block: {e.get('to')!r}"
    scores = s.get("importance_scores") or {}
    keys = ("centrality", "conceptual_weight", "entry_point", "novelty")
    if all(k in scores for k in keys):
        expected_total = sum(int(scores[k]) for k in keys)
        if scores.get("total") != expected_total:
            return False, f"importance_scores.total ({scores.get('total')}) != sum of sub-scores ({expected_total})"
    return True, ""


# ----- Prompt building ---------------------------------------------------

def find_storyline(storyline_id: str):
    for sl in _WALKTHROUGH_DATA.get("storylines", []):
        if sl.get("id") == storyline_id:
            return sl
    return None


def find_block(storyline_id: str, block_id: str):
    """Locate (storyline, col, block) by IDs. Returns (None, None, None) if not found."""
    for sl in _WALKTHROUGH_DATA.get("storylines", []):
        if sl.get("id") != storyline_id:
            continue
        diagram = sl.get("diagram") or {}
        for col in diagram.get("cols", []) or []:
            for blk in col.get("blocks", []) or []:
                if blk.get("id") == block_id:
                    return sl, col, blk
    return None, None, None


def get_phase_label(storyline: dict, phase_id: str) -> str:
    for p in (storyline.get("diagram") or {}).get("phases", []) or []:
        if p.get("id") == phase_id:
            return p.get("label", phase_id)
    return phase_id or ""


def render_code_view(code_view: dict, block_range: str = "") -> str:
    """Render a v0.5 block code_view: a single FileView { file, language,
    context_start_line, context_end_line, lines[] }. Marks in-range lines
    with `*` so the model knows which lines the block actually covers."""
    if not code_view:
        return ""
    parts = []
    f = code_view.get("file", "?")
    lang = code_view.get("language", "")
    parts.append(f"--- {f} (lines {code_view.get('context_start_line','?')}–{code_view.get('context_end_line','?')}, {lang}) ---")
    if block_range:
        parts.append(f"[block range: {block_range}]")
    lo, hi = _parse_line_range(block_range)
    for line in code_view.get("lines", []):
        ln = line.get("line_num", 0)
        in_range = (lo is not None and lo <= ln <= hi)
        marker = "*" if in_range else " "
        parts.append(f"{ln:5d} {marker} {line.get('content','')}")
    return "\n".join(parts)


def _parse_line_range(range_str: str):
    """Parse 'L412–414' / 'L419' / '412-414' → (412, 414) or (419, 419)."""
    import re
    if not range_str:
        return None, None
    m = re.match(r"L?(\d+)(?:[–—-](\d+))?", str(range_str))
    if not m:
        return None, None
    lo = int(m.group(1))
    hi = int(m.group(2)) if m.group(2) else lo
    return lo, hi


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
    return out


def _render_block_right_panel(block: dict) -> list:
    """Render the block's right_panel fields (what the reader sees in the
    dock when they click the block). v0.5 fields: what_it_does, why_its_here,
    touches, failure_mode, plus optional invariants / key_data_structures /
    prerequisites."""
    rp = block.get("right_panel") or {}
    out = []

    if rp.get("what_it_does"):
        out.append(f"\n## What it does\n{rp['what_it_does']}")
    if rp.get("why_its_here"):
        out.append(f"\n## Why it's here\n{rp['why_its_here']}")

    touches = rp.get("touches") or []
    if touches:
        out.append("\n## Touches")
        for t in touches:
            label = t.get("label", "?")
            kind = t.get("kind", "")
            ref = t.get("block")
            line = f"- `{label}`"
            if kind:
                line += f" ({kind})"
            if ref:
                line += f" → block {ref}"
            out.append(line)

    fm = rp.get("failure_mode") or []
    if fm:
        out.append("\n## Failure mode")
        out.extend(_bullets(fm))

    inv = rp.get("invariants") or []
    if inv:
        out.append("\n## Invariants (what must always hold here)")
        out.extend(_bullets(inv))

    kds = rp.get("key_data_structures") or []
    if kds:
        out.append("\n## Key data structures")
        for d in kds:
            out.append(f"- **{d.get('name','?')}** — {d.get('shape','')}")
            if d.get("role"):
                out.append(f"    role: {d['role']}")

    prereqs = rp.get("prerequisites") or []
    if prereqs:
        out.append("\n## Prerequisites")
        for p in prereqs:
            kind = p.get("kind", "?")
            ref = p.get("reference_id", "")
            summary = p.get("summary", "")
            out.append(f"- ({kind}{(' → '+ref) if ref else ''}) {summary}")

    return out


def render_block_context(storyline: dict, col: dict, block: dict, prior_qas: list) -> str:
    """Build the context block fed to the LLM.

    Mirrors what the reader sees: storyline-level mental_model_anchor /
    purpose / architecture / overview, then the specific col + block they
    have open (the col's function description, the block's title /
    line_range / one_liner / right_panel content), then the code, then
    any prior Q&A history on this block.
    """
    out = _render_storyline_context(storyline)

    col_label = col.get("label") or col.get("function") or col.get("id", "?")
    col_desc = col.get("description") or ""
    out.append(f"\n# Block in focus: {block.get('title','?')} ({block.get('id','?')})")
    out.append(f"\n_Column:_ `{col_label}`{' — ' + col_desc if col_desc else ''}")
    out.append(f"_Phase:_ {get_phase_label(storyline, block.get('phase',''))}")
    out.append(f"_Lines:_ {block.get('line_range','?')}")
    if block.get("one_liner"):
        out.append(f"\n## Block one-liner (what the card shows)\n{block['one_liner']}")

    out.extend(_render_block_right_panel(block))

    out.append("\n## Code under discussion")
    out.append(render_code_view(block.get("code_view") or {}, block.get("line_range", "")))

    if prior_qas:
        out.append("\n## Prior follow-up Q&A on this block (most recent last)")
        for qa in prior_qas[-5:]:
            out.append(f"\nQ: {qa.get('question','')}")
            out.append(f"A: {qa.get('answer_markdown','')}")
    return "\n".join(out)


def load_prompt_template() -> str:
    if not PROMPT_TEMPLATE_PATH.exists():
        # Fallback inline template — keeps the server runnable even if
        # the file got deleted.
        return (
            "You are answering a follow-up question about a specific block in a code-reading walkthrough.\n"
            "Answer in markdown. Be concise. Cite line numbers when relevant.\n"
            "If the question is about general syntax/grammar, answer that directly.\n\n"
            "{{CONTEXT}}\n\n"
            "## Reader's question\n{{QUESTION}}\n"
        )
    return PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def build_prompt(storyline_id: str, block_id: str, question: str, prior_qas: list) -> str:
    storyline, col, block = find_block(storyline_id, block_id)
    if block is None:
        raise ValueError(f"unknown block: {storyline_id}/{block_id}")
    template = load_prompt_template()
    context = render_block_context(storyline, col, block, prior_qas)
    return template.replace("{{CONTEXT}}", context).replace("{{QUESTION}}", question.strip())


def load_promote_prompt_template() -> str:
    if not PROMOTE_PROMPT_TEMPLATE_PATH.exists():
        # Tiny inline fallback so the server still runs if the template
        # file got deleted. Real usage ships the markdown template.
        return (
            "Promote the summary storyline below to FULL depth per the v0.5-reading schema.\n"
            "Emit ONE JSON object, no surrounding prose, no markdown fences.\n\n"
            "{{CONTEXT}}\n"
        )
    return PROMOTE_PROMPT_TEMPLATE_PATH.read_text(encoding="utf-8")


def _render_promotion_context(storyline: dict) -> str:
    md = _WALKTHROUGH_DATA.get("metadata", {}) or {}
    summary = _WALKTHROUGH_DATA.get("summary", {}) or {}
    scope = _WALKTHROUGH_DATA.get("scope", {}) or {}
    other_storylines = [
        s for s in _WALKTHROUGH_DATA.get("storylines", [])
        if s.get("id") != storyline.get("id")
    ]
    out = []
    out.append("# Walkthrough being extended")
    out.append(f"- Title: {md.get('title', '?')}")
    out.append(f"- Repo: {md.get('repo', '?')}")
    out.append(f"- Topic / target: {md.get('target', '?')}")
    if summary.get("one_line"):
        out.append(f"- One-line pitch: {summary['one_line']}")
    if summary.get("description"):
        out.append(f"- Description: {summary['description']}")
    if scope.get("importance_criteria"):
        out.append(f"- Importance criteria: {scope['importance_criteria']}")

    out.append("\n# Storyline to promote to FULL depth")
    out.append(f"- id: {storyline.get('id', '?')}")
    out.append(f"- title: {storyline.get('title', '?')}")
    out.append(f"- kind: {storyline.get('kind', '?')}")
    out.append(f"- summary: {storyline.get('summary', '')}")
    out.append(f"- files_touched: {', '.join(storyline.get('files_touched', []) or [])}")
    out.append(f"- importance_scores: {json.dumps(storyline.get('importance_scores', {}))}")

    if other_storylines:
        out.append("\n# Other storylines in this walkthrough (for vocabulary / voice consistency)")
        for s in other_storylines[:8]:
            depth = "full" if s.get("depth", "full") == "full" else "summary"
            out.append(f"- {s.get('id','?')} [{depth}] {s.get('title','')}")
            anchor = s.get("mental_model_anchor")
            if anchor:
                snippet = anchor.replace("\n", " ")[:240]
                out.append(f"    anchor: {snippet}")
    return "\n".join(out)


def build_promote_prompt(storyline: dict) -> str:
    template = load_promote_prompt_template()
    context = _render_promotion_context(storyline)
    return template.replace("{{CONTEXT}}", context)


_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*\n|\n```\s*$", re.MULTILINE)


def parse_cli_json(raw: str):
    """Tolerant parser. Strips markdown fences if the LLM ignored instructions,
    then JSON-parses. Returns (data, error_message)."""
    text = (raw or "").strip()
    text = _JSON_FENCE_RE.sub("", text)
    # If there's leading prose, try to find the first '{' and parse from there
    if not text.startswith("{"):
        i = text.find("{")
        if i > 0:
            text = text[i:]
    try:
        return json.loads(text), None
    except json.JSONDecodeError as e:
        return None, str(e)


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
                in_flight_b = sorted(_in_flight_blocks)
                in_flight_p = sorted(_in_flight_promotions)
            self._send_json(200, {
                "ok": True,
                "cli": _CLI,
                "model": _MODEL,
                "bare": _BARE,
                "html": str(_HTML_PATH),
                "walkthrough_key": compute_walkthrough_key(_WALKTHROUGH_DATA["metadata"]),
                "max_concurrent": _max_concurrent,
                "in_flight_blocks": in_flight_b,
                "in_flight_promotions": in_flight_p,
            })
        elif path == "/followups":
            self._send_json(200, _grouped_followups())
        elif path == "/promotions":
            self._send_json(200, load_promotions())
        else:
            self._send_json(404, {"error": "not found", "path": path})

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/ask", "/promote", "/promote/revert"):
            self._send_json(404, {"error": "not found", "path": path})
            return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            raw = self.rfile.read(length) if length > 0 else b""
            body = json.loads(raw.decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError) as e:
            self._send_json(400, {"error": f"bad request body: {e}"})
            return

        if path == "/promote":
            self._handle_promote(body)
            return
        if path == "/promote/revert":
            self._handle_promote_revert(body)
            return

        # path == "/ask" from here on
        storyline_id = body.get("storyline_id")
        col_id = body.get("col_id")
        block_id = body.get("block_id")
        question = (body.get("question") or "").strip()
        if not storyline_id or not block_id or not question:
            self._send_json(400, {"error": "storyline_id, block_id, and question are required"})
            return
        storyline, col, block = find_block(storyline_id, block_id)
        if block is None:
            self._send_json(404, {"error": f"unknown block: {storyline_id}/{block_id}"})
            return
        # If client didn't pass col_id, recover from the resolved col so
        # the QA entry still records it.
        if not col_id:
            col_id = col.get("id", "")

        block_key = f"{storyline_id}/{block_id}"

        # Gate 1: at most one in-flight question per block. Catches the
        # browser-retry-on-network-blip case and double-clicks without
        # spawning a second subprocess for the same question.
        with _in_flight_lock:
            if block_key in _in_flight_blocks:
                self._send_json(429, {
                    "error": "another question is already in flight for this block",
                    "storyline_id": storyline_id,
                    "block_id": block_id,
                })
                return
            _in_flight_blocks.add(block_key)

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
                prior_qas = [
                    q for q in sidecar["qa"]
                    if q.get("storyline_id") == storyline_id and q.get("block_id") == block_id
                ]
                try:
                    prompt = build_prompt(storyline_id, block_id, question, prior_qas)
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
                    "storyline_id": storyline_id,
                    "col_id": col_id,
                    "block_id": block_id,
                    "question": question,
                    "answer_markdown": result["answer"],
                    "asked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "cli": _CLI,
                    "model": _MODEL,
                    "elapsed_s": round(result["elapsed_s"], 2),
                }
                append_qa(entry)
                # Return the entry in the shape the template expects: it
                # only reads `answer` and `ts`, but we include the full
                # record for completeness.
                self._send_json(200, {
                    "answer": entry["answer_markdown"],
                    "ts": entry["asked_at"],
                    **entry,
                })
            finally:
                _ask_semaphore.release()
        finally:
            with _in_flight_lock:
                _in_flight_blocks.discard(block_key)

    # --- /promote handler ---

    def _handle_promote(self, body: dict) -> None:
        storyline_id = body.get("storyline_id")
        if not storyline_id:
            self._send_json(400, {"error": "storyline_id is required"})
            return
        storyline = find_storyline(storyline_id)
        if storyline is None:
            self._send_json(404, {"error": f"unknown storyline: {storyline_id!r}"})
            return

        # Gate 1: one in-flight promotion per storyline (drop duplicate
        # double-clicks / browser retries instead of spawning a second CLI).
        with _in_flight_lock:
            if storyline_id in _in_flight_promotions:
                self._send_json(429, {
                    "error": "another promotion is in flight for this storyline",
                    "storyline_id": storyline_id,
                })
                return
            _in_flight_promotions.add(storyline_id)

        try:
            # Gate 2: global concurrency cap (shared with /ask). Non-blocking.
            if not _ask_semaphore.acquire(blocking=False):
                self._send_json(429, {
                    "error": f"server is at max concurrency ({_max_concurrent}); try again in a moment",
                    "max_concurrent": _max_concurrent,
                })
                return
            try:
                prompt = build_promote_prompt(storyline)
                result = run_cli(prompt)
                if not result["ok"]:
                    self._send_json(502, {
                        "error": "cli call failed",
                        "stderr": result["stderr"],
                        "elapsed_s": result["elapsed_s"],
                    })
                    return

                promoted, parse_err = parse_cli_json(result["answer"])
                if parse_err:
                    self._send_json(502, {
                        "error": f"CLI returned invalid JSON: {parse_err}",
                        "raw_preview": (result["answer"] or "")[:500],
                        "elapsed_s": result["elapsed_s"],
                    })
                    return

                ok, msg = validate_promoted_storyline(promoted, storyline_id)
                if not ok:
                    self._send_json(502, {
                        "error": f"promoted storyline failed validation: {msg}",
                        "raw_preview": json.dumps(promoted, ensure_ascii=False)[:600],
                        "elapsed_s": result["elapsed_s"],
                    })
                    return

                # Stamp the result so the frontend can render a "Promoted" badge.
                promoted["promoted"] = True
                promoted["depth"] = "full"
                promoted["promoted_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
                promoted["promoted_cli"] = _CLI
                promoted["promoted_model"] = _MODEL

                upsert_promotion(storyline_id, promoted)
                self._send_json(200, {
                    "storyline": promoted,
                    "elapsed_s": round(result["elapsed_s"], 2),
                })
            finally:
                _ask_semaphore.release()
        finally:
            with _in_flight_lock:
                _in_flight_promotions.discard(storyline_id)

    def _handle_promote_revert(self, body: dict) -> None:
        storyline_id = body.get("storyline_id")
        if not storyline_id:
            self._send_json(400, {"error": "storyline_id is required"})
            return
        deleted = delete_promotion(storyline_id)
        self._send_json(200, {"reverted": deleted, "storyline_id": storyline_id})


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
    global _HTML_PATH, _JSON_PATH, _SIDECAR_PATH, _PROMOTIONS_PATH, _WALKTHROUGH_DATA
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
    _PROMOTIONS_PATH = _HTML_PATH.with_suffix(".promotions.json")

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
    print(f"[live_server] promotions: {_PROMOTIONS_PATH}")
    print(f"[live_server] CLI:      {_CLI} ({_CLI_BIN}){' [--bare]' if _BARE else ''}")
    if _MODEL:
        print(f"[live_server] model:    {_MODEL}")
    if _REPO:
        print(f"[live_server] repo cwd: {_REPO}")
    print(f"[live_server] max concurrent /ask: {_max_concurrent}")
    storylines = _WALKTHROUGH_DATA.get("storylines", [])
    total_blocks = sum(
        sum(len(c.get("blocks") or []) for c in (s.get("diagram") or {}).get("cols", []) or [])
        for s in storylines
    )
    print(f"[live_server] storylines: {len(storylines)}, blocks: {total_blocks}")
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
