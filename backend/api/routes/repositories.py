"""NexusForge AI — Repository Routes"""
import os
import uuid
from typing import Annotated, Optional
from datetime import datetime

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.config import settings
from backend.core.database import get_db
from backend.core.dependencies import CurrentUser
from backend.models import Repository
from backend.services.repository_service import RepositoryService

router = APIRouter()


class RepositoryResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    source_type: str
    source_url: Optional[str]
    github_branch: str
    indexed_status: str
    indexing_progress: int
    total_files: int
    indexed_files: int
    total_chunks: int
    detected_languages: Optional[dict]
    detected_frameworks: Optional[dict]
    summary: Optional[str]
    file_tree: Optional[dict]
    created_at: datetime

    model_config = {"from_attributes": True}


class GitHubRepoRequest(BaseModel):
    project_id: str
    url: str
    branch: str = "main"
    github_token: Optional[str] = None  # For private repos


@router.post("/upload", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def upload_repository(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Upload a repository as a ZIP file.
    Triggers async indexing via Celery.
    """
    # Validate file extension
    if not file.filename or not file.filename.endswith(".zip"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only ZIP files are supported",
        )

    # Validate file size
    max_size = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    content = await file.read()
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit",
        )

    # Save file
    upload_path = os.path.join(settings.UPLOAD_DIR, str(uuid.uuid4()))
    os.makedirs(upload_path, exist_ok=True)
    zip_path = os.path.join(upload_path, file.filename)
    async with aiofiles.open(zip_path, "wb") as f:
        await f.write(content)

    # Create repo record + trigger indexing
    repo_service = RepositoryService(db)
    repository = await repo_service.create_from_zip(
        project_id=uuid.UUID(project_id),
        user_id=current_user.id,
        zip_path=zip_path,
        name=file.filename.replace(".zip", ""),
    )

    return repository


@router.post("/github", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def connect_github_repository(
    request: GitHubRepoRequest,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Clone and index a GitHub repository (public or private).
    Uses OAuth token if provided (private repos).
    """
    repo_service = RepositoryService(db)
    repository = await repo_service.create_from_github(
        project_id=uuid.UUID(request.project_id),
        user_id=current_user.id,
        github_url=request.url,
        branch=request.branch,
        github_token=request.github_token or current_user.github_access_token,
    )
    return repository


@router.get("/", response_model=list[RepositoryResponse])
async def list_repositories(
    project_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """List all repositories for a project."""
    from sqlalchemy import select
    from backend.models import Project

    project_uuid = uuid.UUID(project_id)
    proj_result = await db.execute(
        select(Project).where(Project.id == project_uuid, Project.user_id == current_user.id)
    )
    if not proj_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")

    result = await db.execute(
        select(Repository)
        .where(Repository.project_id == project_uuid)
        .order_by(Repository.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{repo_id}", response_model=RepositoryResponse)
async def get_repository(
    repo_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get repository details and indexing status."""
    repo_service = RepositoryService(db)
    repo = await repo_service.get_by_id(uuid.UUID(repo_id), current_user.id)
    if not repo:
        raise HTTPException(status_code=404, detail="Repository not found")
    return repo


@router.get("/{repo_id}/tree")
async def get_file_tree(
    repo_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the file tree structure of a repository."""
    repo_service = RepositoryService(db)
    tree = await repo_service.get_file_tree(uuid.UUID(repo_id), current_user.id)
    return {"tree": tree}


@router.post("/{repo_id}/reindex")
async def reindex_repository(
    repo_id: str,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Trigger re-indexing of a repository."""
    repo_service = RepositoryService(db)
    await repo_service.trigger_reindex(uuid.UUID(repo_id), current_user.id)
    return {"message": "Re-indexing started", "repository_id": repo_id}
