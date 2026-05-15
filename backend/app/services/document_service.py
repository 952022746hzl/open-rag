"""文档上传业务服务层。"""

from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status

from app.api.deps import CurrentUser
from app.core.chunker import chunk_document
from app.core.embedder import embed_texts
from app.core.parsers import SUPPORTED_TYPES, parse_document
from app.core.sparse_encoder import encode_sparse
from app.core.storage import build_object_key, put_object
from app.core.vector_store import VectorPoint, upsert_points
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
        """接收上传文件，完成存储、解析、向量化全流程。

        执行顺序：格式校验 → 大小校验 → 插库 → MinIO 上传 → 解析分块 →
        Embedding → 写入 document_chunks → Qdrant upsert → 标记完成。

        Args:
            file: FastAPI UploadFile 对象。
            visibility: 可见范围，public / department / private。
            raw_tags: 逗号分隔的标签字符串，无标签时为 None。
            current_user: 已通过 JWT 认证的当前用户。

        Returns:
            最新状态的 Document ORM 对象，status 为 completed。

        Raises:
            HTTPException: 文件类型不支持返回 400；文件超过 50 MB 返回 413；
                可见范围非法返回 400；MinIO / Embedding / Qdrant 失败返回 500。
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

        # MinIO 上传
        object_key = build_object_key(doc.id, filename)
        try:
            await put_object(data, object_key, _CONTENT_TYPES[ext])
        except Exception as exc:
            await self.repo.set_status(doc.id, "failed", error_message=str(exc))
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="文件上传至存储服务失败") from exc

        await self.repo.set_object_key(doc.id, object_key)

        # 解析 → 分块
        parsed = parse_document(data, ext)
        chunks = chunk_document(parsed)

        if not chunks:
            await self.repo.set_status(doc.id, "completed")
            result = await self.repo.get_by_id(doc.id)
            assert result is not None
            return result

        # Embedding（稠密 + 稀疏，BM25 为同步 CPU 操作）
        texts = [c.content for c in chunks]
        try:
            embeddings = await embed_texts(texts)
        except Exception as exc:
            await self.repo.set_status(doc.id, "failed", error_message=f"Embedding 失败: {exc}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="向量化失败") from exc
        sparse_embeddings = encode_sparse(texts)

        # 写入 document_chunks，获取主键作为 Qdrant point ID
        chunk_ids = await self.repo.bulk_insert_chunks(doc.id, chunks)

        # Qdrant upsert，payload 含完整权限字段
        upload_ts = int(doc.upload_time.timestamp())
        points = [
            VectorPoint(
                id=chunk_ids[i],
                vector=embeddings[i],
                sparse_vector=sparse_embeddings[i],
                payload={
                    "document_id": doc.id,
                    "chunk_id": chunk_ids[i],
                    "chunk_index": chunks[i].chunk_index,
                    "document_name": doc.file_name,
                    "file_type": doc.file_type,
                    "uploader_id": doc.uploader_id,
                    "department_id": doc.department_id,
                    "visibility_scope": doc.visibility,
                    "tags": doc.tags or [],
                    "upload_date": upload_ts,
                    "source_location": chunks[i].source_location,
                    "snippet": chunks[i].content[:200],
                },
            )
            for i in range(len(chunks))
        ]
        try:
            await upsert_points(points)
        except Exception as exc:
            await self.repo.set_status(doc.id, "failed", error_message=f"Qdrant 写入失败: {exc}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, detail="向量写入失败") from exc

        await self.repo.set_status(doc.id, "completed")

        result = await self.repo.get_by_id(doc.id)
        assert result is not None
        return result
