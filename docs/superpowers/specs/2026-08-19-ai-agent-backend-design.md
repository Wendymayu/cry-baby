# 通用生活助手 AI 后端设计（服装/穿搭域先行）

> 在《服装管理小程序 MVP 设计》(2026-08-15) 之上新增 AI agent 层。服装 CRUD + 鉴权见该 spec，本规格只覆盖 agent + 衣物照片 + 穿搭图片生成。

## 1. 概述与定位

cry-baby 定位为**通用个人生活助手**，首批开发**服装管理与穿搭推荐**领域，后续会扩展更多能力域（美食 / 出行等）。本规格新增 AI agent：基于用户真实衣物的穿搭推荐——文字建议 + 生成含真实衣物的穿搭图，由对话式自主 agent 提供。

- **助手形态**：对话式自主 agent（LLM 多步 ReAct，自主决定调哪些工具）
- **首批能力域**：服装管理 + 穿搭推荐（文字 + 真实衣物出镜的生成图）
- **模型**：国产大模型 API（LLM：通义千问 / 智谱 / DeepSeek；图像：通义万相图生图 / 参考图）
- **复用来源**：从 twinkle（github.com/Wendymayu/twinkle，通用助手学习型实现）迁移 agent 基础设施，**折叠进 cry-baby 的 FastAPI 后端，单进程**（决策见第 2、3 节）

## 2. 仓库与目录结构

单仓（cry-baby）。`backend/` 下两个包：

```
cry-baby/
  backend/
    fastapi_app/                 # ① FastAPI：服装管理 + 鉴权（沿用 2026-08-15 MVP spec）
      main.py                    #   app、CORS、include_router；挂 /ws/agent
      config.py database.py models.py schemas.py
      auth.py deps.py
      routers/
        auth.py                  #   POST /api/auth/login
        clothing.py              #   衣物 CRUD + POST /api/clothing/{id}/photo（照片上传 + 抠图预计算）
        agent.py                 #   /ws/agent  FastAPI WebSocket 路由
    agent/                       # ② 从 twinkle 迁移
      llm_client.py             #   直接复用（国产模型 reasoning_content 已处理）
      tools/
        base.py decorator.py manager.py schema_extractor.py local_function.py errors.py
        builtin/
          outfit.py              #   新增：list_garments / generate_outfit_image / get_weather（可选）
          image_gen.py           #   新增：通义万相 + 抠图（httpx 直调 DashScope）
      react_loop.py              #   twinkle ReAct 循环，剥离 E2A/ws 外壳，保留多步/并行/审批暂停-恢复
      sessions/                  #   直接复用（SessionStore JSON）
      memory/                    #   保留（SQLite+vec0 长期记忆）
      skills/                    #   保留（技能系统）
      hooks/                     #   保留（retry / force-finish / 审批中断）
      permissions/               #   保留（破坏性操作审批，如删衣物）
      prompts.py                 #   复用结构，重写为通用生活助手人设
      config/                    #   复用机制（YAML + .env + ${ENV:-default}），与 fastapi_app config 合并
    tests/
  miniprogram/                   # 小程序前端
  docs/
```

twinkle 迁移为代码内化（拷入 cry-baby，非子模块）。twinkle 自带传输层（`server.py` / `gateway/` / `e2a/` / `schema/message.py`）不迁。

## 3. twinkle 代码处置

| 处置 | 模块 | 说明 |
|---|---|---|
| 直接复用 | `llm_client.py`、`tools/` 框架、`sessions/` | 国产模型兼容 / `@tool`+`ToolManager` / JSON 对话史 |
| 保留（通用助手工具） | `web_search`/`web_fetch`、`file_tools`、`todo_tools`、`cron_tools`、`skills`+`skill_tools`、`subagent`、`memory` | `tool_manager()` 照常注册 |
| 保留（安全） | `permissions`、`hooks` | 破坏性操作审批；retry/force-finish/中断 |
| 复用算法、剥离外壳 | `react_loop` | 去 E2A 帧产出→普通事件；去 `team` 分支；留多步 / 并行工具调用 / 审批暂停-恢复 |
| 复用机制 | `config/` | 与 fastapi_app 合并 |
| 丢弃 | `server.py`、`gateway/`、`e2a/`、`schema/message.py` | ws 传输层，由 FastAPI WebSocket 路由替代 |
| 丢弃 | `command_exec`、`team`/`team_tools`、`workflow`/PPT、`evolution` | shell 危险；subagent 已够；twinkle 专属垂直；R&D 功能 |

