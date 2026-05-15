"""文档上传业务服务层。"""

from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status

from app.api.deps import CurrentUser
from app.core.parsers import SUPPORTED_TYPES
from app.core.storage import build_object_key, put_object
from app.models.document import Document
from app.repositories.document_repo import DocumentRepo

_MAX_BYTES = 50 * 1024 * 1024  # 50 MB

_CONTENT_TYPES: dict[str, str] = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain",
    "md": "text/markdown",
}


class DocumentService:
    """文档上传与管理业务逻辑。

    Attributes:
        repo: 文档数据访问仓储。
    """

    def __init__(self, repo: DocumentRepo):
        self.repo = repo

    async def upload(
        self,
        file: UploadFile,
        visibility: str,
        raw_tags: str | None,
        current_user: CurrentUser,
    ) -> Document:
        """接收上传文件，持久化至 MinIO 并写入文档记录。

        执行顺序：格式校验 → 大小校验 → 插库 → MinIO 上传 → 回填 object_key → 标记完成。

        Args:
            file: FastAPI UploadFile 对象。
            visibility: 可见范围，public / department / private。
            raw_tags: 逗号分隔的标签字符串，无标签时为 None。
            current_user: 已通过 JWT 认证的当前用户。

        Returns:
            最新状态的 Document ORM 对象。

        Raises:
            HTTPException: 文件类型不支持返回 400；文件超过 50 MB 返回 413；
                可见范围非法返回 400；MinIO 上传失败返回 500。
        """
        if visibility not in ("public", "department", "private"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="visibility 只能是 public / department / private")

        filename = file.filename or "unknown"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        if ext not in SUPPORTED_TYPES:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=f"不支持的文件类型：{ext}")

        data = await file.read()
        if len(data) > _MAX_BYTES:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="文件超过 50 MB 限制")

        tags = [t.strip() for t in raw_tags.split(",") if t.strip()] if raw_tags else None

        doc = await self.repo.create(
            file_name=filename,
            file_type=ext,
            uploader_id=current_user.user_id,
            department_id=current_user.department_id,
            visibility=visibility,
            tags=tags,
            file_size=len(data),
            upload_time=datetime.now(timezone.utc),
        )

        object_key = build_object_key(doc.id, filename)
        # todo 这边未向量化解析 暂时只做上传。
        try:
            await put_object(data, object_key, _CONTENT_TYPES[ext])
        except Exception as exc:
            await self.repo.set_status(doc.id, "failed", error_message=str(exc))
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="文件上传至存储服务失败") from exc

        await self.repo.set_object_key(doc.id, object_key)
        await self.repo.set_status(doc.id, "completed")

        result = await self.repo.get_by_id(doc.id)
        assert result is not None
        return result
