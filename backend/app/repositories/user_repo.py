from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import generate_refresh_token, hash_password
from app.models.department import Department
from app.models.user import User, UserRefreshToken


class UserRepo:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_username(self, username: str) -> tuple[User, str | None] | None:
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
        stmt = select(User.id).where(User.username == username)
        return (await self.db.execute(stmt)).scalar_one_or_none() is not None

    async def create_refresh_token(self, user_id: int) -> str:
        token = generate_refresh_token()
        expires_at = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        rt = UserRefreshToken(user_id=user_id, token=token, expires_at=expires_at)
        self.db.add(rt)
        await self.db.commit()
        return token

    async def get_refresh_token(self, token: str) -> UserRefreshToken | None:
        stmt = select(UserRefreshToken).where(UserRefreshToken.token == token)
        return (await self.db.execute(stmt)).scalar_one_or_none()

    async def revoke_refresh_token(self, token: str) -> None:
        stmt = update(UserRefreshToken).where(UserRefreshToken.token == token).values(revoked=True)
        await self.db.execute(stmt)
        await self.db.commit()

    async def update_password(self, user_id: int, new_password_hash: str) -> None:
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(password_hash=new_password_hash, is_first_login=False)
        )
        await self.db.execute(stmt)
        await self.db.commit()
