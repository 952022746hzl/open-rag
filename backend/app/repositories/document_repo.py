"""文档元数据数据访问仓储。

封装 documents 表的增删改查，包含基于用户角色的可见范围过滤逻辑。
"""

from datetime import datetime
from typing import Literal

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document

_Visibility = Literal["public", "department", "private"]
_Status = Literal["processing", "completed", "failed"]


class DocumentRepo:
    """文档相关数据访问对象。

    Attributes:
        db: 当前请求的异步数据库会话。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        *,
        file_name: str,
        file_type: str,
        uploader_id: int,
        department_id: int | None,
        visibility: _Visibility,
        tags: list[str] | None,
        file_size: int | None,
        upload_time: datetime,
    ) -> Document:
        """创建文档记录，初始状态为 processing，object_key 待上传后更新。

        Args:
            file_name: 原始文件名，含扩展名。
            file_type: 文件类型，如 "pdf"。
            uploader_id: 上传者用户 ID。
            department_id: 上传时用户所属部门 ID，无部门时为 None。
            visibility: 可见范围。
            tags: 标签列表，无标签时为 None。
            file_size: 文件字节数，未知时为 None。
            upload_time: 应用层的上传完成时刻。

        Returns:
            已持久化并刷新的 Document ORM 对象。
        """
        doc = Document(
            file_name=file_name,
            file_type=file_type,
            uploader_id=uploader_id,
            department_id=department_id,
            visibility=visibility,
            tags=tags or None,
            file_size=file_size,
            upload_time=upload_time,
            status="processing",
        )
        self.db.add(doc)
        await self.db.commit()
        await self.db.refresh(doc)
        return doc

    async def set_object_key(self, document_id: int, object_key: str) -> None:
        """MinIO 上传成功后，将对象键写回文档记录。

        Args:
            document_id: 目标文档主键。
            object_key: MinIO 对象路径。
        """
        stmt = update(Document).where(Document.id == document_id).values(object_key=object_key)
        await self.db.execute(stmt)
        await self.db.commit()

    async def set_status(
        self,
        document_id: int,
        status: _Status,
        error_message: str | None = None,
    ) -> None:
        """更新文档处理状态。

        Args:
            document_id: 目标文档主键。
            status: 新状态，processing / completed / failed。
            error_message: 失败时的错误描述，成功时为 None。
        """
        stmt = (
            update(Document)
            .where(Document.id == document_id)
            .values(status=status, error_message=error_message)
        )
        await self.db.execute(stmt)
        await self.db.commit()

    async def get_by_id(self, document_id: int) -> Document | None:
        """通过主键查询文档记录。

        Args:
            document_id: 文档主键。

        Returns:
            匹配的 Document 对象；不存在时返回 None。
        """
        stmt = select(Document).where(Document.id == document_id)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def list_visible(
        self,
        *,
        user_id: int,
        department_id: int | None,
        role: str,
        limit: int = 20,
        offset: int = 0,
        file_type: str | None = None,
        tag: str | None = None,
    ) -> tuple[list[Document], int]:
        """按用户权限查询可见文档列表。

        admin 可见全量；member 按三级可见范围过滤。

        Args:
            user_id: 当前用户主键。
            department_id: 当前用户所属部门 ID。
            role: 当前用户角色，"admin" 或 "member"。
            limit: 每页条数，默认 20。
            offset: 跳过条数，默认 0。
            file_type: 按文件类型过滤，为 None 时不过滤。
            tag: 按标签过滤，为 None 时不过滤。

        Returns:
            (当前页文档列表, 符合条件的总条数) 元组。
        """
        stmt = select(Document)

        if role != "admin":
            stmt = stmt.where(
                or_(
                    Document.visibility == "public",
                    and_(Document.visibility == "department", Document.department_id == department_id),
                    and_(Document.visibility == "private", Document.uploader_id == user_id),
                )
            )

        if file_type is not None:
            stmt = stmt.where(Document.file_type == file_type)

        if tag is not None:
            # PostgreSQL ARRAY contains operator
            stmt = stmt.where(Document.tags.contains([tag]))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total: int = (await self.db.execute(count_stmt)).scalar_one()

        rows = (await self.db.execute(stmt.offset(offset).limit(limit))).scalars().all()
        return list(rows), total

    async def update_metadata(
        self,
        document_id: int,
        *,
        visibility: _Visibility | None = None,
        tags: list[str] | None = None,
    ) -> Document | None:
        """更新文档的可见范围和标签。

        仅更新传入的非 None 字段，支持部分更新。

        Args:
            document_id: 目标文档主键。
            visibility: 新的可见范围；为 None 时保持不变。
            tags: 新的标签列表；为 None 时保持不变。

        Returns:
            更新后的 Document 对象；文档不存在时返回 None。
        """
        values: dict = {}
        if visibility is not None:
            values["visibility"] = visibility
        if tags is not None:
            values["tags"] = tags

        if values:
            stmt = update(Document).where(Document.id == document_id).values(**values)
            await self.db.execute(stmt)
            await self.db.commit()

        return await self.get_by_id(document_id)

    async def delete(self, document_id: int) -> None:
        """删除文档记录。

        仅删除数据库记录，MinIO 对象和 Qdrant 向量点须由调用方负责清理。

        Args:
            document_id: 目标文档主键。
        """
        doc = await self.get_by_id(document_id)
        if doc is not None:
            await self.db.delete(doc)
            await self.db.commit()
