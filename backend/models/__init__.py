"""NexusForge AI — All SQLAlchemy ORM Models"""

import uuid
from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.core.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ════════════════════════════════════════════════════════════════════
# USERS
# ════════════════════════════════════════════════════════════════════
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    api_key: Mapped[Optional[str]] = mapped_column(String(64), unique=True, nullable=True, index=True)

    # GitHub OAuth
    github_id: Mapped[Optional[str]] = mapped_column(String(50), unique=True, nullable=True)
    github_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    github_access_token: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="owner", cascade="all, delete-orphan")


# ════════════════════════════════════════════════════════════════════
# PROJECTS
# ════════════════════════════════════════════════════════════════════
class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[str] = mapped_column(String(7), default="#7c3aed")  # Hex color for UI
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="projects")
    repositories: Mapped[List["Repository"]] = relationship("Repository", back_populates="project", cascade="all, delete-orphan")
    chats: Mapped[List["Chat"]] = relationship("Chat", back_populates="project", cascade="all, delete-orphan")
    executions: Mapped[List["Execution"]] = relationship("Execution", back_populates="project", cascade="all, delete-orphan")
    agent_logs: Mapped[List["AgentLog"]] = relationship("AgentLog", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_project_user_name"),
    )


# ════════════════════════════════════════════════════════════════════
# REPOSITORIES
# ════════════════════════════════════════════════════════════════════
class IndexingStatus(str, PyEnum):
    PENDING = "pending"
    INDEXING = "indexing"
    INDEXED = "indexed"
    FAILED = "failed"


class RepoSourceType(str, PyEnum):
    ZIP = "zip"
    GITHUB_PUBLIC = "github_public"
    GITHUB_PRIVATE = "github_private"
    GITHUB_APP = "github_app"
    LOCAL = "local"


class Repository(Base):
    __tablename__ = "repositories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_type: Mapped[str] = mapped_column(Enum(RepoSourceType), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    github_repo_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    github_branch: Mapped[str] = mapped_column(String(255), default="main")
    local_path: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    indexed_status: Mapped[str] = mapped_column(Enum(IndexingStatus), default=IndexingStatus.PENDING, index=True)
    indexing_progress: Mapped[int] = mapped_column(Integer, default=0)  # 0-100
    total_files: Mapped[int] = mapped_column(Integer, default=0)
    indexed_files: Mapped[int] = mapped_column(Integer, default=0)
    total_chunks: Mapped[int] = mapped_column(Integer, default=0)
    detected_languages: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    detected_frameworks: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    architecture_diagram: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    file_tree: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    embedding_model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="repositories")


# ════════════════════════════════════════════════════════════════════
# CHATS
# ════════════════════════════════════════════════════════════════════
class ChatRole(str, PyEnum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    AGENT = "agent"


class Chat(Base):
    __tablename__ = "chats"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    role: Mapped[str] = mapped_column(Enum(ChatRole), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    agent_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="chats")

    __table_args__ = (
        Index("ix_chats_thread_created", "thread_id", "created_at"),
    )


# ════════════════════════════════════════════════════════════════════
# EXECUTIONS
# ════════════════════════════════════════════════════════════════════
class ExecutionStatus(str, PyEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    KILLED = "killed"


class ExecutionRuntime(str, PyEnum):
    PYTHON = "python"
    NODEJS = "nodejs"
    GO = "go"
    BASH = "bash"


class Execution(Base):
    __tablename__ = "executions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    runtime: Mapped[str] = mapped_column(Enum(ExecutionRuntime), nullable=False)
    code: Mapped[str] = mapped_column(Text, nullable=False)
    stdin: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stdout: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    stderr: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exit_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(Enum(ExecutionStatus), default=ExecutionStatus.PENDING, index=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    memory_mb: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    triggered_by_agent: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="executions")


# ════════════════════════════════════════════════════════════════════
# AGENT LOGS
# ════════════════════════════════════════════════════════════════════
class AgentName(str, PyEnum):
    PLANNER = "planner"
    CODER = "coder"
    REVIEWER = "reviewer"
    INFRA = "infra"
    DOCS = "docs"
    DEBUGGER = "debugger"
    ORCHESTRATOR = "orchestrator"


class AgentLog(Base):
    __tablename__ = "agent_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    thread_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    agent_name: Mapped[str] = mapped_column(Enum(AgentName), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    input_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    token_usage: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="success")
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="agent_logs")

    __table_args__ = (
        Index("ix_agent_logs_project_thread", "project_id", "thread_id"),
    )