## 4. 数据流

### 4.1 聊天

```
小程序 wx.connectSocket ─▶ /ws/agent ─验 token→ 取/建 session ─▶ react_loop.run()
  ◀──流式事件──           (FastAPI WS 路由)                       │
                                                                ├─ list_garments(user_id) ─▶ fastapi_app.models (SQLite, 按 user_id)
                                                                ├─ generate_outfit_image(...) ─▶ 通义万相 (httpx)
                                                                └─ LLM ─▶ llm_client ─▶ 国产模型 API
```

- token 放 ws 握手 query 或首帧；路由解出 `user_id`，所有工具按 `user_id` 隔离。
- `react_loop.run()` 为 async 生成器，产出事件：`text_delta` / `tool_call` / `tool_result` / `image_ready` / `approval_request` / `final`。ws 路由逐帧 `send` 回小程序。
- agent 拿衣物**直连 SQLite**（`from fastapi_app.models import ClothingItem` + `from fastapi_app.database import SessionLocal`），不跨服务 HTTP。

### 4.2 审批（破坏性操作）

```
agent 要删衣物 → permissions 判 require-approval → 循环产 approval_request + 暂停(asyncio.Future)
  → ws 路由推小程序 → 小程序弹「确认删除?」→ 用户确认/拒绝 → resolve Future → 循环继续（执行或跳过）
```

`react_loop` 剥离时**保留**暂停/恢复机制，只把 `e2a.ask` 改为普通 `approval_request` 事件。删/改衣物等域内破坏性操作，用权限规则挂 `require-approval`。

### 4.3 衣物照片上传（扩展 `clothing.py`）

```
小程序 wx.request ─POST /api/clothing/{id}/photo (multipart)──▶ FastAPI
  存原图 ─▶ 抠图（预计算：rembg 本地 or 通义抠图）─▶ 存干净图 ─▶ 更新 clothing_items: photo_url + photo_clean_url
```

- 抠图在**上传时预计算**（非循环里），生成穿搭图时直接用干净图当参考，快且省钱。
- `clothing_items` 加 `photo_url`、`photo_clean_url` 两列。
- 通义万相用**图生图 / 参考图**能力，把选中干净衣物图作参考，生成含该真实衣物的搭配图。

### 4.4 会话与持久化

- agent 对话历史：`sessions/`（JSON），与衣物 SQLite 分离。
- 长期记忆：`memory/`（SQLite+vec0），独立。
- 衣物 / 用户：主 SQLite（MVP spec 已定义）。
- 生成图：存对象存储或本地文件；可选加 `outfit_generations` 表（id, user_id, garment_ids, image_url, prompt, created_at）留历史（Phase 2）。

## 5. 工具

通用层（twinkle 保留）：`web_search`/`web_fetch`、`file_tools`、`todo_tools`、`cron_tools`、`skills`+`skill_tools`、`subagent`、`memory`。

领域层（新增，写成 `@tool`）：

| 工具 | 作用 |
|---|---|
| `list_garments(category?, color?, limit?)` | 查本人衣橱，直连 SQLite 按 `user_id` 过滤，返 `{id, category, color, photo_clean_url, remark}` |
| `generate_outfit_image(garment_ids, style?, occasion?)` | 取选中衣物干净图 → 通义万相图生图/参考图 → 存图 → 返 `image_url` |
| `get_weather(location?, date?)`（可选，Phase 2） | 天气 API |

