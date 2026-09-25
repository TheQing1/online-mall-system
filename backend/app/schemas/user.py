from typing import Optional
from pydantic import BaseModel

class UserRegister(BaseModel):
    username: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None

class UserLogin(BaseModel):
    username: str
    password: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserOut"

class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None
    role: str
    # 后台用户管理页需要展示/切换启用状态，之前漏了这个字段，
    # 导致前端读到的永远是 undefined、开关状态失真
    is_active: bool = True

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    email: Optional[str] = None
    phone: Optional[str] = None
    avatar: Optional[str] = None

class AddressCreate(BaseModel):
    receiver: str
    phone: str
    province: str
    city: str
    district: str
    detail: str
    is_default: bool = False

class AddressOut(BaseModel):
    id: int
    receiver: str
    phone: str
    province: str
    city: str
    district: str
    detail: str
    is_default: bool

    class Config:
        from_attributes = True
