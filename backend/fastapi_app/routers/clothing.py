from fastapi import APIRouter, Depends
from fastapi_app.deps import get_current_user, get_db
from fastapi_app.models import ClothingItem
from fastapi_app.schemas import ClothingCreate, ClothingOut

router = APIRouter(prefix="/api/clothing", tags=["clothing"])


@router.get("")
def list_clothing(user=Depends(get_current_user), db=Depends(get_db)):
    items = db.query(ClothingItem).filter_by(user_id=user.id).order_by(ClothingItem.created_at.desc()).all()
    return [ClothingOut.model_validate(i) for i in items]


@router.post("")
def create_clothing(body: ClothingCreate, user=Depends(get_current_user), db=Depends(get_db)):
    item = ClothingItem(user_id=user.id, category=body.category, color=body.color, remark=body.remark)
    db.add(item); db.commit(); db.refresh(item)
    return ClothingOut.model_validate(item)
