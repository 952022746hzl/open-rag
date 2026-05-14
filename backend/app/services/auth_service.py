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
    def __init__(self, repo: UserRepo):
        self.repo = repo

    async def login(self, req: LoginRequest, response: Response) -> LoginResponse:
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
        if refresh_token:
            await self.repo.revoke_refresh_token(refresh_token)
        response.delete_cookie(_COOKIE_NAME)

    async def change_password(self, user_id: int, req: ChangePasswordRequest) -> None:
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
    def __init__(self, repo: UserRepo):
        self.repo = repo

    async def create_user(self, req: CreateUserRequest) -> CreateUserResponse:
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
