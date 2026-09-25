from typing import Optional

from sqlalchemy.orm import Session

from app.models.content import Banner


def get_active_banners(db: Session):
    return (
        db.query(Banner)
        .filter(Banner.is_active == True)  # noqa: E712
        .order_by(Banner.sort.asc(), Banner.id.asc())
        .all()
    )


def admin_list_banners(db: Session):
    return db.query(Banner).order_by(Banner.sort.asc(), Banner.id.desc()).all()


def admin_create_banner(db: Session, data: dict) -> Banner:
    banner = Banner(**data)
    db.add(banner)
    db.commit()
    db.refresh(banner)
    return banner


def admin_update_banner(
    db: Session, banner_id: int, data: dict
) -> Optional[Banner]:
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(banner, key, value)
    db.commit()
    db.refresh(banner)
    return banner


def admin_delete_banner(db: Session, banner_id: int) -> bool:
    banner = db.query(Banner).filter(Banner.id == banner_id).first()
    if not banner:
        return False
    db.delete(banner)
    db.commit()
    return True
