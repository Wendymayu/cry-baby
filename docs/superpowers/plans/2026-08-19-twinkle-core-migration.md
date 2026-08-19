# Twinkle 核心迁移 + 后端脚手架 实现计划 (Plan 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 twinkle 的 agent 核心基础设施(llm_client / tools 框架 / sessions / hooks / prompts / approval_registry / ReAct 循环)迁移进 cry-baby 的 FastAPI 后端,折叠成单进程,循环产出纯 Python `LoopEvent`;并搭好最小服装数据模型 + token 鉴权,用 mock LLM 跑通循环单测。

**Architecture:** 单仓 cry-baby,`backend/fastapi_app/`(新建 FastAPI + 服装 + 鉴权)+ `backend/agent/`(从 twinkle 内化拷入)。twinkle 的 ws/E2A 传输层丢弃;`agent.py` 外科剥离 team/subagent/workflow/todo/permission_context,`E2AResponse`→`LoopEvent`。循环通过 `asyncio.run` 直接单测,不经过 ws(ws 路由是 Plan 3)。

**Tech Stack:** Python 3.11+、FastAPI、SQLAlchemy(同步)、Pydantic、python-jose、httpx、openai SDK(twinkle `llm_client` 复用)、pytest(无 pytest-asyncio,用 `asyncio.run`)。

**twinkle 引用约定:** 所有 `cp` 源路径基于 `D:\code\opensource\github\twinkle\twinkle\agentserver\`。行号截至 2026-08-19 twinkle 仓库状态。

---

## 文件结构(本计划产出)

```
backend/
  requirements.txt
  .env.example
  conftest.py
  fastapi_app/
    __init__.py
    main.py            # FastAPI app + CORS + include_router + /health
    config.py          # 设置(AppID/Secret/SECRET_KEY/DB_URL/LLM_*)
    database.py        # SQLAlchemy engine + SessionLocal + Base
    models.py          # User, ClothingItem(photo 列)
    schemas.py         # Pydantic 入参/出参
    auth.py            # code2session + token gen/verify
    deps.py            # get_current_user
    routers/
      __init__.py
      auth.py          # POST /api/auth/login
      clothing.py      # GET/POST /api/clothing
  agent/
    __init__.py
    events.py          # 新建:LoopEvent
    llm_client.py      # cp as-is(twinkle)
    prompts.py         # cp as-is(twinkle)
    react_loop.py      # cp twinkle/agent.py + 剥离(见 Task 11)
    tools/
      __init__.py      # 重写:精简 tool_manager()
      base.py          # cp as-is
      local_function.py# cp + 改 import
      schema_extractor.py # cp as-is
      decorator.py     # cp + 改 import
      errors.py        # cp + 内联常量
      manager.py       # cp + 改 import
    sessions/
      __init__.py      # 重写:精简
      store.py         # cp + 轻微编辑
    hooks/
      __init__.py      # 新建(空 re-export)
      base.py          # cp as-is
      manager.py       # cp + 改 import
      decorator.py     # cp + 改 import
    permissions/
      __init__.py      # 新建(空 re-export)
      approval_registry.py # cp + 删 e2a/handle_respond + 注入 sessions_dir
  tests/
    __init__.py
    conftest.py        # in-memory sqlite + tmp sessions dir + FakeLLM
    test_health.py
    test_models.py
    test_auth.py
    test_clothing.py
    test_tools.py
    test_sessions.py
    test_hooks_prompts.py
    test_approval.py
    test_loop.py       # 核心:剥离后循环跑通
```

---

## Task 1: 仓库初始化 + 骨架 + 依赖 + conftest

**Files:**
- Create: `backend/requirements.txt`, `backend/.env.example`, `backend/.gitignore`, `backend/conftest.py`, `backend/tests/__init__.py`, `backend/fastapi_app/__init__.py`, `backend/fastapi_app/routers/__init__.py`, `backend/agent/__init__.py`

- [ ] **Step 1: 初始化 git + 建目录**

```bash
cd D:/code/opensource/github/cry-baby
git init
mkdir -p backend/fastapi_app/routers backend/agent/tools backend/agent/sessions backend/agent/hooks backend/agent/permissions backend/tests
```

- [ ] **Step 2: 写 requirements.txt**

`backend/requirements.txt`:
```
fastapi>=0.110
uvicorn[standard]>=0.27
sqlalchemy>=2.0
pydantic>=2.6
python-jose[cryptography]>=3.3
httpx>=0.27
openai>=1.50
pytest>=8
```

- [ ] **Step 3: 写 .env.example / .gitignore**

`backend/.env.example`:
```
APP_ID=
APP_SECRET=
SECRET_KEY=change-me
DB_URL=sqlite:///./clothing.db
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_API_KEY=
LLM_MODEL=qwen-plus
LLM_TIMEOUT=120
```

`backend/.gitignore`:
```
__pycache__/
*.pyc
.env
*.db
.pytest_cache/
sessions/
```

- [ ] **Step 4: 写空包 init 文件**

`backend/fastapi_app/__init__.py`、`backend/fastapi_app/routers/__init__.py`、`backend/agent/__init__.py`、`backend/tests/__init__.py`、`backend/agent/tools/__init__.py`(临时空,Task 6 重写)、`backend/agent/sessions/__init__.py`(临时空,Task 8 重写)、`backend/agent/hooks/__init__.py`(空 re-export,见 Task 9)、`backend/agent/permissions/__init__.py`(空)——内容均空即可。

- [ ] **Step 5: 写 tests/conftest.py(共享 fixture)**

`backend/tests/conftest.py`:
```python
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
```

- [ ] **Step 6: 写一个占位健康检查测试(验证 pytest 跑通)**

`backend/tests/test_health.py`:
```python
from fastapi.testclient import TestClient
from fastapi_app.main import app


