"""NexusForge AI — Auth Routes"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import (
    create_access_token,
    create_refresh_token,
    verify_refresh_token,
)
from backend.services.auth_service import AuthService

router = APIRouter()


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str
    password: str
    full_name: str | None = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    full_name: str | None
    avatar_url: str | None
    github_username: str | None
    is_verified: bool
    created_at: str

    model_config = {"from_attributes": True}


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Register a new user account."""
    auth_service = AuthService(db)
    user = await auth_service.register(
        email=request.email,
        username=request.username,
        password=request.password,
        full_name=request.full_name,
    )
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Authenticate and receive JWT tokens."""
    auth_service = AuthService(db)
    user = await auth_service.authenticate(request.email, request.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshRequest):
    """Exchange a refresh token for a new access token."""
    from jose import JWTError
    try:
        user_id = verify_refresh_token(request.refresh_token)
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )
    return TokenResponse(
        access_token=create_access_token(user_id),
        refresh_token=create_refresh_token(user_id),
    )


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    db: Annotated[AsyncSession, Depends(get_db)],
    credentials=Depends(__import__("fastapi.security", fromlist=["HTTPBearer"]).HTTPBearer()),
):
    """Get the current authenticated user's profile."""
    # Delegated to dependency
    raise HTTPException(status_code=501, detail="Use /api/auth/me with proper auth")
