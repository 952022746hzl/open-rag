from fastapi import APIRouter, Cookie, Depends, Response, status

from app.api.deps import CurrentUser, get_current_user, get_user_repo
from app.repositories.user_repo import UserRepo
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LoginResponse, MeResponse, RefreshResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


def _get_service(repo: UserRepo = Depends(get_user_repo)) -> AuthService:
    return AuthService(repo)


@router.post("/login", response_model=LoginResponse)
async def login(
    req: LoginRequest,
    response: Response,
    service: AuthService = Depends(_get_service),
) -> LoginResponse:
    return await service.login(req, response)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    service: AuthService = Depends(_get_service),
) -> RefreshResponse:
    return await service.refresh(refresh_token, response)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    service: AuthService = Depends(_get_service),
) -> None:
    await service.logout(refresh_token, response)


@router.get("/me", response_model=MeResponse)
async def me(
    current_user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
) -> MeResponse:
    return await service.get_me(current_user.user_id)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    req: ChangePasswordRequest,
    current_user: CurrentUser = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
) -> None:
    await service.change_password(current_user.user_id, req)
