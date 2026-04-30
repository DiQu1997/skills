#!/usr/bin/env python3
"""
deep_research.py - End-to-end repo deep research driver with optional recursion.

This script is an automation layer around:
- scripts/recon.sh (repo metadata)
- scripts/spawn_codex.sh (module-level research via Codex CLI)
- codex exec (plan + synthesis via Codex CLI)

It is intentionally conservative and relies on simple, explainable heuristics
to decide when a module is "too large" and should trigger a recursive run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


SKIP_DIR_NAMES = {
    ".git",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "dist",
    "build",
    "target",
    ".pytest_cache",
    ".mypy_cache",
    ".tox",
}

CODE_EXTS = {
    ".py",
    ".pyi",
    ".rs",
    ".go",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".kt",
    ".scala",
    ".c",
    ".cc",
    ".cpp",
    ".h",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".swift",
    ".m",
    ".mm",
    ".lua",
    ".sh",
    ".bash",
}


@dataclass(frozen=True)
class SizeMetrics:
    relevant_file_count: int
    code_file_count: int
    approx_loc: int


def eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def run_checked(cmd: List[str], cwd: Optional[Path] = None) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if proc.returncode != 0:
        raise RuntimeError(f"Command failed ({proc.returncode}): {' '.join(cmd)}")


def run_capture(cmd: List[str], cwd: Optional[Path] = None) -> str:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "Command failed ({code}): {cmd}\n--- stderr ---\n{err}".format(
                code=proc.returncode, cmd=" ".join(cmd), err=proc.stderr.strip()
            )
        )
    return proc.stdout


def safe_read_text(path: Path, max_bytes: int = 2_000_000) -> str:
    data = path.read_bytes()
    if len(data) > max_bytes:
        data = data[:max_bytes]
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def compute_size_metrics(root: Path) -> SizeMetrics:
    relevant_files: List[Path] = []
    code_files: List[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        for filename in filenames:
            file_path = Path(dirpath) / filename
            if file_path.is_symlink():
                continue
            relevant_files.append(file_path)
            if file_path.suffix.lower() in CODE_EXTS:
                code_files.append(file_path)

    approx_loc = 0
    for f in code_files:
        try:
            approx_loc += safe_read_text(f).count("\n") + 1
        except Exception:
            continue

    return SizeMetrics(
        relevant_file_count=len(relevant_files),
        code_file_count=len(code_files),
        approx_loc=approx_loc,
    )


def is_large_module(metrics: SizeMetrics, *, loc_threshold: int, file_threshold: int) -> bool:
    return metrics.approx_loc >= loc_threshold or metrics.code_file_count >= file_threshold


def load_prompt_file(skill_root: Path, rel: str) -> Optional[str]:
    p = skill_root / rel
    if p.exists():
        return p.read_text(encoding="utf-8")
    return None


def default_plan_prompt(repo_path: Path, focus_path: str, max_modules: int) -> str:
    return f"""You are an expert software architect and codebase researcher.

You are analyzing a local repository at: {repo_path}
Focus area (treat as the root for planning): {focus_path or "."}

TASK:
1) Inspect the codebase structure (directories, entry points, build files, docs).
2) Propose a research plan that is deep enough for a large dataset.
3) The plan must be actionable for multiple parallel subagents.

OUTPUT REQUIREMENTS (VERY IMPORTANT):
- Output ONLY valid JSON. No markdown, no commentary, no trailing commas.
- Paths MUST be relative to the focus root (the focus area above).
- Produce between 8 and {max_modules} modules (prefer 10-15 for large repos).
- Use this exact schema:
{{
  "repo_name": "...",
  "repo_purpose": "...",
  "key_technologies": ["..."],
  "focus_path": "{focus_path or "."}",
  "modules": [
    {{
      "id": "mod-01",
      "name": "...",
      "path": "relative/path",
      "priority": "high|medium|low",
      "estimated_complexity": "high|medium|low",
      "research_questions": ["..."]
    }}
  ],
  "cross_cutting_concerns": ["..."]
}}

