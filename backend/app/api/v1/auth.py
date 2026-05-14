"""认证相关路由控制器。

包含登录、刷新 Token、登出、获取当前用户信息及修改密码等接口。
"""

from fastapi import APIRouter, Cookie, Depends, Response, status

from app.api.deps import CurrentUser, get_current_user, get_user_repo
from app.repositories.user_repo import UserRepo
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, MeResponse, RefreshResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_service(repo: UserRepo = Depends(get_user_repo)) -> AuthService:
    """构造 AuthService 实例。

    Args:
        repo: 注入的用户仓储。

    Returns:
        AuthService 实例。
    """
    return AuthService(repo)


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    response: Response,
    service: AuthService = Depends(_get_service),
) -> LoginResponse:
    """用户登录。

    验证用户名和密码，成功后返回 Access Token 并在 HttpOnly Cookie 中写入 Refresh Token。

    Args:
        req: 包含用户名和密码的登录请求体。
        response: FastAPI Response 对象，用于设置 Cookie。
        service: 认证业务服务。

    Returns:
        包含 Access Token 及用户信息的登录响应。
    """
    return await service.login(req, response)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    service: AuthService = Depends(_get_service),
) -> RefreshResponse:
    """刷新 Access Token。

    使用 HttpOnly Cookie 中的 Refresh Token 换取新的 Access Token。

    Args:
        response: FastAPI Response 对象（预留，供后续扩展使用）。
        refresh_token: 从 Cookie 中读取的 Refresh Token，不存在时为 None。
        service: 认证业务服务。

    Returns:
        包含新 Access Token 的刷新响应。
    """
    return await service.refresh(refresh_token, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    service: AuthService = Depends(_get_service),
) -> None:
    """用户登出。

    吊销 Refresh Token 并清除 Cookie，无论 Token 是否存在均返回 204。

    Args:
        response: FastAPI Response 对象，用于清除 Cookie。
        refresh_token: 从 Cookie 中读取的 Refresh Token，不存在时为 None。
        service: 认证业务服务。
    """
    await service.logout(refresh_token, response)


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
) -> MeResponse:
    """获取当前登录用户的详细信息。

    Args:
        current_user: 由 JWT 解析得到的当前用户。
        service: 认证业务服务。

    Returns:
        当前用户的详细信息响应。
    """
    return await service.get_me(current_user.user_id)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    req: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
) -> None:
    """修改当前用户密码。

    需要提供正确的当前密码，新密码不能与当前密码相同。
    修改成功后 is_first_login 标记会被清除。

    Args:
        req: 包含当前密码和新密码的请求体。
        current_user: 由 JWT 解析得到的当前用户。
        service: 认证业务服务。
    """
    await service.change_password(current_user.user_id, req)
