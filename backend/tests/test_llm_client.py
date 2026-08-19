import asyncio

from agent.llm_client import LLMClient, TextDelta, Finish
from tests.conftest import FakeLLM


def test_llmclient_constructable():
    c = LLMClient(base_url="http://x", api_key="k", model="m", timeout=1.0)
    assert c is not None


def test_fake_llm_contract():
    fake = FakeLLM([
        [Finish(finish_reason="stop", assistant_message={"role": "assistant", "content": "hi"})]
    ])
    out = []
    async def run():
        async for ev in fake.stream([], []):
            out.append(ev)
    asyncio.run(run())
    assert isinstance(out[0], Finish) and out[0].finish_reason == "stop"
    assert fake.calls == 1
