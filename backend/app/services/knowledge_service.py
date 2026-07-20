from typing import Optional
from sqlalchemy.orm import Session
from app.models.knowledge import KnowledgeDoc

def get_all_docs(db: Session):
    return db.query(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc()).all()

def get_doc(db: Session, doc_id: int) -> Optional[KnowledgeDoc]:
    return db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()

def create_doc(db: Session, data: dict) -> KnowledgeDoc:
    doc = KnowledgeDoc(**data)
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc

def update_doc(db: Session, doc_id: int, data: dict) -> Optional[KnowledgeDoc]:
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    if not doc:
        return None
    for key, value in data.items():
        if value is not None:
            setattr(doc, key, value)
    db.commit()
    db.refresh(doc)
    return doc

def delete_doc(db: Session, doc_id: int) -> bool:
    doc = db.query(KnowledgeDoc).filter(KnowledgeDoc.id == doc_id).first()
    if not doc:
        return False
    db.delete(doc)
    db.commit()
    return True
