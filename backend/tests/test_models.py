from datetime import datetime
from fastapi_app.models import User, ClothingItem


def test_create_user_and_clothing(db):
    u = User(openid="oABC")
    db.add(u); db.commit(); db.refresh(u)

    c = ClothingItem(user_id=u.id, category="上衣", color="蓝色",
                     photo_url="/img/a.jpg", photo_clean_url="/img/a-clean.png")
    db.add(c); db.commit(); db.refresh(c)

    assert c.id is not None
    assert c.photo_url == "/img/a.jpg"
    assert c.photo_clean_url == "/img/a-clean.png"
    assert c.remark is None
    assert isinstance(c.created_at, datetime)

    got = db.query(ClothingItem).filter_by(user_id=u.id).first()
    assert got.color == "蓝色"
