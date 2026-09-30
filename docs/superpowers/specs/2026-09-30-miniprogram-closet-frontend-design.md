# 微信小程序前端设计 — 衣橱管理优先

- 日期:2026-09-30
- 状态:待评审
- 范围:微信小程序前端第一阶段(服装与穿搭管理领域)
- 关联后端:FastAPI `backend/fastapi_app/`(REST 已就绪),ReAct agent `/ws/agent`(未实现,占位)

## 1. 背景

项目是通用个人生活助手(微信小程序前端 + FastAPI / ReAct-agent 后端),第一阶段做服装与穿搭管理。后端 REST 部分(微信登录、衣物列表/新建)已就绪可直接对接;ReAct agent 流式对话端点 `/ws/agent` 设计态未落地,前端对话部分本次只占位。

后端现有接口:
- `POST /api/auth/login` — body `{"code": <wx.login code>}`,成功返回 `{"token": <JWT>, "user": {"id","openid"}}`,无 openid 时 `{"error":"no openid"}`
- `GET /api/clothing` — Bearer 鉴权,返回 `ClothingOut[]`,按 `created_at desc`,无分页/筛选
- `POST /api/clothing` — Bearer 鉴权,body `ClothingCreate{category:str, color:str, remark?:str}`,返回 `ClothingOut`
- `GET /health` — 无鉴权,连通性检查
- `ClothingOut` 字段:`id, category, color, remark?, photo_url?, photo_clean_url?`

鉴权:HS256 JWT,7 天 TTL,`Authorization: Bearer <token>`。token payload 含 `openid`,后端反查 `User.id`,衣物按 `user_id` 外键行级隔离。

前端现状:`miniprogram/` 下只有一个 `pages/debug` 调试页(连通/登录/列衣物三按钮),`app.js` 里 `globalData.baseUrl = 'http://127.0.0.1:8000'` 已配好,CORS 全开。AppID 当前为游客模式(`touristappid`)。

## 2. 本次范围

**本次做(in scope):**
- 静默登录链路(wx.login → /api/auth/login → token 存取)
- 衣橱首页:网格列表 + 浮动「+」新建入口 + 下拉刷新
- 新建衣物页:分类选择器 + 颜色色块 + 备注 + 保存
- 三 tab 框架:衣橱、对话(占位)、我的
- 网络层封装(request / api / auth 工具)
- 莫兰迪暖中性视觉风格落地到全局样式
- 保留 debug 页作为开发态绕过入口

**本次不做(out of scope):**
- 对话功能(仅占位页,等后端 `/ws/agent`)
- 衣物删改(PUT/PATCH/DELETE,后端未实现)
- 照片上传(`POST /api/clothing/{id}/photo`,后端未实现)
- 衣物详情页、编辑已有衣物
- 用户头像昵称获取、推送、分享等

## 3. 架构决策:轻量原生

基于现有 `miniprogram/` scaffold,继续用原生小程序,不引入框架(Taro/uni-app)或状态管理库。理由:已有 scaffold 是原生结构、页面少、交互简单,框架会带来迁移成本且无收益;YAGNI。

- 状态:页面级(`onLoad`/`onShow` 拉取 + `data`),全局仅 `app.globalData` 存 `baseUrl` 与(可选)`token` 缓存;token 持久化用 `wx.setStorageSync`。
- 网络:`utils/request.js` 统一封装 `wx.request`,自动注入 `baseUrl` 与 `Bearer`、统一 401 处理;`utils/api.js` 按域聚合接口。
- 组件:仅抽 3 个复用度高的小组件(`closet-card`、`category-picker`、`color-picker`),其余页内联。

## 4. 文件结构(新增/改动)

