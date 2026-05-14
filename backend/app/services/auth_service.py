"""认证与用户业务服务层。

AuthService 处理登录、Token 刷新、登出、密码修改及用户信息查询。
UserService 处理管理员创建用户的业务逻辑。
"""

from datetime import datetime, timezone

from fastapi import HTTPException, Response, status

from app.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.user_repo import UserRepo
from app.schemas.auth import (
    ChangePasswordRequest,
    CreateUserRequest,
    CreateUserResponse,
    LoginRequest,
    LoginResponse,
    MeResponse,
    RefreshResponse,
    UserInfo,
)

_COOKIE_NAME = "refresh_token"
_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400


class AuthService:
    """处理用户认证相关业务逻辑。

    Attributes:
        repo: 用户数据访问仓储。
    """

    def __init__(self, repo: UserRepo):
        self.repo = repo

    async def login(self, req: LoginRequest, response: Response) -> LoginResponse:
        """验证凭据并颁发 Token。

        校验用户名和密码，通过后生成 Access Token 与 Refresh Token。
        Refresh Token 以 HttpOnly Cookie 写入响应，Access Token 在响应体中返回。

        Args:
            req: 包含用户名和密码的登录请求。
            response: FastAPI Response 对象，用于写入 Cookie。

        Returns:
            包含 Access Token、过期时间、用户信息及首次登录标记的响应。

        Raises:
            HTTPException: 用户不存在或密码错误时返回 401；账户被禁用时返回 401。
        """
        result = await self.repo.get_by_username(req.username)
        if result is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
        user, department_name = result

        if not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="账户已被禁用")

        if not verify_password(req.password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")

        access_token = create_access_token(
            sub=str(user.id),
            username=user.username,
            display_name=user.display_name,
            department_id=str(user.department_id) if user.department_id else None,
            department_name=department_name,
            role=user.role,
        )
        refresh_token = await self.repo.create_refresh_token(user.id)

        response.set_cookie(
            key=_COOKIE_NAME,
            value=refresh_token,
            httponly=True,
            secure=settings.COOKIE_SECURE,
            samesite=settings.COOKIE_SAMESITE,
            max_age=_COOKIE_MAX_AGE,
        )

        return LoginResponse(
            access_token=access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS,
            user=UserInfo(
                id=user.id,
                username=user.username,
                display_name=user.display_name,
                department_id=user.department_id,
                department_name=department_name,
                role=user.role,
            ),
            require_password_change=user.is_first_login,
        )

    async def refresh(self, refresh_token: str | None, response: Response) -> RefreshResponse:
        """使用 Refresh Token 换取新的 Access Token。

        校验 Refresh Token 的有效性、吊销状态及过期时间，通过后重新签发 Access Token。
        Refresh Token 本身不轮换，仍保持原有有效期。

        Args:
            refresh_token: 从 Cookie 中读取的 Refresh Token，为 None 时直接报错。
            response: FastAPI Response 对象（预留扩展用）。

        Returns:
            包含新 Access Token 及过期时间的响应。

        Raises:
            HTTPException: Token 缺失、无效或已过期时返回 401；用户不存在或被禁用时返回 401。
        """
        if not refresh_token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="缺少 refresh_token")

        rt = await self.repo.get_refresh_token(refresh_token)
        if rt is None or rt.revoked:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="refresh_token 无效")

        if rt.expires_at < datetime.now(timezone.utc):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="refresh_token 已过期")

        result = await self.repo.get_by_id(rt.user_id)
        if result is None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
        user, department_name = result

        if not user.is_active:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="账户已被禁用")

        access_token = create_access_token(
            sub=str(user.id),
            username=user.username,
            display_name=user.display_name,
            department_id=str(user.department_id) if user.department_id else None,
            department_name=department_name,
            role=user.role,
        )
        return RefreshResponse(access_token=access_token, expires_in=settings.ACCESS_TOKEN_EXPIRE_SECONDS)

    async def logout(self, refresh_token: str | None, response: Response) -> None:
        """登出当前用户。

        若 Cookie 中存在 Refresh Token 则将其吊销，并清除响应中的 Cookie。
        Token 不存在时静默处理，不报错。

        Args:
            refresh_token: 从 Cookie 中读取的 Refresh Token，可为 None。
            response: FastAPI Response 对象，用于清除 Cookie。
        """
        if refresh_token:
            await self.repo.revoke_refresh_token(refresh_token)
        response.delete_cookie(_COOKIE_NAME)

    async def change_password(self, user_id: int, req: ChangePasswordRequest) -> None:
        """修改用户密码。

        校验当前密码正确性，并确保新密码与当前密码不同。
        修改成功后同时清除 is_first_login 标记。

        Args:
            user_id: 当前登录用户的主键 ID。
            req: 包含当前密码和新密码的请求体。

        Raises:
            HTTPException: 用户不存在时返回 404；当前密码错误或新旧密码相同时返回 400。
        """
        result = await self.repo.get_by_id(user_id)
        if result is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")
        user, _ = result

        if not verify_password(req.current_password, user.password_hash):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="当前密码错误")

        if req.current_password == req.new_password:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="新密码不能与当前密码相同")

        await self.repo.update_password(user_id, hash_password(req.new_password))

    async def get_me(self, user_id: int) -> MeResponse:
        """查询当前用户的详细信息。

        Args:
            user_id: 当前登录用户的主键 ID。

        Returns:
            包含用户完整信息的响应对象。

        Raises:
            HTTPException: 用户不存在时返回 404。
        """
        result = await self.repo.get_by_id(user_id)
        if result is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="用户不存在")
        user, department_name = result
        return MeResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            department_id=user.department_id,
            department_name=department_name,
            role=user.role,
            created_at=user.created_at,
        )


class UserService:
    """处理用户管理相关业务逻辑（管理员操作）。

    Attributes:
        repo: 用户数据访问仓储。
    """

    def __init__(self, repo: UserRepo):
        self.repo = repo

    async def create_user(self, req: CreateUserRequest) -> CreateUserResponse:
        """创建新用户。

        校验用户名唯一性后入库，密码经 bcrypt 哈希存储。
        新用户 is_first_login 默认为 True，首次登录后须修改密码。

        Args:
            req: 包含用户名、显示名称、密码、部门 ID 及角色的请求体。

        Returns:
            新创建用户的基本信息响应。

        Raises:
            HTTPException: 用户名已存在时返回 400。
        """
        if await self.repo.username_exists(req.username):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="用户名已存在")
        user = await self.repo.create_user(
            username=req.username,
            display_name=req.display_name,
            password=req.password,
            department_id=req.department_id,
            role=req.role,
        )
        return CreateUserResponse(
            id=user.id,
            username=user.username,
            display_name=user.display_name,
            department_id=user.department_id,
            role=user.role,
            is_active=user.is_active,
        )
