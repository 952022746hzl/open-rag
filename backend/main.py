from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import auth, users
from app.config import settings
from app.database import AsyncSessionLocal
from app.repositories.user_repo import UserRepo


async def _init_admin() -> None:
    async with AsyncSessionLocal() as db:
        repo = UserRepo(db)
        if not await repo.username_exists(settings.INIT_ADMIN_USERNAME):
            await repo.create_user(
                username=settings.INIT_ADMIN_USERNAME,
                display_name="管理员",
                password=settings.INIT_ADMIN_PASSWORD,
                department_id=None,
                role="admin",
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    await _init_admin()
    yield


app = FastAPI(title="Open RAG API", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(users.router, prefix="/api/v1")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
