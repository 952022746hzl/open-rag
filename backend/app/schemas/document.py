"""文档接口请求与响应 Schema。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    """文档元数据响应体。

    Attributes:
        id: 文档主键。
        file_name: 原始文件名。
        file_type: 文件类型，如 pdf、docx。
        uploader_id: 上传者用户 ID。
        department_id: 上传时用户所属部门 ID。
        visibility: 可见范围，public / department / private。
        tags: 标签列表。
        file_size: 文件字节数。
        status: 处理状态，processing / completed / failed。
        upload_time: 上传完成时刻。
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    file_type: str
    uploader_id: int
    department_id: int | None
    visibility: str
    tags: list[str] | None
    file_size: int | None
    status: str
    upload_time: datetime
