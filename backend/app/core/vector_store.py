"""Qdrant 向量存储客户端封装。

集合使用命名向量：dense（text-embedding-3-small）+ sparse（BM25）。
混合检索通过 query_points + FusionQuery(RRF) 实现，由 Qdrant 原生融合。
"""

from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    Fusion,
    FusionQuery,
    MatchValue,
    PointStruct,
    Prefetch,
    ScoredPoint,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

from app.config import settings

_VECTOR_SIZE = 1536  # text-embedding-3-small 输出维度

_client: AsyncQdrantClient | None = None


def _get_client() -> AsyncQdrantClient:
    global _client
    if _client is None:
        _client = AsyncQdrantClient(url=settings.QDRANT_URL)
    return _client


@dataclass
class VectorPoint:
    """待写入 Qdrant 的向量点。

    Attributes:
        id: 点 ID，与 document_chunks.id 一致。
        vector: 1536 维 text-embedding-3-small 稠密向量。
        sparse_vector: BM25 稀疏向量，用于关键字精确匹配。
        payload: 包含权限和元数据字段的字典。
    """

    id: int
    vector: list[float]
    sparse_vector: SparseVector
    payload: dict


async def ensure_collection() -> None:
    """若集合不存在则自动创建，用于应用启动时初始化。

    Raises:
        Exception: Qdrant 连接失败或权限不足时抛出。
    """
    client = _get_client()
    response = await client.get_collections()
    existing = {c.name for c in response.collections}
    if settings.QDRANT_COLLECTION not in existing:
        await client.create_collection(
            collection_name=settings.QDRANT_COLLECTION,
            vectors_config={"dense": VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams()},
            on_disk_payload=True,
        )


async def upsert_points(points: list[VectorPoint]) -> None:
    """批量写入向量点（稠密 + 稀疏）及 payload 至 Qdrant。

    Args:
        points: 待写入的向量点列表，为空时直接返回。

    Raises:
        Exception: Qdrant 写入失败时抛出。
    """
    if not points:
        return
    client = _get_client()
    structs = [
        PointStruct(
            id=p.id,
            vector={"dense": p.vector, "sparse": p.sparse_vector},
            payload=p.payload,
        )
        for p in points
    ]
    await client.upsert(collection_name=settings.QDRANT_COLLECTION, points=structs)


async def hybrid_search(
    dense_vector: list[float],
    sparse_vector: SparseVector,
    query_filter: Filter | None,
    top_k: int,
    score_threshold: float,
) -> list[ScoredPoint]:
    """执行稠密 + 稀疏混合检索，由 Qdrant 原生 RRF 融合两路排名。

    dense prefetch 施加 score_threshold 过滤低语义相关结果；
    sparse prefetch 不设阈值以保障关键字召回；
    RRF 融合后 score 为 Qdrant 内部归一化分数，非原始余弦相似度。

    Args:
        dense_vector: 查询的 1536 维稠密向量。
        sparse_vector: 查询的 BM25 稀疏向量。
        query_filter: 权限 + 业务过滤器，为 None 时不施加过滤。
        top_k: 每路 prefetch 及最终返回的最大结果数量。
        score_threshold: 仅施加于 dense prefetch，过滤低语义相关结果。

    Returns:
        经 RRF 融合后按分数降序排列的 ScoredPoint 列表，含完整 payload。
    """
    client = _get_client()
    response = await client.query_points(
        collection_name=settings.QDRANT_COLLECTION,
        prefetch=[
            Prefetch(
                query=dense_vector,
                using="dense",
                limit=top_k,
                filter=query_filter,
                score_threshold=score_threshold,
            ),
            Prefetch(
                query=sparse_vector,
                using="sparse",
                limit=top_k,
                filter=query_filter,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=top_k,
        with_payload=True,
    )
    return response.points


async def delete_by_document(document_id: int) -> None:
    """删除指定文档在 Qdrant 中的所有向量点。

    Args:
        document_id: 目标文档的主键 ID。

    Raises:
        Exception: Qdrant 删除失败时抛出。
    """
    client = _get_client()
    await client.delete(
        collection_name=settings.QDRANT_COLLECTION,
        points_selector=FilterSelector(
            filter=Filter(
                must=[FieldCondition(key="document_id", match=MatchValue(value=document_id))]
            )
        ),
    )
