"""config-advisor plugin — Configuration health monitor and advisor.

Three hooks (all observer-only, never blocks agent):
1. pre_llm_call: First-turn config health check + inject unread retrospective.
2. post_tool_call: Audit trail + information routing advice (queued for next turn).
3. on_session_finalize: Snapshot data → async LLM retrospective analysis.

Configuration:
  The plugin reads its own .env file located in this directory
  (~/.hermes/plugins/config-advisor/.env). Copy `.env.example` to `.env`
  and fill in your values. System-level env vars of the same name still
  take precedence.

Environment variables:
  CONFIG_ADVISOR_API_KEY          API key (priority: plugin .env, then env)
  CONFIG_ADVISOR_PROVIDER         Provider preset: glm/minimax/juxin (default: glm)
  CONFIG_ADVISOR_BASE_URL         Override API base URL
  CONFIG_ADVISOR_MODEL            Override model name
  CONFIG_ADVISOR_TIMEOUT_S        Request timeout in seconds (default 60)
  CONFIG_ADVISOR_DISABLE=1        Disable the plugin entirely
  ZAI_API_KEY / GLM_API_KEY       Backward-compat key aliases.
"""

from __future__ import annotations

import logging
import os
import time as _time
from pathlib import Path
from typing import Any, Optional

# ── Plugin-local .env loader (same pattern as harness-guard v1.2.0) ──────────
_PLUGIN_DIR = Path(__file__).resolve().parent
_PLUGIN_ENV = _PLUGIN_DIR / ".env"


def _load_plugin_dotenv() -> int:
    if not _PLUGIN_ENV.is_file():
        return 0
    loaded = 0
    try:
        with _PLUGIN_ENV.open("r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
                    loaded += 1
    except OSError:
        pass
    return loaded


logger = logging.getLogger(__name__)
_loaded = _load_plugin_dotenv()
if _loaded:
    logger.info("config-advisor: loaded %d env var(s) from %s", _loaded, _PLUGIN_ENV)

# ── Imports ──────────────────────────────────────────────────────────────────
from .advisor_rules import analyze_tool_call
from .analyzer import read_unread_report, trigger_async_analysis
from .audit_trail import ToolEntry, _summarize, _is_config_related, get_log
from .health_check import check_health, format_report

# ── Pending advice queue (per session) ──────────────────────────────────────
# post_tool_call writes here, pre_llm_call reads + clears on next turn
_advice_queue: dict[str, list[str]] = {}


def _is_disabled() -> bool:
    return os.environ.get("CONFIG_ADVISOR_DISABLE", "").lower() in {"1", "true", "yes", "on"}


# ═══════════════════════════════════════════════════════════════════════════
# Hook: pre_llm_call
# ═══════════════════════════════════════════════════════════════════════════

def _on_pre_llm_call(
    session_id: str = "",
    is_first_turn: bool = False,
    **_kwargs: Any,
) -> Optional[dict]:
    """First-turn: health check + inject unread retrospective + queued advice.

    Returns {"context": "..."} to inject into user message, or None.
    Non-first-turn: only inject queued advice (from post_tool_call).
    """
    if _is_disabled():
        return None

    parts: list[str] = []

    # 1. First-turn only: health check + retrospective report
    if is_first_turn:
        # Health check
        issues = check_health()
        report = format_report(issues)
        if report:
            parts.append(report)

        # Unread retrospective from previous session
        retro = read_unread_report()
        if retro:
            parts.append(retro)

    # 2. Any turn: queued advice from previous post_tool_call
    effective_session = session_id or _kwargs.get("task_id", "") or "unknown"
    pending = _advice_queue.pop(effective_session, [])
    if pending:
        advice_text = "\n".join(pending[:3])  # max 3 advices per turn
        parts.append(advice_text)

    if not parts:
        return None

    # Concatenate, cap at 480 chars to avoid hook_output_spill
    combined = "\n\n".join(parts)
    if len(combined) > 480:
        combined = combined[:470] + "\n…(详见 config-advisor)"
    return {"context": combined}


# ═══════════════════════════════════════════════════════════════════════════
# Hook: post_tool_call (observer — return value ignored)
# ═══════════════════════════════════════════════════════════════════════════

def _on_post_tool_call(
    tool_name: str = "",
    args: Any = None,
    result: Any = None,
    task_id: str = "",
    session_id: str = "",
    duration_ms: int = 0,
    **_kwargs: Any,
) -> None:
    """Record audit entry + generate routing advice for next turn."""
    if _is_disabled():
        return

    effective_session = session_id or task_id or "unknown"

    # 1. Record in audit trail
    entry = ToolEntry(
        tool=tool_name,
        args_summary=_summarize(args),
        result_summary=_summarize(result),
        ts=_time.time(),
        config_related=_is_config_related(tool_name, args),
    )
    get_log().append(effective_session, entry)

    # 2. Generate routing advice (queued for next pre_llm_call)
    advice = analyze_tool_call(tool_name, args, result)
    if advice:
        _advice_queue.setdefault(effective_session, []).append(advice)
        # Cap queue to avoid unbounded growth
        q = _advice_queue[effective_session]
        if len(q) > 5:
            _advice_queue[effective_session] = q[-5:]


# ═══════════════════════════════════════════════════════════════════════════
# Hook: on_session_finalize (real session boundary — NOT on_session_end)
# ═══════════════════════════════════════════════════════════════════════════

def _on_session_finalize(
    session_id: str = "",
    **_kwargs: Any,
) -> None:
    """Session boundary: snapshot audit data → async LLM analysis."""
    if _is_disabled():
        return

    effective_session = session_id or "unknown"

    # CRITICAL: snapshot data BEFORE spawning thread.
    # harness-guard's on_session_end (per-turn) may clear its own audit log,
    # but our on_session_finalize is a different hook (per-session).
    # Still, snapshot is the safe pattern per plan_review F2-2.
    entries = get_log().snapshot_and_clear(effective_session)

    if not entries:
        return  # nothing to analyze

    # Also clear pending advice for this session
    _advice_queue.pop(effective_session, None)

    # Kick off async analysis (daemon thread — non-blocking)
    trigger_async_analysis(effective_session, entries)


# ═══════════════════════════════════════════════════════════════════════════
# Registration
# ═══════════════════════════════════════════════════════════════════════════

def register(ctx) -> None:
    """Register hooks with Hermes."""
    logger.info(
        "config-advisor: registering pre_llm_call + post_tool_call + on_session_finalize hooks"
    )
    ctx.register_hook("pre_llm_call", _on_pre_llm_call)
    ctx.register_hook("post_tool_call", _on_post_tool_call)
    ctx.register_hook("on_session_finalize", _on_session_finalize)
