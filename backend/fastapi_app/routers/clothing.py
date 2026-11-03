import os
import uuid

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from fastapi_app import config
from fastapi_app.deps import get_current_user, get_db
from fastapi_app.models import ClothingItem
from fastapi_app.schemas import ClothingCreate, ClothingOut, ClothingUpdate

router = APIRouter(prefix="/api/clothing", tags=["clothing"])

# 图片上传:类型与大小白名单(只看 header 不够,需读内容校验)
_ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
_EXT_BY_TYPE = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp"}
_MAX_SIZE = 8 * 1024 * 1024  # 8MB


def _remove_photo_file(photo_url):
    """删本地磁盘上的图片文件;容忍文件不存在(删 DB 项时/换图时调用,避免残留)。"""
    if not photo_url:
        return
    name = os.path.basename(photo_url)
    try:
        os.remove(os.path.join(config.UPLOAD_DIR, name))
    except FileNotFoundError:
        pass


@router.get("")
def list_clothing(user=Depends(get_current_user), db=Depends(get_db)):
    items = db.query(ClothingItem).filter_by(user_id=user.id).order_by(ClothingItem.created_at.desc()).all()
    return [ClothingOut.model_validate(i) for i in items]


@router.post("")
def create_clothing(body: ClothingCreate, user=Depends(get_current_user), db=Depends(get_db)):
    item = ClothingItem(
        user_id=user.id, category=body.category, color=body.color, remark=body.remark,
        season_tags=body.season_tags, occasion_tags=body.occasion_tags,
        style_tags=body.style_tags, material_tags=body.material_tags,
    )
    db.add(item); db.commit(); db.refresh(item)
    return ClothingOut.model_validate(item)


@router.get("/{item_id}")
def get_clothing(item_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    item = db.query(ClothingItem).filter_by(id=item_id, user_id=user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    return ClothingOut.model_validate(item)


@router.put("/{item_id}")
def update_clothing(item_id: int, body: ClothingUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    item = db.query(ClothingItem).filter_by(id=item_id, user_id=user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    # Distinguish omitted values from explicit null so optional fields can be cleared.
    for k in body.model_fields_set:
        value = getattr(body, k)
        if k.endswith("_tags") and value is None:
            value = []
        setattr(item, k, value)
    db.commit(); db.refresh(item)
    return ClothingOut.model_validate(item)


@router.delete("/{item_id}")
def delete_clothing(item_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    item = db.query(ClothingItem).filter_by(id=item_id, user_id=user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    _remove_photo_file(item.photo_url)
    db.delete(item); db.commit()
    return {"ok": True}


@router.post("/{item_id}/photo")
def upload_photo(item_id: int, file: UploadFile = File(...), user=Depends(get_current_user), db=Depends(get_db)):
    """给指定衣物上传/替换图片。按 user_id 隔离,别人改不了你的图。换图时删旧文件。"""
    item = db.query(ClothingItem).filter_by(id=item_id, user_id=user.id).first()
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="unsupported image type")
    ext = _EXT_BY_TYPE[file.content_type]
    name = f"{user.id}_{uuid.uuid4().hex}.{ext}"
    path = os.path.join(config.UPLOAD_DIR, name)
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    size = 0
    try:
        with open(path, "wb") as f:
            while True:
                chunk = file.file.read(64 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > _MAX_SIZE:
                    raise HTTPException(status_code=400, detail="image too large")
                f.write(chunk)
    except Exception:
        if os.path.exists(path):
            os.remove(path)
        raise
    old_url = item.photo_url
    item.photo_url = f"/uploads/{name}"
    db.commit(); db.refresh(item)
    _remove_photo_file(old_url)  # 换图成功后再删旧文件,避免删了新的没写成功
    return ClothingOut.model_validate(item)
