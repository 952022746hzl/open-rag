"""用户数据访问仓储。

封装所有与用户表（users）及刷新令牌表（user_refresh_tokens）相关的数据库操作。
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import generate_refresh_token, hash_password
from app.models.department import Department
from app.models.user import User, UserRefreshToken


class UserRepo:
    """用户相关数据访问对象。

    Attributes:
        db: 当前请求的异步数据库会话。
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_username(self, username: str) -> tuple[User, str | None] | None:
        """通过用户名查询用户及其部门名称。

        Args:
            username: 待查询的用户名。

        Returns:
            匹配时返回 (User, 部门名称) 元组，部门名称不存在时为 None；
            用户不存在时返回 None。
        """
        stmt = (
            select(User, Department.department_name)
            .outerjoin(Department, User.department_id == Department.id)
            .where(User.username == username)
        )
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None
        return row.User, row.department_name

    async def get_by_id(self, user_id: int) -> tuple[User, str | None] | None:
        """通过主键查询用户及其部门名称。

        Args:
            user_id: 用户主键 ID。

        Returns:
            匹配时返回 (User, 部门名称) 元组，部门名称不存在时为 None；
            用户不存在时返回 None。
        """
        stmt = (
            select(User, Department.department_name)
            .outerjoin(Department, User.department_id == Department.id)
            .where(User.id == user_id)
        )
        row = (await self.db.execute(stmt)).first()
        if row is None:
            return None
        return row.User, row.department_name

    async def create_user(
        self,
        username: str,
        display_name: str,
        password: str,
        department_id: int | None,
        role: str,
    ) -> User:
        """创建新用户并持久化到数据库。

        密码在写入前会经过 bcrypt 哈希处理。
        新用户的 is_first_login 默认为 True（由模型层默认值控制）。

        Args:
            username: 登录用户名，须全局唯一。
            display_name: 用户显示名称。
            password: 明文密码，方法内部完成哈希。
            department_id: 所属部门 ID，可为 None。
            role: 角色标识，如 "admin" 或 "member"。

        Returns:
            已持久化并刷新的 User ORM 对象。
        """
        user = User(
            username=username,
            display_name=display_name,
            password_hash=hash_password(password),
            department_id=department_id,
            role=role,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def username_exists(self, username: str) -> bool:
        """检查用户名是否已被占用。

        Args:
            username: 待检查的用户名。

        Returns:
            用户名已存在返回 True，否则返回 False。
        """
        stmt = select(User.id).where(User.username == username)
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def create_refresh_token(self, user_id: int) -> str:
        """为指定用户生成并持久化 Refresh Token。

        Token 有效期由配置项 REFRESH_TOKEN_EXPIRE_DAYS 控制。

        Args:
            user_id: 目标用户的主键 ID。

        Returns:
            生成的 Refresh Token 字符串（64 位十六进制）。
        """
        token = generate_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        rt = UserRefreshToken(user_id=user_id, token=token, expires_at=expires_at)
        self.db.add(rt)
        await self.db.commit()
        return token

    async def get_refresh_token(self, token: str) -> UserRefreshToken | None:
        """通过 Token 字符串查询刷新令牌记录。

        Args:
            token: Refresh Token 字符串。

        Returns:
            匹配的 UserRefreshToken 对象；不存在时返回 None。
        """
        stmt = select(UserRefreshToken).where(UserRefreshToken.token == token)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def revoke_refresh_token(self, token: str) -> None:
        """将指定 Refresh Token 标记为已吊销。

        Args:
            token: 待吊销的 Refresh Token 字符串。
        """
        stmt = update(UserRefreshToken).where(UserRefreshToken.token == token).values(revoked=True)
        await self.db.execute(stmt)
        await self.db.commit()

    async def update_password(self, user_id: int, new_password_hash: str) -> None:
        """更新用户密码并清除首次登录标记。

        修改密码时同步将 is_first_login 置为 False，
        表示用户已完成首次登录的密码修改流程。

        Args:
            user_id: 目标用户的主键 ID。
            new_password_hash: 已经过 bcrypt 哈希的新密码。
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(password_hash=new_password_hash, is_first_login=False)
        )
        await self.db.execute(stmt)
        await self.db.commit()
