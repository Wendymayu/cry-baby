# 服装管理小程序 MVP — 设计规格

## 1. 概述

本项目是一个微信小程序，MVP 阶段提供个人服装信息的分类管理：用户可新增、查看、编辑、删除自己的服装条目，并按类别分组浏览。

- **前端**：微信小程序（原生框架）
- **后端**：Python + FastAPI + SQLite
- **身份**：微信静默登录，以 openid 识别用户

## 2. 范围

### 包含（MVP）
- 服装条目 CRUD（增、删、改、查）
- 按类别分组列表
- 微信静默登录（openid）
- 可选备注字段
- 删除二次确认、空状态引导

### 不包含（留待后续）
- 服装照片上传 / 相机与相册权限
- 用户自定义类别（类别为预定义固定集合）
- 搜索 / 筛选 / 统计
- 详情页、底部 tabBar
- 主动多端同步逻辑（数据本就在后端，天然多端可见，MVP 不额外处理）

## 3. 架构

```
微信小程序 (前端)              FastAPI 后端                SQLite (clothing.db)
─────────────────            ───────────────             ─────────────
pages/list  pages/edit  ──▶  routers: auth, clothing  ──▶  users, clothing_items
services/auth.js            models.py (SQLAlchemy)
services/clothing.js         schemas.py (Pydantic)
config/constants.js          auth.py (code2session + token)
utils/displayName.js          deps.py (get_current_user)
```

- 小程序通过 `wx.request` 调后端 REST API（`/api` 前缀）。
- 身份流程：小程序 `wx.login()` 拿 `code` → 后端调微信 `jscode2session` 换 `openid` → 后端签发 token → 客户端存本地，后续请求带 `Authorization: Bearer <token>`。
- 数据流：列表页拉取并按类别分组展示；编辑页提交 → 后端落库 → 返回列表页刷新。

## 4. 数据模型（SQLite）

两张表，openid 做用户隔离，数字主键便于关联：

### users
| 列 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增主键 |
| openid | TEXT UNIQUE | 微信 openid，首次登录插入 |
| created_at | DATETIME | 注册时间 |

### clothing_items
| 列 | 类型 | 说明 |
|---|---|---|
| id | INTEGER PK | 自增主键 |
| user_id | INTEGER FK→users.id | 属主，建索引 |
| category | TEXT | 类别中文串，后端枚举校验 |
| color | TEXT | 颜色中文串，后端枚举校验 |
| remark | TEXT NULL | 可选备注 |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |

**显示名不落库**：由客户端纯函数 `displayName(color, category)` 拼成 `颜色+类别`（如「蓝色上衣」）。列表加载时按类别分组，组内对同名条目按序追加后缀（「蓝色上衣 2」「蓝色上衣 3」）。

## 5. 后端 API（REST，前缀 `/api`）

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/auth/login` | body `{code}` → 调 `jscode2session` → 新用户插入 `users` → 返回 `{token, user}` |
| GET | `/api/clothing` | 取当前用户全部衣物（按 `created_at` 倒序） |
| POST | `/api/clothing` | body `{category, color, remark?}` → 建条目 |
| PUT | `/api/clothing/{id}` | 改 `{category, color, remark?}`，校验属主 |
| DELETE | `/api/clothing/{id}` | 删，校验属主 |

- 类别 / 颜色不单独开接口，作为前端常量 + 后端枚举校验。
- 鉴权：除 `/api/auth/login` 外，都走 token 依赖，从 token 解出 `user_id` 注入。所有读写都只作用于当前 `user_id`，并校验目标条目属主。
- `jscode2session` 返回的 `session_key` 在 MVP 不使用（无需解密用户数据），可忽略。

## 6. 小程序页面与数据流

- **`app.js` — `onLaunch`**：静默登录。`wx.login` → `POST /api/auth/login` → 存 token 到本地；失败给重试提示。
- **`pages/list`（首页，入口）**：衣物按类别分组列出，每条显示拼名 + 备注；空状态显示「添加你的第一件衣服」；右下「+」进编辑页；长按或左滑触发编辑 / 删除；下拉刷新。
- **`pages/edit`**：新增与编辑共用，靠是否传 `id` 区分。表单 = 类别选择器（picker）+ 颜色选择器 + 备注多行输入；保存调 POST/PUT 后 `navigateBack`。
- 无 tabBar、无详情页——单功能 MVP 不需要。

## 7. 类别 / 颜色常量

前端 `config/constants.js` 一份，后端枚举同步一份。

- **类别**：上衣、外套、裤子、裙装、鞋、配饰
- **颜色**：黑色、白色、灰色、红色、橙色、黄色、绿色、蓝色、紫色、粉色、棕色、花色（显示名 = 颜色 + 类别，如「蓝色上衣」）

> 此为初始清单，可在实现阶段增删。

## 8. 异常与空状态

- 网络失败 / 接口报错 → `wx.showToast`「加载失败，下拉重试」。
- 列表空 → 引导添加。
- 删除二次确认（`wx.showModal`）。

## 9. 技术栈与项目结构

### 后端
FastAPI + SQLAlchemy + Pydantic + `python-jose`（签 token）+ `httpx`（调微信）。

```
backend/
  main.py            # app、CORS、include_router
  config.py          # APP_ID, APP_SECRET, SECRET_KEY, DB_URL
  database.py        # engine / session
  models.py          # User, ClothingItem
  schemas.py         # Pydantic 入参 / 出参
  auth.py            # code2session + 生成 / 校验 token
  deps.py            # get_current_user 依赖
  routers/auth.py
  routers/clothing.py
  tests/             # pytest + TestClient + in-memory sqlite
```

### 小程序
原生框架，不引外部 UI 库。

```
miniprogram/
  app.js app.json app.wxss
  config/constants.js
  services/auth.js services/clothing.js   # 封装 wx.request
  utils/displayName.js
  pages/list/
  pages/edit/
```

## 10. 前置条件与部署备注

- 需在 [mp.weixin.qq.com](https://mp.weixin.qq.com) 注册小程序，取得 **AppID + AppSecret**，填入后端 `config.py`。
- **本地开发**：微信开发者工具勾选「不校验合法域名、TLS 版本及 HTTPS 证书」，即可请求 `http://localhost:8000`。
- **上线**：需 HTTPS 域名 + 在小程序后台配置 request 合法域名；国内服务器域名需 ICP 备案。此为发布阶段事项，不阻塞 MVP 开发。

## 11. 测试策略

- **后端**：`pytest` + FastAPI `TestClient`，用 in-memory SQLite，覆盖 auth（mock `jscode2session`）与 clothing CRUD（含属主校验、越权拒绝）。
- **前端**：MVP 阶段以微信开发者工具手动验收为主。
