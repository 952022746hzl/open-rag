"""用户管理路由控制器。

提供管理员专用的用户管理接口，目前包含创建用户功能。
"""

from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, get_user_repo, require_admin
from app.repositories.user_repo import UserRepo
from app.schemas.auth import CreateUserRequest, CreateUserResponse
from app.services.auth_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


def _get_service(repo: UserRepo = Depends(get_user_repo)) -> UserService:
    """构造 UserService 实例。

    Args:
        repo: 注入的用户仓储。

    Returns:
        UserService 实例。
    """
    return UserService(repo)


@router.post("", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    req: CreateUserRequest,
    service: UserService = Depends(_get_service),
    _admin: CurrentUser = Depends(require_admin),
) -> CreateUserResponse:
    """创建新用户（仅管理员可调用）。

    新创建的用户 is_first_login 默认为 True，首次登录后需修改密码。

    Args:
        req: 包含用户名、显示名称、密码、部门及角色的创建请求体。
        service: 用户业务服务。
        _admin: 管理员权限校验依赖，不直接使用，仅用于触发鉴权。

    Returns:
        新创建用户的基本信息响应。
    """
    return await service.create_user(req)
