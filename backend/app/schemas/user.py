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
