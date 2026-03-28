from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.user import UserRead, UserUpdate
from app.security import get_password_hash, verify_password

router = APIRouter(prefix="/users", tags=["users"])

@router.get("/me", response_model=UserRead)
async def get_profile(
    current_user: Annotated[User, Depends(get_current_user)]
):
    return current_user

@router.patch("/me", response_model=UserRead)
async def update_profile(
        current_user: Annotated[User, Depends(get_current_user)],
        db: Annotated[AsyncSession, Depends(get_db)],
        user_in: UserUpdate
):
    update_data = user_in.model_dump(exclude_unset=True)

    # Sensitive fields that require current password verification
    sensitive_fields = ["username", "password"]
    requires_verification = any(field in update_data for field in sensitive_fields)

    if requires_verification:
        if not user_in.current_password or not verify_password(
            user_in.current_password, current_user.hashed_password
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Correct current password is required to update username or password"
            )

    if "username" in update_data and update_data["username"] != current_user.username:
        query = select(User).where(User.username == update_data["username"])
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )

    if "password" in update_data:
        update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

    # Remove current_password from update_data so it doesn't get treated as a model field
    update_data.pop("current_password", None)

    for field, value in update_data.items():
        setattr(current_user, field, value)

    try:
        db.add(current_user)
        await db.commit()
        await db.refresh(current_user)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Error updating profile. Username might already be in use."
        )
    return current_user

