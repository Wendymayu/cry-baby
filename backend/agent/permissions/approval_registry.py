"""ApprovalRegistry — approval_id → asyncio.Future 单例(对齐 TodoStore)。

agent_loop 在 ASK 时 register(approval_id) 拿 Future 并 await;ws_handler
收到 approval.respond 时 resolve Future。

Phase 10: 审批状态持久化 — ASK 时 save_pending() 写磁盘,resolve 后
clear_pending() 清除,重连时 get_pending() 读取,让浏览器断连后能恢复审批卡片。
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger("twinkle.permissions.approval")


@dataclass
class ApprovalPendingRecord:
    """审批中断时持久化的元数据,用于浏览器重连后恢复审批卡片。"""

    approval_id: str
    tool: str
    args: dict[str, Any]
    tool_call_id: str
    reason: str
    request_id: str
    session_id: str
    created_at: float


class ApprovalRegistry:
    def __init__(self, sessions_dir) -> None:
        self._futures: dict[str, asyncio.Future] = {}
        self._sessions_dir = str(sessions_dir)

    # --- persistence helpers ---

    def _pending_path(self, session_id: str) -> Path:
        """Return path to the session's pending-approval file."""
        return Path(self._sessions_dir) / session_id / ".approval_pending.json"

    def _read_pending_file(self, session_id: str) -> list[dict]:
        """Read pending approvals from disk. Returns [] on missing/corrupt file."""
        path = self._pending_path(session_id)
        if not path.is_file():
            return []
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            log.warning("corrupt .approval_pending.json for session %s, ignoring", session_id)
            return []

    def _write_pending_file(self, session_id: str, records: list[dict]) -> None:
        """Atomically write pending approvals to disk (.tmp + os.replace)."""
        path = self._pending_path(session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        try:
            temp_path.write_text(json.dumps(records, ensure_ascii=False), encoding="utf-8")
            os.replace(temp_path, path)
        except Exception:
            log.exception("failed to write .approval_pending.json for session %s", session_id)
            temp_path.unlink(missing_ok=True)

    def save_pending(self, session_id: str, record: ApprovalPendingRecord) -> None:
        """Append a pending approval record to disk."""
        records = self._read_pending_file(session_id)
        records.append(asdict(record))
        self._write_pending_file(session_id, records)

    def clear_pending(self, session_id: str, approval_id: str) -> None:
        """Remove a specific pending approval from disk."""
        records = self._read_pending_file(session_id)
        remaining = [r for r in records if r.get("approval_id") != approval_id]
        if not remaining:
            # Remove the file entirely when empty
            path = self._pending_path(session_id)
            path.unlink(missing_ok=True)
        else:
            self._write_pending_file(session_id, remaining)

    def get_pending(self, session_id: str) -> list[dict]:
        """Read pending approvals for a session. Used by approval.check_pending RPC."""
        return self._read_pending_file(session_id)

    def clear_all_pending(self, session_id: str) -> None:
        """Remove all pending approvals for a session. Safety net in run_stream finally."""
        path = self._pending_path(session_id)
        path.unlink(missing_ok=True)

    # --- in-memory Future management ---

    def register(self, approval_id: str) -> asyncio.Future:
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        self._futures[approval_id] = fut
        return fut

    def resolve(self, approval_id: str, decision: str) -> bool:
        fut = self._futures.get(approval_id)
        if fut is None or fut.done():
            return False
        fut.set_result(decision)
        return True

    def cancel_all(self) -> None:
        for fut in list(self._futures.values()):
            if not fut.done():
                fut.cancel()
        self._futures.clear()


# 模块级单例
APPROVAL_REGISTRY = ApprovalRegistry(sessions_dir="sessions")
