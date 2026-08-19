from fastapi import APIRouter, Depends
from fastapi_app import auth
from fastapi_app.database import SessionLocal
from fastapi_app.models import User
from fastapi_app.deps import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


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
