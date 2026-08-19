import asyncio
from agent.prompts import PromptSection, SystemPromptBuilder
from agent.hooks import HookManager, HookEvent, HookContext
from agent.events import LoopEvent


def test_prompt_builder_orders_by_priority():
    b = SystemPromptBuilder()
    b.add_section(PromptSection(name="z", content="late", priority=90))
    b.add_section(PromptSection(name="a", content="first", priority=10))
    assert b.build().startswith("first")


def test_loopevent_construct():
    e = LoopEvent(kind="text_delta", content="hi")
    assert e.kind == "text_delta" and e.content == "hi"
    f = LoopEvent(kind="final", content="done", is_final=True)
    assert f.is_final is True


def test_hook_manager_executes():
    calls = []

    class H:
        priority = 50
        def get_callbacks(self):
            return {HookEvent.AFTER_MODEL_CALL: self._after}
        async def _after(self, ctx):
            calls.append("after")
        def init(self, agent): pass
        def uninit(self, agent): pass

    ctx = HookContext(agent=None, event=HookEvent.AFTER_MODEL_CALL,
                      inputs=None, session_id=None, request_id=None)
    hm = HookManager()
    hm.register_hook(H())
    asyncio.run(hm.execute(HookEvent.AFTER_MODEL_CALL, ctx))
    assert calls == ["after"]
