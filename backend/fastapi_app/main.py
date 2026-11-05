import os
import asyncio
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from fastapi_app import config
from fastapi_app.retention import purge_expired_items

logger = logging.getLogger(__name__)
_retention_task = None

app = FastAPI(title="cry-baby")
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)


async def _retention_worker():
    while True:
        try:
            await asyncio.to_thread(purge_expired_items)
        except Exception:
            logger.exception("Recycle-bin retention cleanup failed; it will retry in five minutes")
        await asyncio.sleep(5 * 60)


@app.on_event("startup")
async def start_retention_worker():
    global _retention_task
    _retention_task = asyncio.create_task(_retention_worker())


@app.on_event("shutdown")
async def stop_retention_worker():
    if _retention_task is not None:
        _retention_task.cancel()
        try:
            await _retention_task
        except asyncio.CancelledError:
            pass


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
        if "deleted_at" not in existing:
            connection.execute(text("ALTER TABLE clothing_items ADD COLUMN deleted_at DATETIME"))
        connection.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_clothing_items_deleted_at ON clothing_items (deleted_at)"
        ))