def test_health():
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
```

- [ ] **Step 7: 安装依赖并跑测试(预期 FAIL,因 main.py 还没写)**

```bash
cd backend
pip install -r requirements.txt
python -m pytest tests/test_health.py -v
```
Expected: FAIL — `ModuleNotFoundError: fastapi_app.main`(或 main 无 /health)。Task 2 修复。

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "chore: init repo skeleton, deps, conftest"
```

---

## Task 2: FastAPI app + config + database + /health

**Files:**
- Create: `backend/fastapi_app/config.py`, `backend/fastapi_app/database.py`, `backend/fastapi_app/main.py`

- [ ] **Step 1: 写 config.py**

`backend/fastapi_app/config.py`:
```python
import os

APP_ID = os.environ.get("APP_ID", "")
APP_SECRET = os.environ.get("APP_SECRET", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
DB_URL = os.environ.get("DB_URL", "sqlite:///./clothing.db")

# agent LLM(国产模型,OpenAI 兼容端点)
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen-plus")
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "120"))

AGENT_MAX_STEPS = int(os.environ.get("AGENT_MAX_STEPS", "1000"))  # 纯防死循环兜底,非成本护栏
```

- [ ] **Step 2: 写 database.py**

`backend/fastapi_app/database.py`:
```python
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi_app.config import DB_URL

_INMEM = DB_URL.startswith("sqlite") and ":memory:" in DB_URL
engine = create_engine(
    DB_URL,
    connect_args={"check_same_thread": False} if DB_URL.startswith("sqlite") else {},
    poolclass=StaticPool if _INMEM else None,  # 内存库共享单连接,否则各连接是不同库
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
```

- [ ] **Step 3: 写 main.py**

`backend/fastapi_app/main.py`:
```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="cry-baby")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.get("/health")
def health():
    return {"status": "ok"}
```

- [ ] **Step 4: 跑测试,预期 PASS**

```bash
python -m pytest tests/test_health.py -v
```
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: fastapi app + config + database + health endpoint"
```

---

## Task 3: 模型 — User + ClothingItem(含 photo 列)

**Files:**
- Create: `backend/fastapi_app/models.py`
- Test: `backend/tests/test_models.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_models.py`:
```python
from datetime import datetime
from fastapi_app.models import User, ClothingItem


def test_create_user_and_clothing(db):
    u = User(openid="oABC")
    db.add(u); db.commit(); db.refresh(u)

    c = ClothingItem(user_id=u.id, category="上衣", color="蓝色",
                     photo_url="/img/a.jpg", photo_clean_url="/img/a-clean.png")
    db.add(c); db.commit(); db.refresh(c)

    assert c.id is not None
    assert c.photo_url == "/img/a.jpg"
    assert c.photo_clean_url == "/img/a-clean.png"
    assert c.remark is None
    assert isinstance(c.created_at, datetime)

    got = db.query(ClothingItem).filter_by(user_id=u.id).first()
    assert got.color == "蓝色"
