from pydantic import BaseModel
from typing import Optional


class ClothingCreate(BaseModel):
    category: str
    color: str
    remark: Optional[str] = None


class ClothingOut(BaseModel):
    id: int
    category: str
    color: str
    remark: Optional[str] = None
    photo_url: Optional[str] = None
    photo_clean_url: Optional[str] = None
    class Config:
        from_attributes = True
