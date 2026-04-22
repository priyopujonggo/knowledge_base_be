from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User

router = APIRouter()

class UserUpdate(BaseModel):
    username: str | None = None

class UserResponse(BaseModel):
    id: int
    email: str
    username: str | None
    avatar_url: str | None

    class Config:
        from_attributes = True

@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user

@router.patch("/me", response_model=UserResponse)
async def update_profile(
    data: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if data.username:
        current_user.username = data.username
    await db.commit()
    await db.refresh(current_user)
    return current_user