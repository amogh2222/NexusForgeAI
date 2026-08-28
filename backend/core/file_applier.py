import os
import uuid
from typing import Dict, Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.models import Repository

log = structlog.get_logger()

class FileApplier:
    """
    Applies GeneratedCode FileChanges directly to the physical filesystem 
    where the repository was cloned.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def apply_changes(self, repository_id: str, generated_code: Dict[str, Any]) -> bool:
        """
        Takes the dict representation of GeneratedCode (state["generated_code"])
        and applies the files to the local_path of the repository.
        """
        if not generated_code or not generated_code.get("files"):
            log.debug("file_applier.no_files", repository_id=repository_id)
            return False

        try:
            repo_uuid = uuid.UUID(repository_id)
            result = await self.db.execute(select(Repository).where(Repository.id == repo_uuid))
            repo = result.scalars().first()
            
            if not repo or not repo.local_path:
                log.error("file_applier.repo_not_found_or_no_path", repository_id=repository_id)
                return False

            base_path = repo.local_path
            
            if not os.path.exists(base_path):
                log.error("file_applier.path_does_not_exist", path=base_path)
                return False

            applied_count = 0
            for file_change in generated_code.get("files", []):
                relative_path = file_change.get("path", "").lstrip("/")
                if not relative_path:
                    continue
                    
                abs_path = os.path.join(base_path, relative_path)
                
                # Prevent directory traversal attacks
                if not os.path.abspath(abs_path).startswith(os.path.abspath(base_path)):
                    log.warning("file_applier.path_traversal_attempt", path=relative_path)
                    continue

                action = file_change.get("action", "create").lower()
                content = file_change.get("content", "")

                if action in ("create", "modify"):
                    os.makedirs(os.path.dirname(abs_path), exist_ok=True)
                    with open(abs_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    applied_count += 1
                    log.info("file_applier.wrote_file", path=relative_path)
                    
                elif action == "delete":
                    if os.path.exists(abs_path):
                        os.remove(abs_path)
                        applied_count += 1
                        log.info("file_applier.deleted_file", path=relative_path)

            log.info("file_applier.success", applied_count=applied_count)
            return True

        except Exception as e:
            log.error("file_applier.failed", error=str(e), repository_id=repository_id)
            return False
