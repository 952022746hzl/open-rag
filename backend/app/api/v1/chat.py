"""多轮问答路由控制器。"""

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, get_current_user, get_document_repo, get_qa_repo
from app.repositories.document_repo import DocumentRepo
from app.repositories.qa_repo import QaRepo
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/chat", tags=["chat"])


def _get_service(
    doc_repo: DocumentRepo = Depends(get_document_repo),
    qa_repo: QaRepo = Depends(get_qa_repo),
) -> ChatService:
    return ChatService(doc_repo, qa_repo)


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: ChatService = Depends(_get_service),
) -> ChatResponse:
    """多轮问答接口。

    session_id 为 null 时自动创建新会话并在响应中返回；
    后续轮次须携带上一轮返回的 session_id 以维持会话连续性。
    检索时自动从 JWT 提取身份，施加可见范围过滤。

    Args:
        req: 问答请求，含可选 session_id、问题及检索参数。
        current_user: 由 JWT 解析的当前用户。
        service: 问答业务服务。

    Returns:
        包含 session_id、turn_id、答案及引用来源的响应体。
    """
    return await service.chat(req, current_user)
