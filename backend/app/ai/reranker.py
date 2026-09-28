"""交叉编码器重排（Cross-Encoder Rerank）。

召回与重排解决的是不同问题：

- **召回**（向量 / BM25）是双塔结构——query 与文档各自编码，最后只比一次向量距离。
  速度快，但两者从来没有在模型内部交互过，细粒度的相关性判断能力有限；
- **重排**把 ``(query, 文档)`` 拼成一条序列送进模型，让两者在注意力层里充分交互，
  精度明显更高；代价是每条候选都要跑一次前向，只能用在召回之后的那几条候选上。

所以链路是：**召回 10 条 → 重排 → 取 top-3 进 Prompt**。

模型用 ``BAAI/bge-reranker-base``（约 1.1GB），与 Embedding 一样从 ModelScope 下载。
它默认**不开启**（``RAG_RERANK_ENABLED=true`` 才加载）：要多下 1.1GB 模型、
每条问题多花约 1 秒 CPU 前向，收益见 README 里的对比表。

模型加载失败时只记一条 warning 并**退化为原顺序**，不会让整个 AI 客服挂掉——
重排是增强项，不该成为单点故障。
"""

import logging
import math
import threading
from typing import List, Tuple

from langchain_core.documents import Document

from app.core.config import settings

logger = logging.getLogger(__name__)

RERANK_MODEL = "BAAI/bge-reranker-base"
MODEL_CACHE_DIR = str(settings.data_path / "model_cache")

# ModelScope 的缓存布局会在 cache_dir 下再套一层 models/
_MODEL_SNAPSHOT = (
    settings.data_path
    / "model_cache"
    / "models"
    / "BAAI--bge-reranker-base"
    / "snapshots"
    / "master"
)

_reranker = None
_reranker_lock = threading.Lock()
_load_failed = False


def _resolve_model_dir() -> str:
    if (_MODEL_SNAPSHOT / "config.json").exists():
        return str(_MODEL_SNAPSHOT)
    from modelscope import snapshot_download

    logger.info("首次使用重排，正在从 ModelScope 下载 %s ...", RERANK_MODEL)
    return snapshot_download(
        RERANK_MODEL, revision="master", cache_dir=MODEL_CACHE_DIR
    )


def get_reranker():
    """懒加载 CrossEncoder；测试可以直接给 ``_reranker`` 塞一个桩对象。"""
    global _reranker, _load_failed
    if _reranker is not None:
        return _reranker
    with _reranker_lock:
        if _reranker is None:
            from sentence_transformers import CrossEncoder

            _reranker = CrossEncoder(
                _resolve_model_dir(), max_length=512, device="cpu"
            )
            _load_failed = False
    return _reranker


def rerank(
    query: str, candidates: List[Tuple[Document, float]], top_k: int
) -> List[Tuple[Document, float]]:
    """对候选片段重排，返回 ``[(文档, 0~1 相关性), ...]``。

    分数取 sigmoid(logit)：CrossEncoder 输出的是无界 logit，把它压到 0~1 之后，
    就能和召回路共用同一个 ``RAG_MIN_RELEVANCE`` 阈值（0.5 相当于打平）。
    """
    global _load_failed
    if not candidates:
        return []

    try:
        model = get_reranker()
    except Exception as exc:  # pragma: no cover - 依赖网络/模型文件
        if not _load_failed:
            _load_failed = True
            logger.warning("重排模型加载失败，本次退化为召回顺序：%s", exc)
        return candidates[:top_k]

    pairs = [(query, document.page_content) for document, _score in candidates]
    logits = model.predict(pairs)
    scored = [
        (document, 1.0 / (1.0 + math.exp(-float(logit))))
        for (document, _score), logit in zip(candidates, logits)
    ]
    scored.sort(key=lambda item: -item[1])
    return scored[:top_k]
