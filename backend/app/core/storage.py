"""MinIO 对象存储客户端封装。

提供文件上传、预签名下载 URL 生成及对象删除三个核心操作，
所有 I/O 操作通过 asyncio.to_thread 避免阻塞事件循环。
"""

import asyncio
from datetime import datetime, timedelta, timezone
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from app.config import settings

_client: Minio | None = None


def _get_client() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.MINIO_ENDPOINT,
            access_key=settings.MINIO_ACCESS_KEY,
            secret_key=settings.MINIO_SECRET_KEY,
            secure=settings.MINIO_SECURE,
        )
    return _client


def build_object_key(document_id: int, filename: str) -> str:
    """按命名规范构造 MinIO 对象键。

    路径格式：{yyyyMMdd}/{document_id}/{yyyyMMdd-HHmmss}_{filename}

    Args:
        document_id: 已入库的文档主键 ID。
        filename: 原始文件名，含扩展名。

    Returns:
        可直接用于 MinIO 操作的对象键字符串。
    """
    now = datetime.now(timezone.utc)
    date = now.strftime("%Y%m%d")
    ts = now.strftime("%Y%m%d-%H%M%S")
    return f"{date}/{document_id}/{ts}_{filename}"


async def ensure_bucket() -> None:
    """若存储桶不存在则自动创建，用于应用启动时初始化。

    Raises:
        S3Error: MinIO 连接失败或权限不足时抛出。
    """
    def _ensure():
        client = _get_client()
        if not client.bucket_exists(settings.MINIO_BUCKET):
            client.make_bucket(settings.MINIO_BUCKET)

    await asyncio.to_thread(_ensure)


async def put_object(data: bytes, object_key: str, content_type: str) -> None:
    """将字节流上传至 MinIO。

    Args:
        data: 文件原始字节内容。
        object_key: MinIO 对象键，由 build_object_key 生成。
        content_type: MIME 类型，如 "application/pdf"。

    Raises:
        S3Error: 上传失败时抛出。
    """
    def _put():
        _get_client().put_object(
            settings.MINIO_BUCKET,
            object_key,
            BytesIO(data),
            length=len(data),
            content_type=content_type,
        )

    await asyncio.to_thread(_put)


async def get_presigned_url(object_key: str, expires_seconds: int = 3600) -> str:
    """生成对象的临时预签名下载 URL。

    Args:
        object_key: MinIO 对象键。
        expires_seconds: URL 有效期（秒），默认 3600。

    Returns:
        可直接供前端使用的预签名 GET URL。

    Raises:
        S3Error: 对象不存在或签名失败时抛出。
    """
    def _presign() -> str:
        return _get_client().presigned_get_object(
            settings.MINIO_BUCKET,
            object_key,
            expires=timedelta(seconds=expires_seconds),
        )

    return await asyncio.to_thread(_presign)


async def delete_object(object_key: str) -> None:
    """从 MinIO 删除指定对象。

    对象不存在时静默返回，不抛出异常，与删除文档记录的幂等语义保持一致。

    Args:
        object_key: MinIO 对象键。

    Raises:
        S3Error: 非"对象不存在"的其他存储错误时抛出。
    """
    def _delete():
        try:
            _get_client().remove_object(settings.MINIO_BUCKET, object_key)
        except S3Error as e:
            if e.code != "NoSuchKey":
                raise

    await asyncio.to_thread(_delete)
