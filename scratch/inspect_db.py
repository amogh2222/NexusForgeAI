import asyncio
from uuid import UUID
from sqlalchemy import select
from backend.core.database import engine, AsyncSession
from backend.models import User, Project, Repository

async def main():
    async with AsyncSession(engine) as session:
        # Check users
        users_res = await session.execute(select(User))
        users = users_res.scalars().all()
        print(f"=== USERS ({len(users)}) ===")
        for u in users:
            print(f"User ID: {u.id}, Username: {u.username}, Email: {u.email}")
        
        # Check projects
        projects_res = await session.execute(select(Project))
        projects = projects_res.scalars().all()
        print(f"\n=== PROJECTS ({len(projects)}) ===")
        for p in projects:
            print(f"Project ID: {p.id}, Name: {p.name}, User ID: {p.user_id}")

        # Check repositories
        repos_res = await session.execute(select(Repository))
        repos = repos_res.scalars().all()
        print(f"\n=== REPOSITORIES ({len(repos)}) ===")
        for r in repos:
            print(f"Repo ID: {r.id}, Name: {r.name}, Project ID: {r.project_id}, Status: {r.indexed_status}, Progress: {r.indexing_progress}%")

if __name__ == "__main__":
    asyncio.run(main())
