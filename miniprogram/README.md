# cry-baby 小程序前端

微信小程序开发调试骨架,对接 `../backend/` 的 FastAPI。

## 打开项目

1. 安装「微信开发者工具」(稳定版 Stable Build):https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html
2. 打开 DevTools → 导入项目 → 选择**本目录**(`miniprogram/`)。
3. AppID:`project.config.json` 默认用了「游客模式」(`touristappid`),只够调 `/health` 这类无需登录的接口。要测登录,去 [mp.weixin.qq.com](https://mp.weixin.qq.com) 注册小程序,把 `project.config.json` 里的 `appid` 换成真 AppID,并把 AppSecret 配到后端。

## 起后端

```bash
cd ../backend
uvicorn fastapi_app.main:app --reload --port 8000
# 浏览器开 http://127.0.0.1:8000/health 看到 {"status":"ok"}
```

## 调试节奏

- **模拟器**:直接点页面按钮。`project.config.json` 里已设 `urlCheck: false`(关闭域名校验),HTTP 可直连 `127.0.0.1:8000`,无需手动勾选。
- **Network 面板**:每次点按钮后切过来看请求/响应,这是对接后端的主阵地。
- **真机调试**(不是普通「预览」):`127.0.0.1` 在手机上指手机自己,要改成电脑局域网 IP。把 `app.js` 的 `globalData.baseUrl` 改成 `http://<电脑局域网IP>:8000`(`ipconfig` 查 IP),手机和电脑连同一 WiFi。真机调试模式会放宽域名校验,HTTP 能通;普通「预览」在手机上会卡域名校验,HTTP 通常不通(要 ngrok 之类做 HTTPS 隧道)。

## 接口(已对接)

| 按钮 | 请求 | 鉴权 |
|---|---|---|
| 测连通 | `GET /health` | 无 |
| 登录 | `POST /api/auth/login` body `{code}` | 无(用 `wx.login` 的 code 换 token) |
| 列衣物 | `GET /api/clothing` | `Authorization: Bearer <token>` |

游客模式下登录会返回 `{"error":"no openid"}`(后端 code2session 拿不到 openid)——这能证明小程序→后端通了,只是拿不到 token。想测 clothing,可在「手动 token」框里粘贴一个用后端 `make_token(user_id, openid)` 现造的 JWT 绕过登录。

WebSocket 流式(ReAct agent 的 `LoopEvent`)等 Plan 3 后端建了 `ws` 端点,再用 `wx.connectSocket` 接入。
