import os
import traceback
from chromadb.config import Settings as ChromaSettings
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# ChromaDB 持久化目录（放在 backend 下）
CHROMA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_db")

# 本地中文 Embedding 模型（首次运行自动下载，约 100MB）
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

_embeddings = None


def get_embeddings():
    """获取本地 Embedding 模型（免费、离线、中文优化）"""
    global _embeddings
    if _embeddings is None:
        print(f"[Embedding] 加载本地模型: {EMBEDDING_MODEL} ...")
        _embeddings = HuggingFaceEmbeddings(
            model_name=EMBEDDING_MODEL,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        print("[Embedding] 模型加载完成")
    return _embeddings


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
        for i in range(0, len(documents), 100):
            batch = documents[i:i+100]
            vectorstore.add_documents(batch)
    return vectorstore


def search_similar(query: str, k: int = 3):
    """相似度检索，返回 (Document, score) 列表"""
    vectorstore = get_vectorstore()
    try:
        count = vectorstore._collection.count()
        print(f"[向量检索] 索引中文档数: {count}")
    except Exception:
        print("[向量检索] 无法获取索引文档数")
    try:
        results = vectorstore.similarity_search_with_score(query, k=k)
        print(f"[向量检索] 查询 '{query[:30]}...' 返回 {len(results)} 条结果")
        for doc, score in results:
            print(f"  - score={score:.4f} title={doc.metadata.get('title', '?')}")
        return results
    except Exception as e:
        traceback.print_exc()
        print(f"[向量检索] 失败: {e}")
        return []
