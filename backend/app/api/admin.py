import os
import uuid
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_admin
from app.schemas.common import PageResponse, MessageResponse
from app.schemas.product import ProductOut, ProductCreate, ProductUpdate, CategoryOut, CategoryCreate, CategoryUpdate
from app.schemas.order import OrderOut
from app.schemas.user import UserOut
from app.services import product_service, order_service, user_service, knowledge_service
from app.schemas.knowledge import KnowledgeDocCreate, KnowledgeDocUpdate, KnowledgeDocOut
from app.ai.loader import split_documents
from app.ai.vectorstore import rebuild_index
from app.models.knowledge import KnowledgeDoc

router = APIRouter()

# --- Dashboard ---

@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    return order_service.admin_get_dashboard_stats(db)

# --- Products ---

@router.get("/products", response_model=PageResponse[ProductOut])
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin),
):
    return product_service.admin_get_products(db, page, page_size)

@router.post("/products", response_model=ProductOut)
def create_product(data: ProductCreate, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    return product_service.admin_create_product(db, data.model_dump())

@router.put("/products/{product_id}", response_model=ProductOut)
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    product = product_service.admin_update_product(db, product_id, data.model_dump(exclude_none=True))
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return product

@router.delete("/products/{product_id}", response_model=MessageResponse)
def delete_product(product_id: int, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    ok = product_service.admin_delete_product(db, product_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return {"message": "删除成功"}

# --- Categories ---

@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    return product_service.admin_get_all_categories(db)

@router.post("/categories", response_model=CategoryOut)
def create_category(data: CategoryCreate, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    return product_service.admin_create_category(db, data.model_dump())

@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: int, data: CategoryUpdate, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    cat = product_service.admin_update_category(db, category_id, data.model_dump(exclude_none=True))
    if not cat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    return cat

@router.delete("/categories/{category_id}", response_model=MessageResponse)
def delete_category(category_id: int, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    ok = product_service.admin_delete_category(db, category_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    return {"message": "删除成功"}

# --- Orders ---

@router.get("/orders", response_model=PageResponse[OrderOut])
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin),
):
    return order_service.admin_get_orders(db, page, page_size, status)

@router.put("/orders/{order_id}/status", response_model=OrderOut)
def update_order_status(order_id: int, status: str = Query(...), db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    order = order_service.admin_update_order_status(db, order_id, status)
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="订单不存在")
    return order

# --- Users ---

@router.get("/users", response_model=PageResponse[UserOut])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin = Depends(get_current_admin),
):
    from app.models.user import User
    query = db.query(User).order_by(User.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@router.put("/users/{user_id}/toggle-active", response_model=MessageResponse)
def toggle_user_active(user_id: int, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    from app.models.user import User
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.is_active = not user.is_active
    db.commit()
    return {"message": f"用户已{'启用' if user.is_active else '禁用'}"}

# --- Knowledge Base ---

@router.get("/knowledge", response_model=list[KnowledgeDocOut])
def list_knowledge(db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    return knowledge_service.get_all_docs(db)

@router.post("/knowledge", response_model=KnowledgeDocOut)
def create_knowledge(data: KnowledgeDocCreate, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    doc = knowledge_service.create_doc(db, data.model_dump())
    _sync_knowledge_index(db)
    return doc

@router.put("/knowledge/{doc_id}", response_model=KnowledgeDocOut)
def update_knowledge(doc_id: int, data: KnowledgeDocUpdate, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    doc = knowledge_service.update_doc(db, doc_id, data.model_dump(exclude_none=True))
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    _sync_knowledge_index(db)
    return doc

@router.delete("/knowledge/{doc_id}", response_model=MessageResponse)
def delete_knowledge(doc_id: int, db: Session = Depends(get_db), admin = Depends(get_current_admin)):
    ok = knowledge_service.delete_doc(db, doc_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
    _sync_knowledge_index(db)
    return {"message": "删除成功"}

# --- File Upload ---

@router.post("/upload")
async def upload_image(file: UploadFile = File(...), admin = Depends(get_current_admin)):
    """上传商品图片"""
    # 校验文件类型
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="仅支持 jpg/png/gif/webp 格式")

    # 校验大小
    contents = await file.read()
    if len(contents) > settings.max_upload_size:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图片大小不能超过 2MB")

    # 保存文件
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_path = os.path.join(settings.upload_dir, filename)
    os.makedirs(settings.upload_dir, exist_ok=True)
    with open(upload_path, "wb") as f:
        f.write(contents)

    url = f"/static/products/{filename}"
    return {"url": url}


def _sync_knowledge_index(db: Session):
    """同步知识库到向量索引"""
    try:
        docs = db.query(KnowledgeDoc).all()
        if docs:
            langchain_docs = split_documents(docs)
            rebuild_index(langchain_docs)
    except Exception:
        pass  # 索引同步失败不阻塞 CRUD 操作
