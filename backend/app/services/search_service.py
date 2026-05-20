"""语义检索业务服务层。

负责构建权限过滤器、合并业务过滤条件、调用 Qdrant 检索，并为结果补充 MinIO 预签名 URL。
"""

import asyncio
import logging
from datetime import datetime, timezone

from fastapi import HTTPException
from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue, Range

logger = logging.getLogger(__name__)

from app.api.deps import CurrentUser
from app.config import settings
from app.core import reranker as reranker_service
from app.core.embedder import embed_texts
from app.core.sparse_encoder import encode_sparse
from app.core.storage import get_presigned_url
from app.core.vector_store import fetch_document_chunks, hybrid_search
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
        """执行带权限过滤的两阶段文档优先检索。

        阶段一：向量化查询 → 过采样混合检索 → （可选）cross-encoder 精排
            → 按文档最高分识别 Top N 相关文档。
        阶段二：对 Top N 文档直接从 Qdrant 拉取全量 chunk（含评分较低的页面），
            保证同文档内的低分 chunk 优先于其他文档的高分 chunk 出现在结果中。

        Args:
            req: 检索请求，包含查询词、topK、阈值、rerank 开关及业务过滤条件。
            current_user: 已通过 JWT 认证的当前用户，用于构建权限过滤。

        Returns:
            按文档相关度排列的检索结果列表、结果总数及 rerank_applied 标志。

        Raises:
            HTTPException 503: reranker 不可用。
            HTTPException 504: reranker 推理超时。
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

        # 过采样：内部多取，保证候选池足够大供 reranker 精排
        raw_hits = await hybrid_search(
            dense_vector=query_vector,
            sparse_vector=sparse_vecs[0],
            query_filter=combined_filter,
            top_k=req.top_k * settings.SEARCH_OVERSAMPLING_FACTOR,
            score_threshold=req.score_threshold,
        )
        logger.info(
            "hybrid raw=%d top_k=%d threshold=%.2f",
            len(raw_hits), req.top_k, req.score_threshold,
        )

        # Rerank：在文档分组前对全量候选集精排
        rerank_applied = False
        if req.use_rerank and raw_hits:
            top_n = req.rerank_top_n or (req.top_k * settings.SEARCH_OVERSAMPLING_FACTOR)
            try:
                raw_hits, rerank_applied = await reranker_service.rerank(
                    query=req.query,
                    hits=raw_hits,
                    top_n=top_n,
                )
            except asyncio.TimeoutError:
                logger.warning("reranker timeout")
                raise HTTPException(status_code=504, detail="reranker timeout")
            except Exception as exc:
                logger.error("reranker error: %s", exc)
                raise HTTPException(status_code=503, detail="reranker unavailable")
        logger.info("rerank applied=%s hits_after=%d", rerank_applied, len(raw_hits))

        # ── 阶段一：识别相关文档，按各文档最高 chunk 分降序排列 ──────────────
        doc_best_score: dict[int, float] = {}
        for hit in raw_hits:
            doc_id = hit.payload["document_id"]
            if hit.score > doc_best_score.get(doc_id, -1):
                doc_best_score[doc_id] = hit.score
        ranked_doc_ids = sorted(doc_best_score, key=doc_best_score.__getitem__, reverse=True)
        logger.info("stage1 docs=%d ids=%s", len(ranked_doc_ids), ranked_doc_ids[:5])

        # ── 阶段二：拉取相关文档的全量 chunk，补全低分页面 ───────────────────
        all_doc_chunks = await fetch_document_chunks(
            document_ids=ranked_doc_ids,
            query_filter=combined_filter,
            limit_per_doc=settings.SEARCH_CHUNKS_PER_DOC,
        )
        logger.info(
            "stage2 docs=%d chunks=%d",
            len(all_doc_chunks),
            sum(len(v) for v in all_doc_chunks.values()),
        )

        # 已命中的 chunk 保留其真实分数，未命中的继承所在文档最高分
        chunk_scores: dict[int, float] = {
            hit.payload["chunk_id"]: hit.score for hit in raw_hits
        }

        # 按文档排名顺序拼接，组内按 point ID（写入顺序即页面顺序）升序
        # top_k 控制"何时停止纳入新文档"，不在文档内部截断，保证同文档完整性
        hits: list[tuple[dict, float]] = []
        for doc_id in ranked_doc_ids:
            records = sorted(all_doc_chunks.get(doc_id, []), key=lambda r: r.id)
            for record in records:
                chunk_id = record.payload["chunk_id"]
                score = chunk_scores.get(chunk_id, doc_best_score[doc_id])
                hits.append((record.payload, score))
            if len(hits) >= req.top_k:
                break

        # 批量取 object_key，避免 N+1 查询
        doc_ids = {payload["document_id"] for payload, _ in hits}
        docs = {doc.id: doc for doc in await self.repo.get_by_ids(doc_ids)}

        results: list[SearchResultItem] = []
        for payload, score in hits:
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
                score=score,
                download_url=download_url,
            ))

        logger.info("search done results=%d rerank=%s", len(results), rerank_applied)
        return SearchResponse(results=results, total=len(results), rerank_applied=rerank_applied)
