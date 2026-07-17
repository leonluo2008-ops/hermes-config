"""Async LLM analyzer for session-end retrospective.

Runs in a background daemon thread (on_session_finalize trigger).
Reads report on next session's pre_llm_call (is_first_turn gate).
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional

from .advisor_rules import summarize_config_activity
from .audit_trail import ToolEntry
from .health_check import check_health, format_report

logger = logging.getLogger(__name__)

# Provider presets (same pattern as harness-guard v1.2.0)
_PROVIDER_PRESETS = {
    "glm": {
        "base_url": "https://open.bigmodel.cn/api/coding/paas/v4",
        "model": "glm-5.2",
    },
    "minimax": {
        "base_url": "https://api.minimaxi.com/v1",
        "model": "MiniMax-M3",
    },
    "juxin": {
        "base_url": "https://api.jxincm.cn/v1",
        "model": "gemini-3.5-flash",
    },
}

_DEFAULT_PROVIDER = "glm"
_DEFAULT_TIMEOUT_S = 60
_DEFAULT_MAX_TOKENS = 2048

# Report directory
_REPORT_DIR: Optional[Path] = None


def _get_report_dir() -> Path:
    global _REPORT_DIR
    if _REPORT_DIR is not None:
        return _REPORT_DIR
    home = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
    _REPORT_DIR = Path(home) / "config-advisor" / "reports"
    _REPORT_DIR.mkdir(parents=True, exist_ok=True)
    return _REPORT_DIR


def _get_provider_config() -> dict:
    provider = os.getenv("CONFIG_ADVISOR_PROVIDER", _DEFAULT_PROVIDER).strip().lower()
    return _PROVIDER_PRESETS.get(provider, _PROVIDER_PRESETS[_DEFAULT_PROVIDER])


def _get_api_base() -> str:
    env = os.getenv("CONFIG_ADVISOR_BASE_URL", "").strip()
    if env:
        return env.rstrip("/")
    return _get_provider_config()["base_url"].rstrip("/")


def _get_model() -> str:
    env = os.getenv("CONFIG_ADVISOR_MODEL", "").strip()
    if env:
        return env
    return _get_provider_config()["model"]


def _get_api_key() -> str:
    return (
        os.getenv("CONFIG_ADVISOR_API_KEY", "")
        or os.getenv("ZAI_API_KEY", "")
        or os.getenv("GLM_API_KEY", "")
        or os.getenv("MINIMAX_CN_API_KEY", "")
        or os.getenv("JUXIN_GEMINI_API_KEY", "")
    ).strip()


def _get_timeout_s() -> int:
    try:
        return int(os.getenv("CONFIG_ADVISOR_TIMEOUT_S", str(_DEFAULT_TIMEOUT_S)).strip())
    except (ValueError, TypeError):
        return _DEFAULT_TIMEOUT_S


def _is_disabled() -> bool:
    return os.environ.get("CONFIG_ADVISOR_DISABLE", "").lower() in {"1", "true", "yes", "on"}


def trigger_async_analysis(
    session_id: str,
    audit_entries: list[ToolEntry],
) -> None:
    """Kick off LLM analysis in a background daemon thread.

    Called from on_session_finalize. Must not block.
    Data is already snapshotted by the caller.
    """
    if _is_disabled():
        return

    api_key = _get_api_key()
    if not api_key:
        logger.info("config-advisor: no API key, skipping retrospective analysis")
        _write_minimal_report(session_id, audit_entries)
        return

    # Snapshot data for the thread
    snapshot = {
        "session_id": session_id,
        "timestamp": time.time(),
        "config_activity": summarize_config_activity(audit_entries),
        "health": format_report(check_health()),
        "tool_count": len(audit_entries),
    }

    thread = threading.Thread(
        target=_run_analysis_thread,
        args=(snapshot, api_key),
        daemon=True,
        name=f"config-advisor-{session_id[:12]}",
    )
    thread.start()
    logger.info("config-advisor: started analysis thread for session %s", session_id[:12])


def _run_analysis_thread(snapshot: dict, api_key: str) -> None:
    """Background thread: call LLM, write report to file."""
    session_id = snapshot["session_id"]
    try:
        analysis = _call_llm(snapshot, api_key)
        _write_report(session_id, analysis, snapshot)
        logger.info("config-advisor: analysis complete for session %s", session_id[:12])
    except Exception as exc:
        logger.warning("config-advisor: analysis thread failed: %s", exc)
        # Write minimal fallback report (atomic — no half files)
        _write_minimal_report(session_id, [], error=str(exc))


def _call_llm(snapshot: dict, api_key: str) -> str:
    """Call LLM provider for retrospective analysis."""
    import httpx

    prompt = _build_prompt(snapshot)
    api_base = _get_api_base()
    model = _get_model()

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": _DEFAULT_MAX_TOKENS,
        "temperature": 0.1,
    }

    resp = httpx.post(
        f"{api_base}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
        timeout=_get_timeout_s(),
    )

    if resp.status_code != 200:
        return f"⚠️ LLM API 返回 {resp.status_code}，跳过分析"

    data = resp.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()

    # Strip <think> tags (thinking models)
    import re
    content = re.sub(r"<think>.*?</think>\s*", "", content, flags=re.DOTALL).strip()

    return content or "⚠️ LLM 返回为空"


def _build_prompt(snapshot: dict) -> str:
    """Build the retrospective analysis prompt."""
    return f"""你是 Hermes Agent 的配置顾问。基于以下会话数据，产出简洁的配置优化建议。

