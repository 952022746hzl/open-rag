"""文档分块 ORM 模型。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DocumentChunk(Base):
    """文档分块表，存储每个文本分块的内容与位置元数据。

    Attributes:
        id: 分块主键，同时作为 Qdrant 向量点 ID。
        document_id: 所属文档 ID，级联删除。
        chunk_index: 分块在文档内的全局序号。
        chunk_content: 分块的纯文本内容。
        tokens: 该分块的 token 数量。
        source_location: 来源位置标识，如"第3页"、"Sheet1"；无结构来源时为 None。
        created_at: 记录创建时刻。
    """

    __tablename__ = "document_chunks"
    __table_args__ = (UniqueConstraint("document_id", "chunk_index"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_content: Mapped[str] = mapped_column(Text, nullable=False)
    tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
