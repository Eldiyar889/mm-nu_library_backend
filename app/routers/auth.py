from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.dependencies import get_db, get_current_user
from app.models.user import User
from app.schemas.user import UserCreate, UserRead, TokenData
from app.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token
)

router = APIRouter(prefix="/auth", tags=["auth"])

class MessageResponse(BaseModel):
    message: str

@router.post("/register", response_model=UserRead)
async def register(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    query = select(User).where(User.username == user_in.username)
    result = await db.execute(query)
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User with this username already exists",
        )
    
    db_user = User(
        username=user_in.username,
        full_name=user_in.full_name,
        hashed_password=get_password_hash(user_in.password),
    )
    db.add(db_user)
    await db.commit()
    await db.refresh(db_user)
    return db_user

@router.post("/login")
async def login(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)]
):
    query = select(User).where(User.username == form_data.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    
    access_token = create_access_token(subject=user.id)
    refresh_token = create_refresh_token(subject=user.id)

    # Set Refresh Token in HttpOnly Cookie (Invisible to JS, very secure)
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        expires=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        samesite="lax",
        secure=settings.COOKIE_SECURE,
    )

    # Return Access Token in JSON (So JS can save it to localStorage)
    return {
        "access_token": access_token,
        "token_type": "bearer"
    }

@router.post("/refresh")
async def refresh_token(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_db)]
):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    try:
        payload = jwt.decode(
            refresh_token, 
            settings.SECRET_KEY, 
            algorithms=[settings.ALGORITHM]
        )
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )
        token_data = TokenData(user_id=payload.get("sub"))
    except (jwt.PyJWTError, ValidationError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
        )
    
    query = select(User).where(User.id == token_data.user_id)
    result = await db.execute(query)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Issue new tokens (Rotation)
    new_access_token = create_access_token(subject=user.id)
    new_refresh_token = create_refresh_token(subject=user.id)

    # Update the secure Refresh Cookie
    response.set_cookie(
        key="refresh_token",
        value=new_refresh_token,
        httponly=True,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        expires=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        samesite="lax",
        secure=settings.COOKIE_SECURE
    )
    
    # Return new Access Token for localStorage
    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }

@router.post("/logout", response_model=MessageResponse)
async def logout(
    response: Response,
    current_user: Annotated[User, Depends(get_current_user)]
):
    # Clear the secure refresh cookie
    response.delete_cookie("refresh_token")
    return {"message": "Successfully logged out"}
