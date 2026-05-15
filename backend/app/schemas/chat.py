"""多轮问答请求与响应 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.search import SearchFilter


class ChatRequest(BaseModel):
    """多轮问答请求体。

    Attributes:
        session_id: 会话 ID；传 null 时服务端自动创建新会话。
        question: 当前问题文本。
        top_k: 检索返回的最大 chunk 数，默认 5。
        score_threshold: dense 检索分数下界，默认 0.6。
        filter: 可选业务过滤条件，格式与语义检索接口一致。
    """

    session_id: str | None = None
    question: str
    top_k: int = Field(default=5, ge=1, le=50)
    score_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    filter: SearchFilter | None = None


class Citation(BaseModel):
    """回答中引用的单条文档片段。

    Attributes:
        chunk_id: 分块主键。
        document_id: 所属文档主键。
        document_name: 原始文件名。
        source_location: 来源位置标识，如"第3页"。
        snippet: 分块前 200 字符。
        download_url: MinIO 预签名下载 URL。
    """

    chunk_id: int
    document_id: int
    document_name: str
    source_location: str | None
    snippet: str
    download_url: str


class ChatResponse(BaseModel):
    """多轮问答响应体。

    Attributes:
        session_id: 本次对话所属会话 ID。
        turn_id: 本轮在会话中的轮次序号。
        question: 用户问题原文。
        answer: LLM 生成的回答。
        citations: 本轮检索到的引用列表。
        timestamp: 回答生成时刻。
    """

    session_id: str
    turn_id: int
    question: str
    answer: str
    citations: list[Citation]
    timestamp: datetime
