import asyncio

from agent.permissions import ApprovalRegistry


def test_register_and_resolve(tmp_sessions_dir):
    reg = ApprovalRegistry(sessions_dir=tmp_sessions_dir)

    async def _setup():
        fut = reg.register("ap1")
        assert not fut.done()
        assert reg.resolve("ap1", "approved") is True
        assert fut.done() and fut.result() == "approved"

    asyncio.run(_setup())


def test_resolve_unknown_returns_false(tmp_sessions_dir):
    reg = ApprovalRegistry(sessions_dir=tmp_sessions_dir)
    assert reg.resolve("nope", "approved") is False
