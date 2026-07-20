from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.user import User, Address
from app.core.security import hash_password, verify_password, create_access_token

def register_user(db: Session, username: str, password: str, email: Optional[str], phone: Optional[str]) -> User:
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
    user = User(
        username=username,
        password_hash=hash_password(password),
        email=email,
        phone=phone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def authenticate_user(db: Session, username: str, password: str) -> Optional[User]:
    user = db.query(User).filter(User.username == username).first()
    if not user or not verify_password(password, user.password_hash):
        return None
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="账号已被禁用")
    return user

def login_user(db: Session, username: str, password: str) -> dict:
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = create_access_token(data={"sub": str(user.id)})
    user_out = {
        "id": user.id, "username": user.username,
        "email": user.email, "phone": user.phone,
        "avatar": user.avatar,
        "role": user.role.value if hasattr(user.role, 'value') else user.role,
    }
    return {"access_token": token, "token_type": "bearer", "user": user_out}

def update_profile(db: Session, user: User, data: dict) -> User:
    for key, value in data.items():
        if value is not None:
            setattr(user, key, value)
    db.commit()
    db.refresh(user)
    return user

# --- Address CRUD ---

def get_addresses(db: Session, user: User):
    return db.query(Address).filter(Address.user_id == user.id).order_by(Address.is_default.desc()).all()

def create_address(db: Session, user: User, data: dict) -> Address:
    if data.get("is_default"):
        db.query(Address).filter(Address.user_id == user.id, Address.is_default == True).update({"is_default": False})
    address = Address(user_id=user.id, **data)
    db.add(address)
    db.commit()
    db.refresh(address)
    return address

def update_address(db: Session, address_id: int, user: User, data: dict) -> Optional[Address]:
    address = db.query(Address).filter(Address.id == address_id, Address.user_id == user.id).first()
    if not address:
        return None
    if data.get("is_default"):
        db.query(Address).filter(Address.user_id == user.id, Address.is_default == True).update({"is_default": False})
    for key, value in data.items():
        if value is not None:
            setattr(address, key, value)
    db.commit()
    db.refresh(address)
    return address

def delete_address(db: Session, address_id: int, user: User) -> bool:
    address = db.query(Address).filter(Address.id == address_id, Address.user_id == user.id).first()
    if not address:
        return False
    db.delete(address)
    db.commit()
    return True
