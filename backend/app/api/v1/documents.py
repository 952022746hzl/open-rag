"""文档管理路由控制器。

目前提供文件上传接口，后续扩展列表、下载、更新、删除。
"""

from fastapi import APIRouter, Depends, Form, UploadFile, status

from app.api.deps import CurrentUser, get_current_user, get_document_repo
from app.repositories.document_repo import DocumentRepo
from app.schemas.document import DocumentResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_service(repo: DocumentRepo = Depends(get_document_repo)) -> DocumentService:
    return DocumentService(repo)


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile,
    visibility: str = Form(...),
    tags: str | None = Form(default=None),
    current_user: CurrentUser = Depends(get_current_user),
    service: DocumentService = Depends(_get_service),
) -> DocumentResponse:
    """上传文档文件。

    接受 multipart/form-data 格式，支持 pdf / docx / xlsx / pptx / txt / md，
    单文件上限 50 MB。uploader_id 与 department_id 由服务端从 JWT 中提取。

    Args:
        file: 上传的文件对象。
        visibility: 可见范围，public / department / private。
        tags: 逗号分隔的标签字符串，如 "质量标准,焊接"；可选。
        current_user: 由 JWT 解析的当前用户。
        service: 文档业务服务。

    Returns:
        包含文档元数据的响应体，status 为 completed。
    """
    doc = await service.upload(file, visibility, tags, current_user)
    return DocumentResponse.model_validate(doc)
