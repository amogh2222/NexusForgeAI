"""NexusForge AI — GitHub Integration Routes"""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import CurrentUser
from backend.core.security import create_access_token, create_refresh_token
from backend.services.auth_service import AuthService

router = APIRouter()

GITHUB_AUTH_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_URL = "https://api.github.com"


class GitHubOAuthCallbackRequest(BaseModel):
    code: str
    state: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_new_user: bool = False


@router.get("/oauth/url")
async def get_github_oauth_url():
    """Get the GitHub OAuth authorization URL."""
    if not settings.GITHUB_CLIENT_ID:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")

    params = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "redirect_uri": settings.GITHUB_REDIRECT_URI,
        "scope": "user:email,repo,read:org",
        "state": "nexusforge_oauth",
    }
    url = GITHUB_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return {"url": url}


@router.post("/oauth/callback", response_model=TokenResponse)
async def github_oauth_callback(
    request: GitHubOAuthCallbackRequest,
    db: AsyncSession = Depends(get_db),
):
    """Exchange GitHub OAuth code for NexusForge JWT tokens."""
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(status_code=503, detail="GitHub OAuth not configured")

    async with httpx.AsyncClient() as client:
        # Exchange code for access token
        token_response = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": request.code,
            },
            headers={"Accept": "application/json"},
            timeout=30,
        )

        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Failed to exchange GitHub code")

        token_data = token_response.json()
        github_access_token = token_data.get("access_token")

        if not github_access_token:
            raise HTTPException(status_code=400, detail="Invalid GitHub response")

        # Fetch user info from GitHub
        user_response = await client.get(
            f"{GITHUB_API_URL}/user",
            headers={"Authorization": f"token {github_access_token}"},
        )
        user_data = user_response.json()

        # Fetch primary email
        email_response = await client.get(
            f"{GITHUB_API_URL}/user/emails",
            headers={"Authorization": f"token {github_access_token}"},
        )
        emails = email_response.json()
        primary_email = next(
            (e["email"] for e in emails if e.get("primary") and e.get("verified")),
            user_data.get("email") or f"{user_data['login']}@github.com",
        )

    # Create or update user
    auth_service = AuthService(db)
    existing = await auth_service.get_user_by_email(primary_email)
    is_new = existing is None

    user = await auth_service.create_or_update_github_user(
        github_id=str(user_data["id"]),
        github_username=user_data["login"],
        email=primary_email,
        full_name=user_data.get("name"),
        avatar_url=user_data.get("avatar_url"),
        access_token=github_access_token,
    )

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
        is_new_user=is_new,
    )


@router.get("/repos")
async def list_github_repos(
    current_user: CurrentUser,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=30, le=100),
):
    """List the current user's GitHub repositories."""
    if not current_user.github_access_token:
        raise HTTPException(status_code=400, detail="GitHub account not connected")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/user/repos",
            headers={"Authorization": f"token {current_user.github_access_token}"},
            params={"sort": "updated", "per_page": per_page, "page": page},
        )
        repos = response.json()

    return {
        "repos": [
            {
                "id": r["id"],
                "name": r["name"],
                "full_name": r["full_name"],
                "description": r.get("description"),
                "private": r["private"],
                "url": r["html_url"],
                "clone_url": r["clone_url"],
                "default_branch": r["default_branch"],
                "language": r.get("language"),
                "stargazers_count": r.get("stargazers_count", 0),
                "updated_at": r.get("updated_at"),
            }
            for r in repos
            if isinstance(r, dict)
        ]
    }


@router.get("/repos/{owner}/{repo}/branches")
async def list_repo_branches(
    owner: str,
    repo: str,
    current_user: CurrentUser,
):
    """List branches for a GitHub repository."""
    if not current_user.github_access_token:
        raise HTTPException(status_code=400, detail="GitHub account not connected")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/branches",
            headers={"Authorization": f"token {current_user.github_access_token}"},
        )
        branches = response.json()

    return {"branches": [b["name"] for b in branches if isinstance(b, dict)]}


@router.get("/repos/{owner}/{repo}/pulls")
async def list_pull_requests(
    owner: str,
    repo: str,
    current_user: CurrentUser,
    state: str = "open",
):
    """List pull requests for AI analysis."""
    if not current_user.github_access_token:
        raise HTTPException(status_code=400, detail="GitHub account not connected")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{GITHUB_API_URL}/repos/{owner}/{repo}/pulls",
            headers={"Authorization": f"token {current_user.github_access_token}"},
            params={"state": state, "per_page": 20},
        )
        prs = response.json()

    return {
        "pull_requests": [
            {
                "number": pr["number"],
                "title": pr["title"],
                "author": pr["user"]["login"],
                "state": pr["state"],
                "url": pr["html_url"],
                "base_branch": pr["base"]["ref"],
                "head_branch": pr["head"]["ref"],
                "created_at": pr["created_at"],
                "body": (pr.get("body") or "")[:500],
            }
            for pr in prs
            if isinstance(pr, dict)
        ]
    }
