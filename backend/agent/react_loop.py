"""ReActAgent — a ReAct-pattern agent: think -> (tool -> result)* -> answer.

run() is an async generator yielding LoopEvent frames so the ws send
boundary stays in server.py (agent never touches the socket).

Twinkle is stream-only; unary has been removed.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass
from typing import AsyncIterator

from .llm_client import Finish, LLMClient, TextDelta
from .sessions import SessionStore
from .permissions.approval_registry import APPROVAL_REGISTRY, ApprovalPendingRecord
from .tools.manager import ToolManager
from .tools.errors import format_tool_error
from .hooks.base import (
    AgentHook,
    HookContext,
    HookEvent,
    HookInterrupt,
    InvokeInputs,
    ModelCallInputs,
    ToolCallInputs,
)
from .hooks.decorator import hook
from .hooks.manager import HookManager
from .prompts import PromptSection, SystemPromptBuilder
from .events import LoopEvent

log = logging.getLogger("twinkle.agentserver")


# ---------------------------------------------------------------------------
# AgentRequest — pure business input, no transport-layer concepts
# ---------------------------------------------------------------------------

@dataclass
class AgentRequest:
    """One agent run's business inputs. No E2A / WebSocket concepts.

    server.py is responsible for constructing this from the transport envelope.
    """

    session_id: str
    request_id: str
    query: str


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def build_system_prompt(workspace_dir="", memory_dir="", skills_dir="") -> str:
    """Build the base system prompt injected once per session at position 0.

    Includes agent identity, runtime environment, workspace overview, and
    tool usage guidance. Dynamic values (platform, date, workspace paths)
    are resolved at injection time so the prompt stays current.
    """
    os_type = sys.platform

    # Windows-specific mkdir warning
    mkdir_warning = ""
    if os_type.startswith("win"):
        mkdir_warning = (
            "\n⚠️ Windows `mkdir` 不支持 `-p`！创建嵌套目录请用 "
            "PowerShell `New-Item -ItemType Directory -Path \"parent/child\" -Force` "
            "或 cmd 分步 `mkdir parent && mkdir parent\\child`。"
        )

    prompt = f"""# 身份与行为原则

对外交流时，不要主动提及内部框架名、目录名或运行细节。

- **直接进入正题** — 少说"好的""很乐意"，直接开始做事。
- **先想再做** — 接到任务后先理清思路，想清楚步骤再执行。
- **办事严谨** — 做事牢靠是获得信任的关键。
- **尽量不拒绝** — 尽量满足合理请求，仅在涉及违法、有害或超出能力时才拒绝并说明原因。
- **简洁输出** — 不要重复表达相同的意思，每个想法只说一次。

# 运行环境

**必须严格使用与当前平台匹配的命令语法**，切勿混用其他平台命令。常见差异：

| 操作 | Windows | Linux/macOS |
|------|---------|-------------|
| 创建目录 | `mkdir folder` | `mkdir -p folder` |
| 查看文件 | `type file.txt` | `cat file.txt` |
| 列出文件 | `dir` | `ls -la` |
| 删除目录 | `rmdir folder` | `rm -rf folder` |{mkdir_warning}

# 工作区

以下目录仅供执行任务时内部参考，不要主动向用户展示内部路径。

| 路径 | 用途 |
|------|------|
| `{workspace_dir}` | 工作区根目录，文件操作默认收敛于此 |
| `{memory_dir}` | 长期记忆存储 |
| `{skills_dir}` | 技能库 |

# 工具使用指南

## Todo（任务规划）

你有 todo 工具来规划和追踪多步骤任务：todo_create、todo_update、todo_list、todo_get。
- 非平凡的多步骤请求：先调 todo_create 列出子任务，逐步执行并用 todo_update(task_id, status="completed", result=...) 标记完成，调 todo_list 查看进度，调 todo_get 查看单任务详情。
- 简单单步请求：直接回答或调工具，不要使用 todo。

