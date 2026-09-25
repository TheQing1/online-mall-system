import os
import uuid
from typing import List, Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
)
from sqlalchemy.orm import Session

from app.ai import indexer
from app.ai.vectorstore import search_similar
from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_admin
from app.models.knowledge import KnowledgeDoc, KnowledgeCategory
from app.models.chat import EvalTestCase
from app.schemas.common import PageResponse, MessageResponse
from app.schemas.content import BannerCreate, BannerOut, BannerUpdate
from app.schemas.eval import EvalCaseCreate, EvalCaseOut
from app.schemas.knowledge import (
    KnowledgeDocCreate,
    KnowledgeDocOut,
    KnowledgeDocUpdate,
)
from app.schemas.order import OrderOut, RefundReview
from app.schemas.product import (
    CategoryCreate,
    CategoryOut,
    CategoryUpdate,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from app.schemas.user import UserOut
from app.services import (
    content_service,
    knowledge_service,
    order_service,
    product_service,
)

router = APIRouter()


# --- Dashboard ---


@router.get("/dashboard")
def dashboard(
    db: Session = Depends(get_db), admin=Depends(get_current_admin)
):
    return order_service.admin_get_dashboard_stats(db)


# --- Products ---


@router.get("/products", response_model=PageResponse[ProductOut])
def list_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return product_service.admin_get_products(db, page, page_size)


@router.post("/products", response_model=ProductOut)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return product_service.admin_create_product(db, data.model_dump())


@router.put("/products/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    product = product_service.admin_update_product(
        db, product_id, data.model_dump(exclude_none=True)
    )
    if not product:
        raise HTTPException(status_code=404, detail="商品不存在")
    return product


@router.delete("/products/{product_id}", response_model=MessageResponse)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    ok = product_service.admin_delete_product(db, product_id)
    if not ok:
        raise HTTPException(status_code=404, detail="商品不存在")
    return {"message": "删除成功"}


# --- Categories ---


@router.get("/categories", response_model=list[CategoryOut])
def list_categories(
    db: Session = Depends(get_db), admin=Depends(get_current_admin)
):
    return product_service.admin_get_all_categories(db)


@router.post("/categories", response_model=CategoryOut)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return product_service.admin_create_category(db, data.model_dump())


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    data: CategoryUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    cat = product_service.admin_update_category(
        db, category_id, data.model_dump(exclude_none=True)
    )
    if not cat:
        raise HTTPException(status_code=404, detail="分类不存在")
    return cat


@router.delete("/categories/{category_id}", response_model=MessageResponse)
def delete_category(
    category_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    ok = product_service.admin_delete_category(db, category_id)
    if not ok:
        raise HTTPException(status_code=404, detail="分类不存在")
    return {"message": "删除成功"}


# --- Orders ---


@router.get("/orders", response_model=PageResponse[OrderOut])
def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    order_no: Optional[str] = None,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return order_service.admin_get_orders(db, page, page_size, status, order_no)


@router.put("/orders/{order_id}/status", response_model=OrderOut)
def update_order_status(
    order_id: int,
    status: str = Query(...),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    order = order_service.admin_update_order_status(db, order_id, status)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


@router.get("/refunds", response_model=PageResponse[OrderOut])
def list_refunds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return order_service.admin_get_refund_orders(db, page, page_size)


@router.post("/orders/{order_id}/refund/review", response_model=OrderOut)
def review_refund(
    order_id: int,
    data: RefundReview,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    order = order_service.admin_review_refund(db, order_id, data.approve, data.note)
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    return order


# --- Users ---


@router.get("/users", response_model=PageResponse[UserOut])
def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    from app.models.user import User

    query = db.query(User).order_by(User.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.put("/users/{user_id}/toggle-active", response_model=MessageResponse)
def toggle_user_active(
    user_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    from app.models.user import User

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_active = not user.is_active
    db.commit()
    return {"message": "已启用" if user.is_active else "已禁用"}


# --- Knowledge Base ---


def _category_enum(value: str) -> KnowledgeCategory:
    try:
        return KnowledgeCategory(value)
    except ValueError:
        return KnowledgeCategory.OTHER


@router.get("/knowledge", response_model=list[KnowledgeDocOut])
def list_knowledge(
    db: Session = Depends(get_db), admin=Depends(get_current_admin)
):
    return knowledge_service.get_all_docs(db)


@router.post("/knowledge", response_model=KnowledgeDocOut)
def create_knowledge(
    data: KnowledgeDocCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    payload = data.model_dump()
    payload["category"] = _category_enum(payload.get("category"))
    doc = knowledge_service.create_doc(db, payload)
    indexer.sync_knowledge_doc(db, doc)
    return doc


@router.put("/knowledge/{doc_id}", response_model=KnowledgeDocOut)
def update_knowledge(
    doc_id: int,
    data: KnowledgeDocUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    payload = data.model_dump(exclude_none=True)
    if "category" in payload:
        payload["category"] = _category_enum(payload["category"])
    doc = knowledge_service.update_doc(db, doc_id, payload)
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    indexer.sync_knowledge_doc(db, doc)
    return doc


@router.delete("/knowledge/{doc_id}", response_model=MessageResponse)
def delete_knowledge(
    doc_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    ok = knowledge_service.delete_doc(db, doc_id)
    if not ok:
        raise HTTPException(status_code=404, detail="文档不存在")
    from app.ai.vectorstore import delete_document_vectors

    delete_document_vectors(doc_id)
    return {"message": "删除成功"}


@router.post("/knowledge/import", response_model=MessageResponse)
async def import_knowledge(
    category: str = Form("other"),
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """批量导入 .md/.txt 知识文档，并增量同步向量索引。"""
    category_enum = _category_enum(category)
    imported = 0
    for file in files:
        ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
        if ext not in ("md", "txt"):
            continue
        raw = await file.read()
        if len(raw) > 2 * 1024 * 1024:
            continue
        try:
            content = raw.decode("utf-8").strip()
        except UnicodeDecodeError:
            content = raw.decode("gbk", errors="ignore").strip()
        if not content:
            continue
        title = os.path.splitext(os.path.basename(file.filename))[0][:100]
        doc = knowledge_service.create_doc(
            db, {"title": title, "content": content, "category": category_enum}
        )
        try:
            indexer.sync_knowledge_doc(db, doc)
        except Exception:
            pass
        imported += 1
    if imported == 0:
        raise HTTPException(status_code=400, detail="没有可导入的 .md/.txt 文件")
    return {"message": f"成功导入 {imported} 个文档"}


# --- RAG 评测 ---


@router.get("/ai/eval-cases", response_model=list[EvalCaseOut])
def list_eval_cases(
    db: Session = Depends(get_db), admin=Depends(get_current_admin)
):
    return (
        db.query(EvalTestCase)
        .order_by(EvalTestCase.created_at.desc())
        .all()
    )


@router.post("/ai/eval-cases", response_model=EvalCaseOut)
def create_eval_case(
    data: EvalCaseCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    case = EvalTestCase(question=data.question, expected_title=data.expected_title)
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@router.delete("/ai/eval-cases/{case_id}", response_model=MessageResponse)
def delete_eval_case(
    case_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    case = db.query(EvalTestCase).filter(EvalTestCase.id == case_id).first()
    if not case:
        raise HTTPException(status_code=404, detail="用例不存在")
    db.delete(case)
    db.commit()
    return {"message": "删除成功"}


@router.post("/ai/eval/run")
def run_eval(
    db: Session = Depends(get_db), admin=Depends(get_current_admin)
):
    """批量跑检索评测：只验证召回，不消耗 LLM Token。"""
    cases = db.query(EvalTestCase).all()
    results = []
    for case in cases:
        retrieved = search_similar(case.question, k=5)
        titles = [
            doc.metadata.get("title", "")
            for doc, score in retrieved
            if score <= settings.rag_score_threshold
        ]
        best_score = min((float(s) for _, s in retrieved), default=None)
        hit = case.expected_title in titles
        results.append(
            {
                "id": case.id,
                "question": case.question,
                "expected_title": case.expected_title,
                "hit": hit,
                "retrieved_titles": titles,
                "best_score": best_score,
            }
        )
    hits = sum(1 for r in results if r["hit"])
    return {
        "total": len(results),
        "hit_rate": round(hits / len(results), 4) if results else 0,
        "results": results,
    }


# --- File Upload ---


@router.post("/upload")
async def upload_image(
    file: UploadFile = File(...), admin=Depends(get_current_admin)
):
    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("jpg", "jpeg", "png", "gif", "webp"):
        raise HTTPException(status_code=400, detail="仅支持 jpg/png/gif/webp 格式")
    contents = await file.read()
    if len(contents) > settings.max_upload_size:
        raise HTTPException(status_code=400, detail="图片大小不能超过 2MB")
    filename = f"{uuid.uuid4().hex}.{ext}"
    upload_path = os.path.join(settings.upload_dir, filename)
    os.makedirs(settings.upload_dir, exist_ok=True)
    with open(upload_path, "wb") as f:
        f.write(contents)
    return {"url": f"/static/products/{filename}"}


# --- Banners ---


@router.get("/banners", response_model=list[BannerOut])
def admin_list_banners(
    db: Session = Depends(get_db), admin=Depends(get_current_admin)
):
    return content_service.admin_list_banners(db)


@router.post("/banners", response_model=BannerOut)
def admin_create_banner(
    data: BannerCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    return content_service.admin_create_banner(db, data.model_dump())


@router.put("/banners/{banner_id}", response_model=BannerOut)
def admin_update_banner(
    banner_id: int,
    data: BannerUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    banner = content_service.admin_update_banner(
        db, banner_id, data.model_dump(exclude_none=True)
    )
    if not banner:
        raise HTTPException(status_code=404, detail="Banner 不存在")
    return banner


@router.delete("/banners/{banner_id}", response_model=MessageResponse)
def admin_delete_banner(
    banner_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_current_admin),
):
    ok = content_service.admin_delete_banner(db, banner_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Banner 不存在")
    return {"message": "删除成功"}
