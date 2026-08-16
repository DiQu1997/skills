#!/usr/bin/env python3
"""serve.py — enable live per-block Q&A for a rendered Code Canvas.

Serves the canvas HTML and exposes POST /ask, which pipes the page-built
prompt to `claude -p` (or `codex exec`). The static HTML works standalone;
when served from here the page detects /__alive and switches the 「问」
button from clipboard mode to live mode. Q&A history persists in a
sidecar `<html>.qa.json` next to the HTML.

Usage:
    python3 serve.py canvas.html [--port 8340] [--cli claude|codex]
                     [--model <id>] [--repo <path>] [--cli-bin <path>]
Then open http://127.0.0.1:<port>/
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

TIMEOUT_S = 300
ERROR_NEEDLES = ("Not logged in", "Please run /login", "API key not", "rate limit", "401 Unauthorized")

ARGS = None


def run_cli(prompt: str) -> dict:
    if ARGS.cli == "claude":
        cmd = [ARGS.cli_bin or "claude", "-p"]
        if ARGS.model:
            cmd += ["--model", ARGS.model]
    else:
        cmd = [ARGS.cli_bin or "codex", "exec"]
        if ARGS.model:
            cmd += ["-m", ARGS.model]
    cmd.append(prompt)
    t0 = time.time()
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S,
                              cwd=str(ARGS.repo) if ARGS.repo else None)
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "CLI 超时"}
    except OSError as e:
        return {"ok": False, "error": f"无法启动 {cmd[0]}: {e}"}
    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    if proc.returncode != 0 or (out and len(out) < 400 and any(n.lower() in out.lower() for n in ERROR_NEEDLES)):
        return {"ok": False, "error": (err or out)[:2000]}
    if not out:
        return {"ok": False, "error": "CLI 返回为空" + (f"（stderr: {err[:200]}）" if err else "")}
    return {"ok": True, "answer": out, "elapsed_s": round(time.time() - t0, 1)}


def sidecar() -> Path:
    return ARGS.html.with_suffix(ARGS.html.suffix + ".qa.json")


def persist(record: dict) -> None:
    path = sidecar()
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    except Exception:
        data = []
    data.append(record)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        sys.stderr.write("[serve] " + fmt % args + "\n")

    def _json(self, code: int, obj: dict) -> None:
        body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.rstrip("/") in ("", "/index.html") or self.path == "/":
            body = ARGS.html.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/__alive"):
            self._json(200, {"ok": True, "html": ARGS.html.name, "cli": ARGS.cli})
        else:
            self._json(404, {"ok": False, "error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/ask"):
            return self._json(404, {"ok": False, "error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(n).decode("utf-8"))
            prompt = req["prompt"]
        except Exception as e:
            return self._json(400, {"ok": False, "error": f"bad request: {e}"})
        result = run_cli(prompt)
        if result.get("ok"):
            persist({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "card": req.get("card"),
                     "block": req.get("block"), "question": req.get("question"),
                     "answer": result["answer"]})
        self._json(200, result)


def main() -> None:
    global ARGS
    p = argparse.ArgumentParser()
    p.add_argument("html", type=Path)
    p.add_argument("--port", type=int, default=8340)
    p.add_argument("--cli", choices=["claude", "codex"], default="claude")
    p.add_argument("--model", default=None)
    p.add_argument("--repo", type=Path, default=None, help="CLI 子进程的工作目录（让它能顺手读仓库）")
    p.add_argument("--cli-bin", default=None, help="CLI 可执行文件路径覆盖（调试用）")
    ARGS = p.parse_args()
    if not ARGS.html.exists():
        sys.exit(f"{ARGS.html} 不存在——先用 render.py 渲染")
    if not ARGS.cli_bin and not shutil.which(ARGS.cli):
        sys.exit(f"{ARGS.cli} 不在 PATH 上")
    print(f"serving {ARGS.html} at http://127.0.0.1:{ARGS.port}/  (cli: {ARGS.cli})")
    ThreadingHTTPServer(("127.0.0.1", ARGS.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
