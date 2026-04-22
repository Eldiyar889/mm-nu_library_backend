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
    # Извлекаем только те поля, которые прислал пользователь
    update_data = user_in.model_dump(exclude_unset=True)

    # 1. Проверка уникальности нового Username
    if "username" in update_data and update_data["username"] != current_user.username:
        query = select(User).where(User.username == update_data["username"])
        result = await db.execute(query)
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already registered"
            )

    # 2. Логика смены пароля
    # Проверяем, что пользователь передал все поля для смены пароля
    if user_in.new_password:
        # А) Проверяем совпадение новых паролей
        if user_in.new_password != user_in.repeat_new_password:
            raise HTTPException(status_code=400, detail="New passwords do not match")

        # Б) Проверяем старый пароль (обязательно!)
        if not verify_password(user_in.last_password, current_user.hashed_password):
            raise HTTPException(status_code=400, detail="Incorrect current password")

        # В) Хэшируем новый и удаляем лишнее из словаря
        update_data["hashed_password"] = get_password_hash(user_in.new_password)

    # Удаляем поля, которых нет в модели базы данных (User),
    # чтобы setattr не упал с ошибкой
    for field in ["new_password", "repeat_new_password", "last_password"]:
        update_data.pop(field, None)

    # 3. Обновление объекта
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
            detail="Error updating profile."
        )
    return current_user

