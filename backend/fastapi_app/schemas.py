from pydantic import BaseModel, Field
from typing import List, Optional


class ClothingCreate(BaseModel):
    category: str
    color: Optional[str] = None
    remark: Optional[str] = None
    season_tags: List[str] = Field(default_factory=list)
    occasion_tags: List[str] = Field(default_factory=list)
    style_tags: List[str] = Field(default_factory=list)
    material_tags: List[str] = Field(default_factory=list)


class ClothingUpdate(BaseModel):
    """PATCH 语义:只改非 None 字段。"""
    category: Optional[str] = None
    color: Optional[str] = None
    remark: Optional[str] = None
    season_tags: Optional[List[str]] = None
    occasion_tags: Optional[List[str]] = None
    style_tags: Optional[List[str]] = None
    material_tags: Optional[List[str]] = None


class ClothingOut(BaseModel):
    id: int
    category: str
    color: Optional[str] = None
    remark: Optional[str] = None
    season_tags: List[str] = Field(default_factory=list)
    occasion_tags: List[str] = Field(default_factory=list)
    style_tags: List[str] = Field(default_factory=list)
    material_tags: List[str] = Field(default_factory=list)
    photo_url: Optional[str] = None
    photo_clean_url: Optional[str] = None
    class Config:
        from_attributes = True
