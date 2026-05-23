"""
NexusForge AI — FastAPI Dependencies
Reusable dependency injection factories.
"""
from typing import Annotated, Optional
from uuid import UUID

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db
from backend.core.security import verify_access_token
from backend.models import User
from backend.services.auth_service import AuthService

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Extract and validate the current user from JWT bearer token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        user_id = verify_access_token(credentials.credentials)
    except JWTError:
        raise credentials_exception

    auth_service = AuthService(db)
    user = await auth_service.get_user_by_id(UUID(user_id))
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user")
    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        HTTPBearer(auto_error=False)
    ),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Optional auth — returns None if no token provided."""
    if not credentials:
        return None
    try:
        user_id = verify_access_token(credentials.credentials)
        auth_service = AuthService(db)
        return await auth_service.get_user_by_id(UUID(user_id))
    except Exception:
        return None


# ─── Pagination ──────────────────────────────────────────────────
class PaginationParams:
    def __init__(
        self,
        skip: int = Query(default=0, ge=0, description="Number of items to skip"),
        limit: int = Query(default=20, ge=1, le=100, description="Number of items to return"),
    ):
        self.skip = skip
        self.limit = limit


# ─── Type Aliases ────────────────────────────────────────────────
CurrentUser = Annotated[User, Depends(get_current_user)]
DBSession = Annotated[AsyncSession, Depends(get_db)]
Pagination = Annotated[PaginationParams, Depends()]
