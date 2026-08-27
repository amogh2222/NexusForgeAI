import asyncio
from backend.core.database import SessionLocal
from backend.models import Project, Repository, User
from backend.workers.tasks.indexing_task import index_github_repository
import uuid

async def setup_db():
    async with SessionLocal() as db:
        user = User(id=uuid.uuid4(), email="testx3@example.com", username="testx3", password_hash="xx")
        db.add(user)
        project = Project(id=uuid.uuid4(), name="Test3", owner_id=user.id)
        db.add(project)
        repo = Repository(id=uuid.uuid4(), project_id=project.id, name="DellPartVisionAI", source_type="github", source_url="https://github.com/amogh2222/DellPartVisionAI", github_branch="main")
        db.add(repo)
        await db.commit()
        return str(repo.id)

if __name__ == "__main__":
    repo_id = asyncio.run(setup_db())
    print(f"Testing ingestion for {repo_id}...")
    index_github_repository(repo_id, "https://github.com/amogh2222/DellPartVisionAI", "main")
    print("Done!")
