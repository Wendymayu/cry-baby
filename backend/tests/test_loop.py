import asyncio
from agent.llm_client import TextDelta, Finish
from agent.sessions import SessionStore
from agent.tools import tool, ToolManager
from agent.react_loop import ReActAgent, AgentRequest
from tests.conftest import FakeLLM


@tool
async def echo(text: str) -> str:
    """Echo the given text back to the caller."""
    return f"echo: {text}"


def _make_agent(scripts, tmp_path):
    fake = FakeLLM(scripts)
    store = SessionStore(tmp_path / "sessions")
    tm = ToolManager(); tm.register(echo)
    return ReActAgent(llm=fake, store=store, tools=tm, max_steps=10,
                      workspace_dir=str(tmp_path), memory_dir=str(tmp_path),
                      skills_dir=str(tmp_path))


def test_loop_calls_tool_then_finishes(tmp_path):
    asyncio.run(SessionStore(tmp_path / "sessions").create_session("s1"))
    agent = _make_agent([
        [Finish(finish_reason="tool_calls", assistant_message={
            "role": "assistant", "content": None,
            "tool_calls": [{"id": "c1", "type": "function",
                           "function": {"name": "echo", "arguments": "{\"text\":\"hi\"}"}}]})],
        [TextDelta(content="done"), Finish(finish_reason="stop",
                  assistant_message={"role": "assistant", "content": "done"})],
    ], tmp_path)

    req = AgentRequest(session_id="s1", request_id="r1", query="please echo hi")
    events = []
    async def run():
        async for e in agent.run(req):
            events.append(e)
    asyncio.run(run())

    kinds = [e.kind for e in events]
    assert "tool_call" in kinds
    assert "tool_result" in kinds
    assert kinds[-1] == "final"
    assert events[-1].content == "done"
    tr = next(e for e in events if e.kind == "tool_result")
    assert tr.result == "echo: hi"
    msgs = SessionStore(tmp_path / "sessions").get_messages("s1")
    assert any(m.get("role") == "tool" for m in msgs)