```
miniprogram/
  app.js                      # 改:onLaunch 从 storage 恢复 baseUrl(否则用默认 127.0.0.1:8000)+ 调 auth.ensureLogin()
  app.json                    # 改:注册 pages + tabBar
  app.wxss                    # 改:莫兰迪色板 + 全局基础样式
  utils/
    request.js                # 新:wx.request 封装
    api.js                   # 新:auth + clothing 接口
    auth.js                  # 新:静默登录 + token 存取
    constants.js             # 新:预设分类、颜色清单
  components/
    closet-card/             # 新:衣橱网格卡片
      index.{js,wxml,wxss,json}
    category-picker/         # 新:分类选择器(picker 或弹窗)
      index.{js,wxml,wxss,json}
    color-picker/            # 新:颜色色块选择
      index.{js,wxml,wxss,json}
  pages/
    debug/                    # 保留:开发调试 + 手动 token 绕过
    closet/                   # 新:衣橱首页(网格列表)
      closet.{js,wxml,wxss,json}
    clothing-edit/           # 新:新建衣物
      clothing-edit.{js,wxml,wxss,json}
    chat/                    # 新:对话占位页
      chat.{js,wxml,wxss,json}
    profile/                 # 新:我的
      profile.{js,wxml,wxss,json}
  project.config.json         # 不改(appid 仍游客模式;真机时用户自换)
```

## 5. 页面规格

### 5.1 pages/closet — 衣橱首页
- 顶部:`navigationBarTitleText = 衣橱`
- 主体:两列网格,每格用 `closet-card` 组件(色块 + 分类 + 备注)
- 右下浮动「+」按钮 → `wx.navigateTo` 到 `/pages/clothing-edit/index`
- 下拉刷新:`onPullDownRefresh` 重新拉列表
- 数据:`onShow` 调 `api.clothing.list()`,存 `data.items`;`onShow` 而非 `onLoad` 保证新建返回后自动刷新
- 空状态:无衣物时展示引导文案 + 「添加第一件」按钮
- 失败:网络/鉴权错误展示提示 + 重试按钮

### 5.2 pages/clothing-edit — 新建衣物
- 分类:用 `category-picker`(预设分类,选一个)
- 颜色:用 `color-picker`(预设色块,选一个)
- 备注:`textarea`,可选
- 保存按钮:校验分类+颜色必选 → `api.clothing.create({category,color,remark})` → 成功 `wx.navigateBack`
- 保存中禁用按钮防重复提交

### 5.3 pages/chat — 对话占位
- 展示「对话功能即将上线」+ 简短说明(后续接入智能穿搭建议/生活助手对话)
- 无交互逻辑;布局预留未来聊天气泡区 + 输入框位置(空容器),便于后续替换

### 5.4 pages/profile — 我的
- 设置项:后端地址切换(默认 `http://127.0.0.1:8000`,可改局域网 IP,存 `globalData.baseUrl` + storage)
- 入口:跳转 debug 页(开发调试)
- 关于:版本号 + 项目说明(一句话)
- (不获取用户头像昵称,本次不做)

### 5.5 pages/debug — 保留
- 维持现有三按钮(连通/登录/列衣物)+ 手动 token 输入框
- 不进 tabBar,仅开发态从 profile 进入

## 6. 组件规格

### 6.1 closet-card
- props:`item`(ClothingOut 子集:`category, color, remark`)
- 渲染:顶部色块(取 `color` 对应色值,花色用渐变)、底部分类(主)+ 备注(次,可选)
- 莫兰迪色板:卡片白底 + 暖边

### 6.2 category-picker
- props:`value`(当前分类)、`bind:change`
- 数据源:`constants.CATEGORIES`
- 实现:可用原生 `picker`(mode=selector)或自绘弹窗;初版优先原生 picker

### 6.3 color-picker
- props:`value`(当前颜色 key)、`bind:change`
- 数据源:`constants.COLORS`(key + 名称 + 色值)
- 渲染:色块网格,选中态加边框/对勾

## 7. 网络层

### 7.1 utils/request.js
- `request({url, method, data, needAuth=true})`:拼 `globalData.baseUrl` + url;若 `needAuth` 注入 `Authorization: Bearer <storage token>`;返回 Promise
- 成功(2xx):resolve `res.data`
- 401:`auth.clearToken()` → `auth.ensureLogin()` 重新静默登录 → 用新 token 原请求重试一次;仍失败则 reject,由页面提示「登录失败,请到 我的 → 开发调试 粘贴 token」
- 网络/其他错误:reject 错误信息

### 7.2 utils/api.js
- `auth.login(code)` → POST /api/auth/login
- `clothing.list()` → GET /api/clothing
- `clothing.create({category,color,remark})` → POST /api/clothing