"""

    return prompt


def normal_base_sections(workspace_dir="", memory_dir="", skills_dir="") -> list[PromptSection]:
    """Normal-mode base sections for the generic agent path."""
    return [PromptSection("system_prompt", build_system_prompt(workspace_dir, memory_dir, skills_dir), priority=10)]


_MAX_HOOK_RETRIES = 3


# ---------------------------------------------------------------------------
# ReActAgent
# ---------------------------------------------------------------------------

class ReActAgent:
    """A ReAct-pattern agent: LLM think → tool calls → results → re-decide.

    Hooks are injected at construction time via *hooks*.  ``run()`` is the
    single public entry point — it processes one user message through the
    ReAct loop and yields LoopEvent frames.
    """

    def __init__(
        self,
        llm: LLMClient,
        store: SessionStore,
        tools: ToolManager,
        *,
        hooks: tuple[AgentHook, ...] = (),
        max_steps: int | None = None,
        base_sections: list[PromptSection] | None = None,
        workspace_dir: str | None = None,
        memory_dir: str | None = None,
        skills_dir: str | None = None,
    ) -> None:
        self._llm = llm
        self._session_store = store
        self._tool_manager = tools
        self._hook_manager = HookManager()
        for h in hooks:
            self._hook_manager.register_hook(h)
        self._max_steps = max_steps  # None = unbounded; anti-infinite-loop backstop only
        self._base_sections = base_sections
        self._workspace_dir = workspace_dir or ""
        self._memory_dir = memory_dir or ""
        self._skills_dir = skills_dir or ""

    @property
    def session_store(self) -> SessionStore:
        """The SessionStore this agent reads/writes conversation history from."""
        return self._session_store

    def register_hook(self, hook_instance: AgentHook) -> None:
        """Register an AgentHook (kept for test injection — prefer constructor)."""
        self._hook_manager.register_hook(hook_instance)

    def unregister_hook(self, hook_instance: AgentHook) -> None:
        """Unregister an AgentHook."""
        self._hook_manager.unregister_hook(hook_instance)

    # -- Public entry point -------------------------------------------------

    async def run(self, request: AgentRequest) -> AsyncIterator[LoopEvent]:
        """Process one user message through the ReAct loop.

        Triggers BEFORE_INVOKE / AFTER_INVOKE hooks, delegates to the
        internal ReAct loop, writes interrupt snapshots on failure.
        """
        session_id = request.session_id
        request_id = request.request_id

        ctx = HookContext(
            agent=self,
            event=HookEvent.BEFORE_INVOKE,
            inputs=InvokeInputs(query=request.query),
            session_id=session_id,
            request_id=request_id,
            extra={},
        )

        await self._hook_manager.execute(HookEvent.BEFORE_INVOKE, ctx)

        completed_normally = False
        try:
            async for frame in self._run_react_loop(ctx, request):
                yield frame
            completed_normally = True
        except HookInterrupt:
            completed_normally = True
            yield LoopEvent(kind="error", message="execution interrupted", is_final=True)
        except Exception as exc:
            ctx.exception = exc
            await self._hook_manager.execute(HookEvent.ON_MODEL_EXCEPTION, ctx)
            raise
        finally:
            if not completed_normally:
                try:
                    snapshot = await self._build_interrupt_snapshot(ctx, session_id)
                    await self._session_store.append(
                        session_id,
                        {"role": "assistant", "content": snapshot},
                        request_id=request_id,
                    )
                except asyncio.CancelledError:
                    log.warning("interrupt snapshot cancelled for session %s", session_id)
                except Exception:
                    log.exception("failed to write interrupt snapshot for session %s", session_id)
            APPROVAL_REGISTRY.clear_all_pending(session_id)
            await self._hook_manager.execute(HookEvent.AFTER_INVOKE, ctx)

    # -- ReAct loop ---------------------------------------------------------

    async def _run_react_loop(
        self,
        ctx: HookContext,
        request: AgentRequest,
    ) -> AsyncIterator[LoopEvent]:
        """The ReAct loop with hook trigger points.

        Model calls use manual self._hook_manager.execute() (async generator
        incompatible with @hook).  Tool calls use @hook-decorated _tool_call.
        """
        session_id = request.session_id
        request_id = request.request_id

        await self._fill_missing_tool_results(session_id, request_id)

        await self._session_store.append(
            session_id,
            {"role": "user", "content": request.query},
            request_id=request_id,
        )

        seq = 0
        full_text = ""
        # 一次冻结 tool schemas:invoke 内不变。
        # 对齐 jiuwenswarm:tools 跨步稳定 → system prefix 字节稳定 → provider 自动 prefix cache 命中。
        tool_schemas = self._tool_manager.schemas()
        step = 0
        while self._max_steps is None or step < self._max_steps:
            step += 1
            msgs = self._session_store.get_messages(session_id)

            # -- BEFORE_MODEL_CALL -- #
            # 每步新建 builder + 注 base sections(或构造时注入的 member/subagent)
            builder = SystemPromptBuilder()
            if self._base_sections is not None:
                base = self._base_sections
            else:
                base = normal_base_sections(self._workspace_dir, self._memory_dir, self._skills_dir)
            for sec in base:
                builder.add_section(sec)
            # per-invoke 冻结段(before_invoke hooks 如 SkillHook/MemoryHook 注入,跨步稳定)
            for sec in ctx.extra.get("frozen_sections", []):
                builder.add_section(sec)
            ctx.builder = builder

            ctx.inputs = ModelCallInputs(messages=msgs, tools=tool_schemas)
            await self._hook_manager.execute(HookEvent.BEFORE_MODEL_CALL, ctx)

            # -- 注 builder.build() 为首条 system + env 尾部 UserMessage -- #
            ctx.inputs.messages = (
                [{"role": "system", "content": ctx.builder.build()}]
                + ctx.inputs.messages
            )
            env_entries = ctx.extra.pop("environment_context", None)
            if env_entries:
                env_text = "\n\n".join(e["content"] for e in env_entries)
                ctx.inputs.messages.append(
                    {"role": "user",
                     "content": f"<environment_context>\n{env_text}\n</environment_context>"})

            # Check force_finish
            force_finish = ctx.consume_force_finish_request()
            if force_finish is not None:
                yield LoopEvent(
                    kind="final",
                    content=str(force_finish.result or ""),
                    is_final=True,
                )
                return

            # -- LLM stream with retry loop -- #
            should_reask = False
            for retry_attempt in range(_MAX_HOOK_RETRIES + 1):
                ctx.retry_attempt = retry_attempt
                ctx.exception = None
                try:
                    async for stream_event in self._llm.stream(messages=ctx.inputs.messages, tools=ctx.inputs.tools):
                        if isinstance(stream_event, TextDelta):
                            full_text += stream_event.content
                            yield LoopEvent(
                                kind="text_delta",
                                content=stream_event.content,
                            )
                            seq += 1
                        elif isinstance(stream_event, Finish):
                            await self._session_store.append(
                                session_id,
                                stream_event.assistant_message,
                                request_id=request_id,
                                event_type="chat.final",
                            )
                            tool_calls = stream_event.assistant_message.get("tool_calls")
                            if stream_event.finish_reason == "tool_calls" and tool_calls:
                                if len(tool_calls) > 1:
                                    # --- Parallel path ---
                                    try:
                                        parallel_results = await self._try_parallel_tool_calls(
                                            tool_calls, session_id, request_id,
                                        )
                                        id_to_call = {tc["id"]: tc for tc in tool_calls}
                                        for tool_call_id, result in parallel_results:
                                            tc = id_to_call.get(tool_call_id, {})
                                            try:
                                                p_args = json.loads(tc.get("function", {}).get("arguments") or "{}")
                                            except Exception:
                                                p_args = {}
                                            yield LoopEvent(
                                                kind="tool_call",
                                                tool_call_id=tool_call_id,
                                                name=tc.get("function", {}).get("name"),
                                                args=p_args,
                                            )
                                            yield LoopEvent(
                                                kind="tool_result",
                                                tool_call_id=tool_call_id,
                                                result=result,
                                            )
                                            await self._session_store.append(
                                                session_id,
                                                {"role": "tool", "tool_call_id": tool_call_id, "content": result},
                                                request_id=request_id,
                                                event_type="chat.tool_result",
                                            )
                                        await self._hook_manager.execute(HookEvent.AFTER_MODEL_CALL, ctx)
                                        should_reask = True
                                        break
                                    except HookInterrupt:
                                        log.info("parallel tool calls fell back to sequential (HookInterrupt)")
                                if len(tool_calls) <= 1 or should_reask is False:
                                    # --- Sequential path ---
                                    for tool_call in tool_calls:
                                        name = tool_call["function"]["name"]
                                        try:
                                            args = json.loads(tool_call["function"]["arguments"] or "{}")
                                        except Exception:
                                            args = {}
                                        yield LoopEvent(
                                            kind="tool_call",
                                            tool_call_id=tool_call["id"],
                                            name=name,
                                            args=args,
                                        )
                                        ctx.inputs = ToolCallInputs(
                                            name=name, args=args, tool_call_id=tool_call["id"]
                                        )
                                        try:
                                            result = await self._tool_call(ctx)
                                        except HookInterrupt as hook_interrupt:
                                            if "approval_id" not in hook_interrupt.data:
                                                yield LoopEvent(
                                                    kind="error",
                                                    message="tool execution interrupted",
                                                    is_final=True,
                                                )
                                                return
                                            # ASK: register Future + yield approval_request + suspend
                                            approval_id = hook_interrupt.data["approval_id"]
                                            future = APPROVAL_REGISTRY.register(approval_id)
                                            APPROVAL_REGISTRY.save_pending(session_id, ApprovalPendingRecord(
                                                approval_id=approval_id,
                                                tool=hook_interrupt.data["tool"],
                                                args=hook_interrupt.data["args"],
                                                tool_call_id=tool_call["id"],
                                                reason=hook_interrupt.data["reason"],
                                                request_id=request_id,
                                                session_id=session_id,
                                                created_at=time.time(),
                                            ))
                                            yield LoopEvent(
                                                kind="approval_request",
                                                approval_id=approval_id,
                                                name=hook_interrupt.data["tool"],
                                                args=hook_interrupt.data["args"],
                                                tool_call_id=tool_call["id"],
                                                reason=hook_interrupt.data.get("reason"),
                                            )
                                            seq += 1
                                            decision = await future  # SUSPEND
                                            if decision in ("allow", "allow_always"):
                                                ctx.extra["_approval_decision"] = decision
                                                ctx.extra.setdefault("_approved_tool_call_ids", set()).add(tool_call["id"])
                                                try:
                                                    result = await self._tool_call(ctx)
                                                except HookInterrupt:
                                                    raise
                                                except Exception as exc:
                                                    result = format_tool_error(exc)
                                            else:
                                                result = format_tool_error(
                                                    f"tool denied by user: {hook_interrupt.data['tool']} "
                                                    f"— {hook_interrupt.data.get('reason', '')}")
                                        except Exception as exc:
                                            result = format_tool_error(exc)
                                        yield LoopEvent(
                                            kind="tool_result",
                                            tool_call_id=tool_call["id"],
                                            result=result,
                                        )
                                        await self._session_store.append(
                                            session_id,
                                            {"role": "tool", "tool_call_id": tool_call["id"], "content": result},
                                            request_id=request_id,
                                            event_type="chat.tool_result",
                                        )
                                    await self._hook_manager.execute(HookEvent.AFTER_MODEL_CALL, ctx)
                                should_reask = True
                                break
                            # Final answer
                            yield LoopEvent(
                                kind="final",
                                content=full_text,
                                is_final=True,
                            )
                            await self._hook_manager.execute(HookEvent.AFTER_MODEL_CALL, ctx)
                            return
                    if should_reask:
                        break
                    await self._hook_manager.execute(HookEvent.AFTER_MODEL_CALL, ctx)
                    break
                except asyncio.CancelledError:
                    raise
                except HookInterrupt:
                    raise
                except Exception as exc:
                    ctx.exception = exc
                    await self._hook_manager.execute(HookEvent.ON_MODEL_EXCEPTION, ctx)
                    force_finish = ctx.consume_force_finish_request()
                    if force_finish is not None:
                        yield LoopEvent(
                            kind="final",
                            content=str(force_finish.result or ""),
                            is_final=True,
                        )
                        return
                    retry_request = ctx.consume_retry_request()
                    if retry_request is not None and retry_attempt < _MAX_HOOK_RETRIES:
                        if retry_request.delay > 0:
                            await asyncio.sleep(retry_request.delay)
                        log.info("hook requested LLM retry, attempt %d/%d",
                                 retry_attempt + 1, _MAX_HOOK_RETRIES)
                        continue
                    raise
            if should_reask:
                continue

        # exceeded max_steps (only when bounded)
        if self._max_steps is not None:
            yield LoopEvent(
                kind="error",
                message=f"agent loop exceeded max_steps={self._max_steps}",
                is_final=True,
            )

    # -- Parallel tool execution --------------------------------------------

    async def _try_parallel_tool_calls(
        self,
        tool_calls: list[dict],
        session_id: str,
        request_id: str,
    ) -> list[tuple[str, str]]:
        """Execute multiple tool calls concurrently via asyncio.gather.

        Each tool call gets its own HookContext (isolated inputs + extra) so
        concurrent calls don't race on shared state.  Results are returned in
        the same order as *tool_calls*.
        """
        results_per_tool: list[tuple[str, str] | None] = [None] * len(tool_calls)

        async def _execute_one_tool(idx: int, tool_call: dict) -> None:
            name = tool_call["function"]["name"]
            try:
                args = json.loads(tool_call["function"]["arguments"] or "{}")
            except Exception:
                args = {}

            tool_call_context = HookContext(
                agent=self,
                event=HookEvent.BEFORE_TOOL_CALL,
                inputs=ToolCallInputs(name=name, args=args, tool_call_id=tool_call["id"]),
                session_id=session_id,
                request_id=request_id,
                extra={},
            )
            try:
                result = await self._tool_call(tool_call_context)
            except HookInterrupt:
                raise
            except Exception as exc:
                result = format_tool_error(exc)

            results_per_tool[idx] = (tool_call["id"], result)

        raw_results = await asyncio.gather(
            *[asyncio.create_task(_execute_one_tool(i, tool_call)) for i, tool_call in enumerate(tool_calls)],
            return_exceptions=True,
        )

        for result_item in raw_results:
            if isinstance(result_item, HookInterrupt):
                raise result_item

        results: list[tuple[str, str]] = []
        for result_item in results_per_tool:
            if result_item is not None:
                results.append(result_item)
        return results

    # -- Interrupt snapshot -------------------------------------------------

    async def _build_interrupt_snapshot(self, ctx: HookContext, session_id: str) -> str:
        """Build an interrupt snapshot message from session history + TodoStore."""
        parts = ["[SYSTEM] 任务中断。"]

        if ctx.exception:
            exc_type = type(ctx.exception).__name__
            exc_msg = str(ctx.exception)
            if len(exc_msg) > 100:
                exc_msg = exc_msg[:100] + "..."
            parts.append(f"中断原因：{exc_type}: {exc_msg}")
        else:
            parts.append("中断原因：请求被取消")

        msgs = self._session_store.get_messages(session_id)
        for m in reversed(msgs):
            if m.get("role") == "assistant" and m.get("tool_calls"):
                tools = [tc.get("function", {}).get("name", "unknown") for tc in m.get("tool_calls", [])]
                parts.append(f"中断前正在执行：{', '.join(tools)}")
                break

        return " ".join(parts)

    # -- Orphan tool-result fill --------------------------------------------

    async def _fill_missing_tool_results(self, session_id: str, request_id: str) -> None:
        """Inject synthetic tool_result for orphan tool_calls from a crash."""
        msgs = self._session_store.get_messages(session_id)
        if not msgs:
            return
        last_assistant = None
        for m in reversed(msgs):
            if m.get("role") == "assistant" and m.get("tool_calls"):
                last_assistant = m
                break
        if last_assistant is None:
            return

        pending = APPROVAL_REGISTRY.get_pending(session_id)
        pending_map = {p["tool_call_id"]: p for p in pending if p.get("tool_call_id")}

        for tc in last_assistant["tool_calls"]:
            tc_id = tc.get("id")
            if tc_id and not any(m.get("role") == "tool" and m.get("tool_call_id") == tc_id
                                for m in msgs):
                tool_name = tc.get("function", {}).get("name", "unknown")
                tool_args = tc.get("function", {}).get("arguments", "")
                parts = [f"[interrupted: {tool_name} was interrupted, result unknown."]
                if tool_args:
                    args_preview = tool_args[:200] + ("..." if len(tool_args) > 200 else "")
                    parts.append(f"Args: {args_preview}.")
                approval = pending_map.get(tc_id)
                if approval:
                    parts.append(f"Approval was pending (reason: {approval.get('reason', 'unknown')}).")
                parts.append("]")
                content = " ".join(parts)
                await self._session_store.append(
                    session_id,
                    {"role": "tool", "tool_call_id": tc_id, "content": content},
                    request_id=request_id)

    # -- @hook-decorated tool call ------------------------------------------

    @hook(HookEvent.BEFORE_TOOL_CALL, HookEvent.AFTER_TOOL_CALL,
          on_exception=HookEvent.ON_TOOL_EXCEPTION)
    async def _tool_call(self, ctx: HookContext) -> str:
        """Tool execution wrapped with @hook lifecycle."""
        inputs: ToolCallInputs = ctx.inputs  # type: ignore[assignment]
        return await self._tool_manager.execute(inputs.name, inputs.args)
