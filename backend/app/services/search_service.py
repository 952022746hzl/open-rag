"""语义检索业务服务层。

负责构建权限过滤器、合并业务过滤条件、调用 Qdrant 检索，并为结果补充 MinIO 预签名 URL。
"""

from collections import defaultdict
from datetime import datetime, timezone

from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue, Range

from app.api.deps import CurrentUser
from app.config import settings
from app.core.embedder import embed_texts
from app.core.sparse_encoder import encode_sparse
from app.core.storage import get_presigned_url
from app.core.vector_store import hybrid_search
from app.repositories.document_repo import DocumentRepo
from app.schemas.search import SearchFilter, SearchRequest, SearchResponse, SearchResultItem


def _build_combined_filter(
    user_id: int,
    department_id: int | None,
    role: str,
    user_filter: SearchFilter | None,
) -> Filter | None:
    """将权限过滤与业务过滤合并为单个 Qdrant Filter。

    权限过滤与所有业务条件以 must（AND）关系组合；
    权限内部三种可见范围以 should（OR）关系组合。
    admin 跳过权限过滤。

    Args:
        user_id: 当前用户主键。
        department_id: 当前用户所属部门 ID，无部门时为 None。
        role: 当前用户角色，"admin" 或 "member"。
        user_filter: 请求体中的业务过滤条件，为 None 时不施加业务过滤。

    Returns:
        合并后的 Qdrant Filter；无任何条件时返回 None。
    """
    must: list = []

    if role != "admin":
        should: list = [
            FieldCondition(key="visibility_scope", match=MatchValue(value="public")),
            Filter(must=[
                FieldCondition(key="visibility_scope", match=MatchValue(value="private")),
                FieldCondition(key="uploader_id", match=MatchValue(value=user_id)),
            ]),
        ]
        if department_id is not None:
            should.append(Filter(must=[
                FieldCondition(key="visibility_scope", match=MatchValue(value="department")),
                FieldCondition(key="department_id", match=MatchValue(value=department_id)),
            ]))
        must.append(Filter(should=should))

    if user_filter:
        if user_filter.file_types:
            must.append(FieldCondition(key="file_type", match=MatchAny(any=user_filter.file_types)))
        if user_filter.uploader_ids:
            must.append(FieldCondition(key="uploader_id", match=MatchAny(any=user_filter.uploader_ids)))
        if user_filter.department_ids:
            must.append(FieldCondition(key="department_id", match=MatchAny(any=user_filter.department_ids)))
        if user_filter.tags:
            must.append(FieldCondition(key="tags", match=MatchAny(any=user_filter.tags)))
        if user_filter.document_ids:
            must.append(FieldCondition(key="document_id", match=MatchAny(any=user_filter.document_ids)))
        if user_filter.upload_date_from:
            must.append(FieldCondition(key="upload_date", range=Range(gte=_date_to_ts(user_filter.upload_date_from))))
        if user_filter.upload_date_to:
            must.append(FieldCondition(key="upload_date", range=Range(lte=_date_to_ts(user_filter.upload_date_to, end_of_day=True))))

    return Filter(must=must) if must else None


def _date_to_ts(date_str: str, end_of_day: bool = False) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if end_of_day:
        dt = dt.replace(hour=23, minute=59, second=59)
    return int(dt.timestamp())


class SearchService:
    """语义检索业务逻辑。

    Attributes:
        repo: 文档数据访问仓储，用于查询 object_key 生成预签名 URL。
    """

    def __init__(self, repo: DocumentRepo):
        self.repo = repo

    async def search(self, req: SearchRequest, current_user: CurrentUser) -> SearchResponse:
        """执行带权限过滤的语义检索。

        步骤：向量化查询 → 构建过滤器 → 过采样 ANN 搜索 →
        按文档分组（保证高相关文档多片召回）→ 批量获取 object_key → 生成预签名 URL → 组装响应。

        内部搜索量 = top_k × SEARCH_OVERSAMPLING_FACTOR，确保同一文档的多个 chunk
        有机会进入候选池；再按文档分组后，每个文档最多保留 SEARCH_CHUNKS_PER_DOC 个 chunk，
        文档间按最高分排序，最终裁剪至 top_k 条返回。

        Args:
            req: 检索请求，包含查询词、topK、阈值及业务过滤条件。
            current_user: 已通过 JWT 认证的当前用户，用于构建权限过滤。

        Returns:
            按文档相关度排列的检索结果列表及结果总数。
        """
        embeddings = await embed_texts([req.query])
        query_vector = embeddings[0]
        sparse_vecs = encode_sparse([req.query])

        combined_filter = _build_combined_filter(
            user_id=current_user.user_id,
            department_id=current_user.department_id,
            role=current_user.role,
            user_filter=req.filter,
        )

        # 过采样：内部多取，保证同一文档的次高分 chunk 也进入候选池
        raw_hits = await hybrid_search(
            dense_vector=query_vector,
            sparse_vector=sparse_vecs[0],
            query_filter=combined_filter,
            top_k=req.top_k * settings.SEARCH_OVERSAMPLING_FACTOR,
            score_threshold=req.score_threshold,
        )

        # 按文档分组（Qdrant 已全局按分数降序排列，组内顺序即分数由高到低）
        doc_hits: dict[int, list] = defaultdict(list)
        for hit in raw_hits:
            doc_hits[hit.payload["document_id"]].append(hit)

        # 文档按组内最高分排序，每个文档取前 SEARCH_CHUNKS_PER_DOC 个 chunk
        sorted_docs = sorted(doc_hits, key=lambda d: doc_hits[d][0].score, reverse=True)
        hits = []
        for doc_id in sorted_docs:
            hits.extend(doc_hits[doc_id][: settings.SEARCH_CHUNKS_PER_DOC])
            if len(hits) >= req.top_k:
                break
        hits = hits[: req.top_k]

        # 批量取 object_key，避免 N+1 查询
        doc_ids = {hit.payload["document_id"] for hit in hits}
        docs = {doc.id: doc for doc in await self.repo.get_by_ids(doc_ids)}

        results: list[SearchResultItem] = []
        for hit in hits:
            payload = hit.payload
            doc = docs.get(payload["document_id"])
            download_url = ""
            if doc and doc.object_key:
                download_url = await get_presigned_url(doc.object_key)

            results.append(SearchResultItem(
                chunk_id=payload["chunk_id"],
                document_id=payload["document_id"],
                document_name=payload["document_name"],
                file_type=payload["file_type"],
                uploader_id=payload["uploader_id"],
                tags=payload.get("tags") or [],
                source_location=payload.get("source_location"),
                snippet=payload.get("snippet", ""),
                score=hit.score,
                download_url=download_url,
            ))

        return SearchResponse(results=results, total=len(results))