PLANNING HEURISTICS:
- Prioritize entry points, core execution/model, key domain logic, and important infra (config/logging/errors).
- Large directories should become their own module even if they contain multiple subareas.
- Use module names that describe responsibility, not directory names.
"""


def default_module_prompt(
    module_path: str,
    questions: List[str],
    metrics: SizeMetrics,
    *,
    prefer_depth: bool,
) -> str:
    qs = "\n".join([f"{i+1}. {q}" for i, q in enumerate(questions)]) or "1. (No explicit questions provided; infer the most important questions.)"
    depth_line = (
        "Prioritize depth: explain mechanisms step-by-step and include code evidence."
        if prefer_depth
        else "Prioritize a crisp but complete map of responsibilities and main flows."
    )
    return f"""Analyze the module at: {module_path}

Module sizing context (heuristic):
- code_file_count: {metrics.code_file_count}
- approx_loc: {metrics.approx_loc}

Research questions:
{qs}

AUTOPLAN_JSON SCHEMA (populate realistically):
{{
  "module_path": "{module_path}",
  "relevant_file_count": {metrics.relevant_file_count},
  "code_file_count": {metrics.code_file_count},
  "approx_loc": {metrics.approx_loc},
  "too_large_for_single_pass": true|false,
  "reasons_too_large": ["..."],
  "suggested_subpaths": [
    {{
      "path": "relative/subpath",
      "purpose": "...",
      "research_questions": ["...", "..."]
    }}
  ]
}}

{depth_line}
"""


def default_synth_prompt(repo_name: str, outdir: str) -> str:
    return f"""You are writing a professor-quality deep research report.

Repository name: {repo_name}
Research artifact directory (relative to repo root): {outdir}

TASK:
- Read the artifacts under `{outdir}`:
  - `recon_output.md`
  - `research_plan.json`
  - all module reports in `modules/`
  - any nested reports in `subreports/` (if present)
- Produce ONE cohesive report that is step-by-step and explanatory.
- When you claim something important, point to concrete file paths and identifiers (function/type names).

STYLE:
- Teach the reader how to build a correct mental model.
- Use a guided walkthrough: overview -> architecture -> module map -> 3-5 key end-to-end flows.
- For each key flow, walk step-by-step (numbered), include the key files/functions, and explain WHY it is structured that way.
- Include design tradeoffs (what it optimizes for vs sacrifices).