抠图是上传时内部函数（`image_gen.remove_background`），不是工具。LLM 的选衣 / 配色 / 解释是 ReAct 推理，不是工具。以后加新领域（美食 / 出行…）= 再加一组领域工具，不动通用层。

## 6. 系统提示词

**通用生活助手人设，不绑死穿搭**。把「当前可用能力域」作为工具清单写进提示词，加域只加工具不改人设。大意：

> 你是一个个人生活助手，帮用户处理日常事务。你当前能管理衣物衣橱、根据真实衣物生成穿搭推荐图，也能搜索、读写文件、管待办、设定时任务、用技能、派子任务、记长期记忆。后续会开放更多能力域。

## 7. 分阶段（靠工具可用性 + 审批，不靠步数）

**无 `max_steps` 成本护栏**（用户决策：不限制 agent 自主步数）。分阶段放开：

- **Phase 1（验证域工具）**：注册 `list_garments` + `generate_outfit_image`（+ 通用工具）。目标：验证抠图质量、通义万相参考图效果、LLM 选衣合理性。成本靠图片次数上限 + 日预算控制。
- **Phase 2（放开迭代 + 多轮）**：加破坏性域工具（删 / 改衣物，走审批）+ 多轮记忆（`SessionStore`）+ 允许迭代（「换一条裤子」→ 重新 `list_garments` + 重新生成）。

放开程度由工具可用性与审批控制，不卡步数。

## 8. 异常与成本护栏

- **失败处理**：LLM 超时 / API 错 → 复用 twinkle `retry`/`force-finish` 钩子，仍失败上报用户；工具失败（查库错、通义万相报错）→ 抓住返错给循环，LLM 可解释 / 重试，不可恢复上报；图片生成失败 → 「生成失败，重试」。
- **ws 断连**：`SessionStore` 已落盘，会话不丢；循环可取消，重连按 `session_id` 恢复。
- **成本护栏（无 `max_steps`）**：① 每轮图片生成次数上限（如 ≤2 张 / 轮，循环内计数）；② 每日预算硬上限（累计花费超阈值则停，配置项；花费记一张轻量 `spend_log` 表按 `user_id` + 日期累计 LLM token 与出图次数折算金额）。
- **安全护栏**：单轮墙钟超时（防死循环 / 卡死，**非成本护栏**，可选；twinkle 自带 `max_steps=1000` 纯防死循环兜底，保留可调）。
- **破坏性操作审批**：删 / 改衣物等走 `permissions` `require-approval`。
- **越权**：所有工具按 `user_id` 隔离，删 / 改校验属主（沿用 MVP spec）。

## 9. 测试

- **后端单测**：pytest + FastAPI `TestClient` + in-memory SQLite。覆盖衣物 CRUD + 属主、照片上传 + 抠图（mock）、`list_garments` 隔离。
- **循环测试**：`llm_client` mock 成脚本化工具调用序列，断言调对工具、走审批暂停 / 恢复、并行工具调用正确。
- **出图工具**：`generate_outfit_image` mock `httpx`（不真调通义万相），断言参考图组装 / 存图 / 返 URL。
- **ws 路由**：`TestClient` websocket，发消息收流式事件；审批来回（发 approval_response，断言循环恢复）。
- **权限**：删衣物要求审批，拒绝 → 不删。
- **成本护栏**：图片次数上限拒绝；日预算超限停。
- **前端**：微信开发者工具手动验收。

## 10. 前置与待办

- 复用 2026-08-15 MVP spec 的前置（AppID / AppSecret、本地开发域名校验）。
- 实现时确认：通义万相图生图 / 参考图具体 API 端点与参数（DashScope image-synthesis）。
- 天气工具 Phase 2 再定 API。
- 顺手更新 `README.md` / `CLAUDE.md`：定位改为「通用生活助手，当前先做服装 / 穿搭域」（现文档仍写「个人衣物分类管理」，与真实定位不符）。
