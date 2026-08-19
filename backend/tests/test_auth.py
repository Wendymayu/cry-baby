from fastapi.testclient import TestClient
from fastapi_app.main import app
import fastapi_app.auth as auth


def test_login_returns_token(monkeypatch, db):
    async def fake_code2session(code):
        return {"openid": "oABC"}
    monkeypatch.setattr(auth, "code2session", fake_code2session)

    client = TestClient(app)
    resp = client.post("/api/auth/login", json={"code": "any"})
    assert resp.status_code == 200
    data = resp.json()
    assert "token" in data and data["user"]["openid"] == "oABC"