## 会话数据
- Session: {snapshot['session_id'][:16]}
- 工具调用总数: {snapshot['tool_count']}

## 配置活动摘要
{snapshot['config_activity']}

## 配置健康状态
{snapshot['health'] or '全部健康'}

## 输出要求
1. 列出 1-3 条具体建议（哪些配置该调整、晋升、删除）
2. 每条建议一句话，格式："文件名: 建议"
3. 如果没有需要调整的，直接回复"配置健康，无需调整"
4. 回复不超过 200 字"""


def _write_report(
    session_id: str,
    analysis: str,
    snapshot: dict,
) -> None:
    """Write report to file atomically (write tmp + rename)."""
    report_dir = _get_report_dir()
    date_str = time.strftime("%Y-%m-%d_%H%M", time.localtime(snapshot["timestamp"]))

    # Atomic write: tmp file + rename
    final_path = report_dir / f"retro_{date_str}_{session_id[:8]}.md"
    tmp_path = final_path.with_suffix(".tmp")

    content = f"""# 配置复盘报告

- 日期: {time.strftime("%Y-%m-%d %H:%M", time.localtime(snapshot["timestamp"]))}
- Session: {session_id[:16]}
- 工具调用: {snapshot['tool_count']}

## LLM 分析

{analysis}

## 原始数据

### 配置活动
{snapshot['config_activity']}

### 健康检查
{snapshot['health'] or '全部健康'}
"""

    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.rename(final_path)  # atomic on same filesystem


def _write_minimal_report(
    session_id: str,
    audit_entries: list[ToolEntry],
    error: str = "",
) -> None:
    """Write a fallback report without LLM analysis."""
    report_dir = _get_report_dir()
    date_str = time.strftime("%Y-%m-%d_%H%M")

    final_path = report_dir / f"retro_{date_str}_{session_id[:8]}.md"
    tmp_path = final_path.with_suffix(".tmp")

    content = f"""# 配置复盘报告（无 LLM 分析）

- 日期: {time.strftime("%Y-%m-%d %H:%M")}
- Session: {session_id[:16]}

## 配置活动
{summarize_config_activity(audit_entries)}

## 健康检查
{format_report(check_health()) or '全部健康'}
"""
    if error:
        content += f"\n## 错误\n分析失败: {error}\n"

    tmp_path.write_text(content, encoding="utf-8")
    tmp_path.rename(final_path)


def read_unread_report() -> Optional[str]:
    """Read the most recent unread report for pre_llm_call injection.

    Returns concise summary (<500 chars) or None.
    Marks report as read by renaming (adds .read suffix).
    """
    if _is_disabled():
        return None

    report_dir = _get_report_dir()
    reports = sorted(report_dir.glob("retro_*.md"), reverse=True)

    for report in reports:
        read_marker = report.with_suffix(".md.read")
        if read_marker.exists():
            continue  # already read

        try:
            content = report.read_text(encoding="utf-8")
            # Extract LLM analysis section
            import re
            match = re.search(r"## LLM 分析\s*\n(.*?)(?:\n##|\Z)", content, re.DOTALL)
            if match:
                analysis = match.group(1).strip()
                if analysis and "无需调整" not in analysis:
                    # Mark as read
                    report.rename(read_marker)
                    # Truncate for injection
                    if len(analysis) > 400:
                        analysis = analysis[:390] + "…"
                    return f"📋 上次会话配置复盘：\n{analysis}"
                else:
                    # Nothing interesting — mark as read silently
                    report.rename(read_marker)
        except OSError:
            continue

    return None
