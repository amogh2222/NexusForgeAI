"""
NexusForge AI — GitHub Integration API Routes
Handles fetching GitHub repositories for the authenticated user.
"""
from fastapi import APIRouter, Depends, HTTPException
import httpx
import structlog
from backend.core.dependencies import get_current_user
from backend.models import User

log = structlog.get_logger()
router = APIRouter(tags=["github"])

@router.get("/repos")
async def get_github_repos(user: User = Depends(get_current_user)):
    """Fetch all GitHub repositories for the authenticated user."""
    if not user.github_access_token:
        raise HTTPException(status_code=400, detail="GitHub account not linked")

    async with httpx.AsyncClient() as client:
        # Fetch up to 100 repositories
        resp = await client.get(
            "https://api.github.com/user/repos?per_page=100&sort=updated",
            headers={
                "Authorization": f"Bearer {user.github_access_token}",
                "Accept": "application/vnd.github.v3+json"
            }
        )

        if resp.status_code != 200:
            log.error("github_api.fetch_repos_failed", status=resp.status_code, response=resp.text)
            raise HTTPException(status_code=500, detail="Failed to fetch repositories from GitHub")

        repos_data = resp.json()
        
        # Format the response for the frontend
        formatted_repos = []
        for repo in repos_data:
            formatted_repos.append({
                "id": repo["id"],
                "name": repo["name"],
                "full_name": repo["full_name"],
                "private": repo["private"],
                "html_url": repo["html_url"],
                "description": repo["description"],
                "updated_at": repo["updated_at"],
                "clone_url": repo["clone_url"],
                "default_branch": repo["default_branch"]
            })

        return {"repositories": formatted_repos}