### 7.3 utils/auth.js
- `ensureLogin()`:若有有效 token 直接 resolve;否则 `wx.login` 取 code → `api.auth.login(code)` → 存 token
- `getToken()` / `setToken(t)` / `clearToken()`:storage 读写
- `loginWithManualToken(t)`:debug 页绕过用

## 8. 登录流程

1. `app.js` `onLaunch` 调 `auth.ensureLogin()`(静默,不阻塞页面渲染;closet 页 `onShow` 依赖 token 时再 await)
2. 成功:token 存 storage,后续接口自动注入
3. 失败(如游客模式 `jscode2session` 拿不到 openid):不阻塞 UI,衣橱页会 401/失败,引导用户去 debug 页手动粘贴 token(后端 `make_token` 现造的 JWT)绕过
4. 真机真 AppID 时:静默登录端到端跑通,无感

## 9. 预设数据(utils/constants.js)

分类(CATEGORIES):上衣、外套、衬衫、裤子、裙装、鞋、配饰

颜色(COLORS,key + 名称 + 色值):
- black 黑 #222222
- white 白 #ffffff(渲染用边框区分)
- gray 灰 #9ca3af
- red 红 #dc2626
- blue 蓝 #3b82f6
- green 绿 #16a34a
- yellow 黄 #eab308
- brown 棕 #a16207
- pink 粉 #ec4899
- multicolor 花色 `linear-gradient(135deg,#f87171,#fbbf24,#34d399,#60a5fa,#a78bfa)`

说明:后端 `category`/`color` 存自由字符串,前端写入时存「分类中文名」与「颜色 key」(如 `black`),读取时按 key 反查色值渲染。这保证后端 schema 不变,前端可控、可筛选。

## 10. 视觉风格

莫兰迪暖中性,统一写在 `app.wxss`:

| 用途 | 变量名(注释约定) | 色值 |
|---|---|---|
| 主色(按钮/选中) | primary | #a68a64 |
| 正文文字 | text | #5a4a3a |
| 背景 | bg | #faf8f5 |
| 卡片底 | card | #ffffff |
| 卡片边 | card-border | #f0ece6 |
| 次要文字 | text-secondary | #a89a8a |

- tabBar 选中色 = primary,未选 = text-secondary
- 浮动「+」按钮 = primary 圆形 + 阴影
- 全局 `page{background:bg; color:text}`

## 11. 占位与未来扩展

- **对话页**:本次只占位。后端 `/ws/agent`(WebSocket)落地后,用 `wx.connectSocket` 接,token 走 query 或首帧,按 `LoopEvent.kind`(text_delta/tool_call/tool_result/approval_request/final/error)分发渲染;`sequence` 字段用于排序/去重。破坏性工具的 `approval_request` 需前端回发决策。
- **衣物删改/照片**:后端补全 PUT/PATCH/DELETE 与照片上传后,衣橱卡片长按出删除、`clothing-edit` 支持编辑模式、卡片色块支持显示照片。
- **分类/颜色自定义**:若后续需要,`category-picker`/`color-picker` 扩展自定义新增,后端无需改。

## 12. 验证方式

- **游客模式(touristappid)**:静默登录会失败(后端 `jscode2session` 无 AppSecret 配不上),用 debug 页手动粘贴后端 `make_token` 现造的 JWT,测 GET/POST /api/clothing 链路。
- **真机真 AppID**:用户把真 AppID 填入 `project.config.json`、AppSecret 填入后端 `.env`,静默登录端到端无感跑通。
- **后端**:从 `backend/` 跑 `uvicorn fastapi_app.main:app --reload --port 8000`,baseUrl 已配 8000,真机改局域网 IP(在 profile 页切换)。
- 单元/集成测试:小程序前端本次不强制(原生小程序测试成本高),以真机/开发者工具手动验证为主。

## 13. 关键约束与风险

- 后端 `/ws/agent` 未实现,对话页只能占位,不能本次联调。
- 游客 AppID 下无法端到端验证登录,依赖 debug 页绕过。
- 后端衣物无分页/筛选,衣橱量大时全量拉取;本次可接受(个人助手,量小)。
- `category`/`color` 后端是自由字符串,前端靠 `constants` 约束写入,旧脏数据(若有)可能渲染为默认色/原样显示——本次首次开发无历史数据,不影响。
