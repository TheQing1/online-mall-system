"""向量存储层：本地 BGE Embedding + ChromaDB 原生客户端。

项目早期使用 langchain-chroma 0.2.2，但它要求 chromadb<0.7，
与 1.x 预编译 wheel 冲突；这里改为直接调用 Chroma 原生 API，
既能使用新版本，也不影响上层 RAG 代码。

向量库与模型缓存都放在 ``settings.data_dir``（默认 ``backend/data``）下，
而不是 Python 包内部——见 config.data_dir 的说明。
"""

import os
import traceback
from typing import List

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from app.core.config import settings

# 测试会 monkeypatch 这个模块级变量，因此保持为字符串路径
CHROMA_DIR = str(settings.data_path / "chroma_db")
MODEL_CACHE_DIR = str(settings.data_path / "model_cache")
CHROMA_COLLECTION = "mall_knowledge"
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

# ModelScope 的缓存布局会在 cache_dir 下再套一层 models/
_MODEL_SNAPSHOT = os.path.join(
    MODEL_CACHE_DIR, "models", "BAAI--bge-small-zh-v1.5", "snapshots", "master"
)

_embeddings = None
# 按路径缓存 Chroma 客户端。原先每次检索都新建 PersistentClient，
# 既浪费又容易在并发下争抢文件锁。
_clients: dict = {}

# 写入代数：每次向量库发生变化都 +1。BM25 索引（retriever 里的内存索引）
# 靠它判断是否需要重建，避免「知识库更新了但词频索引还是旧的」。
_index_generation = 0


def index_generation() -> int:
    return _index_generation


def _bump_index_generation() -> None:
    global _index_generation
    _index_generation += 1


def get_embeddings():
    """获取本地 Embedding 模型（通过 ModelScope 下载，国内可用）。"""
    global _embeddings
    if _embeddings is None:
        if os.path.exists(os.path.join(_MODEL_SNAPSHOT, "config.json")):
            model_dir = _MODEL_SNAPSHOT
            print(f"[Embedding] 使用本地缓存模型: {model_dir}")
        else:
            from modelscope import snapshot_download

            print(f"[Embedding] 从 ModelScope 下载模型: {EMBEDDING_MODEL} ...")
            model_dir = snapshot_download(
                EMBEDDING_MODEL,
                revision="master",
                cache_dir=MODEL_CACHE_DIR,
            )
        print(f"[Embedding] 模型路径: {model_dir}")
        _embeddings = HuggingFaceEmbeddings(
            model_name=model_dir,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        print("[Embedding] 模型加载完成")
    return _embeddings


class _EmbeddingFunction:
    """适配 Chroma embedding_function 接口。"""

    def __init__(self):
        self.model = None

    def __call__(self, input: List[str]):
        if self.model is None:
            self.model = get_embeddings()
        return self.model.embed_documents(list(input))

    def name(self):
        return "custom_bge"


_ef = _EmbeddingFunction()


def _settings():
    return ChromaSettings(anonymized_telemetry=False)


def _get_client():
    """按路径复用 PersistentClient。"""
    path = os.path.abspath(CHROMA_DIR)
    client = _clients.get(path)
    if client is None:
        os.makedirs(path, exist_ok=True)
        client = chromadb.PersistentClient(path=path, settings=_settings())
        _clients[path] = client
    return client


def get_vectorstore():
    """获取（必要时创建）Chroma 集合；向量由上层显式传入。"""
    client = _get_client()
    try:
        return client.get_collection(name=CHROMA_COLLECTION)
    except Exception:
        return client.create_collection(
            name=CHROMA_COLLECTION,
            metadata={"hnsw:space": "cosine"},
        )


def _embed(texts: List[str]):
    """query 与文档共用同一向量函数。

    曾按 BGE v1 的用法给 query 加上「为这个句子生成表示以用于检索相关文章：」
    指令前缀，并在自建评测集上做过 A/B：命中率不变，但平均余弦距离从 0.357
    劣化到 0.401。bge-*-v1.5 不再需要该前缀（那是 v1 的要求），因此不加。
    见 tests/test_rag_quality.py。
    """
    return _ef(texts)


def _chunk_ids(doc_id, start: int, count: int) -> List[str]:
    return [f"{doc_id}-{start + i}" for i in range(count)]


def rebuild_index(documents):
    """全量重建向量集合，用于索引损坏后的兜底。

    只删除集合、不删除目录：原来直接 ``shutil.rmtree(CHROMA_DIR)`` 会把
    已缓存客户端的底层文件删掉，正在运行的进程后续查询会失败。
    """
    client = _get_client()
    try:
        client.delete_collection(CHROMA_COLLECTION)
    except Exception as e:
        print(f"[向量索引] 删除集合失败(忽略): {e}")
    _bump_index_generation()

    vectorstore = get_vectorstore()
    if not documents:
        return vectorstore

    for start in range(0, len(documents), 100):
        batch = documents[start : start + 100]
        texts = [d.page_content for d in batch]
        vectorstore.add(
            ids=_chunk_ids("init", start, len(batch)),
            documents=texts,
            embeddings=_embed(texts),
            metadatas=[d.metadata for d in batch],
        )
    return vectorstore


def replace_document_vectors(doc_id, documents):
    """增量重建单个知识文档：删除该文档旧向量后批量写入新切片。"""
    vectorstore = get_vectorstore()
    _bump_index_generation()
    if doc_id is not None:
        try:
            vectorstore.delete(where={"id": int(doc_id)})
        except Exception as e:
            print(f"[向量索引] 删除旧向量失败(忽略): {e}")
    if documents:
        texts = [d.page_content for d in documents]
        vectorstore.add(
            ids=_chunk_ids(doc_id, 0, len(documents)),
            documents=texts,
            embeddings=_embed(texts),
            metadatas=[d.metadata for d in documents],
        )


def delete_document_vectors(doc_id):
    """删除指定知识文档的全部向量。"""
    if doc_id is None:
        return
    vectorstore = get_vectorstore()
    _bump_index_generation()
    try:
        vectorstore.delete(where={"id": int(doc_id)})
    except Exception as e:
        print(f"[向量索引] 删除向量失败(忽略): {e}")


def search_similar(query: str, k: int = 3):
    """相似度检索，返回 (Document, score) 列表；score 为余弦距离。"""
    vectorstore = get_vectorstore()
    try:
        count = vectorstore.count()
    except Exception:
        count = 0
    if count == 0:
        return []
    try:
        result = vectorstore.query(
            query_embeddings=_embed([query]),
            n_results=min(k, count),
            include=["documents", "metadatas", "distances"],
        )
        docs, metadatas, distances = (
            result["documents"][0],
            result["metadatas"][0],
            result["distances"][0],
        )
        output = []
        for content, meta, distance in zip(docs, metadatas, distances):
            output.append(
                (
                    Document(page_content=content, metadata=meta or {}),
                    float(distance),
                )
            )
        return output
    except Exception:
        traceback.print_exc()
        return []
