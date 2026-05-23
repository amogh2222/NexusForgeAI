import asyncio
import uuid
from sqlalchemy import select
from backend.core.database import engine, AsyncSession
from backend.models import User, Project
from backend.core.security import hash_password

async def main():
    async with AsyncSession(engine) as session:
        # Check if default user exists
        email = "demo@nexusforge.ai"
        res = await session.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()
        
        if not user:
            print("Creating default user...")
            user = User(
                id=uuid.uuid4(),
                email=email,
                username="demo",
                password_hash=hash_password("password123"),
                full_name="Demo User",
                is_active=True,
                is_verified=True,
                api_key="demo-api-key-value-for-testing"
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
            print(f"Created user: {user.email} (ID: {user.id})")
        else:
            print(f"Default user already exists: {user.email} (ID: {user.id})")

        # Check if default project exists
        proj_id = uuid.UUID("00000000-0000-0000-0000-000000000000")
        res = await session.execute(select(Project).where(Project.id == proj_id))
        project = res.scalar_one_or_none()

        if not project:
            print("Creating default project...")
            project = Project(
                id=proj_id,
                user_id=user.id,
                name="Demo Project",
                description="Default workspace project for repository analysis.",
                color="#7c3aed"
            )
            session.add(project)
            await session.commit()
            await session.refresh(project)
            print(f"Created project: {project.name} (ID: {project.id})")
        else:
            print(f"Default project already exists: {project.name} (ID: {project.id})")

if __name__ == "__main__":
    asyncio.run(main())
