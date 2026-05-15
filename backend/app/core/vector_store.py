"""Qdrant 向量存储客户端封装。

集合名称、向量维度通过配置注入；提供集合初始化、批量写入和按文档删除三个操作。
"""

from dataclasses import dataclass

from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FilterSelector,
    MatchValue,
    PointStruct,
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
        vector: 1536 维浮点向量。
        payload: 包含权限和元数据字段的字典。
    """

    id: int
    vector: list[float]
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
            vectors_config=VectorParams(size=_VECTOR_SIZE, distance=Distance.COSINE),
            on_disk_payload=True,
        )


async def upsert_points(points: list[VectorPoint]) -> None:
    """批量写入向量点及 payload 至 Qdrant。

    Args:
        points: 待写入的向量点列表，为空时直接返回。

    Raises:
        Exception: Qdrant 写入失败时抛出。
    """
    if not points:
        return
    client = _get_client()
    structs = [
        PointStruct(id=p.id, vector=p.vector, payload=p.payload)
        for p in points
    ]
    await client.upsert(collection_name=settings.QDRANT_COLLECTION, points=structs)


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
