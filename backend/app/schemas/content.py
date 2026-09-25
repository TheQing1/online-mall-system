from typing import Optional
from pydantic import BaseModel


class BannerOut(BaseModel):
    id: int
    title: str
    image: str
    link: Optional[str] = None
    sort: int
    is_active: bool

    class Config:
        from_attributes = True


class BannerCreate(BaseModel):
    title: str
    image: str
    link: Optional[str] = None
    sort: int = 0
    is_active: bool = True


class BannerUpdate(BaseModel):
    title: Optional[str] = None
    image: Optional[str] = None
    link: Optional[str] = None
    sort: Optional[int] = None
    is_active: Optional[bool] = None
