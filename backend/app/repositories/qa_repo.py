"""问答会话与记录数据访问仓储。"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.qa import QaRecord, QaSession


class QaRepo:
    """问答相关数据访问对象。

    Attributes:
        db: 当前请求的异步数据库会话。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(self, user_id: int) -> QaSession:
        """创建新问答会话。

        Args:
            user_id: 发起用户主键。

        Returns:
            已持久化的 QaSession 对象。
        """
        session = QaSession(
            session_id=f"sess_{uuid.uuid4().hex[:16]}",
            user_id=user_id,
            turn_count=0,
        )
        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)
        return session

    async def get_session(self, session_id: str) -> QaSession | None:
        """查询会话记录。

        Args:
            session_id: 会话主键。

        Returns:
            匹配的 QaSession；不存在时返回 None。
        """
        stmt = select(QaSession).where(QaSession.session_id == session_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def get_history(self, session_id: str, limit: int) -> list[QaRecord]:
        """查询最近 N 轮历史记录，按 turn_id 升序返回。

        Args:
            session_id: 目标会话主键。
            limit: 取最近的轮次数量。

        Returns:
            按时间升序排列的 QaRecord 列表。
        """
        stmt = (
            select(QaRecord)
            .where(QaRecord.session_id == session_id)
            .order_by(QaRecord.turn_id.desc())
            .limit(limit)
        )
        rows = (await self.db.execute(stmt)).scalars().all()
        return list(reversed(rows))

    async def save_record(
        self,
        session_id: str,
        turn_id: int,
        question: str,
        answer: str,
        context: dict,
    ) -> QaRecord:
        """写入一轮问答记录并更新会话状态。

        Args:
            session_id: 所属会话主键。
            turn_id: 本轮轮次序号。
            question: 用户问题。
            answer: LLM 回答。
            context: 包含引用、token 用量等信息的字典。

        Returns:
            已持久化的 QaRecord 对象。
        """
        record = QaRecord(
            session_id=session_id,
            turn_id=turn_id,
            question=question,
            answer=answer,
            context=context,
        )
        self.db.add(record)

        now = datetime.now(timezone.utc)
        await self.db.execute(
            update(QaSession)
            .where(QaSession.session_id == session_id)
            .values(turn_count=QaSession.turn_count + 1, last_active_at=now)
        )

        await self.db.commit()
        await self.db.refresh(record)
        return record
