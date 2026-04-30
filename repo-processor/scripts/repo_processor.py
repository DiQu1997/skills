#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import traceback
import signal
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPT_DIR.parent / "templates"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="repo-processor orchestrator")
    parser.add_argument("target", help="Target path")
    parser.add_argument("--max-agents", type=int, default=5)
    parser.add_argument("--small-repo-files", type=int, default=20)
    parser.add_argument("--small-repo-loc", type=int, default=3000)
    parser.add_argument("--skip-dirs", default="vendor,third_party,node_modules,.git")
    parser.add_argument("--skip-generated", default="true")
    parser.add_argument("--work-dir", default="")
    return parser.parse_args()


def run_checked(cmd: List[str]) -> None:
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")


def load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def render_template(template_text: str, tokens: Dict[str, str]) -> str:
    out = template_text
    for k, v in tokens.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def format_list(items: List[str]) -> str:
    if not items:
        return "None"
    return "\n".join(items)


def primary_language(files: List[str]) -> str:
    counts: Dict[str, int] = {}
    for f in files:
        ext = Path(f).suffix.lower()
        if ext in {".rs"}:
            lang = "rust"
        elif ext in {".py", ".pyi"}:
            lang = "python"
        elif ext in {".go"}:
            lang = "go"
        elif ext in {".js", ".jsx"}:
            lang = "javascript"
        elif ext in {".ts", ".tsx"}:
            lang = "typescript"
        elif ext in {".java"}:
            lang = "java"
        elif ext in {".kt"}:
            lang = "kotlin"
        elif ext in {".scala"}:
            lang = "scala"
        elif ext in {".c", ".h"}:
            lang = "c"
        elif ext in {".cc", ".cpp", ".hpp"}:
            lang = "cpp"
        else:
            lang = "unknown"
        counts[lang] = counts.get(lang, 0) + 1
    if not counts:
        return "unknown"
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[0][0]


def task_output_ok(path: Path) -> bool:
    if not path.exists():
        return False
    if path.stat().st_size < 200:
        return False
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    if "# RESEARCH FAILED" in text:
        return False
    return True


def append_log(log_path: Path, message: str) -> None:
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {message}\n")


def log_event(progress_log: Path, event: str, data: Dict[str, object]) -> None:
    payload = {"ts": time.strftime("%Y-%m-%d %H:%M:%S"), "event": event}
    payload.update(data)
    progress_log.parent.mkdir(parents=True, exist_ok=True)
    with progress_log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True) + "\n")


