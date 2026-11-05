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
python run_local.py
```

该命令会读取 `backend/.env` 并启动本地 API。小程序使用微信开发者工具打开 `miniprogram/`。本地调试可在“我的”页面设置后端地址；正式微信登录需要配置小程序 `APP_ID`、`APP_SECRET` 和强随机 `SECRET_KEY`。

## 照片存储

生产环境使用阿里云 OSS，默认 Bucket 为 `cry-baby-clothes`，地域为上海。设置以下后端环境变量后，上传照片会写入 OSS；数据库只保存对象 key，API 返回有时效的签名地址。建议将 Bucket 设为私有。未配置 AccessKey 时使用 `backend/uploads/` 本地存储，适合本机开发。

```text
OSS_BUCKET=cry-baby-clothes
OSS_ENDPOINT=https://oss-cn-shanghai.aliyuncs.com
OSS_ACCESS_KEY_ID=...
OSS_ACCESS_KEY_SECRET=...
OSS_SIGNED_URL_TTL=604800
```

为后端创建仅允许该 Bucket 上传、读取和删除对象的 RAM 身份，并将密钥放在部署环境的密钥配置中，不要提交到 Git。小程序上线前，把 `cry-baby-clothes.oss-cn-shanghai.aliyuncs.com` 加入微信公众平台的下载合法域名；若使用自定义 HTTPS 域名，则将 `OSS_ENDPOINT` 配置成该域名对应的 OSS CNAME 地址。

已有本地照片不会自动搬迁。配置好上述环境变量并安装 `backend/requirements.txt` 后，在 `backend/` 目录运行 `python -m fastapi_app.migrate_photos_to_oss`；脚本会更新数据库中的照片引用并保留本地原图。
