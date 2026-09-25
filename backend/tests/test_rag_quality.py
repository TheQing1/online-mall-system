"""真实向量模型下的召回率回归测试。

与 ``test_ai.py`` 不同，这里**不**使用假向量：它加载真实的
``BAAI/bge-small-zh-v1.5``，对 ``app.ai.eval_dataset`` 里的知识库与评测用例
建索引并计算命中率。因此它验证的是「检索到底有没有效果」，
而不只是「评测接口能不能跑通」。

没有本地模型缓存（例如 CI）时整个模块会自动 skip，不会让构建失败：

    python -m app.core.seed   # 或先跑一次应用，自动下载模型
    cd backend && pytest tests/test_rag_quality.py -v -s

设计取舍：评测集刻意包含大量口语化改写（与文档几乎没有字面重叠）。
只靠关键词重合就能全中的评测集是没有意义的，见 eval_dataset 的注释。
"""

from pathlib import Path

import pytest

from app.ai.eval_dataset import EVAL_CASES, KNOWLEDGE_DOCS

pytestmark = pytest.mark.rag_quality

# 与生产一致：Chroma 用余弦距离，RAG 链路只保留 distance <= 0.7 的片段，
# 且 generate_stream 取 top-3（见 app/ai/rag.py）。
RAG_SCORE_THRESHOLD = 0.7
TOP_K = 3

# 期望的召回下限。实测：recall@1 = 90%，recall@3 = 95%，recall@10 = 100%。
MIN_HIT_RATE = 0.85

_CACHE_ROOT = Path(__file__).resolve().parents[1] / "app" / "models"


def _local_model_dir():
    """返回本地已缓存的模型目录；找不到返回 None。"""
    for candidate in _CACHE_ROOT.rglob("config.json"):
        if "bge" in str(candidate).lower():
            return candidate.parent
    return None


@pytest.fixture(scope="module")
def retrieval_index(tmp_path_factory):
    model_dir = _local_model_dir()
    if model_dir is None:
        pytest.skip(
            "本地没有 BGE 模型缓存，跳过真实检索质量测试（首次运行应用会自动下载）"
        )

    pytest.importorskip("sentence_transformers")
    pytest.importorskip("chromadb")

    import chromadb
    from langchain_huggingface import HuggingFaceEmbeddings
    from langchain_text_splitters import RecursiveCharacterTextSplitter

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

    texts, metadatas = [], []
    for title, _category, content in KNOWLEDGE_DOCS:
        for piece in splitter.split_text(content):
            texts.append(piece)
            metadatas.append({"title": title})

    client = chromadb.PersistentClient(path=str(tmp_path_factory.mktemp("chroma")))
    collection = client.create_collection(
        "rag_quality", metadata={"hnsw:space": "cosine"}
    )
    collection.add(
        ids=[f"chunk-{i}" for i in range(len(texts))],
        documents=texts,
        embeddings=embeddings.embed_documents(texts),
        metadatas=metadatas,
    )
    return embeddings, collection


def test_retrieval_hit_rate(retrieval_index):
    """20 条评测用例的召回命中率必须达标。

    评测集刻意混入口语化改写：实测 recall@1 = 90%、recall@3 = 95%，
    说明大部分问题首条即命中，但仍有语义鸿沟（例如「没有手机信号的地方
    还能打电话吗」指向卫星通话，命中文档排在第 6 位）。
    """
    embeddings, collection = retrieval_index

    hits, ranks, misses = 0, [], []
    for question, expected_title in EVAL_CASES:
        result = collection.query(
            query_embeddings=embeddings.embed_documents([question]),
            n_results=TOP_K,
            include=["metadatas", "distances"],
        )
        pairs = list(zip(result["metadatas"][0], result["distances"][0]))
        retrieved = [
            meta["title"] for meta, distance in pairs if distance <= RAG_SCORE_THRESHOLD
        ]
        if expected_title in retrieved:
            hits += 1
            ranks.append(retrieved.index(expected_title) + 1)
        else:
            ranks.append(None)
            misses.append((question, expected_title, retrieved))

    total = len(EVAL_CASES)
    hit_rate = hits / total
    top1 = sum(1 for r in ranks if r == 1) / total

    print(
        f"\n[RAG 召回率] recall@1 = {top1:.1%}   recall@{TOP_K} = {hits}/{total} = "
        f"{hit_rate:.1%}   (阈值 distance <= {RAG_SCORE_THRESHOLD}, "
        f"文档 {len(KNOWLEDGE_DOCS)} 篇, 用例 {total} 条)"
    )
    for question, expected_title, retrieved in misses:
        print(f"  未命中: {question!r} 期望={expected_title} 实际召回={retrieved}")

    assert hit_rate >= MIN_HIT_RATE, (
        f"召回命中率 {hit_rate:.0%}（{hits}/{total}）低于下限 "
        f"{MIN_HIT_RATE:.0%}。未命中：{misses}"
    )


def test_knowledge_base_covers_every_eval_case(retrieval_index):
    """每个评测用例期望的文档都必须真的在知识库里，否则评测本身是错的。"""
    _embeddings, collection = retrieval_index
    indexed_titles = {
        meta["title"]
        for meta in collection.get(include=["metadatas"])["metadatas"]
    }
    expected_titles = {title for _q, title in EVAL_CASES}

    assert expected_titles <= indexed_titles, (
        f"评测用例引用了不存在的文档：{expected_titles - indexed_titles}"
    )
