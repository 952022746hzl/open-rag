"""问答会话与记录 ORM 模型。"""

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QaSession(Base):
    """问答会话表，一个会话对应多轮连续对话。

    Attributes:
        session_id: 会话主键，格式 sess_<16位十六进制>。
        user_id: 发起用户 ID。
        turn_count: 当前总轮次数，每次问答后递增。
        created_at: 会话创建时刻。
        last_active_at: 最后活跃时刻，每次问答后更新。
    """

    __tablename__ = "qa_sessions"

    session_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    turn_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class QaRecord(Base):
    """问答记录表，每行对应一轮问答。

    Attributes:
        id: 记录主键。
        session_id: 所属会话 ID，会话删除时级联删除。
        turn_id: 该会话内的轮次序号，从 1 开始。
        question: 用户问题文本。
        answer: LLM 回答文本。
        context: JSONB，存储本轮引用、检索参数、token 用量等扩展信息。
        created_at: 记录创建时刻。
    """

    __tablename__ = "qa_records"
    __table_args__ = (UniqueConstraint("session_id", "turn_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(50), ForeignKey("qa_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_id: Mapped[int] = mapped_column(Integer, nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
