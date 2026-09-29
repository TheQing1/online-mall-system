"""部署预热：把「第一个用户来才发生」的昂贵初始化提前到发布阶段。

不预热的后果（都是真在本地 compose 上踩过的）：

1. Embedding 模型（BGE，约 100MB）首次使用要从 ModelScope 下载，冷启动还要
   把它读进内存。第一个提问的人会等上几分钟，而 docker compose 的
   healthcheck 会在模型下载期间把 backend 判成 unhealthy——``web`` 服务
   ``depends_on: service_healthy`` 于是一直起不来，看起来像「部署失败」。
2. BM25 索引是内存结构，第一次检索才构建；知识库越大冷启动越慢。

所以部署脚本在 ``compose up`` **之前**先跑一次：

    docker compose run --rm backend python -m app.ai.warmup

它做三件事：加载模型 → 检查/重建向量索引 → 用一条真实问题走一遍检索路径
（确保向量库和 BM25 两条召回都能跑）。做完之后模型与向量库都落在
``mall-data`` 卷里，正式启动时是秒级。

之所以用「真实走一遍检索」而不是只 import 一下模块：import 成功但集合为空、
BM25 语料为空这类问题，只有真跑一次查询才暴露得出来。
"""

import sys
import time


def _ensure_index(db) -> int:
    """知识库有文档但向量库为空时重建；返回向量片段数。"""
    from app.ai.indexer import sync_all_knowledge
    from app.ai.vectorstore import get_vectorstore
    from app.models.knowledge import KnowledgeDoc

    doc_count = db.query(KnowledgeDoc).count()
    if doc_count == 0:
        print("[预热] 知识库为空，跳过向量索引检查")
        return 0

    try:
        existing = get_vectorstore().count()
    except Exception as exc:  # 集合不存在等情况，按 0 处理
        print(f"[预热] 读取向量库失败（按空处理）：{exc}")
        existing = 0

    if existing == 0:
        print(f"[预热] 向量库为空，按知识库全量重建（{doc_count} 篇文档）...")
        return sync_all_knowledge(db)

    print(f"[预热] 向量库已有 {existing} 个片段，跳过重建")
    return existing


def main() -> int:
    started = time.perf_counter()

    print("[预热] 加载 Embedding 模型（首次会从 ModelScope 下载约 100MB）...")
    step = time.perf_counter()
    from app.ai.vectorstore import get_embeddings

    get_embeddings()
    print(f"[预热] 模型就绪（{time.perf_counter() - step:.1f}s）")

    # 数据库连不上不该让整个部署失败：预热是「提前做掉」而不是「必须先做」，
    # 真正的初始化在 backend 的 entrypoint 里还会再做一次。
    step = time.perf_counter()
    try:
        from app.core.database import SessionLocal

        db = SessionLocal()
    except Exception as exc:
        print(f"[预热] 数据库不可用，跳过向量索引检查：{exc}")
        return 0

    try:
        chunks = _ensure_index(db)
    except Exception as exc:
        print(f"[预热] 向量索引检查失败（不阻断部署）：{exc}")
        return 0
    finally:
        db.close()
    print(f"[预热] 索引就绪（{chunks} 个片段，{time.perf_counter() - step:.1f}s）")

    # 真跑一条查询：既预热 BM25 索引，也验证「向量 + 词频」两条召回都活着。
    step = time.perf_counter()
    from app.ai.retriever import retrieve

    hits = retrieve("怎么申请退款", k=3)
    print(f"[预热] 检索自检命中 {len(hits)} 条（{time.perf_counter() - step:.1f}s）")
    if not hits:
        print(
            "[预热] 警告：检索没有命中任何片段。"
            "商城仍可访问，但 AI 客服会答不出知识库内容，请检查知识库与向量索引。"
        )

    print(f"[预热] 完成，总用时 {time.perf_counter() - started:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
