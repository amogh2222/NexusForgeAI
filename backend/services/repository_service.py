"""NexusForge AI — Repository Service"""
import os
import uuid
from pathlib import Path
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.core.config import settings
from backend.models import Repository, IndexingStatus, RepoSourceType

log = structlog.get_logger()


class RepositoryService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _enforce_single_repository(self, project_id: UUID):
        """Ensure only one repository exists per project. Deletes others."""
        result = await self.db.execute(select(Repository).where(Repository.project_id == project_id))
        existing_repos = result.scalars().all()
        for r in existing_repos:
            await self.db.delete(r)
        if existing_repos:
            await self.db.commit()

    async def create_from_zip(
        self,
        project_id: UUID,
        user_id: UUID,
        zip_path: str,
        name: str,
    ) -> Repository:
        """Create a repository record from a ZIP upload and trigger indexing."""
        await self._enforce_single_repository(project_id)

        repo = Repository(
            id=uuid.uuid4(),
            project_id=project_id,
            name=name,
            source_type=RepoSourceType.ZIP,
            local_path=zip_path,
            indexed_status=IndexingStatus.PENDING,
        )
        self.db.add(repo)
        await self.db.commit()
        await self.db.refresh(repo)

        # Trigger async indexing
        from backend.workers.tasks.indexing_task import index_repository
        index_repository.delay(
            repository_id=str(repo.id),
            project_id=str(project_id),
            source_path=zip_path,
            source_type="zip",
        )

        return repo

    async def create_from_github(
        self,
        project_id: UUID,
        user_id: UUID,
        github_url: str,
        branch: str = "main",
        github_token: Optional[str] = None,
    ) -> Repository:
        """Clone a GitHub repo and trigger indexing."""
        import re
        # Parse GitHub URL
        match = re.match(r"https://github\.com/([^/]+)/([^/]+?)(?:\.git)?$", github_url)
        if not match:
            raise ValueError(f"Invalid GitHub URL: {github_url}")

        _, repo_name = match.group(1), match.group(2)
        clone_dir = os.path.join(settings.UPLOAD_DIR, str(uuid.uuid4()), repo_name)
        os.makedirs(os.path.dirname(clone_dir), exist_ok=True)

        # Determine source type
        source_type = RepoSourceType.GITHUB_PRIVATE if github_token else RepoSourceType.GITHUB_PUBLIC

        await self._enforce_single_repository(project_id)

        repo = Repository(
            id=uuid.uuid4(),
            project_id=project_id,
            name=repo_name,
            source_type=source_type,
            source_url=github_url,
            github_branch=branch,
            local_path=clone_dir,
            indexed_status=IndexingStatus.PENDING,
        )
        self.db.add(repo)
        await self.db.commit()
        await self.db.refresh(repo)

        # Trigger async clone + index
        from backend.workers.tasks.indexing_task import index_repository
        index_repository.delay(
            repository_id=str(repo.id),
            project_id=str(project_id),
            source_path=clone_dir,
            source_type="github",
            github_url=github_url,
            github_token=github_token,
            branch=branch,
        )

        return repo

    async def get_by_id(self, repo_id: UUID, user_id: UUID) -> Optional[Repository]:
        """Get a repository with user ownership validation."""
        from backend.models import Project
        result = await self.db.execute(
            select(Repository)
            .join(Project, Project.id == Repository.project_id)
            .where(Repository.id == repo_id, Project.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def get_file_tree(self, repo_id: UUID, user_id: UUID) -> dict:
        """Get the file tree from database or scan directory."""
        repo = await self.get_by_id(repo_id, user_id)
        if not repo:
            return {}
        if repo.file_tree:
            # Auto-migrate: check if the first child has the 'path' key
            children = repo.file_tree.get("children", [])
            if not children or any("path" in c for c in children):
                return repo.file_tree
        if repo.local_path and os.path.exists(repo.local_path):
            tree = self._build_file_tree(repo.local_path)
            repo.file_tree = tree
            await self.db.commit()
            return tree
        return {}

    def _build_file_tree(self, root_dir: str, max_depth: int = 5) -> dict:
        """Build a nested file tree structure with relative paths."""
        SKIP = {"node_modules", ".git", "__pycache__", "dist", "build", ".next", "venv"}

        def walk(path: str, depth: int) -> dict:
            if depth > max_depth:
                return {}
            rel_path = os.path.relpath(path, root_dir)
            if rel_path == ".":
                rel_path = ""
            result = {
                "name": os.path.basename(path) or os.path.basename(root_dir),
                "path": rel_path,
                "type": "directory",
                "children": []
            }
            try:
                entries = sorted(os.scandir(path), key=lambda e: (not e.is_dir(), e.name.lower()))
                for entry in entries[:200]:
                    if entry.name in SKIP or entry.name.startswith("."):
                        continue
                    if entry.is_dir():
                        result["children"].append(walk(entry.path, depth + 1))
                    else:
                        entry_rel_path = os.path.relpath(entry.path, root_dir)
                        result["children"].append({
                            "name": entry.name,
                            "path": entry_rel_path,
                            "type": "file",
                            "size": entry.stat().st_size,
                            "extension": Path(entry.name).suffix,
                        })
            except PermissionError:
                pass
            return result

        return walk(root_dir, 0)

    async def trigger_reindex(self, repo_id: UUID, user_id: UUID):
        """Reset status and trigger re-indexing."""
        repo = await self.get_by_id(repo_id, user_id)
        if not repo:
            raise ValueError("Repository not found")

        repo.indexed_status = IndexingStatus.PENDING
        repo.indexing_progress = 0
        await self.db.commit()

        from backend.workers.tasks.indexing_task import index_repository
        index_repository.delay(
            repository_id=str(repo.id),
            project_id=str(repo.project_id),
            source_path=repo.local_path,
            source_type=repo.source_type,
        )

    async def delete(self, repo_id: UUID, user_id: UUID):
        """Delete a repository from the database."""
        repo = await self.get_by_id(repo_id, user_id)
        if not repo:
            raise ValueError("Repository not found")
        await self.db.delete(repo)
        await self.db.commit()
