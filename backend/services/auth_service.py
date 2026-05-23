"""NexusForge AI — Auth Service"""
import secrets
import uuid
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.security import hash_password, verify_password
from backend.models import User


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(
        self,
        email: str,
        username: str,
        password: str,
        full_name: Optional[str] = None,
    ) -> User:
        """Register a new user."""
        from fastapi import HTTPException

        # Check email uniqueness
        existing = await self.db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already registered")

        # Check username uniqueness
        existing_username = await self.db.execute(select(User).where(User.username == username))
        if existing_username.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Username already taken")

        user = User(
            id=uuid.uuid4(),
            email=email,
            username=username,
            password_hash=hash_password(password),
            full_name=full_name,
            api_key=secrets.token_hex(32),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def authenticate(self, email: str, password: str) -> Optional[User]:
        """Verify credentials and return user if valid."""
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user or not user.password_hash:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    async def get_user_by_id(self, user_id: UUID) -> Optional[User]:
        """Get user by ID."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_user_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def create_or_update_github_user(
        self,
        github_id: str,
        github_username: str,
        email: str,
        full_name: Optional[str] = None,
        avatar_url: Optional[str] = None,
        access_token: Optional[str] = None,
    ) -> User:
        """Create or update a user from GitHub OAuth."""
        # Check if user exists by github_id
        result = await self.db.execute(select(User).where(User.github_id == github_id))
        user = result.scalar_one_or_none()

        if user:
            user.github_access_token = access_token
            user.avatar_url = avatar_url
            user.github_username = github_username
        else:
            # Check if email exists
            email_result = await self.db.execute(select(User).where(User.email == email))
            user = email_result.scalar_one_or_none()

            if user:
                # Link GitHub to existing account
                user.github_id = github_id
                user.github_username = github_username
                user.github_access_token = access_token
                user.avatar_url = avatar_url or user.avatar_url
            else:
                # Create new user from GitHub
                user = User(
                    id=uuid.uuid4(),
                    email=email,
                    username=github_username,
                    full_name=full_name,
                    avatar_url=avatar_url,
                    github_id=github_id,
                    github_username=github_username,
                    github_access_token=access_token,
                    is_verified=True,  # GitHub email is verified
                    api_key=secrets.token_hex(32),
                )
                self.db.add(user)

        await self.db.commit()
        await self.db.refresh(user)
        return user
