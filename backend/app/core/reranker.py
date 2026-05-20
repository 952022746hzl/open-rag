"""Cross-Encoder 重排序模块。

使用 sentence-transformers CrossEncoder 对候选 chunk 与查询词进行语义打分，
替换 RRF 位置分数，提升最终结果的语义精度。
"""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor

from app.config import settings

logger = logging.getLogger(__name__)

_model = None
# 单线程 executor 保证模型加载与推理串行，避免重复初始化
_executor = ThreadPoolExecutor(max_workers=1)


def _get_model():
    """懒加载 CrossEncoder，失败时直接抛出异常。"""
    global _model
    if _model is None:
        from sentence_transformers import CrossEncoder  # noqa: PLC0415

        logger.info("loading reranker: %s", settings.RERANKER_MODEL_PATH)
        _model = CrossEncoder(settings.RERANKER_MODEL_PATH)
        logger.info("reranker loaded")
    return _model


def _sync_score(query: str, snippets: list[str]) -> list[float]:
    model = _get_model()
    pairs = [[query, s] for s in snippets]
    return [float(s) for s in model.predict(pairs, show_progress_bar=False)]


async def rerank(query: str, hits: list, top_n: int) -> tuple[list, bool]:
    """对 RRF 候选集执行 cross-encoder 精排。

    在独立线程池中运行同步推理，避免阻塞事件循环。
    出现任何异常时直接向上层抛出，不降级。

    Args:
        query: 原始检索查询词。
        hits: Qdrant ScoredPoint 列表（RRF 融合后候选集）。
        top_n: 精排后保留的候选数量，取值区间 [1, len(hits)]。

    Returns:
        (按 rerank_score 降序排列的 hits[:top_n], True) 二元组。
        候选集为空时返回 ([], False)。

    Raises:
        asyncio.TimeoutError: 推理超时（超过 RERANKER_TIMEOUT_S）。
        Exception: 模型加载失败或推理异常。
    """
    if not hits:
        return hits, False

    snippets = [hit.payload.get("snippet", "") for hit in hits]
    loop = asyncio.get_event_loop()

    scores: list[float] = await asyncio.wait_for(
        loop.run_in_executor(_executor, _sync_score, query, snippets),
        timeout=settings.RERANKER_TIMEOUT_S,
    )

    for hit, score in zip(hits, scores):
        hit.score = score

    reranked = sorted(hits, key=lambda h: h.score, reverse=True)
    return reranked[:top_n], True
