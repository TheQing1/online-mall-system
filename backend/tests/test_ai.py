import math

from app.ai import indexer, vectorstore
from app.models.knowledge import KnowledgeCategory, KnowledgeDoc

from tests.conftest import auth_header


class FakeEmbeddings:
    """确定性假 Embedding：字符散列向量，用于无网络测试。"""

    def embed_documents(self, texts):
        vectors = []
        for text in texts:
            vec = [0.0] * 16
            for i, ch in enumerate(text):
                vec[i % 16] += ord(ch) * (i + 1)
            norm = math.sqrt(sum(v * v for v in vec)) or 1
            vectors.append([v / norm for v in vec])
        return vectors


def _seed_vectorstore(db, tmp_path, monkeypatch):
    monkeypatch.setattr(vectorstore, "CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setattr(
        vectorstore, "get_embeddings", lambda: FakeEmbeddings()
    )
    # 重置单例 embedding function 缓存
    vectorstore._ef.model = None


def test_knowledge_incremental_index_and_search(db, tmp_path, monkeypatch):
    _seed_vectorstore(db, tmp_path, monkeypatch)

    doc = KnowledgeDoc(
        title="退换货政策",
        content="自收到商品之日起 7 日内可申请无理由退货，退货运费由买家承担。",
        category=KnowledgeCategory.REFUND,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)

    count = indexer.sync_knowledge_doc(db, doc)
    assert count >= 1

    results = vectorstore.search_similar("自收到商品之日起 7 日内可申请无理由退货", k=3)
    assert results
    assert results[0][0].metadata["title"] == "退换货政策"

    # 增量更新同一文档后检索新内容
    doc.content = "退换货政策已更新：支持 30 天无理由退货。"
    db.commit()
    indexer.sync_knowledge_doc(db, doc)
    results = vectorstore.search_similar("退换货政策已更新：支持 30 天无理由退货", k=3)
    assert results
    assert results[0][0].metadata["id"] == doc.id

    # 删除文档后无召回
    vectorstore.delete_document_vectors(doc.id)
    assert vectorstore.search_similar("退换货政策已更新", k=3) == []


def test_rag_eval_endpoint(client, db, tmp_path, monkeypatch, admin):
    from app.models.chat import EvalTestCase

    _seed_vectorstore(db, tmp_path, monkeypatch)
    doc = KnowledgeDoc(
        title="配送说明",
        content="省会城市 1-3 天送达，订单满 99 元包邮。",
        category=KnowledgeCategory.ORDER,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    indexer.sync_knowledge_doc(db, doc)

    case = EvalTestCase(question="省会城市几天能送到？", expected_title="配送说明")
    db.add(case)
    db.commit()

    headers = auth_header(client, "admin_test", "admin123")
    res = client.post("/api/v1/admin/ai/eval/run", headers=headers)
    assert res.status_code == 200
    payload = res.json()

    # 这里用假向量，命中率本身没有意义（真实模型的召回率见 test_rag_quality.py）。
    # 但「接口是否按用例数正确统计」必须被断言 —— 之前只写了 hit_rate >= 0，
    # 而命中率天然非负，等于什么都没验证。
    assert payload["total"] == 1
    assert payload["hit_rate"] in (0.0, 1.0)
    result = payload["results"][0]
    assert result["question"] == "省会城市几天能送到？"
    assert result["expected_title"] == "配送说明"
    assert isinstance(result["hit"], bool)
    assert isinstance(result["retrieved_titles"], list)
    # 该文档确实被索引了，至少要能召回一条
    assert result["retrieved_titles"], payload
