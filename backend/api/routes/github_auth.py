"""
NexusForge AI — GitHub OAuth API Routes
Handles OAuth2 login flow and token exchange for private repository support.
"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
import httpx
import structlog
import urllib.parse

from backend.core.config import settings
# Assuming there is an auth dependency, if not, we use a placeholder
# from backend.api.dependencies import get_current_user

log = structlog.get_logger()

router = APIRouter(prefix="/auth/github", tags=["auth"])

@router.get("/login")
async def github_login(request: Request):
    """Redirect to GitHub OAuth login."""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(
            status_code=400,
            detail="GitHub OAuth not configured. Please set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET in .env, or use the Quick Demo Sign-in button.",
        )

    # Resolve client host dynamically
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost:8000"
    scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
    if ":8000" in host:
        client_host = host.replace(":8000", ":3000")
    else:
        client_host = host

    redirect_uri = f"{scheme}://{client_host}/auth/github/callback"

    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": "repo user",
        "allow_signup": "true",
    }
    url = f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url)

@router.get("/callback")
async def github_callback(code: str, request: Request):
    """Handle OAuth callback and exchange code for token."""
    if not code:
        raise HTTPException(status_code=400, detail="Authorization code missing")

    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": settings.GITHUB_REDIRECT_URI,
            },
            headers={"Accept": "application/json"}
        )

        if resp.status_code != 200:
            log.error("github_oauth.token_exchange_failed", status=resp.status_code, response=resp.text)
            raise HTTPException(status_code=500, detail="Failed to exchange token")

        data = resp.json()
        access_token = data.get("access_token")

        if not access_token:
            log.error("github_oauth.no_token", response=data)
            raise HTTPException(status_code=400, detail="Invalid token response")

        # Fetch GitHub User Profile
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
        )
        if user_resp.status_code != 200:
            raise HTTPException(status_code=500, detail="Failed to fetch GitHub profile")

        gh_user = user_resp.json()
        gh_id = str(gh_user.get("id"))
        gh_username = gh_user.get("login")
        gh_email = gh_user.get("email") or f"{gh_username}@github.nexusforge.local"

        # Database integration
        from backend.core.database import get_db
        from backend.models import User
        from sqlalchemy import select
        from backend.core.security import create_access_token

        async for db in get_db():
            # Check if user exists by github_id
            result = await db.execute(select(User).where(User.github_id == gh_id))
            user = result.scalars().first()

            if not user:
                # Check if email exists
                result = await db.execute(select(User).where(User.email == gh_email))
                user = result.scalars().first()
                if user:
                    # Link account
                    user.github_id = gh_id
                    user.github_username = gh_username
                    user.github_access_token = access_token
                else:
                    # Create new user
                    user = User(
                        email=gh_email,
                        username=gh_username,
                        full_name=gh_user.get("name"),
                        avatar_url=gh_user.get("avatar_url"),
                        github_id=gh_id,
                        github_username=gh_username,
                        github_access_token=access_token,
                        is_verified=True
                    )
                    db.add(user)
            else:
                # Update existing user's token
                user.github_access_token = access_token
                user.github_username = gh_username

            await db.commit()
            await db.refresh(user)

            # Generate JWT Token
            jwt_token = create_access_token(str(user.id))

            # Redirect back to frontend or return JSON
            host = request.headers.get("x-forwarded-host") or request.headers.get("host") or "localhost:8000"
            scheme = request.headers.get("x-forwarded-proto") or request.url.scheme
            if ":8000" in host:
                frontend_host = host.replace(":8000", ":3000")
            else:
                frontend_host = host

            frontend_url = f"{scheme}://{frontend_host}"

            # If client called via fetch/JSON, return payload directly
            accept = request.headers.get("accept", "")
            if "application/json" in accept and "text/html" not in accept:
                return {
                    "access_token": jwt_token,
                    "token_type": "bearer",
                    "user_id": str(user.id),
                    "username": user.username,
                }

            return RedirectResponse(f"{frontend_url}/?token={jwt_token}")


