"""知识文档与向量索引同步。"""

from sqlalchemy.orm import Session

from app.ai.loader import split_documents
from app.ai.vectorstore import replace_document_vectors
from app.models.knowledge import KnowledgeDoc


def sync_knowledge_doc(db: Session, doc: KnowledgeDoc) -> int:
    """按文档增量同步向量索引，返回切片数。"""
    chunks = split_documents([doc])
    replace_document_vectors(doc.id, chunks)
    return len(chunks)


def sync_all_knowledge(db: Session) -> int:
    """全量重建（用于初始化或批量导入后的兜底）。"""
    docs = db.query(KnowledgeDoc).all()
    count = 0
    for doc in docs:
        count += sync_knowledge_doc(db, doc)
    return count
