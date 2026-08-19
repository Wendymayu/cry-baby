import httpx
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi_app.config import APP_ID, APP_SECRET, SECRET_KEY

TOKEN_TTL_MINUTES = 60 * 24 * 7


async def code2session(code: str) -> dict:
    """微信 jscode2session。测试 monkeypatch 此函数。"""
    url = "https://api.weixin.qq.com/sns/jscode2session"
    params = {"appid": APP_ID, "secret": APP_SECRET,
              "js_code": code, "grant_type": "authorization_code"}
    async with httpx.AsyncClient(timeout=10) as c:
        r = await c.get(url, params=params)
        r.raise_for_status()
        return r.json()


def make_token(user_id: int, openid: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "openid": openid,
               "exp": now + timedelta(minutes=TOKEN_TTL_MINUTES)}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        return None
