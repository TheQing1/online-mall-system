from typing import AsyncGenerator
from langchain_openai import ChatOpenAI
from app.core.config import settings
from app.ai.prompts import CHAT_PROMPT
from app.ai.vectorstore import search_similar


def get_llm() -> ChatOpenAI:
    """获取 DeepSeek LLM 实例"""
    if not settings.deepseek_api_key or settings.deepseek_api_key == "your-deepseek-api-key":
        raise ValueError("请在 .env 中配置 DEEPSEEK_API_KEY")
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.deepseek_api_key,
        base_url=settings.deepseek_base_url,
        streaming=True,
        temperature=0.7,
    )


async def generate_stream(query: str) -> AsyncGenerator[str, None]:
    """RAG 流式生成回答"""
    # 1. 检索相关知识
    results = search_similar(query, k=3)

    # 2. 构建上下文（ChromaDB 返回距离，越小越相似；过滤距离 > 0.7 的）
    context_parts = []
    for doc, score in results:
        if score <= 0.7:
            context_parts.append(
                f"【{doc.metadata.get('title', '未知')}】\n{doc.page_content}\n"
            )

    context = "\n".join(context_parts) if context_parts else "暂无相关知识库信息"

    # 3. 构建 Prompt
    prompt_value = CHAT_PROMPT.format(context=context, question=query)

    # 4. 流式调用 LLM
    llm = get_llm()
    async for chunk in llm.astream(prompt_value):
        if chunk.content:
            yield chunk.content
