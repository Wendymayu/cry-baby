from fastapi import APIRouter, Depends, HTTPException
from fastapi_app import auth
from fastapi_app import config, storage
from fastapi_app.database import SessionLocal
from fastapi_app.models import ClothingItem, User
from fastapi_app.deps import get_current_user, get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])

DEV_OPENID = "debug-user"


@router.post("/login")
async def login(body: dict, db=Depends(get_db)):
    code = body.get("code", "")
    session = await auth.code2session(code)
    openid = session.get("openid", "")
    if not openid:
        return {"error": "no openid"}
    user = db.query(User).filter_by(openid=openid).first()
    if user is None:
        user = User(openid=openid)
        db.add(user); db.commit(); db.refresh(user)
    token = auth.make_token(user.id, user.openid)
    return {"token": token, "user": {"id": user.id, "openid": user.openid}}


@router.post("/dev_token")
def dev_token(db=Depends(get_db)):
    """本地开发态一键签发调试 token(游客/测试 AppID 无法走 wx.login 时绕过用)。
    仅在未配置 AppSecret 时可用;生产配了 AppSecret 即自动关闭,避免被滥用。"""
    if config.APP_SECRET:
        raise HTTPException(status_code=404, detail="not found")
    user = db.query(User).filter_by(openid=DEV_OPENID).first()
    if user is None:
        user = User(openid=DEV_OPENID)
        db.add(user); db.commit(); db.refresh(user)
    token = auth.make_token(user.id, user.openid)
    return {"token": token, "user": {"id": user.id, "openid": user.openid}}


@router.delete("/account")
def delete_account(user=Depends(get_current_user), db=Depends(get_db)):
    """Delete the signed-in account, wardrobe rows, and uploaded clothing photos."""
    items = db.query(ClothingItem).filter_by(user_id=user.id).all()
    photo_urls = [item.photo_url for item in items if item.photo_url]
    for item in items:
        db.delete(item)
    db.delete(user)
    db.commit()

    for photo_url in photo_urls:
        storage.delete_photo(photo_url)
    return {"ok": True}
