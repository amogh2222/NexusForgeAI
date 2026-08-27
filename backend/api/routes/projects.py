"""NexusForge AI — Projects Routes"""
import uuid
from datetime import datetime
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from backend.core.dependencies import CurrentUser, DBSession, Pagination
from backend.models import Project

router = APIRouter()


class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: str = "#7c3aed"


class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    color: str
    is_archived: bool
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[ProjectResponse])
async def list_projects(
    current_user: CurrentUser,
    db: DBSession,
    pagination: Pagination,
):
    result = await db.execute(
        select(Project)
        .where(Project.user_id == current_user.id, Project.is_archived.is_(False))
        .offset(pagination.skip)
        .limit(pagination.limit)
        .order_by(Project.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    request: ProjectCreate,
    current_user: CurrentUser,
    db: DBSession,
):
    project = Project(
        id=uuid.uuid4(),
        user_id=current_user.id,
        name=request.name,
        description=request.description,
        color=request.color,
    )
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(project_id: str, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(Project).where(Project.id == UUID(project_id), Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: str,
    request: ProjectUpdate,
    current_user: CurrentUser,
    db: DBSession,
):
    result = await db.execute(
        select(Project).where(Project.id == UUID(project_id), Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if request.name is not None:
        project.name = request.name
    if request.description is not None:
        project.description = request.description
    if request.color is not None:
        project.color = request.color

    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str, current_user: CurrentUser, db: DBSession):
    result = await db.execute(
        select(Project).where(Project.id == UUID(project_id), Project.user_id == current_user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()
