"""Configuration health snapshot for config-advisor.

Pure Python, zero-latency checks on config files. No LLM calls.
Called from pre_llm_call hook (only on first turn).
"""

from __future__ import annotations

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

# Thresholds (sourced from hermes-config-organization skill references)
SOUL_MAX = 2000          # chars — workflow shouldn't be in SOUL.md
HERMES_MD_MAX = 6000     # chars — 30% of 20K truncation limit
MEMORY_WARN = 1760       # chars — 80% of 2200 hard limit
MEMORY_HARD = 2200
USER_WARN = 1100         # chars — 80% of 1375 hard limit
USER_HARD = 1375


@dataclass
class HealthIssue:
    severity: str        # "ok" | "warn" | "error"
    file: str
    message: str
    size: int = 0


def _get_hermes_home() -> Path:
    return Path(os.environ.get("HERMES_HOME", str(Path.home() / ".hermes")))


def _file_size(path: Path) -> int:
    try:
        return path.stat().st_size
    except OSError:
        return -1


def check_health() -> List[HealthIssue]:
    """Run all config health checks. Returns list of issues.

    Zero-latency: only os.path.exists() + os.path.getsize().
    No subprocess, no network, no LLM.
    """
    home = _get_hermes_home()
    issues: List[HealthIssue] = []

    # 1. SOUL.md
    soul = home / "SOUL.md"
    soul_size = _file_size(soul)
    if soul_size < 0:
        issues.append(HealthIssue("error", "SOUL.md", "不存在 — Hermes 回退默认身份"))
    elif soul_size > SOUL_MAX:
        issues.append(HealthIssue("warn", "SOUL.md", f"{soul_size} 字符，超过 {SOUL_MAX} — workflow 应移到 .hermes.md", soul_size))

    # 2. ~/.hermes.md (global context)
    hermes_md = Path.home() / ".hermes.md"
    hm_size = _file_size(hermes_md)
    if hm_size < 0:
        issues.append(HealthIssue("error", "~/.hermes.md", "不存在 — 无全局兜底"))
    elif hm_size > HERMES_MD_MAX:
        issues.append(HealthIssue("warn", "~/.hermes.md", f"{hm_size} 字符，超过 {HERMES_MD_MAX} — 建议拆到 skill", hm_size))

    # 3. git project .hermes.md
    import subprocess
    try:
        git_root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            stderr=subprocess.DEVNULL, timeout=2,
        ).decode().strip()
        if git_root:
            proj_hermes = Path(git_root) / ".hermes.md"
            if not proj_hermes.exists():
                issues.append(HealthIssue("warn", ".hermes.md", f"git 项目 {Path(git_root).name} 缺 .hermes.md — 全局规则不可见"))
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass  # not in a git repo — skip

    # 4. MEMORY.md
    memory = home / "memories" / "MEMORY.md"
    mem_size = _file_size(memory)
    if mem_size >= 0 and mem_size > MEMORY_WARN:
        pct = mem_size * 100 // MEMORY_HARD
        issues.append(HealthIssue("warn", "MEMORY.md", f"{mem_size}/{MEMORY_HARD} ({pct}%) — 接近上限", mem_size))

    # 5. USER.md
    user_md = home / "memories" / "USER.md"
    user_size = _file_size(user_md)
    if user_size < 0:
        issues.append(HealthIssue("warn", "USER.md", "不存在 — 身份信息未初始化"))
    elif user_size > USER_WARN:
        pct = user_size * 100 // USER_HARD
        issues.append(HealthIssue("warn", "USER.md", f"{user_size}/{USER_HARD} ({pct}%) — 接近上限", user_size))

    return issues


def format_report(issues: List[HealthIssue]) -> str:
    """Format issues into a concise report for pre_llm_call injection.

    Keeps output <500 chars to avoid hook_output_spill.
    Returns empty string if all healthy (caller returns None).
    """
    if not issues:
        return ""

    # Only report warns and errors — healthy files are silent
    problems = [i for i in issues if i.severity in ("warn", "error")]
    if not problems:
        return ""

    lines = ["📋 配置健康检查："]
    for p in problems[:5]:  # cap at 5 to stay <500 chars
        icon = "⚠️" if p.severity == "warn" else "✗"
        lines.append(f"{icon} {p.file}: {p.message}")

    # Hint for first action
    errors = [p for p in problems if p.severity == "error"]
    if errors:
        lines.append(f"→ 优先处理: {errors[0].file}")

    report = "\n".join(lines)
    # Hard cap at 480 chars (leave margin under 500)
    if len(report) > 480:
        report = report[:470] + "\n…(详见 config-advisor 报告)"
    return report
