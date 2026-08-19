from fastapi.testclient import TestClient
from fastapi_app.main import app
from fastapi_app.auth import make_token
from fastapi_app.models import User, ClothingItem


def _client_with_user(db, openid="oA"):
    u = User(openid=openid)
    db.add(u); db.commit(); db.refresh(u)
    token = make_token(u.id, u.openid)
    return TestClient(app), u


def test_no_token_returns_401(db):
    client = TestClient(app)
    assert client.get("/api/clothing").status_code == 401


def test_create_and_list(db):
    client, u = _client_with_user(db)
    h = {"Authorization": f"Bearer {make_token(u.id, u.openid)}"}
    r = client.post("/api/clothing", json={"category": "上衣", "color": "蓝色"}, headers=h)
    assert r.status_code == 200 and r.json()["color"] == "蓝色"
    r = client.get("/api/clothing", headers=h)
    assert r.status_code == 200
    assert len(r.json()) == 1 and r.json()[0]["category"] == "上衣"


def test_isolation_between_users(db):
    c1, u1 = _client_with_user(db, "oA")
    c2, u2 = _client_with_user(db, "oB")
    h1 = {"Authorization": f"Bearer {make_token(u1.id, u1.openid)}"}
    h2 = {"Authorization": f"Bearer {make_token(u2.id, u2.openid)}"}
    c1.post("/api/clothing", json={"category": "裤", "color": "黑"}, headers=h1)
    assert len(c2.get("/api/clothing", headers=h2).json()) == 0
    assert len(c1.get("/api/clothing", headers=h1).json()) == 1
