from fastapi import APIRouter, Depends, status

from app.api.deps import CurrentUser, get_user_repo, require_admin
from app.repositories.user_repo import UserRepo
from app.schemas.auth import CreateUserRequest, CreateUserResponse
from app.services.auth_service import UserService

router = APIRouter(prefix="/users", tags=["users"])


def _get_service(repo: UserRepo = Depends(get_user_repo)) -> UserService:
    return UserService(repo)


@router.post("", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    req: CreateUserRequest,
    service: UserService = Depends(_get_service),
    _admin: CurrentUser = Depends(require_admin),
) -> CreateUserResponse:
    return await service.create_user(req)
