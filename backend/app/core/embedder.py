"""OpenAI text-embedding-3-small 批量向量化。

每批最多 25 条，按响应中的 index 字段排序以保证与输入顺序一致。
"""

import openai

from app.config import settings

_MODEL = "text-embedding-3-small"
_BATCH_SIZE = 25

_client: openai.AsyncOpenAI | None = None


def _get_client() -> openai.AsyncOpenAI:
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_URL,
        )
    return _client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """将文本列表批量转为向量，保持输入顺序。

    Args:
        texts: 待向量化的文本列表，长度任意。

    Returns:
        与输入等长的向量列表，每个向量维度为 1536。

    Raises:
        openai.OpenAIError: API 调用失败时抛出。
    """
    client = _get_client()
    results: list[list[float]] = []

    for i in range(0, len(texts), _BATCH_SIZE):
        batch = texts[i : i + _BATCH_SIZE]
        response = await client.embeddings.create(model=_MODEL, input=batch)
        # OpenAI 不保证响应顺序，按 index 排序后追加
        sorted_data = sorted(response.data, key=lambda e: e.index)
        results.extend(item.embedding for item in sorted_data)

    return results
