import os
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from app.core.config import settings

# ChromaDB 持久化目录（放在 backend 下）
CHROMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_db")


def get_embeddings():
    """获取 Embedding 模型"""
    if settings.deepseek_api_key and settings.deepseek_api_key != "your-deepseek-api-key":
        return OpenAIEmbeddings(
            model="text-embedding-3-small",
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
        )
    # Fallback: use a local/smaller embedding approach
    raise ValueError(
        "请在 .env 中配置 DEEPSEEK_API_KEY。"
        "获取 Key: https://platform.deepseek.com/api_keys"
    )


def get_vectorstore():
    """获取或创建 ChromaDB 向量存储"""
    embeddings = get_embeddings()
    os.makedirs(CHROMA_DIR, exist_ok=True)
    return Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        client_settings=ChromaSettings(anonymized_telemetry=False),
    )


def rebuild_index(documents):
    """用 LangChain Documents 重建向量索引（先清空再添加）"""
    import shutil
    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)

    embeddings = get_embeddings()
    vectorstore = Chroma(
        persist_directory=CHROMA_DIR,
        embedding_function=embeddings,
        client_settings=ChromaSettings(anonymized_telemetry=False),
    )
    if documents:
        # 批量添加，每批最多 100 个
        for i in range(0, len(documents), 100):
            batch = documents[i:i+100]
            vectorstore.add_documents(batch)
    return vectorstore


def search_similar(query: str, k: int = 3):
    """相似度检索，返回 (Document, score) 列表"""
    vectorstore = get_vectorstore()
    # 先检查是否有数据
    try:
        results = vectorstore.similarity_search_with_score(query, k=k)
        return results
    except Exception:
        return []
