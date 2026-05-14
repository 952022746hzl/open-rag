from datetime import datetime

from pydantic import BaseModel, field_validator


def _check_password_complexity(v: str) -> str:
    if len(v) < 8:
        raise ValueError("密码长度至少8位")
    if not any(c.isalpha() for c in v):
        raise ValueError("密码必须包含字母")
    if not any(c.isdigit() for c in v):
        raise ValueError("密码必须包含数字")
    return v


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: int
    username: str
    display_name: str
    department_id: int | None
    department_name: str | None
    role: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfo
    require_password_change: bool = False


class RefreshResponse(BaseModel):
    access_token: str
    expires_in: int


class MeResponse(BaseModel):
    id: int
    username: str
    display_name: str
    department_id: int | None
    department_name: str | None
    role: str
    created_at: datetime


class CreateUserRequest(BaseModel):
    username: str
    display_name: str
    password: str
    department_id: int | None = None
    role: str = "member"

    @field_validator("password")
    @classmethod
    def password_complexity(cls, v: str) -> str:
        return _check_password_complexity(v)

    @field_validator("role")
    @classmethod
    def role_valid(cls, v: str) -> str:
        if v not in ("admin", "member"):
            raise ValueError("角色只能是 admin 或 member")
        return v


class CreateUserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    department_id: int | None
    role: str
    is_active: bool


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def new_password_complexity(cls, v: str) -> str:
        return _check_password_complexity(v)
