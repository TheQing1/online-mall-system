from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.schemas.user import UserUpdate, AddressCreate, AddressOut
from app.schemas.common import MessageResponse
from app.services import user_service

router = APIRouter()

@router.put("/profile", response_model=MessageResponse)
def update_profile(data: UserUpdate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    user_service.update_profile(db, current_user, data.model_dump(exclude_none=True))
    return {"message": "更新成功"}

# --- Address endpoints ---

@router.get("/addresses", response_model=list[AddressOut])
def list_addresses(db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return user_service.get_addresses(db, current_user)

@router.post("/addresses", response_model=AddressOut)
def create_address(data: AddressCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    return user_service.create_address(db, current_user, data.model_dump())

@router.put("/addresses/{address_id}", response_model=AddressOut)
def update_address(address_id: int, data: AddressCreate, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    addr = user_service.update_address(db, address_id, current_user, data.model_dump())
    if not addr:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在")
    return addr

@router.delete("/addresses/{address_id}", response_model=MessageResponse)
def delete_address(address_id: int, db: Session = Depends(get_db), current_user = Depends(get_current_user)):
    ok = user_service.delete_address(db, address_id, current_user)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="地址不存在")
    return {"message": "删除成功"}
