"""
NexusForge AI — GitHub OAuth API Routes
Handles OAuth2 login flow and token exchange for private repository support.
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
import httpx
import structlog
from typing import Optional
import urllib.parse

from backend.core.config import settings
# Assuming there is an auth dependency, if not, we use a placeholder
# from backend.api.dependencies import get_current_user

log = structlog.get_logger()

router = APIRouter(prefix="/auth/github", tags=["auth"])

@router.get("/login")
async def github_login():
    """Redirect to GitHub OAuth login."""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")
    
    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_REDIRECT_URI,
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
            
        # In a real app, we would save this token to the user's profile in the DB here
        # user = await get_current_user(request)
        # await user.save_github_token(access_token)
        
        log.info("github_oauth.success")
        return {"status": "success", "message": "GitHub account linked successfully"}

