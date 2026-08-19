from fastapi import Depends, Header
from fastapi_app.auth import decode_token
from fastapi_app.database import SessionLocal
from fastapi_app.models import User


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(authorization: str = Header(default=""), db=Depends(get_db)) -> User:
    if not authorization.startswith("Bearer "):
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="missing token")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token)
    if not payload:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="invalid token")
    user = db.query(User).filter_by(openid=payload["openid"]).first()
    if not user:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="user not found")
    return user
