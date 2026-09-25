from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.content import BannerOut
from app.services import content_service

router = APIRouter()


@router.get("", response_model=list[BannerOut])
def list_banners(db: Session = Depends(get_db)):
    """商城首页轮播（仅启用）。"""
    return content_service.get_active_banners(db)
