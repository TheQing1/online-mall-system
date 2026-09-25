"""向量存储层：本地 BGE Embedding + ChromaDB 原生客户端。

项目早期使用 langchain-chroma 0.2.2，但它要求 chromadb<0.7，
与 1.x 预编译 wheel 冲突；这里改为直接调用 Chroma 原生 API，
既能使用新版本，也不影响上层 RAG 代码。
"""

import os
import traceback
from typing import List, Optional

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

CHROMA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "chroma_db"
)
CHROMA_COLLECTION = "mall_knowledge"
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"

_embeddings = None


def get_embeddings():
    """获取本地 Embedding 模型（通过 ModelScope 下载，国内可用）。"""
    global _embeddings
    if _embeddings is None:
        cache_root = os.path.join(os.path.dirname(CHROMA_DIR), "models")
        local_model = os.path.join(
            cache_root,
            "models",
            "BAAI--bge-small-zh-v1.5",
            "snapshots",
            "master",
        )
        if os.path.exists(os.path.join(local_model, "config.json")):
            model_dir = local_model
            print(f"[Embedding] 使用本地缓存模型: {model_dir}")
        else:
            from modelscope import snapshot_download

            print(f"[Embedding] 从 ModelScope 下载模型: {EMBEDDING_MODEL} ...")
            model_dir = snapshot_download(
                EMBEDDING_MODEL,
                revision="master",
                cache_dir=cache_root,
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


def get_vectorstore():
    """获取（必要时创建）Chroma 集合；向量由上层显式传入。"""
    os.makedirs(CHROMA_DIR, exist_ok=True)
    client = chromadb.PersistentClient(path=CHROMA_DIR, settings=_settings())
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
    """重建向量索引（先清空目录再写入），兼容 seed/初始化场景。"""
    import shutil

    if os.path.exists(CHROMA_DIR):
        shutil.rmtree(CHROMA_DIR)
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
