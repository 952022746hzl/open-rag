"""语义检索路由控制器。"""

from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, get_current_user, get_document_repo
from app.repositories.document_repo import DocumentRepo
from app.schemas.search import SearchRequest, SearchResponse
from app.services.search_service import SearchService

router = APIRouter(prefix="/search", tags=["search"])


def _get_service(repo: DocumentRepo = Depends(get_document_repo)) -> SearchService:
    return SearchService(repo)

# todo 调试接口 后面service 接入chat接口后删除
# rerank 后面可以接
# top_k 粗筛为 20~50 rerank后取topK5
# 默认 score_threshold 粗筛是 0.3 然后进行 rerank。
@router.post("", response_model=SearchResponse)
async def search(
    req: SearchRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: SearchService = Depends(_get_service),
) -> SearchResponse:
    """带权限过滤的语义检索。

    自动从 JWT 提取身份信息构建可见范围过滤，与请求体中的业务过滤条件合并后执行 ANN 搜索。

    Args:
        req: 检索请求，包含查询词、topK、阈值及可选业务过滤条件。
        current_user: 由 JWT 解析的当前用户。
        service: 检索业务服务。

    Returns:
        按相似度降序排列的检索结果列表及结果总数。
    """
    return await service.search(req, current_user)
