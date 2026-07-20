from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.schema import Document
from typing import List
from app.models.knowledge import KnowledgeDoc


def split_documents(knowledge_docs: List[KnowledgeDoc]) -> List[Document]:
    """将数据库中的知识库文档切分为检索片段"""
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "，", " ", ""],
    )
    langchain_docs = []
    for doc in knowledge_docs:
        langchain_docs.append(Document(
            page_content=doc.content,
            metadata={
                "id": doc.id,
                "title": doc.title,
                "category": doc.category.value if hasattr(doc.category, 'value') else str(doc.category),
            }
        ))
    return text_splitter.split_documents(langchain_docs)
