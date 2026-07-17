"""Lightweight audit trail for config-advisor.

Records tool calls per session for retrospective analysis.
Thread-safe (deque + lock), same pattern as harness-guard's audit_log.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_MAX_ENTRIES_PER_SESSION = 100
_MAX_SESSIONS = 50


@dataclass
class ToolEntry:
    tool: str
    args_summary: str  # truncated
    result_summary: str  # truncated
    ts: float
    # Tag for routing analysis
    config_related: bool = False  # touched a config file?


def _summarize(data: Any, max_len: int = 200) -> str:
    """Truncate data to a compact string for storage."""
    s = str(data) if not isinstance(data, str) else data
    if len(s) > max_len:
        return s[:max_len] + "…"
    return s


# Config file patterns — if tool args reference these, tag as config_related
_CONFIG_PATTERNS = (
    "SOUL.md", ".hermes.md", "MEMORY.md", "USER.md",
    "config.yaml", "plugin.yaml", "SKILL.md",
    "memory",  # the memory tool
    "skill_manage",  # skill operations
)


def _is_config_related(tool_name: str, args: Any) -> bool:
    """Check if this tool call touches config files."""
    if tool_name in ("memory", "skill_manage"):
        return True
    args_str = str(args) if args else ""
    return any(p in args_str for p in _CONFIG_PATTERNS)


class ConfigAuditLog:
    """Thread-safe per-session audit log."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sessions: dict[str, deque] = {}

    def append(self, session_id: str, entry: ToolEntry) -> None:
        with self._lock:
            if session_id not in self._sessions:
                if len(self._sessions) >= _MAX_SESSIONS:
                    # Evict oldest session
                    oldest = min(self._sessions.keys(), key=lambda s: self._sessions[s][0].ts if self._sessions[s] else 0)
                    del self._sessions[oldest]
                self._sessions[session_id] = deque(maxlen=_MAX_ENTRIES_PER_SESSION)
            self._sessions[session_id].append(entry)

    def get_session(self, session_id: str) -> list[ToolEntry]:
        """Return a copy of entries for a session."""
        with self._lock:
            dq = self._sessions.get(session_id)
            if not dq:
                return []
            return list(dq)

    def snapshot_and_clear(self, session_id: str) -> list[ToolEntry]:
        """Atomically copy + clear a session's entries.

        Used by on_session_finalize to avoid race with harness-guard's clear.
        """
        with self._lock:
            dq = self._sessions.pop(session_id, None)
            if not dq:
                return []
            return list(dq)

    def clear_session(self, session_id: str) -> None:
        with self._lock:
            self._sessions.pop(session_id, None)


# Module-level singleton
_log = ConfigAuditLog()


def get_log() -> ConfigAuditLog:
    return _log