```

- [ ] **Step 2: 跑测试,预期 FAIL(`models` 未定义)**

```bash
python -m pytest tests/test_models.py -v
```
Expected: FAIL — `ModuleNotFoundError: fastapi_app.models`。

- [ ] **Step 3: 写 models.py**

`backend/fastapi_app/models.py`:
```python
from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from fastapi_app.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(Text, unique, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ClothingItem(Base):
    __tablename__ = "clothing_items"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    category = Column(Text, nullable=False)
    color = Column(Text, nullable=False)
    remark = Column(Text, nullable=True)
    photo_url = Column(Text, nullable=True)         # 原图
    photo_clean_url = Column(Text, nullable=True)   # 抠图后干净图(上传时预计算)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **Step 4: 跑测试,预期 PASS**

```bash
python -m pytest tests/test_models.py -v
```
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: User + ClothingItem models with photo columns"
```

---

## Task 4: token 鉴权 + 微信 code2session + /api/auth/login

**Files:**
- Create: `backend/fastapi_app/auth.py`, `backend/fastapi_app/deps.py`, `backend/fastapi_app/routers/auth.py`
- Modify: `backend/fastapi_app/main.py`(挂 router)
- Test: `backend/tests/test_auth.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_auth.py`:
```python
from fastapi.testclient import TestClient
from fastapi_app.main import app
import fastapi_app.auth as auth


def test_login_returns_token(monkeypatch, db):
    async def fake_code2session(code):
        return {"openid": "oABC"}
    monkeypatch.setattr(auth, "code2session", fake_code2session)

    client = TestClient(app)
    resp = client.post("/api/auth/login", json={"code": "any"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data and data["user"]["openid"] == "oABC"
```
> 鉴权路由的 401/200 用例放在 Task 5(clothing 路由挂载后)一起测。

- [ ] **Step 2: 跑测试,预期 FAIL**

```bash
python -m pytest tests/test_auth.py -v
```
Expected: FAIL — `auth` 模块不存在。

- [ ] **Step 3: 写 auth.py**

`backend/fastapi_app/auth.py`:
```python
import httpx
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi_app.config import APP_ID, APP_SECRET, SECRET_KEY

TOKEN_TTL_MINUTES = 60 * 24 * 7


async def code2session(code: str) -> dict:
    """微信 jscode2session。测试 monkeypatch 此函数。"""
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {"appid": APP_ID, "secret": APP_SECRET,
              "js_code": code, "grant_type": "authorization_code"}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        return r.json()


def make_token(user_id: int, openid: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "openid": openid,
               "exp": now + timedelta(minutes=TOKEN_TTL_MINUTES)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None
```

- [ ] **Step 4: 写 deps.py**

`backend/fastapi_app/deps.py`:
```python
from fastapi import Depends, Header
from fastapi_app.auth import decode_token
from fastapi_app.database import SessionLocal
from fastapi_app.models import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(authorization: str = Header(default=""), db=Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="missing token")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    if not payload:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="invalid token")
    user = db.query(User).filter_by(openid=payload["openid"]).first()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="user not found")
    return user
```

- [ ] **Step 5: 写 routers/auth.py**

`backend/fastapi_app/routers/auth.py`:
```python
from fastapi import APIRouter, Depends
from fastapi_app.auth import code2session, make_token
from fastapi_app.database import SessionLocal
from fastapi_app.models import User
from fastapi_app.deps import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(body: dict, db=Depends(get_db)):
    code = body.get("code", "")
    session = await code2session(code)
    openid = session.get("openid", "")
    if not openid:
        return {"error": "no openid"}
    user = db.query(User).filter_by(openid=openid).first()
    if user is None:
        user = User(openid=openid)
        db.add(user); db.commit(); db.refresh(user)
    token = make_token(user.id, user.openid)
    return {"token": token, "user": {"id": user.id, "openid": user.openid}}
```

- [ ] **Step 6: 挂 router 到 main.py**

在 `backend/fastapi_app/main.py` 追加:
```python
from fastapi_app.routers import auth as auth_router
app.include_router(auth_router.router)
```

- [ ] **Step 7: 跑测试,预期 PASS**

```bash
python -m pytest tests/test_auth.py -v
```
Expected: PASS(仅 login 用例;401/200 鉴权用例在 Task 5)。

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "feat: wechat code2session + token auth + login endpoint"
```

---

## Task 5: 服装 router(GET 列表 + POST 新建,按 user 隔离)

**Files:**
- Create: `backend/fastapi_app/schemas.py`, `backend/fastapi_app/routers/clothing.py`
- Modify: `backend/fastapi_app/main.py`(挂 clothing router)
- Test: `backend/tests/test_clothing.py`

- [ ] **Step 1: 写失败测试**

`backend/tests/test_clothing.py`:
```python
from fastapi.testclient import TestClient
from fastapi_app.main import app
from fastapi_app.auth import make_token
from fastapi_app.models import User, ClothingItem


def _client_with_user(db, openid="oA"):
    u = User(openid=openid)
    db.add(u); db.commit(); db.refresh(u)
    token = make_token(u.id, u.openid)
    return TestClient(app), u


def test_no_token_returns_401(db):
    client = TestClient(app)
    assert client.get("/api/clothing").status_code == 401


def test_create_and_list(db):
    client, u = _client_with_user(db)
    h = {"Authorization": f"Bearer {make_token(u.id, u.openid)}"}
    r = client.post("/api/clothing", json={"category": "上衣", "color": "蓝色"}, headers=h)
    assert r.status_code == 200 and r.json()["color"] == "蓝色"
    r = client.get("/api/clothing", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 1 and r.json()[0]["category"] == "上衣"


def test_isolation_between_users(db):
    c1, u1 = _client_with_user(db, "oA")
    c2, u2 = _client_with_user(db, "oB")
    h1 = {"Authorization": f"Bearer {make_token(u1.id, u1.openid)}"}
    h2 = {"Authorization": f"Bearer {make_token(u2.id, u2.openid)}"}
    c1.post("/api/clothing", json={"category": "裤", "color": "黑"}, headers=h1)
    assert len(c2.get("/api/clothing", headers=h2).json()) == 0
    assert len(c1.get("/api/clothing", headers=h1).json()) == 1
```

- [ ] **Step 2: 跑测试,预期 FAIL**

```bash
python -m pytest tests/test_clothing.py -v
```
Expected: FAIL — `/api/clothing` 路由不存在。

- [ ] **Step 3: 写 schemas.py**

`backend/fastapi_app/schemas.py`:
```python
from pydantic import BaseModel
from typing import Optional


class ClothingCreate(BaseModel):
    category: str
    color: str
    remark: Optional[str] = None


class ClothingOut(BaseModel):
    id: int
    category: str
    color: str
    remark: Optional[str] = None
    photo_url: Optional[str] = None
    photo_clean_url: Optional[str] = None
    class Config:
        from_attributes = True
```

- [ ] **Step 4: 写 routers/clothing.py**

`backend/fastapi_app/routers/clothing.py`:
```python
from fastapi import APIRouter, Depends
from fastapi_app.deps import get_current_user, get_db
from fastapi_app.models import ClothingItem
from fastapi_app.schemas import ClothingCreate, ClothingOut

router = APIRouter(prefix="/api/clothing", tags=["clothing"])


@router.get("")
def list_clothing(user=Depends(get_current_user), db=Depends(get_db)):
    items = db.query(ClothingItem).filter_by(user_id=user.id).order_by(ClothingItem.created_at.desc()).all()
    return [ClothingOut.from_orm(i) for i in items]


@router.post("")
def create_clothing(body: ClothingCreate, user=Depends(get_current_user), db=Depends(get_db)):
    item = ClothingItem(user_id=user.id, category=body.category, color=body.color, remark=body.remark)
    db.add(item); db.commit(); db.refresh(item)
    return ClothingOut.from_orm(item)
```

- [ ] **Step 5: 挂 router**

`backend/fastapi_app/main.py` 追加:
```python
from fastapi_app.routers import clothing as clothing_router
app.include_router(clothing_router.router)
```

- [ ] **Step 6: 跑测试,预期 PASS**

```bash
python -m pytest tests/test_clothing.py tests/test_auth.py -v
```
Expected: PASS(此时 `test_protected_with_token` 应为 200)。

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "feat: clothing list/create endpoints with user isolation"
```

---

## Task 6: 迁移 agent tools 框架

**Files:**
- Copy (as-is): `backend/agent/tools/base.py`, `backend/agent/tools/schema_extractor.py`
- Copy (edit imports): `backend/agent/tools/local_function.py`, `backend/agent/tools/decorator.py`, `backend/agent/tools/manager.py`
- Copy (inline const): `backend/agent/tools/errors.py`
- Rewrite: `backend/agent/tools/__init__.py`
- Test: `backend/tests/test_tools.py`

- [ ] **Step 1: cp as-is 文件**

```bash
TW=D:/code/opensource/github/twinkle/twinkle/agentserver
cp "$TW/tools/base.py" backend/agent/tools/base.py
cp "$TW/tools/schema_extractor.py" backend/agent/tools/schema_extractor.py
```

- [ ] **Step 2: cp + 改 import(local_function / decorator / manager)**

```bash
cp "$TW/tools/local_function.py" backend/agent/tools/local_function.py
cp "$TW/tools/decorator.py" backend/agent/tools/decorator.py
cp "$TW/tools/manager.py" backend/agent/tools/manager.py
# 把 from twinkle.agentserver.tools.X import → from .X import
sed -i 's|from twinkle\.agentserver\.tools\.|from .|g' backend/agent/tools/local_function.py backend/agent/tools/decorator.py backend/agent/tools/manager.py
```

- [ ] **Step 3: cp errors.py + 内联 TOOL_ERROR_PREFIX**

```bash
cp "$TW/tools/errors.py" backend/agent/tools/errors.py
```
编辑 `backend/agent/tools/errors.py`:删除 `from twinkle.observability.attributes import TOOL_ERROR_PREFIX` 这一行,在文件顶部加:
```python
TOOL_ERROR_PREFIX = "[tool error]"
```

- [ ] **Step 4: 重写 tools/__init__.py(精简 tool_manager,只 re-export)**

`backend/agent/tools/__init__.py`:
```python
from .base import Tool, ToolCard
from .local_function import LocalFunction
from .decorator import tool
from .manager import ToolManager


def tool_manager() -> ToolManager:
    """精简构建器:不注册 twinkle 内置工具;领域工具在各 Task 自行 register。"""
    return ToolManager()


__all__ = ["Tool", "ToolCard", "LocalFunction", "tool", "ToolManager", "tool_manager"]
```

- [ ] **Step 5: 写失败测试**

`backend/tests/test_tools.py`:
```python
import asyncio
from agent.tools import tool, ToolManager


@tool
async def echo(text: str) -> str:
    """Echo the given text back to the caller."""
    return f"echo: {text}"


def test_tool_extract_and_schemas():
    assert echo.card.name == "echo"
    assert echo.card.description.startswith("Echo")
    assert echo.card.parameters["properties"]["text"]["type"] == "string"

    tm = ToolManager()
    tm.register(echo)
    schemas = tm.schemas()
    assert schemas[0]["type"] == "function"
    assert schemas[0]["function"]["name"] == "echo"


def test_tool_execute_and_unknown():
    tm = ToolManager()
    tm.register(echo)
    out = asyncio.run(tm.execute("echo", {"text": "hi"}))
    assert out == "echo: hi"

    from agent.tools.errors import ToolError
    try:
        asyncio.run(tm.execute("nope", {}))
        assert False, "should raise"
    except ToolError:
        pass
```

- [ ] **Step 6: 跑测试,预期 PASS(cp 的框架即用)**

```bash
python -m pytest tests/test_tools.py -v
```
Expected: PASS。若 FAIL 多半是 import 残留,检查 sed 是否改全。

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "feat: port twinkle tools framework (base/decorator/manager/schema_extractor/errors)"
```

---

## Task 7: 迁移 llm_client(as-is)+ FakeLLM 测试替身

**Files:**
- Copy (as-is): `backend/agent/llm_client.py`
- Test infra: `backend/tests/conftest.py`(追加 `FakeLLM`)
- Test: `backend/tests/test_llm_client.py`

- [ ] **Step 1: cp llm_client.py as-is**

```bash
cp "$TW/llm_client.py" backend/agent/llm_client.py
```
确认:该文件只 import `openai`,无 twinkle 模块依赖(按移植 spec)。

- [ ] **Step 2: 追加 FakeLLM 到 conftest**

在 `backend/tests/conftest.py` 追加:
```python
from agent.llm_client import TextDelta, Finish


class FakeLLM:
    """模拟 LLMClient.stream 契约:按脚本依次吐 TextDelta / Finish。"""
    def __init__(self, scripts):
        # scripts: list[ list[TextDelta|Finish] ]  每次调用消费一段
        self._scripts = list(scripts)
        self.calls = 0

    async def stream(self, messages, tools):
        seq = self._scripts[self.calls]
        self.calls += 1
        for ev in seq:
            yield ev
```

- [ ] **Step 3: 写测试(验证 FakeLLM 契约 + llm_client 可构造)**

`backend/tests/test_llm_client.py`:
```python
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
```

- [ ] **Step 4: 跑测试,预期 PASS**

```bash
python -m pytest tests/test_llm_client.py -v
```
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: port llm_client + FakeLLM test double"
```

---

## Task 8: 迁移 sessions(SessionStore)

**Files:**
- Copy (edit): `backend/agent/sessions/store.py`
- Rewrite: `backend/agent/sessions/__init__.py`
- Test: `backend/tests/test_sessions.py`

- [ ] **Step 1: cp store.py + 处理 list_sessions 的延迟 config import**

```bash
mkdir -p backend/agent/sessions
cp "$TW/sessions/store.py" backend/agent/sessions/store.py
```
编辑 `backend/agent/sessions/store.py` 的 `list_sessions`(原 ~118 行):该处 `from twinkle.config import SUBAGENT_LIST_SESSIONS_FILTER` 在 `try/except ImportError` 内、失败回退 `False`。直接把 `include_subagents` 默认强制为 `False` 并删掉该 try/except 块,使无 twinkle.config 依赖。即:把
```python
if include_subagents is None:
    try:
        from twinkle.config import SUBAGENT_LIST_SESSIONS_FILTER
        include_subagents = SUBAGENT_LIST_SESSIONS_FILTER
    except ImportError:
        include_subagents = False
```
替换为:
```python
if include_subagents is None:
    include_subagents = False
```

- [ ] **Step 2: 重写 sessions/__init__.py**

`backend/agent/sessions/__init__.py`:
```python
from .store import SessionStore

__all__ = ["SessionStore"]
```

- [ ] **Step 3: 写失败测试**

`backend/tests/test_sessions.py`:
```python
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

    store2 = SessionStore(tmp_sessions_dir)  # 重新加载,缓存空
    msgs = store2.get_messages("s2")
    assert len(msgs) == 1 and msgs[0]["content"] == "persist"
```

- [ ] **Step 4: 跑测试,预期 PASS**

```bash
python -m pytest tests/test_sessions.py -v
```
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: port SessionStore with disk-persisted JSONL history"
```

---

## Task 9: 迁移 prompts + hooks + 新建 events.py(LoopEvent)

**Files:**
- Copy (as-is): `backend/agent/prompts.py`, `backend/agent/hooks/base.py`
- Copy (edit imports): `backend/agent/hooks/manager.py`, `backend/agent/hooks/decorator.py`
- Create: `backend/agent/hooks/__init__.py`, `backend/agent/events.py`
- Test: `backend/tests/test_hooks_prompts.py`

- [ ] **Step 1: cp as-is**

```bash
mkdir -p backend/agent/hooks
cp "$TW/prompts.py" backend/agent/prompts.py
cp "$TW/hooks/base.py" backend/agent/hooks/base.py
```

- [ ] **Step 2: cp hooks/manager + decorator,改 import**

```bash
cp "$TW/hooks/manager.py" backend/agent/hooks/manager.py
cp "$TW/hooks/decorator.py" backend/agent/hooks/decorator.py
sed -i 's|from twinkle\.agentserver\.hooks\.|from .|g' backend/agent/hooks/manager.py backend/agent/hooks/decorator.py
```

- [ ] **Step 3: 写 hooks/__init__.py**

`backend/agent/hooks/__init__.py`:
```python
from .base import AgentHook, HookEvent, HookContext, HookInterrupt
from .manager import HookManager
from .decorator import hook

__all__ = ["AgentHook", "HookEvent", "HookContext", "HookInterrupt", "HookManager", "hook"]
```

- [ ] **Step 4: 写 events.py(LoopEvent)**

`backend/agent/events.py`:
```python
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
```

- [ ] **Step 5: 写测试**

`backend/tests/test_hooks_prompts.py`:
```python
import asyncio
from agent.prompts import PromptSection, SystemPromptBuilder
from agent.hooks import HookManager, HookEvent
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

    hm = HookManager()
    hm.register_hook(H())
    asyncio.run(hm.execute(HookEvent.AFTER_MODEL_CALL, None))
    assert calls == ["after"]
```

- [ ] **Step 6: 跑测试,预期 PASS**

```bash
python -m pytest tests/test_hooks_prompts.py -v
```
Expected: PASS。

- [ ] **Step 7: 提交**

```bash
git add -A
git commit -m "feat: port prompts/hooks + new LoopEvent"
```

---

## Task 10: 迁移 permissions/approval_registry(审批 Future)

**Files:**
- Copy (edit): `backend/agent/permissions/approval_registry.py`
- Create: `backend/agent/permissions/__init__.py`
- Test: `backend/tests/test_approval.py`

- [ ] **Step 1: cp + 编辑(删 e2a 依赖与 ws handle_respond,注入 sessions_dir)**

```bash
mkdir -p backend/agent/permissions
cp "$TW/permissions/approval_registry.py" backend/agent/permissions/approval_registry.py
```
编辑 `backend/agent/permissions/approval_registry.py`:
1. 删除 `from twinkle.e2a.models import E2AEnvelope, E2AResponse` 这一行。
2. 删除整个 `handle_respond` 方法(ws RPC 处理器)。
3. `ApprovalRegistry.__init__` 增加 `sessions_dir` 参数并存储;把 `_pending_path` 里 `from twinkle.config import SESSIONS_DIR` 改为用 `self._sessions_dir`。具体:把
   ```python
   def _pending_path(self):
       from twinkle.config import SESSIONS_DIR
       return Path(SESSIONS_DIR) / "pending"
   ```
   改为
   ```python
   def _pending_path(self):
       return Path(self._sessions_dir) / "pending"
   ```
   并在 `__init__` 签名加 `sessions_dir` 参数 + `self._sessions_dir = str(sessions_dir)`,`_pending_path` 所在目录需 `Path(...).mkdir(parents=True, exist_ok=True)`(保留原 mkdir 逻辑)。
4. 删除模块级 `APPROVAL_REGISTRY = ApprovalRegistry()` 单例(改为在 app wiring 处构建);保留 `ApprovalPendingRecord` 与类。

- [ ] **Step 2: 写 permissions/__init__.py**

`backend/agent/permissions/__init__.py`:
```python
from .approval_registry import ApprovalRegistry, ApprovalPendingRecord

__all__ = ["ApprovalRegistry", "ApprovalPendingRecord"]
```

- [ ] **Step 3: 写失败测试**

`backend/tests/test_approval.py`:
```python
import asyncio
from agent.permissions import ApprovalRegistry


def test_register_and_resolve(tmp_sessions_dir):
    reg = ApprovalRegistry(sessions_dir=tmp_sessions_dir)
    fut = reg.register("ap1")
    assert not fut.done()
    assert reg.resolve("ap1", "approved") is True
    assert fut.done() and fut.result() == "approved"


def test_resolve_unknown_returns_false(tmp_sessions_dir):
    reg = ApprovalRegistry(sessions_dir=tmp_sessions_dir)
    assert reg.resolve("nope", "approved") is False
```

- [ ] **Step 4: 跑测试,预期 PASS**

```bash
python -m pytest tests/test_approval.py -v
```
Expected: PASS。若 FAIL 因 `__init__` 签名或 `_pending_path` 编辑有误,按 Step 1 复核。

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "feat: port ApprovalRegistry (Future-based approval, no ws)"
```

---

## Task 11: 迁移 + 剥离 ReAct 循环(agent.py → react_loop.py)

**Files:**
- Copy (heavy edit): `backend/agent/react_loop.py`(源:`twinkle/agentserver/agent.py`,881 行)
- Test: `backend/tests/test_loop.py`(核心)

> 这是本计划最重的任务。剥离清单来自移植 spec(行号截至 2026-08-19 twinkle)。执行者须**读 `agent.py` 原文**逐项应用。

- [ ] **Step 1: cp 并改 import 路径**

```bash
cp "$TW/agent.py" backend/agent/react_loop.py
# 把 from twinkle.agentserver.X import → from .X import
sed -i 's|from twinkle\.agentserver\.|from .|g' backend/agent/react_loop.py
```
之后 `react_loop.py` 仍可能残留:`from twinkle.e2a.models import E2AResponse`、`from twinkle.config import ...`、`from twinkle.agentserver.permission_context import set_permission_channel`、`from .todo import ...`(todo 走的是 `from twinkle.agentserver.todo`,sed 已改成 `from .todo`),以及 `from .workflow import tools as workflow_tools`(若有)。这些在下面步骤删除。

- [ ] **Step 2: 删除 team/member/subagent 相关代码区域**

删除以下区域(行号为原 agent.py):
- `_Inbox` 协议(72–77)。
- `AgentRequest.mode` 字段(69 行)及其所有 `request.mode` 引用。
- `build_agent_runtime_prompt()`(149–188)。
- `build_leader_system_prompt()`(193–275)。
- `build_member_system_prompt()`(280–315)。
- `leader_base_sections()`(325–327)。
- `member_base_sections()`(330–336)。
- `_TEAM_LEADER_TOOL_WHITELIST`(339–361)。
- `__init__` 的 `inbox` 参数与 `self._inbox = inbox`(387, 397)。
- `_run_react_loop` 中:`is_team_mode`(490)、团队白名单过滤(503–505)、收件箱清空(508–511)、leader base-sections 分支(518–519,保留 `if self._base_sections is not None` 与 `else: normal_base_sections()`)。

- [ ] **Step 3: 删除 todo 管道 + permission_context(与 E2A 耦合)**

- 删除 `from .todo import ...` 整块(原 21–26)。
- 删 `from .permission_context import set_permission_channel`(原 27)。
- 删 `AgentRequest.channel` 字段(原 68)。
- `_run_react_loop` 中删:`PLAN_TODO_SESSION_ID.set(...)`(485)、`reset_todo_events()`(486)、`set_permission_channel(...)`(487)。
- 删 `flush_todo_events()` 的两处 yield(原 590–598、667–676)。
- `_try_parallel_tool_calls` 中删 `TODO_EVENTS.set(todo_buffer)`(765)及相关 todo 缓冲。
- `_build_interrupt_snapshot` 中删 `get_todo_store` 的 try 块(823–831)。

- [ ] **Step 4: 删 config 静态依赖(Option A:注入路径)**

- 删 `from twinkle.config import AGENT_MAX_STEPS as MAX_STEPS, MEMORY_DIR, SKILLS_DIR, WORKSPACE_DIR`(原 44–49)。
- `__init__` 已有 `max_steps` 参数;`_max_steps` 默认改用传入值(None 表示无上限,或由 wiring 传 `AGENT_MAX_STEPS`)。
- `build_system_prompt(workspace_dir, memory_dir, skills_dir)` 改为接收参数(替代原静态 `WORKSPACE_DIR/MEMORY_DIR/SKILLS_DIR`),`__init__` 增加 `workspace_dir=None, memory_dir=None, skills_dir=None` 三参并传入 `build_system_prompt`。若不想动签名,可临时硬编码为字符串 `""`,但**测试要求传入**(见 Step 6)。

- [ ] **Step 5: E2AResponse → LoopEvent 的 yield 替换 + 插入 tool_call/tool_result**

- 删 `from twinkle.e2a.models import E2AResponse`(原 43),加:
  ```python
  from .events import LoopEvent
  ```
- `run()` 返回类型 `AsyncIterator[E2AResponse]` → `AsyncIterator[LoopEvent]`。
- 按下表替换各 yield 点(行号为原 agent.py):

| 原行 | 替换为 |
|---|---|
| 442 | `yield LoopEvent(kind="error", message="execution interrupted", is_final=True)` |
| 547 | `yield LoopEvent(kind="final", content=str(force_finish.result or ""), is_final=True); return` |
| 566 | `yield LoopEvent(kind="text_delta", content=stream_event.content)` |
| 626 | `yield LoopEvent(kind="error", message="tool execution interrupted", is_final=True); return` |
| 644 | `yield LoopEvent(kind="approval_request", approval_id=hook_interrupt.data["approval_id"], name=hook_interrupt.data["tool"], args=hook_interrupt.data["args"], tool_call_id=tool_call["id"], reason=hook_interrupt.data.get("reason"))` |
| 687 | `yield LoopEvent(kind="final", content=full_text, is_final=True); return` |
| 710 | `yield LoopEvent(kind="final", content=str(force_finish.result or ""), is_final=True); return` |
| 731 | `yield LoopEvent(kind="error", message=f"agent loop exceeded max_steps={self._max_steps}", is_final=True)` |

- **插入**(原本被抑制,现在必加):
  - 顺序路径,`args = json.loads(...)` 之后、`ToolCallInputs` 之前(原 ~618):
    ```python
    yield LoopEvent(kind="tool_call", tool_call_id=tool_call["id"], name=name, args=args)
    ```
  - `result = await self._tool_call(ctx)` 成功返回后、append 之前(原 ~681):
    ```python
    yield LoopEvent(kind="tool_result", tool_call_id=tool_call["id"], result=result)
    ```
  - 并行路径 `_try_parallel_tool_calls`,`gather` 返回后,循环内对每个 `tool_call_id` 发同样的 `tool_call` + `tool_result`(原 ~790–799)。

- [ ] **Step 6: 写失败测试(核心:剥离后循环跑通)**

`backend/tests/test_loop.py`:
```python
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
        # 第 1 次调用:要调 echo
        [Finish(finish_reason="tool_calls", assistant_message={
            "role": "assistant", "content": None,
            "tool_calls": [{"id": "c1", "type": "function",
                           "function": {"name": "echo", "arguments": "{\"text\":\"hi\"}"}}]})],
        # 第 2 次调用:收尾
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
    # tool_result 内容
    tr = next(e for e in events if e.kind == "tool_result")
    assert tr.result == "echo: hi"
    # 会话历史已落盘
    msgs = SessionStore(tmp_path / "sessions").get_messages("s1")
    assert any(m.get("role") == "tool" for m in msgs)
```

- [ ] **Step 7: 跑测试,预期先 FAIL(剥离未完成/有残留 import)**

```bash
python -m pytest tests/test_loop.py -v
```
Expected: 初次大概率 FAIL —— 残留 `twinkle.*` import、未删的 team/todo 引用、yield 未替换全。逐一按 Step 2–5 复核直至:

- [ ] **Step 8: 跑全量测试,预期 PASS**

```bash
python -m pytest tests/ -v
```
Expected: 全部 PASS。`test_loop` 是关键:证明剥离后的循环能多步、调工具、落盘、收尾。

- [ ] **Step 9: 提交**

```bash
git add -A
git commit -m "feat: port + strip ReAct loop to LoopEvent, multi-step tool-call verified"
```

---

## 完成判定

Plan 1 完成时:
- `backend/` 是一个可跑的 FastAPI app(健康检查 + 微信登录 + 服装增查 + 用户隔离)。
- `backend/agent/` 内化了 twinkle 的 llm_client / tools / sessions / hooks / prompts / approval_registry / 剥离后的 ReAct 循环,循环产出 `LoopEvent`,用 mock LLM 单测跑通(多步 + 工具调用 + 落盘 + 收尾)。
- `python -m pytest tests/ -v` 全绿。
- 尚未涉及:照片上传 + 抠图 + 通义万相(Plan 2)、穿搭工具 + ws 路由(Plan 3)、permissions 审批接线/破坏性工具/多轮记忆(Phase 2)。

## 自审备注

- `test_protected_with_token` 在 Task 4 阶段断言 `!= 401`(clothing 路由未挂),Task 5 后变 200;两 Task 测试一起跑验证。
- `react_loop.py` 剥离高度依赖原 agent.py 行号;若 twinkle 已更新,按移植 spec 的"区域/含义"重定位而非死守行号。
- `max_steps` 仅作防死循环兜底(`AGENT_MAX_STEPS=1000`),不作为成本护栏(遵循 spec 第 7、8 节)。
- Plan 1 未碰 README/CLAUDE.md 定位更新(列入 spec 第 10 节待办,Phase 收尾或专门任务处理)。
