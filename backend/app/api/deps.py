from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_access_token
from app.database import get_db
from app.repositories.user_repo import UserRepo

_bearer = HTTPBearer()


@dataclass
class CurrentUser:
    user_id: int
    username: str
    display_name: str
    department_id: int | None
    department_name: str | None
    role: str


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
) -> CurrentUser:
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
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return current_user


def get_user_repo(db: AsyncSession = Depends(get_db)) -> UserRepo:
    return UserRepo(db)
