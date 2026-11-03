from fastapi.testclient import TestClient
from fastapi_app.main import app
import fastapi_app.auth as auth
import fastapi_app.config as config


def test_login_returns_token(monkeypatch, db):
    async def fake_code2session(code):
        return {"openid": "oABC"}
    monkeypatch.setattr(auth, "code2session", fake_code2session)

    client = TestClient(app)
    resp = client.post("/api/auth/login", json={"code": "any"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data and data["user"]["openid"] == "oABC"


def test_dev_token_mints_and_authorizes(db):
    client = TestClient(app)
    resp = client.post("/api/auth/dev_token")
    assert resp.status_code == 200
    token = resp.json()["token"]
    # 端到端:换来的 token 能通过 /api/clothing 鉴权
    r2 = client.get("/api/clothing", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 200


def test_dev_token_disabled_when_appsecret_configured(db, monkeypatch):
    monkeypatch.setattr(config, "APP_SECRET", "configured-for-prod")
    client = TestClient(app)
    resp = client.post("/api/auth/dev_token")
    assert resp.status_code == 404