def write_json(path: Path, data: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    tmp.replace(path)


def update_task_status(status_dir: Path, task_id: str, updates: Dict[str, object]) -> None:
    status_path = status_dir / f"{task_id}.json"
    current: Dict[str, object] = {}
    if status_path.exists():
        try:
            current = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception:
            current = {}
    current.update(updates)
    write_json(status_path, current)


def tail_file(path: Path, max_lines: int = 40) -> str:
    try:
        lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(lines[-max_lines:])
    except Exception:
        return ""


def run_task_once(
    repo_path: Path,
    task: dict,
    prompt_text: str,
    work_dir: Path,
    suffix: str,
    log_path: Path,
    status_dir: Path,
    progress_log: Path,
) -> Tuple[str, bool]:
    task_id = task.get("task_id", "task")
    prompt_path = work_dir / "prompts" / f"{task_id}{suffix}.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt_text, encoding="utf-8")

    output_path = task.get("output")
    output_abs = (repo_path / output_path) if output_path else None
    task_log = work_dir / "logs" / f"{task_id}.log"
    task_log.parent.mkdir(parents=True, exist_ok=True)

    task_meta = {
        "task_id": task_id,
        "type": task.get("type"),
        "path": task.get("path"),
        "output": output_path,
        "prompt": str(prompt_path),
        "source_files": task.get("source_files"),
        "child_docs": task.get("child_docs"),
        "local_source_files": task.get("local_source_files"),
    }
    update_task_status(status_dir, task_id, {**task_meta, "status": "running", "started_at": time.time()})
    log_event(progress_log, "task_start", task_meta)

    append_log(log_path, f"START {task_id} type={task.get('type')} path={task.get('path')}")
    start = time.time()
    cmd = [str(SCRIPT_DIR / "spawn_codex.sh"), str(repo_path), str(prompt_path), str(task_log)]
    proc = subprocess.run(cmd)
    ok = proc.returncode == 0
    if output_abs is not None:
        ok = ok and task_output_ok(output_abs)
    elapsed = time.time() - start

    err_path = Path(str(task_log) + ".stderr")
    err_tail = tail_file(err_path) if err_path.exists() else ""
    status = "OK" if ok else "FAIL"
    size = output_abs.stat().st_size if (output_abs is not None and output_abs.exists()) else 0
    append_log(
        log_path,
        "END {task_id} status={status} seconds={elapsed:.1f} "
        "returncode={rc} output={output} size={size} prompt={prompt}".format(
            task_id=task_id,
            status=status,
            elapsed=elapsed,
            rc=proc.returncode,
            output=output_path or "None",
            size=size,
            prompt=prompt_path,
        ),
    )
    if not ok and err_tail:
        append_log(log_path, f"STDERR_TAIL {task_id}:\n{err_tail}")
    update_task_status(
        status_dir,
        task_id,
        {
            "status": "ok" if ok else "fail",
            "ended_at": time.time(),
            "returncode": proc.returncode,
            "output_size": size,
            "stderr_tail": err_tail,
        },
    )
    log_event(
        progress_log,
        "task_end",
        {
            "task_id": task_id,
            "status": "ok" if ok else "fail",
            "returncode": proc.returncode,
            "output": output_path or "None",
            "output_size": size,
        },
    )
    return task_id, ok


def run_task_with_retry(
    repo_path: Path,
    task: dict,
    prompt_text: str,
    work_dir: Path,
    log_path: Path,
    status_dir: Path,
    progress_log: Path,
) -> Tuple[str, bool]:
    task_id, ok = run_task_once(repo_path, task, prompt_text, work_dir, "", log_path, status_dir, progress_log)
    if ok:
        return task_id, True

    retry_prompt = (
        prompt_text
        + "\\n\\nRETRY MODE: Be concise. Focus only on required headings and rules. "
        + "If unsure, write \"None\" in that section."
    )
    append_log(log_path, f"RETRY {task_id}")
    log_event(progress_log, "task_retry", {"task_id": task_id})
    return run_task_once(repo_path, task, retry_prompt, work_dir, ".retry", log_path, status_dir, progress_log)


def main() -> int:
    args = parse_args()
    target = Path(args.target).resolve()
    if not target.exists() or not target.is_dir():
        print(f"Target not found: {target}", file=sys.stderr)
        return 2

    work_dir = Path(args.work_dir).resolve() if args.work_dir else Path(f"/tmp/repo-processor-{int(time.time())}")
    work_dir.mkdir(parents=True, exist_ok=True)
    summary_log = work_dir / "summary.log"
    progress_log = work_dir / "progress.jsonl"
    status_dir = work_dir / "status"

    def handle_signal(signum: int, _frame) -> None:
        append_log(summary_log, f"SIGNAL {signum} received; terminating")
        raise SystemExit(1)

    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    append_log(summary_log, f"START repo-processor target={target} max_agents={args.max_agents}")

    try:
        recon_path = work_dir / "recon_output.json"
        plan_path = work_dir / "execution_plan.json"

        try:
            run_checked([
                str(SCRIPT_DIR / "recon.sh"),
                str(target),
                str(recon_path),
                "--skip-dirs",
                args.skip_dirs,
                "--skip-generated",
                args.skip_generated,
            ])
        except Exception as e:
            append_log(summary_log, f"RECON failed: {e}")
            append_log(summary_log, traceback.format_exc())
            return 1

        try:
            run_checked([
                sys.executable,
                str(SCRIPT_DIR / "plan.py"),
                str(recon_path),
                str(plan_path),
            ])
        except Exception as e:
            append_log(summary_log, f"PLAN failed: {e}")
            append_log(summary_log, traceback.format_exc())
            return 1
        append_log(summary_log, f"PLAN written: {plan_path}")
        log_event(progress_log, "plan_written", {"path": str(plan_path)})

        recon = json.loads(recon_path.read_text(encoding="utf-8"))
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        write_json(work_dir / "tasks.json", {"levels": plan.get("levels", [])})

        total_files = int(recon.get("total_files", 0))
        total_loc = int(recon.get("total_loc", 0))
        small_repo = total_files <= args.small_repo_files and total_loc <= args.small_repo_loc

        leaf_prompt = load_text(TEMPLATES_DIR / "leaf_prompt.md")
        rollup_prompt = load_text(TEMPLATES_DIR / "rollup_prompt.md")
        global_prompt = load_text(TEMPLATES_DIR / "global_prompt.md")
        small_repo_prompt = load_text(TEMPLATES_DIR / "small_repo_prompt.md")

        if small_repo:
            append_log(summary_log, "Small repo mode enabled")
            log_event(progress_log, "mode", {"mode": "small_repo"})
            all_source_files: List[str] = []
            for entry in recon.get("directory_tree", []):
                rel_dir = entry.get("path", "")
                for f in entry.get("source_files", []):
                    all_source_files.append(f"{rel_dir}/{f}" if rel_dir else f)

            leaf_outputs: List[str] = []
            rollup_outputs: List[str] = []
            global_outputs: List[str] = []
            for level in plan.get("levels", []):
                for task in level.get("tasks", []):
                    ttype = task.get("type")
                    if ttype == "leaf":
                        leaf_outputs.append(f"{task.get('output')} (dir: {task.get('path')})")
                    elif ttype == "rollup":
                        rollup_outputs.append(f"{task.get('output')} (dir: {task.get('path')})")
                    elif ttype == "global":
                        global_outputs.extend(task.get("outputs", []))

            tokens = {
                "TARGET_DIR": str(target),
                "ALL_SOURCE_FILES": format_list(all_source_files),
                "LEAF_OUTPUTS": format_list(leaf_outputs),
                "ROLLUP_OUTPUTS": format_list(rollup_outputs),
                "GLOBAL_OUTPUTS": format_list(global_outputs),
            }
            prompt_text = render_template(small_repo_prompt, tokens)
            prompt_path = work_dir / "prompts" / "small_repo.md"
            prompt_path.parent.mkdir(parents=True, exist_ok=True)
            prompt_path.write_text(prompt_text, encoding="utf-8")
            log_path = work_dir / "logs" / "small_repo.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)

            cmd = [str(SCRIPT_DIR / "spawn_codex.sh"), str(target), str(prompt_path), str(log_path)]
            proc = subprocess.run(cmd)
            append_log(summary_log, f"SMALL_REPO spawn returncode={proc.returncode} log={log_path}")
            log_event(progress_log, "small_repo_spawn", {"returncode": proc.returncode, "log": str(log_path)})

            validate_proc = subprocess.run([str(SCRIPT_DIR / "validate.sh"), str(plan_path)])
            if validate_proc.returncode == 0:
                append_log(summary_log, "Small repo mode validation OK")
                print("repo-processor complete:")
                print(f"  Target: {target}")
                print(f"  Work dir: {work_dir}")
                return 0
            append_log(summary_log, "Small repo mode validation failed; falling back to standard pipeline")
            print("Small repo mode validation failed; falling back to standard pipeline.")

        existing_docs = recon.get("existing_docs", [])
        build_files = recon.get("build_files", [])

        failures: List[str] = []

        for level in plan.get("levels", []):
            tasks = level.get("tasks", [])
            if not tasks:
                continue
            append_log(summary_log, f"LEVEL {level.get('level')} start tasks={len(tasks)}")
            log_event(progress_log, "level_start", {"level": level.get("level"), "tasks": len(tasks)})

            futures = []
            future_to_task: Dict[object, dict] = {}
            with ThreadPoolExecutor(max_workers=args.max_agents) as executor:
                for task in tasks:
                    ttype = task.get("type")
                    if ttype == "leaf":
                        rel_dir = task.get("path", ".")
                        files = task.get("source_files", [])
                        files_full = [f"{rel_dir}/{f}" if rel_dir not in {".", ""} else f for f in files]
                        tokens = {
                            "TARGET_DIR": rel_dir if rel_dir not in {"", "."} else target.name,
                            "FILES": format_list(files_full),
                            "DETAIL_LEVEL": str(task.get("detail_level", "standard")).upper(),
                            "LANGUAGE": primary_language(files),
                            "OUTPUT_PATH": str((target / task.get("output")).resolve()),
                        }
                        prompt_text = render_template(leaf_prompt, tokens)
                        fut = executor.submit(
                            run_task_with_retry,
                            target,
                            task,
                            prompt_text,
                            work_dir,
                            summary_log,
                            status_dir,
                            progress_log,
                        )
                        futures.append(fut)
                        future_to_task[fut] = task
                    elif ttype == "rollup":
                        rel_dir = task.get("path", ".")
                        child_docs = task.get("child_docs", [])
                        local_files = task.get("local_source_files", [])
                        local_files_full = [f"{rel_dir}/{f}" if rel_dir not in {".", ""} else f for f in local_files]
                        tokens = {
                            "TARGET_DIR": rel_dir if rel_dir not in {"", "."} else target.name,
                            "CHILD_DOCS": format_list(child_docs),
                            "LOCAL_SOURCE_FILES": format_list(local_files_full),
                            "OUTPUT_PATH": str((target / task.get("output")).resolve()),
                        }
                        prompt_text = render_template(rollup_prompt, tokens)
                        fut = executor.submit(
                            run_task_with_retry,
                            target,
                            task,
                            prompt_text,
                            work_dir,
                            summary_log,
                            status_dir,
                            progress_log,
                        )
                        futures.append(fut)
                        future_to_task[fut] = task
                    elif ttype == "global":
                        tokens = {
                            "ALL_DOCS": format_list(task.get("all_docs", [])),
                            "PROJECT_DOCS": format_list(existing_docs),
                            "BUILD_FILES": format_list(build_files),
                            "TARGET_DIR": str(target),
                        }
                        prompt_text = render_template(global_prompt, tokens)
                        fut = executor.submit(
                            run_task_with_retry,
                            target,
                            task,
                            prompt_text,
                            work_dir,
                            summary_log,
                            status_dir,
                            progress_log,
                        )
                        futures.append(fut)
                        future_to_task[fut] = task

                for fut in as_completed(futures):
                    task = future_to_task.get(fut)
                    try:
                        task_id, ok = fut.result()
                        if not ok:
                            failures.append(task_id)
                    except Exception as e:
                        tid = task.get("task_id") if task else "unknown"
                        failures.append(tid)
                        append_log(summary_log, f"EXCEPTION task={tid} error={e}")
                        append_log(summary_log, traceback.format_exc())
            append_log(summary_log, f"LEVEL {level.get('level')} done")
            log_event(progress_log, "level_done", {"level": level.get("level")})

        if failures:
            print("Some tasks failed:", ", ".join(failures), file=sys.stderr)
            append_log(summary_log, f"FAILURES {len(failures)}: {', '.join(failures)}")

        # Final validation
        validate_cmd = [str(SCRIPT_DIR / "validate.sh"), str(plan_path)]
        validate_proc = subprocess.run(validate_cmd)
        if validate_proc.returncode != 0:
            print("Validation failed. Check outputs and consider retry.")
            append_log(summary_log, "VALIDATION failed")
            return 1

        append_log(summary_log, "VALIDATION ok")
        print("repo-processor complete:")
        print(f"  Target: {target}")
        print(f"  Work dir: {work_dir}")
        return 0
    except SystemExit:
        raise
    except Exception as e:
        append_log(summary_log, f"FATAL error: {e}")
        append_log(summary_log, traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
