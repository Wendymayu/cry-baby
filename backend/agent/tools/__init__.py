from .base import Tool, ToolCard
from .local_function import LocalFunction
from .decorator import tool
from .manager import ToolManager


def tool_manager() -> ToolManager:
    """精简构建器:不预注册内置工具;领域工具在各 Task 内自行 register。"""
    return ToolManager()


__all__ = ["Tool", "ToolCard", "LocalFunction", "tool", "ToolManager", "tool_manager"]