OUTPUT:
- Output markdown only.
- Start with `# Deep Research Report: ...`
"""


def normalize_rel_path(p: str) -> str:
    p = p.strip()
    p = p.lstrip("./")
    return p or "."


def validate_plan(plan: Dict[str, Any]) -> None:
    if "modules" not in plan or not isinstance(plan["modules"], list) or not plan["modules"]:
        raise ValueError("Plan JSON missing non-empty 'modules' list")
    for m in plan["modules"]:
        for key in ("id", "name", "path", "priority", "estimated_complexity", "research_questions"):
            if key not in m:
                raise ValueError(f"Module missing key: {key}")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


_STATUS_ICON: Dict[str, str] = {
    "completed": "✅",
    "failed": "❌",
    "in_progress": "🔄",
    "pending": "⏳",
}


def _extract_overview(report_path: Path, max_lines: int = 12) -> str:
    """Extract the Module Overview section from a completed module report."""
    try:
        text = report_path.read_text(encoding="utf-8")
        lines = text.splitlines()
        in_section = False
        collected: List[str] = []
        for line in lines:
            if re.match(r"^#{1,3}\s+Module Overview", line, re.IGNORECASE):
                in_section = True
                continue
            if in_section:
                if re.match(r"^#{1,3}\s+", line):
                    break
                collected.append(line)
                if len(collected) >= max_lines:
                    break
        # Trim blank edges
        while collected and not collected[0].strip():
            collected.pop(0)
        while collected and not collected[-1].strip():
            collected.pop()
        return "\n".join(collected)
    except Exception:
        return ""


def write_progress_md(
    outdir: Path,
    plan: Dict[str, Any],
    phase: str,
    statuses: Dict[str, str],
    modules_dir: Path,
) -> None:
    """Write/update a human-readable progress document to {outdir}/progress.md.

    The document contains:
    - Overall research plan (purpose, technologies, module list)
    - Per-module status table
    - Findings excerpts from completed modules

    The next run reads this to show the user what has been done; the resume logic
    itself uses file existence (not this document), but this document is the
    human-readable companion that lets anyone understand where the run stands.
    """
    repo_name = plan.get("repo_name") or "unknown"
    repo_purpose = plan.get("repo_purpose") or ""
    key_techs: List[str] = [str(t) for t in (plan.get("key_technologies") or [])]
    cross_cutting: List[str] = [str(c) for c in (plan.get("cross_cutting_concerns") or [])]
    modules: List[Dict[str, Any]] = plan.get("modules") or []

    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(modules)
    done = sum(1 for m in modules if statuses.get(str(m.get("id") or "")) == "completed")
    failed = sum(1 for m in modules if statuses.get(str(m.get("id") or "")) == "failed")

    lines: List[str] = [
        f"# Deep Research Progress: {repo_name}",
        "",
        f"**Phase**: {phase}  ",
        f"**Updated**: {now}  ",
        f"**Progress**: {done}/{total} modules done" + (f", {failed} failed" if failed else ""),
        "",
        "---",
        "",
        "## Research Plan",
        "",
        f"**Purpose**: {repo_purpose}",
        "",
        f"**Technologies**: {', '.join(key_techs) or '—'}",
    ]
    if cross_cutting:
        lines.append(f"**Cross-cutting concerns**: {', '.join(cross_cutting)}")

    lines.extend([
        "",
        "## Module Status",
        "",
        "| # | Module | Path | Priority | Status |",
        "|---|--------|------|----------|--------|",
    ])
    for i, m in enumerate(modules, 1):
        mid = str(m.get("id") or "")
        s = statuses.get(mid, "pending")
        icon = _STATUS_ICON.get(s, "⏳")
        lines.append(
            f"| {i} | **{m.get('name', '')}** | `{m.get('path', '')}` "
            f"| {m.get('priority', '')} | {icon} {s} |"
        )

    # Findings excerpts from completed modules
    completed_modules = [m for m in modules if statuses.get(str(m.get("id") or "")) == "completed"]
    if completed_modules:
        lines.extend(["", "---", "", "## Findings So Far", ""])
        for m in completed_modules:
            lines.append(f"### ✅ {m.get('name', '')} (`{m.get('path', '')}`)")
            lines.append("")
            out_name = sanitize_module_filename(str(m["id"]), str(m["name"])) + ".md"
            snippet = _extract_overview(modules_dir / out_name)
            if snippet:
                lines.append(snippet)
            lines.append("")

    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "progress.md").write_text("\n".join(lines), encoding="utf-8")


def call_codex_to_file(repo_path: Path, prompt: str, out_file: Path) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_file.with_suffix(out_file.suffix + ".tmp")
    run_log = out_file.with_suffix(out_file.suffix + ".run.log")
    stderr = out_file.with_suffix(out_file.suffix + ".stderr")
    cmd = [
        "codex",
        "exec",
        "--dangerously-bypass-approvals-and-sandbox",
        "--output-last-message",
        str(tmp),
        "-C",
        str(repo_path),
        prompt,
    ]
    eprint(f"[codex] -> {out_file}")
    proc = subprocess.run(cmd, stdout=run_log.open("w"), stderr=stderr.open("w"), text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"codex exec failed ({proc.returncode}). See: {stderr}")
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise RuntimeError(f"codex exec produced empty output message. See: {run_log} and {stderr}")
    tmp.replace(out_file)


def call_spawn_subagent(
    skill_root: Path,
    repo_path: Path,
    prompt: str,
    out_file: Path,
    focus_path: str,
) -> None:
    spawn = skill_root / "scripts" / "spawn_codex.sh"
    cmd = ["bash", str(spawn), str(repo_path), prompt, str(out_file), focus_path]
    eprint(f"[subagent] {focus_path} -> {out_file.name}")
    run_checked(cmd, cwd=skill_root)


def sanitize_module_filename(module_id: str, name: str) -> str:
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-").lower()[:60]
    return f"{module_id}-{safe_name}".strip("-")


def load_json_strict(path: Path) -> Dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    return json.loads(raw)


def build_repo_name(repo_path: Path, focus_path: str) -> str:
    base = repo_path.name
    if focus_path and focus_path not in (".", "./"):
        base = f"{base}:{focus_path}"
    return base


def deep_research_run(
    *,
    skill_root: Path,
    repo_path: Path,
    focus_path: str,
    outdir_rel: str,
    max_agents: int,
    max_modules: int,
    loc_threshold: int,
    file_threshold: int,
    max_depth: int,
    force: bool = False,
) -> Path:
    """Run the full deep-research pipeline, resuming from prior outputs when possible.

    Resume behaviour (when force=False):
    - Phase 1 (recon):    skipped if recon_output.md already exists.
    - Phase 2 (plan):     skipped if research_plan.json exists and is valid.
    - Phase 3 (modules):  each module is skipped individually if its .md already exists.
    - Phase 4 (synth):    skipped if the final report file already exists.

    A human-readable progress.md is written to outdir after every status change so
    that the next run (or a human) can see exactly where the run stands.

    Pass force=True (--force on CLI) to ignore all prior outputs and re-run everything.
    """
    focus_path = normalize_rel_path(focus_path)
    outdir_rel = normalize_rel_path(outdir_rel)

    outdir = repo_path / outdir_rel
    outdir.mkdir(parents=True, exist_ok=True)

    recon_out = outdir / "recon_output.md"
    plan_out = outdir / "research_plan.json"
    modules_dir = outdir / "modules"

    # ------------------------------------------------------------------ #
    # Phase 1: recon                                                       #
    # ------------------------------------------------------------------ #
    recon_script = skill_root / "scripts" / "recon.sh"
    if force or not recon_out.exists():
        eprint("[phase] recon")
        run_checked(["bash", str(recon_script), str(repo_path / focus_path), str(recon_out)], cwd=skill_root)
    else:
        eprint(f"[resume] recon_output.md already exists — skipping recon")

    # ------------------------------------------------------------------ #
    # Phase 2: plan                                                        #
    # ------------------------------------------------------------------ #
    plan: Optional[Dict[str, Any]] = None
    if not force and plan_out.exists():
        try:
            candidate = load_json_strict(plan_out)
            validate_plan(candidate)
            plan = candidate
            eprint(f"[resume] research_plan.json already exists and is valid — skipping planning")
        except Exception:
            plan = None  # invalid; fall through to re-plan

    if plan is None:
        eprint("[phase] planning")
        plan_prompt = (
            load_prompt_file(skill_root, "prompts/plan.prompt.md")
            or default_plan_prompt(repo_path, focus_path if focus_path != "." else "", max_modules)
        )
        plan_prompt = (
            plan_prompt.replace("{REPO_PATH}", str(repo_path))
            .replace("{FOCUS_PATH}", focus_path if focus_path != "." else ".")
            .replace("{MAX_MODULES}", str(max_modules))
        )
        call_codex_to_file(repo_path, plan_prompt, plan_out)

        # Validate/normalize plan — one repair attempt on failure
        try:
            plan = load_json_strict(plan_out)
            validate_plan(plan)
        except Exception:
            repair_prompt = (
                f"The file `{plan_out}` is supposed to be strict JSON, but it failed to parse/validate.\n"
                f"Rewrite it into STRICT valid JSON matching the required schema. Output ONLY JSON.\n\n"
                f"Original content:\n{plan_out.read_text(encoding='utf-8')}\n"
            )
            call_codex_to_file(repo_path, repair_prompt, plan_out)
            plan = load_json_strict(plan_out)
            validate_plan(plan)

    repo_name = plan.get("repo_name") or build_repo_name(repo_path, focus_path if focus_path != "." else "")

    # ------------------------------------------------------------------ #
    # Phase 3: module research (parallel Codex subagents)                 #
    # ------------------------------------------------------------------ #
    modules: List[Dict[str, Any]] = plan["modules"]
    prio_rank = {"high": 0, "medium": 1, "low": 2}
    modules.sort(key=lambda m: (prio_rank.get(str(m.get("priority", "medium")).lower(), 1), str(m.get("id"))))

    def module_focus_path(module_rel: str) -> str:
        module_rel = normalize_rel_path(module_rel)
        if focus_path in (".", "./"):
            return module_rel
        return normalize_rel_path(str(Path(focus_path) / module_rel))

    def module_disk_path(module_rel: str) -> Path:
        return repo_path / module_focus_path(module_rel)

    module_tasks: List[Tuple[Dict[str, Any], SizeMetrics, bool, Path, str, str]] = []
    for m in modules:
        module_rel = str(m["path"])
        disk_path = module_disk_path(module_rel)
        metrics = compute_size_metrics(disk_path) if disk_path.exists() else SizeMetrics(0, 0, 0)
        large = is_large_module(metrics, loc_threshold=loc_threshold, file_threshold=file_threshold)
        prompt = default_module_prompt(
            module_path=module_focus_path(module_rel),
            questions=list(m.get("research_questions") or []),
            metrics=metrics,
            prefer_depth=not large,
        )
        out_name = sanitize_module_filename(str(m["id"]), str(m["name"])) + ".md"
        out_file = modules_dir / out_name
        module_tasks.append((m, metrics, large, out_file, module_focus_path(module_rel), prompt))

    modules_dir.mkdir(parents=True, exist_ok=True)

    # Seed per-module statuses from existing output files
    statuses: Dict[str, str] = {}
    for m, _metrics, _large, out_file, _fpath, _prompt in module_tasks:
        mid = str(m.get("id") or "")
        if not force and out_file.exists() and out_file.stat().st_size > 0:
            statuses[mid] = "completed"
        else:
            statuses[mid] = "pending"

    write_progress_md(outdir, plan, "module-research", statuses, modules_dir)

    status_lock = threading.Lock()

    def run_module(
        m: Dict[str, Any],
        out_file: Path,
        fpath: str,
        prompt: str,
    ) -> None:
        mid = str(m.get("id") or "")
        with status_lock:
            if statuses.get(mid) == "completed":
                eprint(f"[resume] {m['name']} — output already exists, skipping")
                return
            statuses[mid] = "in_progress"
            write_progress_md(outdir, plan, "module-research", statuses, modules_dir)

        try:
            call_spawn_subagent(skill_root, repo_path, prompt, out_file, fpath)
            with status_lock:
                statuses[mid] = "completed"
                write_progress_md(outdir, plan, "module-research", statuses, modules_dir)
        except Exception:
            with status_lock:
                statuses[mid] = "failed"
                write_progress_md(outdir, plan, "module-research", statuses, modules_dir)
            raise

    eprint("[phase] module research")
    with ThreadPoolExecutor(max_workers=max_agents) as ex:
        futs = [
            ex.submit(run_module, m, out_file, fpath, prompt)
            for m, _metrics, _large, out_file, fpath, prompt in module_tasks
        ]
        for fut in as_completed(futs):
            fut.result()

    # ------------------------------------------------------------------ #
    # Phase 3b: recursive runs for large modules (optional)               #
    # ------------------------------------------------------------------ #
    if max_depth > 0:
        write_progress_md(outdir, plan, "recursive-research", statuses, modules_dir)
        for m, metrics, large, out_file, fpath, _prompt in module_tasks:
            if not large:
                continue
            if not (repo_path / fpath).exists():
                continue
            sub_outdir_rel = normalize_rel_path(str(Path(outdir_rel) / "subreports" / str(m["id"])))
            sub_report = deep_research_run(
                skill_root=skill_root,
                repo_path=repo_path,
                focus_path=fpath,
                outdir_rel=sub_outdir_rel,
                max_agents=max(1, min(max_agents, 4)),
                max_modules=max_modules,
                loc_threshold=loc_threshold,
                file_threshold=file_threshold,
                max_depth=max_depth - 1,
                force=force,
            )
            try:
                pointer = (
                    f"\n\n---\n\n"
                    f"### Nested Deep Research Report\n"
                    f"- Reason: module too large (code_file_count={metrics.code_file_count}, approx_loc={metrics.approx_loc}).\n"
                    f"- Sub-report: `{sub_report.relative_to(repo_path)}`\n"
                )
                out_file.write_text(out_file.read_text(encoding="utf-8") + pointer, encoding="utf-8")
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Phase 4: synthesis                                                   #
    # ------------------------------------------------------------------ #
    final_report = outdir / f"{re.sub(r'[^a-zA-Z0-9._:-]+', '-', repo_name).strip('-')}-deep-research.md"
    if force or not final_report.exists():
        eprint("[phase] synthesis")
        write_progress_md(outdir, plan, "synthesis", statuses, modules_dir)
        synth_prompt = load_prompt_file(skill_root, "prompts/synth.prompt.md") or default_synth_prompt(repo_name, outdir_rel)
        synth_prompt = (
            synth_prompt.replace("{REPO_NAME}", repo_name)
            .replace("{OUTDIR}", outdir_rel)
            .replace("{FOCUS_PATH}", focus_path if focus_path != "." else ".")
        )
        call_codex_to_file(repo_path, synth_prompt, final_report)
    else:
        eprint(f"[resume] final report already exists — skipping synthesis")

    write_progress_md(outdir, plan, "complete", statuses, modules_dir)
    return final_report


def main() -> int:
    ap = argparse.ArgumentParser(description="Automated repo deep research with recursion.")
    ap.add_argument("repo_path", help="Path to repo root")
    ap.add_argument("--focus", default=".", help="Focus subdirectory (relative to repo root)")
    ap.add_argument("--outdir", default=".deep_research", help="Output directory (relative to repo root)")
    ap.add_argument("--max-agents", type=int, default=4, help="Max parallel subagents")
    ap.add_argument("--max-modules", type=int, default=15, help="Upper bound for modules in plan")
    ap.add_argument("--loc-threshold", type=int, default=6000, help="Recurse when module approx LOC >= threshold")
    ap.add_argument("--file-threshold", type=int, default=60, help="Recurse when code file count >= threshold")
    ap.add_argument("--max-depth", type=int, default=1, help="Max recursion depth for large modules")
    ap.add_argument(
        "--force",
        action="store_true",
        help="Ignore all prior outputs and re-run every phase from scratch",
    )
    args = ap.parse_args()

    repo_path = Path(args.repo_path).expanduser().resolve()
    if not repo_path.exists():
        eprint(f"Repo path does not exist: {repo_path}")
        return 2

    skill_root = Path(__file__).resolve().parents[1]
    try:
        report = deep_research_run(
            skill_root=skill_root,
            repo_path=repo_path,
            focus_path=args.focus,
            outdir_rel=args.outdir,
            max_agents=max(1, args.max_agents),
            max_modules=max(8, args.max_modules),
            loc_threshold=max(500, args.loc_threshold),
            file_threshold=max(10, args.file_threshold),
            max_depth=max(0, args.max_depth),
            force=args.force,
        )
    except Exception as e:
        eprint(str(e))
        return 1

    print(str(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
