# cry-baby

微信小程序 + FastAPI 的个人衣橱管理 MVP。当前阶段聚焦衣物分类浏览、新增、编辑、删除和照片管理；穿搭 Agent 暂不作为 MVP 的用户入口，后续基于现有鉴权和衣物 API 演进。

## 项目结构

- `miniprogram/`：原生微信小程序，衣橱和个人设置页面。
- `backend/fastapi_app/`：FastAPI、微信登录、JWT 鉴权、衣物 API、SQLite 数据模型。
- `backend/agent/`：预研中的 Agent 核心，目前不属于衣橱 MVP 的运行链路。
- `tests/`、`backend/tests/`：前端工具层与后端 API 测试。

## 本地运行

后端从 `backend/` 目录启动：

```powershell
uvicorn fastapi_app.main:app --reload --port 8000
```

小程序使用微信开发者工具打开 `miniprogram/`。本地调试可在“我的”页面设置后端地址；正式微信登录需要配置小程序 `APP_ID`、`APP_SECRET` 和强随机 `SECRET_KEY`。
