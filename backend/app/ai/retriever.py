"""检索层：向量召回、BM25 召回，以及两者的融合。

对上层只暴露 ``retrieve()``，返回 ``[(Document, score), ...]``，score 是
**0~1 的相关性得分（越大越相关）**——刻意与 Chroma 返回的「余弦距离」相反，
这样 ``rag.py`` 与离线评测都不必关心底下用的是哪种召回策略。

为什么单独抽一层：原先把「向量检索 + 阈值过滤」直接写在 ``vectorstore`` 里，
离线评测只好把同样的逻辑再抄一遍，于是「评测通过」并不等于「线上那条代码路径
通过」。抽出来之后，评测和线上生成调用的是同一个函数。

关于 BM25：中文必须分词，这里用 jieba 按词典切词（比字符 bigram 更接近真实
词边界）。BM25 索引是纯内存结构，按向量库的写入代数缓存，知识库变动后自动重建。
语料规模在万级片段以内时这个做法足够；再大就应该换成独立的倒排索引服务。

为什么用 ``BM25Plus`` 而不是更常见的 ``BM25Okapi``：Okapi 的 IDF 是
``log((N - df + 0.5) / (df + 0.5))``，当某个词出现在超过一半的文档里时它是
**负数**，于是「命中了这个词」的文档得分反而低于完全没命中的文档（后者是 0）——
在只有一两条片段的小语料上尤其致命。项目的知识库刚好充满这类高频词
（「商品」「订单」「配送」），所以改用 IDF 恒非负的 ``BM25Plus``。
这是被 tests/test_ai.py 的一条用例抓出来的。
"""

import re
import threading
from typing import List, Optional, Tuple

import jieba
from langchain_core.documents import Document
from rank_bm25 import BM25Plus

from app.ai.vectorstore import get_vectorstore, index_generation, search_similar
from app.core.config import settings

# 纯标点/空白的分词结果不参与 BM25 统计
_NOISE = re.compile(r"^[\W_]+$", re.UNICODE)


def _tokenize(text: str) -> List[str]:
    return [token for token in jieba.lcut(text.lower()) if not _NOISE.match(token)]


_bm25_cache: Optional[tuple] = None
_bm25_lock = threading.Lock()


def _bm25_index():
    """返回 ``(bm25, documents)``；索引为空时 bm25 为 None。"""
    global _bm25_cache
    generation = index_generation()
    cached = _bm25_cache
    if cached and cached[0] == generation:
        return cached[1], cached[2]

    with _bm25_lock:
        # 双检：并发下只让第一个线程真正重建
        if _bm25_cache and _bm25_cache[0] == generation:
            return _bm25_cache[1], _bm25_cache[2]

        payload = get_vectorstore().get(include=["documents", "metadatas"])
        documents = [
            Document(page_content=text, metadata=meta or {})
            for text, meta in zip(
                payload.get("documents") or [], payload.get("metadatas") or []
            )
        ]
        if not documents:
            _bm25_cache = (generation, None, [])
            return None, []

        bm25 = BM25Plus([_tokenize(doc.page_content) for doc in documents])
        _bm25_cache = (generation, bm25, documents)
        return bm25, documents


def bm25_search(query: str, limit: int = 10) -> List[Tuple[Document, float]]:
    """BM25 词频召回，返回按分数降序的 (文档, 分数)。"""
    bm25, documents = _bm25_index()
    if bm25 is None:
        return []

    tokens = _tokenize(query)
    if not tokens:
        return []

    scores = bm25.get_scores(tokens)
    ranked = sorted(range(len(documents)), key=lambda i: -scores[i])[:limit]
    return [(documents[i], float(scores[i])) for i in ranked if scores[i] > 0]


def _min_max(pairs: List[Tuple[Document, float]]) -> List[Tuple[Document, float]]:
    """把一路召回的分数线性映射到 0~1，让两路分数可以加权相加。

    只有单条候选（或全部同分）时统一给 1.0，否则除以极差后最高分恒为 1.0
    —— 这正是「必须归一化」的原因：BM25 的分数是无上界的词频量，
    直接和 0~1 的余弦相似度相加会被它彻底主导。
    """
    if not pairs:
        return []
    values = [score for _doc, score in pairs]
    low, high = min(values), max(values)
    if high - low < 1e-9:
        return [(doc, 1.0) for doc, _score in pairs]
    return [(doc, (score - low) / (high - low)) for doc, score in pairs]


def retrieve(
    query: str, k: int = 3, mode: Optional[str] = None
) -> List[Tuple[Document, float]]:
    """按配置的策略召回 top-k，返回 (文档, 相关性得分)。

    得分语义在两种模式下不同，这是有意的取舍：

    - ``vector``：得分就是余弦相似度（``1 - 距离``），是**绝对**质量指标，
      阈值过滤因此比较严格；
    - ``hybrid``：得分是两路归一化分数的加权和，只在本次候选集合内可比，
      0.3 大致等于「至少有一路把它排进了前半段」。绝对质量由向量那一路
      （以及重排阶段，如果开启）来保证。
    """
    mode = (mode or settings.rag_retrieval_mode).lower()

    if mode != "hybrid":
        return [
            (doc, 1.0 - distance) for doc, distance in search_similar(query, k=k)
        ]

    # 两路各多取一些候选再融合：只各取 3 条的话，某一路独有的正确答案
    # 根本没机会进入融合列表。
    candidates = max(k * 4, 10)
    vector_hits = [
        (doc, 1.0 - distance)
        for doc, distance in search_similar(query, k=candidates)
    ]
    bm25_hits = bm25_search(query, limit=candidates)

    # 以片段正文作为同一片段的标识：两条召回路径拿到的是同一批 Chroma 文档，
    # 但 search_similar 只回传 metadata（同一文档的多个片段 id 相同），
    # 正文才是唯一能对上号的东西。
    fused: dict = {}
    for doc, score in _min_max(vector_hits):
        fused[doc.page_content] = [doc, settings.rag_vector_weight * score]
    for doc, score in _min_max(bm25_hits):
        entry = fused.get(doc.page_content)
        if entry is None:
            fused[doc.page_content] = [doc, settings.rag_bm25_weight * score]
        else:
            entry[1] += settings.rag_bm25_weight * score

    ranked = sorted(fused.values(), key=lambda item: -item[1])
    return [(doc, score) for doc, score in ranked[:k]]
