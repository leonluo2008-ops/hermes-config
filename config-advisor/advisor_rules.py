"""Information routing advice rules for config-advisor.

Pure rule-based checks (no LLM). Analyzes tool calls and generates
non-blocking suggestions injected via pre_llm_call on the next turn.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from .audit_trail import ToolEntry

logger = logging.getLogger(__name__)

# Max advice length to keep injection <500 chars total
_MAX_ADVICE_LEN = 300


def analyze_tool_call(
    tool_name: str,
    args: Any,
    result: Any,
) -> Optional[str]:
    """Check if a tool call warrants a routing suggestion.

    Returns advice string (to be queued for next turn's pre_llm_call),
    or None if no suggestion.
    """
    if tool_name == "memory":
        return _check_memory_write(args)
    if tool_name == "patch":
        return _check_patch_target(args)
    return None


def _check_memory_write(args: Any) -> Optional[str]:
    """When agent writes to MEMORY, suggest better routing if applicable."""
    if not isinstance(args, dict):
        return None

    action = args.get("action", "")
    if action not in ("add", "replace", "operations"):
        return None

    # Extract content being written
    content = ""
    if "content" in args:
        content = str(args["content"])
    elif "operations" in args:
        content = str(args["operations"])

    if not content:
        return None

    suggestions = []

    # Check: is this a project-level constraint? (contains paths, project names)
    if any(kw in content.lower() for kw in ("/home/", "~/.hermes/", "项目", "project", "构建", "deploy", "build")):
        suggestions.append(
            "💡 这条信息看起来是项目级约束，建议放到 .hermes.md（持久可见 vs MEMORY 冻结快照）"
        )

    # Check: is this a 3+ step workflow? (contains numbered steps, arrows, sequences)
    if any(kw in content for kw in ("→", "步骤", "step", "1.", "2.", "3.", "流程")):
        suggestions.append(
            "💡 这看起来是 3+ 步骤流程，建议创建 skill（渐进式披露，不占常驻 token）"
        )

    # Check: is this temporary state? (commit SHA, PR number, task progress)
    if any(kw in content.lower() for kw in ("commit", "pr #", "phase", "已提交", "已完成", "进度")):
        suggestions.append(
            "💡 这看起来是临时状态，7 天内会过期——不写 MEMORY，用 session_search 回忆"
        )

    if not suggestions:
        return None

    advice = "\n".join(suggestions[:2])  # max 2 suggestions
    if len(advice) > _MAX_ADVICE_LEN:
        advice = advice[:_MAX_ADVICE_LEN - 3] + "…"
    return advice


def _check_patch_target(args: Any) -> Optional[str]:
    """When agent patches a config file, check for issues."""
    if not isinstance(args, dict):
        return None

    path = str(args.get("path", ""))
    if not path:
        return None

    # Check: patching a large .hermes.md section?
    if ".hermes.md" in path and "new_string" in args:
        new_str = str(args["new_string"])
        if len(new_str) > 1500:  # ~50 lines
            return (
                "💡 这段写入较长（>50 行），建议考虑拆成 skill，"
                ".hermes.md 只留 pointer"
            )

    return None


def summarize_config_activity(entries: list[ToolEntry]) -> str:
    """Summarize config-related tool activity for retrospective report.

    Used by analyzer.py to build the LLM prompt.
    """
    config_entries = [e for e in entries if e.config_related]
    if not config_entries:
        return "本会话无配置文件操作。"

    lines = [f"本会话共 {len(config_entries)} 次配置相关操作："]
    counts: dict[str, int] = {}
    for e in config_entries:
        counts[e.tool] = counts.get(e.tool, 0) + 1
    for tool, count in sorted(counts.items(), key=lambda x: -x[1]):
        lines.append(f"  {tool}: {count} 次")

    return "\n".join(lines)
