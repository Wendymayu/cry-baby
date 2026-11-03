import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from fastapi_app import config

app = FastAPI(title="cry-baby")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


@app.get("/health")
def health():
    return {"status": "ok"}


from fastapi_app.routers import auth as auth_router
app.include_router(auth_router.router)

from fastapi_app.routers import clothing as clothing_router
app.include_router(clothing_router.router)

# 上传图片静态服务(/uploads/* → 本地磁盘)。生产可换 OSS,接口契约不变。
os.makedirs(config.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=config.UPLOAD_DIR), name="uploads")

# dev 自举:确保表存在(生产应用迁移工具,不靠这里)。
from sqlalchemy import inspect, text
from fastapi_app.database import Base, engine  # noqa: E402
Base.metadata.create_all(bind=engine)

# Local MVP schema migration: create_all doesn't add columns to an existing SQLite DB.
if engine.dialect.name == "sqlite":
    existing = {column["name"] for column in inspect(engine).get_columns("clothing_items")}
    tag_columns = ("season_tags", "occasion_tags", "style_tags", "material_tags")
    with engine.begin() as connection:
        for column in tag_columns:
            if column not in existing:
                connection.execute(text(
                    f"ALTER TABLE clothing_items ADD COLUMN {column} JSON NOT NULL DEFAULT '[]'"
                ))
