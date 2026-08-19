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
