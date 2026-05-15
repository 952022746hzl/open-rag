from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import get_db
from app.repositories.document_repo import DocumentRepo
from app.repositories.user_repo import UserRepo

_bearer = HTTPBearer()


@dataclass
class CurrentUser:
    """已通过 JWT 认证的当前请求用户信息。

    Attributes:
        user_id: 用户主键 ID。
        username: 登录用户名。
        display_name: 显示名称。
        department_id: 所属部门 ID，未分配部门时为 None。
        department_name: 所属部门名称，未分配部门时为 None。
        role: 角色标识，如 "admin" 或 "member"。
    """

    user_id: int
    username: str
    display_name: str
    department_id: int | None
    department_name: str | None
    role: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> CurrentUser:
    """从 Authorization Bearer Token 中解析当前用户。

    Args:
        credentials: FastAPI HTTPBearer 提取的凭证对象。

    Returns:
        解析成功后填充的 CurrentUser 实例。

    Raises:
        HTTPException: Token 解析失败或已过期时返回 401。
    """
    try:
        payload = decode_access_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Token 无效或已过期")

    dept_id = payload.get("department_id")
    return CurrentUser(
        user_id=int(payload["sub"]),
        username=payload["username"],
        display_name=payload["display_name"],
        department_id=int(dept_id) if dept_id else None,
        department_name=payload.get("department_name"),
        role=payload["role"],
    )


async def require_admin(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    """校验当前用户是否具有管理员角色。

    Args:
        current_user: 由 get_current_user 解析得到的当前用户。

    Returns:
        校验通过的 CurrentUser 实例。

    Raises:
        HTTPException: 非管理员用户时返回 403。
    """
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


def get_document_repo(db: AsyncSession = Depends(get_db)) -> DocumentRepo:
    """创建并返回 DocumentRepo 实例。

    Args:
        db: 由 get_db 注入的异步数据库会话。

    Returns:
        绑定当前会话的 DocumentRepo 实例。
    """
    return DocumentRepo(db)


def get_user_repo(db: AsyncSession = Depends(get_db)) -> UserRepo:
    """创建并返回 UserRepo 实例。

    Args:
        db: 由 get_db 注入的异步数据库会话。

    Returns:
        绑定当前会话的 UserRepo 实例。
    """
    return UserRepo(db)
