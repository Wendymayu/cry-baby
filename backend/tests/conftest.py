import os, tempfile
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("DB_URL", "sqlite:///:memory:")
os.environ.setdefault("LLM_BASE_URL", "http://localhost")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_MODEL", "test-model")

import pytest
from fastapi_app.database import Base, engine, SessionLocal


@pytest.fixture()
def db():
    Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def tmp_sessions_dir(tmp_path):
    return tmp_path / "sessions"


from agent.llm_client import TextDelta, Finish


class FakeLLM:
    """模拟 LLMClient.stream 契约:按脚本依次吐 TextDelta / Finish。"""
    def __init__(self, scripts):
        self._scripts = list(scripts)
        self.calls = 0

    async def stream(self, messages, tools):
        seq = self._scripts[self.calls]
        self.calls += 1
        for ev in seq:
            yield ev
