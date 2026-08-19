from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Any

LoopKind = Literal["text_delta", "tool_call", "tool_result",
                   "approval_request", "final", "error"]


@dataclass
class LoopEvent:
    kind: LoopKind
    content: str | None = None
    tool_call_id: str | None = None
    name: str | None = None
    args: dict[str, Any] | None = None
    result: str | None = None
    approval_id: str | None = None
    reason: str | None = None
    message: str | None = None
    is_final: bool = False
    sequence: int = 0
