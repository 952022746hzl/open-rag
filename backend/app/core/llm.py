"""DeepSeek 大模型客户端封装。

DeepSeek API 兼容 OpenAI 接口，直接复用 openai SDK，仅替换 base_url 和 api_key。
"""

import openai

from app.config import settings

_client: openai.AsyncOpenAI | None = None


def _get_client() -> openai.AsyncOpenAI:
    global _client
    if _client is None:
        _client = openai.AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_API_URL,
        )
    return _client


async def chat_complete(messages: list[dict]) -> tuple[str, int]:
    """调用 DeepSeek Chat Completion 接口。

    Args:
        messages: OpenAI 格式的消息列表，包含 system / user / assistant 角色。

    Returns:
        (回答文本, 本次调用消耗的 total_tokens) 元组。

    Raises:
        openai.OpenAIError: API 调用失败时抛出（含 context_length_exceeded 等）。
    """
    client = _get_client()
    response = await client.chat.completions.create(
        model=settings.OPENAI_CHAT_MODEL,
        messages=messages,
    )
    answer = response.choices[0].message.content or ""
    tokens = response.usage.total_tokens if response.usage else 0
    return answer, tokens
