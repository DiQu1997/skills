#!/usr/bin/env python3
"""
live_review.py — open a rendered review HTML with live-mode Q&A enabled.

Detects whether a companion live_server.py is already serving the given
HTML. If yes, just opens the browser. If no, starts the server in the
background (detached from this process), waits for /__alive, and then
opens the browser.

Usage:
    python3 live_review.py <path/to/review.html>           # start (or reuse) and open browser
    python3 live_review.py <html> --no-open                # just start, don't open
    python3 live_review.py --status                        # list running live servers
    python3 live_review.py --stop                          # stop all live-review servers
    python3 live_review.py --stop <html>                   # stop the one serving <html>

The server is detached via `start_new_session=True` so it survives this
script exiting. Stop it via `--stop` or just kill the PID. PID + log
files live under /tmp/live-review-<port>.{pid,log}.
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

LIVE_SERVER = Path(__file__).parent / "live_server.py"
PID_DIR = Path("/tmp")
DEFAULT_PORT = 8765
PORT_RANGE = range(8765, 8776)  # try 11 ports
ALIVE_TIMEOUT_S = 0.5
START_WAIT_S = 8.0


def alive(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/__alive", timeout=ALIVE_TIMEOUT_S) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return None


def pid_file(port): return PID_DIR / f"live-review-{port}.pid"
def log_file(port): return PID_DIR / f"live-review-{port}.log"


def start_in_background(html, port, cli, model, repo, bare, max_concurrent):
    if not LIVE_SERVER.exists():
        sys.exit(f"live_server.py not found at {LIVE_SERVER}")
    cmd = [sys.executable, "-u", str(LIVE_SERVER), str(html), "--port", str(port), "--cli", cli]
    if model: cmd.extend(["--model", model])
    if repo:  cmd.extend(["--repo", str(repo)])
    if bare:  cmd.append("--bare")
    if max_concurrent is not None:
        cmd.extend(["--max-concurrent", str(max_concurrent)])
    log = open(log_file(port), "w", encoding="utf-8")
    kwargs = {"stdout": log, "stderr": subprocess.STDOUT, "stdin": subprocess.DEVNULL}
    if os.name == "posix":
        # Detach from this script's process group so the server keeps
        # running after we exit.
        kwargs["start_new_session"] = True
    else:
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    proc = subprocess.Popen(cmd, **kwargs)
    pid_file(port).write_text(str(proc.pid))
    return proc.pid


def wait_for_alive(port, timeout=START_WAIT_S):
    deadline = time.time() + timeout
    while time.time() < deadline:
        info = alive(port)
        if info: return info
        time.sleep(0.1)
    return None


def find_free_port(preferred):
    """Return preferred if free, else the next free port in the range, else None."""
    if alive(preferred) is None:
        return preferred
    for p in PORT_RANGE:
        if p == preferred:
            continue
        if alive(p) is None:
            return p
    return None


def find_existing_for(html_path):
    """Return (port, info) of an already-running server serving this HTML, or (None, None)."""
    target = str(html_path.resolve())
    for port in PORT_RANGE:
        info = alive(port)
        if info and info.get("ok") and info.get("html") == target:
            return port, info
    return None, None


def cmd_start(args):
    html = args.html.resolve()
    if not html.exists():
        sys.exit(f"HTML not found: {html}")

    # 1. Already running for this exact HTML? Reuse.
    existing_port, existing_info = find_existing_for(html)
    if existing_port is not None:
        url = f"http://127.0.0.1:{existing_port}/"
        print(f"[live-review] reusing existing server on port {existing_port} (cli={existing_info.get('cli')})")
        print(f"[live-review] open: {url}")
        if not args.no_open:
            webbrowser.open(url)
        return

    # 2. Pick a port: requested port if free, else any free port in the range.
    port = find_free_port(args.port)
    if port is None:
        sys.exit(f"all ports in {min(PORT_RANGE)}–{max(PORT_RANGE)} are in use; try --status / --stop")

    if port != args.port:
        print(f"[live-review] port {args.port} busy with another file; using {port} instead")

    # 3. Start the server in the background.
    pid = start_in_background(html, port, args.cli, args.model, args.repo, args.bare, args.max_concurrent)
    info = wait_for_alive(port)
    if info is None:
        sys.exit(
            f"server (pid {pid}) on port {port} did not respond to /__alive within {START_WAIT_S}s.\n"
            f"  Check logs: {log_file(port)}"
        )

    url = f"http://127.0.0.1:{port}/"
    print(f"[live-review] started server pid={pid} on port {port} (cli={info.get('cli')})")
    print(f"[live-review] log: {log_file(port)}")
    print(f"[live-review] open: {url}")
    if not args.no_open:
        webbrowser.open(url)


def cmd_status(args):
    found = []
    for port in PORT_RANGE:
        info = alive(port)
        if info:
            found.append((port, info))
    if not found:
        print("(no live-review servers running on ports {}–{})".format(min(PORT_RANGE), max(PORT_RANGE)))
        return
    print(f"{'port':<6} {'cli':<7} html")
    for port, info in found:
        html = Path(info.get("html", "?")).name
        print(f"{port:<6} {(info.get('cli') or '?'):<7} {html}")


def cmd_stop(args):
    target = args.html.resolve() if args.html else None
    stopped = 0
    for port in PORT_RANGE:
        info = alive(port)
        if not info:
            # Clean up stale pid file if present
            pf = pid_file(port)
            if pf.exists():
                try: pf.unlink()
                except OSError: pass
            continue
        if target and info.get("html") != str(target):
            continue
        pf = pid_file(port)
        pid = None
        if pf.exists():
            try: pid = int(pf.read_text().strip())
            except (OSError, ValueError): pass
        if pid is not None:
            try:
                os.kill(pid, signal.SIGTERM)
                pf.unlink()
                stopped += 1
                print(f"[live-review] stopped pid={pid} on port {port}")
                continue
            except ProcessLookupError:
                pf.unlink()
            except OSError as e:
                print(f"[live-review] could not signal pid={pid}: {e}", file=sys.stderr)
        # Fallback: no pid file (rare) — we know it's alive but can't target it
        print(f"[live-review] port {port} has a server but no pid file at {pf}; skipping")
    if stopped == 0:
        if target:
            print(f"(no live-review server found serving {target})")
        else:
            print("(no live-review servers to stop)")


def parse_args():
    p = argparse.ArgumentParser(
        description="Start (or reuse) the code-review live_server and open the rendered HTML in a browser.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("html", type=Path, nargs="?", help="Path to the rendered review HTML.")
    p.add_argument("--port", type=int, default=DEFAULT_PORT, help=f"Preferred port (default {DEFAULT_PORT}).")
    p.add_argument("--cli", choices=["codex", "claude"], default="codex")
    p.add_argument("--model", default=None, help="Model id passed through to the CLI.")
    p.add_argument("--repo", type=Path, default=None, help="Working dir for the CLI subprocess.")
    p.add_argument("--bare", action="store_true",
                   help="Pass --bare to claude (only meaningful with --cli claude). Requires ANTHROPIC_API_KEY env.")
    p.add_argument("--max-concurrent", type=int, default=None,
                   help="Cap on concurrent /ask subprocesses (default: server's own default).")
    p.add_argument("--no-open", action="store_true", help="Do not auto-open a browser tab.")
    p.add_argument("--status", action="store_true", help="List running live-review servers and exit.")
    p.add_argument("--stop", action="store_true",
                   help="Stop the server serving <html>, or all live-review servers if no <html> given.")
    return p.parse_args()


def main():
    args = parse_args()
    if args.status:
        cmd_status(args)
    elif args.stop:
        cmd_stop(args)
    else:
        if not args.html:
            print("usage: live_review.py <html> | --status | --stop [<html>]", file=sys.stderr)
            sys.exit(2)
        cmd_start(args)


if __name__ == "__main__":
    main()
