from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from uuid import UUID

from app.core.auth import AuthenticatedUser, get_current_user

router = APIRouter(prefix="/auth", tags=["authentication"])


class CurrentUserResponse(BaseModel):
    id: UUID
    auth_user_id: UUID
    organization_id: UUID
    email: str
    role: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@router.get("/me", response_model=CurrentUserResponse)
def get_me(current: AuthenticatedUser = Depends(get_current_user)):
    profile = current.profile
    return CurrentUserResponse(
        id=profile.id,
        auth_user_id=current.auth_user_id,
        organization_id=profile.organization_id,
        email=profile.email,
        role=profile.role,
        is_active=profile.is_active,
    )
