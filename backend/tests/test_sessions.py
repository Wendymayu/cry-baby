import asyncio

from agent.sessions import SessionStore


def test_session_append_and_get_messages(tmp_sessions_dir):
    store = SessionStore(tmp_sessions_dir)
    asyncio.run(store.create_session("s1"))
    asyncio.run(store.append("s1", {"role": "user", "content": "hi"}))
    asyncio.run(store.append("s1", {"role": "assistant", "content": "hello"}))
    msgs = store.get_messages("s1")
    assert len(msgs) == 2
    assert msgs[0]["content"] == "hi"
    assert msgs[1]["role"] == "assistant"


def test_session_persists_across_instances(tmp_sessions_dir):
    store1 = SessionStore(tmp_sessions_dir)
    asyncio.run(store1.create_session("s2"))
    asyncio.run(store1.append("s2", {"role": "user", "content": "persist"}))
    store2 = SessionStore(tmp_sessions_dir)
    msgs = store2.get_messages("s2")
    assert len(msgs) == 1 and msgs[0]["content"] == "persist"
