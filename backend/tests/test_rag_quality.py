"""真实向量模型下的召回率回归测试，以及两种检索策略的对比。

与 ``test_ai.py`` 不同，这里**不**使用假向量：它加载真实的
``BAAI/bge-small-zh-v1.5``，对 ``app.ai.eval_dataset`` 里的知识库与评测用例
建索引并计算命中率。因此它验证的是「检索到底有没有效果」，
而不只是「评测接口能不能跑通」。

关键点：这里调用的是**生产同一条代码路径**（``app.ai.retriever.retrieve``），
而不是把检索逻辑再抄一遍。原先是后者，于是「评测通过」并不代表线上那条路径
通过——任何对检索的改动都不会被这套评测覆盖。

没有本地模型缓存（例如 CI，或没跑过 seed）时整个模块会自动 skip：

    python -m app.core.seed   # 或先跑一次应用，自动下载模型
    cd backend && pytest tests/test_rag_quality.py -v -s

设计取舍：评测集刻意包含大量口语化改写（与文档几乎没有字面重叠）与多组近义
干扰文档。只靠关键词重合就能全中的评测集是没有意义的，见 eval_dataset 的注释。
"""

import pytest
from langchain_core.documents import Document

from app.ai.eval_dataset import EVAL_CASES, KNOWLEDGE_DOCS
from app.core.config import settings

pytestmark = pytest.mark.rag_quality

# 与生产一致：generate_stream 取 top-3（见 app/ai/rag.py）
TOP_K = 3

# 向量模式的召回下限（回归门槛）。实测值见打印输出与 README。
MIN_HIT_RATE = 0.85

# 模型缓存位于 backend/data/model_cache（在 Python 包之外）
_MODEL_CACHE = settings.data_path / "model_cache"


def _local_model_dir():
    """返回本地已缓存的模型目录；找不到返回 None。"""
    if not _MODEL_CACHE.exists():
        return None
    for candidate in _MODEL_CACHE.rglob("config.json"):
        if "bge" in str(candidate).lower():
            return candidate.parent
    return None


@pytest.fixture(scope="module")
def _rag_index(tmp_path_factory):
    """用真实 BGE 模型 + 生产切片参数建好向量索引，供本模块所有用例复用。"""
    model_dir = _local_model_dir()
    if model_dir is None:
        pytest.skip(
            "本地没有 BGE 模型缓存，跳过真实检索质量测试（首次运行应用会自动下载）"
        )

    pytest.importorskip("sentence_transformers")
    pytest.importorskip("chromadb")

    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    from app.ai import vectorstore

    embeddings = HuggingFaceEmbeddings(
        model_name=str(model_dir),
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )

    # 复用生产同款切片参数
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50,
        separators=["\n\n", "\n", "。", "，", " ", ""],
    )
    documents = [
        Document(page_content=content, metadata={"id": index + 1, "title": title})
        for index, (title, _category, content) in enumerate(KNOWLEDGE_DOCS)
    ]
    chunks = splitter.split_documents(documents)

    # 整个模块期间都指向临时目录与真实模型；退出时自动还原
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            vectorstore, "CHROMA_DIR", str(tmp_path_factory.mktemp("chroma"))
        )
        patch.setattr(vectorstore, "get_embeddings", lambda: embeddings)
        vectorstore._ef.model = None
        vectorstore.rebuild_index(chunks)
        yield embeddings


def _evaluate(mode: str):
    """跑完整评测集，返回 (recall@1, recall@k, 每条用例的命中排名, 未命中明细)。"""
    from app.ai.retriever import retrieve

    top1 = hits = 0
    ranks = []
    misses = []
    for question, expected_title in EVAL_CASES:
        retrieved = retrieve(question, k=TOP_K, mode=mode)
        titles = [
            doc.metadata.get("title", "")
            for doc, score in retrieved
            if score >= settings.rag_min_relevance
        ]
        if expected_title in titles:
            hits += 1
            rank = titles.index(expected_title) + 1
            ranks.append(rank)
            top1 += rank == 1
        else:
            ranks.append(None)
            misses.append((question, expected_title, titles))
    return top1, hits, ranks, misses


def _report(mode: str, top1: int, hits: int, misses) -> None:
    total = len(EVAL_CASES)
    print(
        f"\n[{mode}] recall@1 = {top1 / total:.1%}   "
        f"recall@{TOP_K} = {hits}/{total} = {hits / total:.1%}   "
        f"(相关性下限 {settings.rag_min_relevance}, "
        f"文档 {len(KNOWLEDGE_DOCS)} 篇, 用例 {total} 条)"
    )
    for question, expected_title, titles in misses:
        print(f"  未命中: {question!r} 期望={expected_title} 实际召回={titles}")


def test_vector_retrieval_hit_rate(_rag_index):
    """纯向量检索的召回率必须达标。"""
    top1, hits, _ranks, misses = _evaluate("vector")
    _report("vector", top1, hits, misses)

    total = len(EVAL_CASES)
    assert hits / total >= MIN_HIT_RATE, (
        f"召回命中率 {hits / total:.0%}（{hits}/{total}）低于下限 "
        f"{MIN_HIT_RATE:.0%}。未命中：{misses}"
    )


def test_hybrid_retrieval_is_not_worse_than_vector(_rag_index):
    """混合检索（向量 + BM25）的召回率不得低于纯向量。

    这条断言的作用是「不让方案 B 悄悄变差」：融合检索最容易踩的坑就是
    BM25 的词面命中把语义命中的结果挤出 top-3（口语化提问尤其明显）。
    如果哪天调权重、换分词器把它调坏了，这里会直接变红。
    """
    vec_top1, vec_hits, _ranks, _misses = _evaluate("vector")
    hyb_top1, hyb_hits, _hyb_ranks, hyb_misses = _evaluate("hybrid")

    total = len(EVAL_CASES)
    print(
        f"\n[检索策略对比] 文档 {len(KNOWLEDGE_DOCS)} 篇 / 用例 {total} 条 / top-{TOP_K}"
        f"\n  vector : recall@1 = {vec_top1 / total:.1%}   "
        f"recall@{TOP_K} = {vec_hits / total:.1%}"
        f"\n  hybrid : recall@1 = {hyb_top1 / total:.1%}   "
        f"recall@{TOP_K} = {hyb_hits / total:.1%}"
        f"\n  权重   : vector={settings.rag_vector_weight} bm25={settings.rag_bm25_weight}"
    )
    for question, expected_title, titles in hyb_misses:
        print(f"  hybrid 未命中: {question!r} 期望={expected_title} 实际召回={titles}")

    assert hyb_hits >= vec_hits, (
        f"混合检索把召回率拉低了：vector {vec_hits}/{total} → hybrid {hyb_hits}/{total}"
    )


def test_knowledge_base_covers_every_eval_case(_rag_index):
    """每个评测用例期望的文档都必须真的在知识库里，否则评测本身是错的。"""
    from app.ai.vectorstore import get_vectorstore

    indexed_titles = {
        meta.get("title")
        for meta in get_vectorstore().get(include=["metadatas"])["metadatas"]
        if meta
    }
    expected_titles = {title for _question, title in EVAL_CASES}

    assert expected_titles <= indexed_titles, (
        f"评测用例引用了不存在的文档：{expected_titles - indexed_titles}"
    )
