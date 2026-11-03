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


def test_create_without_color_ok(db):
    # 颜色改为可选:有图时可不填
    client, u = _client_with_user(db)
    h = {"Authorization": f"Bearer {make_token(u.id, u.openid)}"}
    r = client.post("/api/clothing", json={"category": "上衣"}, headers=h)
    assert r.status_code == 200
    assert r.json()["color"] is None and r.json()["category"] == "上衣"


def test_upload_photo_sets_url_and_serves(db):
    client, u = _client_with_user(db)
    h = {"Authorization": f"Bearer {make_token(u.id, u.openid)}"}
    item = client.post("/api/clothing", json={"category": "上衣"}, headers=h).json()
    r = client.post(
        f"/api/clothing/{item['id']}/photo",
        files={"file": ("a.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")},
        headers=h,
    )
    assert r.status_code == 200
    photo_url = r.json()["photo_url"]
    assert photo_url and photo_url.startswith("/uploads/")
    # 静态路由可达:
    assert client.get(photo_url).status_code == 200


def test_upload_other_user_404(db):
    c1, u1 = _client_with_user(db, "oA")
    c2, u2 = _client_with_user(db, "oB")
    h1 = {"Authorization": f"Bearer {make_token(u1.id, u1.openid)}"}
    h2 = {"Authorization": f"Bearer {make_token(u2.id, u2.openid)}"}
    item = c1.post("/api/clothing", json={"category": "上衣"}, headers=h1).json()
    r = c2.post(
        f"/api/clothing/{item['id']}/photo",
        files={"file": ("a.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")},
        headers=h2,
    )
    assert r.status_code == 404


def test_get_single_item(db):
    client, u = _client_with_user(db)
    h = {"Authorization": f"Bearer {make_token(u.id, u.openid)}"}
    item = client.post("/api/clothing", json={"category": "上衣", "color": "黑"}, headers=h).json()
    r = client.get(f"/api/clothing/{item['id']}", headers=h)
    assert r.status_code == 200 and r.json()["category"] == "上衣"
    # 跨用户 404
    _, u2 = _client_with_user(db, "oB")
    h2 = {"Authorization": f"Bearer {make_token(u2.id, u2.openid)}"}
    assert client.get(f"/api/clothing/{item['id']}", headers=h2).status_code == 404


def test_update_item(db):
    client, u = _client_with_user(db)
    h = {"Authorization": f"Bearer {make_token(u.id, u.openid)}"}
    item = client.post("/api/clothing", json={"category": "上衣", "color": "黑"}, headers=h).json()
    r = client.put(f"/api/clothing/{item['id']}", json={"color": "白", "remark": "圆领"}, headers=h)
    assert r.status_code == 200
    assert r.json()["color"] == "白" and r.json()["remark"] == "圆领" and r.json()["category"] == "上衣"


def test_update_other_user_404(db):
    c1, u1 = _client_with_user(db, "oA")
    c2, u2 = _client_with_user(db, "oB")
    h1 = {"Authorization": f"Bearer {make_token(u1.id, u1.openid)}"}
    h2 = {"Authorization": f"Bearer {make_token(u2.id, u2.openid)}"}
    item = c1.post("/api/clothing", json={"category": "上衣"}, headers=h1).json()
    assert c2.put(f"/api/clothing/{item['id']}", json={"color": "白"}, headers=h2).status_code == 404


def test_delete_item(db):
    client, u = _client_with_user(db)
    h = {"Authorization": f"Bearer {make_token(u.id, u.openid)}"}
    item = client.post("/api/clothing", json={"category": "上衣"}, headers=h).json()
    assert client.delete(f"/api/clothing/{item['id']}", headers=h).status_code == 200
    assert len(client.get("/api/clothing", headers=h).json()) == 0


def test_delete_other_user_404(db):
    c1, u1 = _client_with_user(db, "oA")
    c2, u2 = _client_with_user(db, "oB")
    h1 = {"Authorization": f"Bearer {make_token(u1.id, u1.openid)}"}
    h2 = {"Authorization": f"Bearer {make_token(u2.id, u2.openid)}"}
    item = c1.post("/api/clothing", json={"category": "上衣"}, headers=h1).json()
    assert c2.delete(f"/api/clothing/{item['id']}", headers=h2).status_code == 404
    # 原主仍可见
    assert len(c1.get("/api/clothing", headers=h1).json()) == 1


def test_delete_removes_photo_file(db):
    import os
    from fastapi_app import config
    client, u = _client_with_user(db)
    h = {"Authorization": f"Bearer {make_token(u.id, u.openid)}"}
    item = client.post("/api/clothing", json={"category": "上衣"}, headers=h).json()
    up = client.post(
        f"/api/clothing/{item['id']}/photo",
        files={"file": ("a.jpg", b"\xff\xd8\xff\xe0", "image/jpeg")}, headers=h,
    ).json()
    file_path = os.path.join(config.UPLOAD_DIR, os.path.basename(up["photo_url"]))
    assert os.path.exists(file_path)
    assert client.delete(f"/api/clothing/{item['id']}", headers=h).status_code == 200
    assert not os.path.exists(file_path)  # 删条目时连图一起删
