from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.security import create_access_token
from app.schemas.user import UserRegister, UserLogin, TokenOut, UserOut
from app.services import user_service

router = APIRouter()

@router.post("/register", response_model=TokenOut)
def register(data: UserRegister, db: Session = Depends(get_db)):
    """用户注册"""
    user = user_service.register_user(db, data.username, data.password, data.email, data.phone)
    token = create_access_token(data={"sub": str(user.id)})
    user_out = {
        "id": user.id, "username": user.username,
        "email": user.email, "phone": user.phone,
        "avatar": user.avatar,
        "role": user.role.value if hasattr(user.role, 'value') else user.role,
    }
    return {"access_token": token, "token_type": "bearer", "user": user_out}

@router.post("/login", response_model=TokenOut)
def login(data: UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    return user_service.login_user(db, data.username, data.password)

@router.get("/me", response_model=UserOut)
def get_me(current_user = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user
