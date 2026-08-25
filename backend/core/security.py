"""
NexusForge AI — JWT Security
Token creation, validation, and password hashing.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt

from backend.core.config import settings

import bcrypt

def hash_password(password: str) -> str:
    passwd_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(passwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    passwd_bytes = plain_password.encode('utf-8')
    hashed_bytes = hashed_password.encode('utf-8')
    try:
        return bcrypt.checkpw(passwd_bytes, hashed_bytes)
    except Exception:
        return False


# ─── JWT Tokens ──────────────────────────────────────────────────
def create_access_token(subject: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create a short-lived access token."""
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": subject,
        "exp": expire,
        "type": "access",
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str) -> str:
    """Create a long-lived refresh token."""
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": subject,
        "exp": expire,
        "type": "refresh",
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict:
    """Decode and validate a JWT token. Raises JWTError on failure."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise JWTError(f"Token validation failed: {e}") from e


def verify_access_token(token: str) -> str:
    """Verify an access token and return the subject (user_id)."""
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise JWTError("Invalid token type")
    sub = payload.get("sub")
    if not sub:
        raise JWTError("Token missing subject")
    return sub


def verify_refresh_token(token: str) -> str:
    """Verify a refresh token and return the subject (user_id)."""
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise JWTError("Invalid token type")
    sub = payload.get("sub")
    if not sub:
        raise JWTError("Token missing subject")
    return sub
