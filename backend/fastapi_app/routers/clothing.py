import uuid
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from fastapi_app import storage
from fastapi_app.deps import get_current_user, get_db
from fastapi_app.models import ClothingItem
from fastapi_app.retention import RETENTION_DAYS, expires_at
from fastapi_app.schemas import ClothingCreate, ClothingOut, ClothingUpdate

router = APIRouter(prefix="/api/clothing", tags=["clothing"])

# 图片上传:类型与大小白名单(只看 header 不够,需读内容校验)
_ALLOWED_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp"}
_EXT_BY_TYPE = {"image/jpeg": "jpg", "image/jpg": "jpg", "image/png": "png", "image/webp": "webp"}
_MAX_SIZE = 8 * 1024 * 1024  # 8MB


def _out(item):
    result = ClothingOut.model_validate(item).model_dump()
    result["photo_url"] = storage.photo_url(item.photo_url)
    return result


@router.get("")
def list_clothing(user=Depends(get_current_user), db=Depends(get_db)):
    items = db.query(ClothingItem).filter_by(user_id=user.id, deleted_at=None).order_by(ClothingItem.created_at.desc()).all()
    return [_out(i) for i in items]


@router.get("/trash")
def list_trash(user=Depends(get_current_user), db=Depends(get_db)):
    cutoff = datetime.utcnow() - timedelta(days=RETENTION_DAYS)
    items = db.query(ClothingItem).filter(
        ClothingItem.user_id == user.id,
        ClothingItem.deleted_at.isnot(None),
        ClothingItem.deleted_at > cutoff,
    ).order_by(ClothingItem.deleted_at.desc()).all()
    result = []
    for item in items:
        entry = _out(item)
        entry["deleted_at"] = item.deleted_at.isoformat() + "Z"
        entry["expires_at"] = expires_at(item.deleted_at).isoformat() + "Z"
        result.append(entry)
    return result


@router.post("")
def create_clothing(body: ClothingCreate, user=Depends(get_current_user), db=Depends(get_db)):
    item = ClothingItem(
        user_id=user.id, category=body.category, color=body.color, remark=body.remark,
        season_tags=body.season_tags, occasion_tags=body.occasion_tags,
        style_tags=body.style_tags, material_tags=body.material_tags,
    )
    db.add(item); db.commit(); db.refresh(item)
    return _out(item)


@router.get("/{item_id}")
def get_clothing(item_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    item = db.query(ClothingItem).filter_by(id=item_id, user_id=user.id, deleted_at=None).first()
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    return _out(item)


@router.put("/{item_id}")
def update_clothing(item_id: int, body: ClothingUpdate, user=Depends(get_current_user), db=Depends(get_db)):
    item = db.query(ClothingItem).filter_by(id=item_id, user_id=user.id, deleted_at=None).first()
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    # Distinguish omitted values from explicit null so optional fields can be cleared.
    for k in body.model_fields_set:
        value = getattr(body, k)
        if k.endswith("_tags") and value is None:
            value = []
        setattr(item, k, value)
    db.commit(); db.refresh(item)
    return _out(item)


@router.delete("/{item_id}")
def delete_clothing(item_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    item = db.query(ClothingItem).filter_by(id=item_id, user_id=user.id, deleted_at=None).first()
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    item.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "deleted_at": item.deleted_at.isoformat() + "Z"}


@router.post("/{item_id}/restore")
def restore_clothing(item_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    item = db.query(ClothingItem).filter(
        ClothingItem.id == item_id,
        ClothingItem.user_id == user.id,
        ClothingItem.deleted_at.isnot(None),
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    if expires_at(item.deleted_at) <= datetime.utcnow():
        raise HTTPException(status_code=410, detail="recycle period expired")
    item.deleted_at = None
    db.commit(); db.refresh(item)
    return _out(item)


@router.delete("/{item_id}/permanent")
def delete_clothing_permanently(item_id: int, user=Depends(get_current_user), db=Depends(get_db)):
    item = db.query(ClothingItem).filter(
        ClothingItem.id == item_id,
        ClothingItem.user_id == user.id,
        ClothingItem.deleted_at.isnot(None),
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    try:
        storage.delete_photo(item.photo_url)
    except Exception as exc:
        raise HTTPException(status_code=502, detail="photo deletion unavailable") from exc
    db.delete(item); db.commit()
    return {"ok": True}


@router.post("/{item_id}/photo")
def upload_photo(item_id: int, file: UploadFile = File(...), user=Depends(get_current_user), db=Depends(get_db)):
    """给指定衣物上传/替换图片。按 user_id 隔离,别人改不了你的图。换图时删旧文件。"""
    item = db.query(ClothingItem).filter_by(id=item_id, user_id=user.id, deleted_at=None).first()
    if not item:
        raise HTTPException(status_code=404, detail="not found")
    if file.content_type not in _ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="unsupported image type")
    ext = _EXT_BY_TYPE[file.content_type]
    name = f"{user.id}_{uuid.uuid4().hex}.{ext}"
    key = f"users/{user.id}/clothing/{item.id}/{name}"
    data = bytearray()
    try:
        while True:
            chunk = file.file.read(64 * 1024)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > _MAX_SIZE:
                raise HTTPException(status_code=400, detail="image too large")
        photo_ref = storage.save_photo(key, bytes(data), file.content_type)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail="photo storage unavailable") from exc
    old_url = item.photo_url
    item.photo_url = photo_ref
    db.commit(); db.refresh(item)
    storage.delete_photo(old_url)  # 新照片保存并提交成功后再删旧图。
    return _out(item)
