"""语义检索请求与响应 Schema。"""

from pydantic import BaseModel, Field


class SearchFilter(BaseModel):
    """业务过滤条件，所有字段可选，为 None 时不施加该条件。

    Attributes:
        file_types: 文件类型白名单，如 ["pdf", "docx"]。
        uploader_ids: 上传者 ID 白名单。
        department_ids: 部门 ID 白名单。
        tags: 标签白名单，命中任意标签即满足条件。
        upload_date_from: 上传日期下界，ISO 8601 格式 YYYY-MM-DD，取当日 00:00:00 UTC。
        upload_date_to: 上传日期上界，ISO 8601 格式 YYYY-MM-DD，取当日 23:59:59 UTC。
        document_ids: 文档 ID 白名单，限定检索范围。
    """

    file_types: list[str] | None = None
    uploader_ids: list[int] | None = None
    department_ids: list[int] | None = None
    tags: list[str] | None = None
    upload_date_from: str | None = None
    upload_date_to: str | None = None
    document_ids: list[int] | None = None


class SearchRequest(BaseModel):
    """语义检索请求体。

    Attributes:
        query: 自然语言检索问题。
        top_k: 返回最相似的 k 条结果，默认 5。
        score_threshold: 相似度分数阈值，低于此值的结果过滤掉，默认 0.6。
        filter: 业务过滤条件，为 None 时仅施加权限过滤。
        use_rerank: 是否启用重排序，默认 True。
        rerank_top_n: reranker 保留的候选数量，默认等于 top_k × SEARCH_OVERSAMPLING_FACTOR（全量候选）；
            显式传入时可缩小候选池以降低延迟。
    """

    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    filter: SearchFilter | None = None
    use_rerank: bool = False
    rerank_top_n: int | None = None


class SearchResultItem(BaseModel):
    """单条检索结果。

    Attributes:
        chunk_id: 分块主键，与 document_chunks.id 一致。
        document_id: 所属文档主键。
        document_name: 原始文件名。
        file_type: 文件类型，如 pdf、docx。
        uploader_id: 上传者用户 ID。
        tags: 文档标签列表。
        source_location: 来源位置标识，如"第3页"；无结构来源时为 None。
        snippet: 分块前 200 字符，用于引用展示。
        score: 向量相似度分数。
        download_url: MinIO 预签名下载 URL，有效期 1 小时。
    """

    chunk_id: int
    document_id: int
    document_name: str
    file_type: str
    uploader_id: int
    tags: list[str]
    source_location: str | None
    snippet: str
    score: float
    download_url: str


class SearchResponse(BaseModel):
    """语义检索响应体。

    Attributes:
        results: 检索结果列表，已按相似度降序排列。
        total: 本次返回的结果数量。
        rerank_applied: 本次是否实际执行了重排序。
    """

    results: list[SearchResultItem]
    total: int
    rerank_applied: bool = False
