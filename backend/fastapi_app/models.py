from datetime import datetime
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from fastapi_app.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    openid = Column(Text, unique=True, nullable=False)
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
