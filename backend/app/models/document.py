"""文档元数据 ORM 模型。"""

from datetime import datetime

from sqlalchemy import ARRAY, BigInteger, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Document(Base):
    """文档表，存储上传文件的元数据及处理状态。

    Attributes:
        id: 文档主键。
        file_name: 原始文件名，含扩展名。
        file_type: 文件类型，如 pdf、docx。
        object_key: MinIO 对象路径；插库时为 None，MinIO 上传成功后更新。
        uploader_id: 上传用户 ID，从 JWT 提取。
        department_id: 上传时用户所属部门 ID，从 JWT 提取，private 文档为 None。
        visibility: 可见范围，public / department / private。
        tags: 标签列表，用于过滤检索。
        upload_time: 应用层记录的上传完成时刻，用于对外展示和过滤。
        file_size: 文件字节数。
        status: 处理状态，processing / completed / failed。
        error_message: 处理失败时的错误描述。
        created_at: 数据库记录创建时刻。
        updated_at: 数据库记录最后更新时刻。
    """

    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    object_key: Mapped[str | None] = mapped_column(String(512), nullable=True)
    uploader_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("users.id"), nullable=False, index=True
    )
    department_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("departments.id"), nullable=True, index=True
    )
    visibility: Mapped[str] = mapped_column(
        String(20), nullable=False, default="public", index=True
    )
    tags: Mapped[list[str] | None] = mapped_column(ARRAY(Text()), nullable=True)
    upload_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="processing")
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
