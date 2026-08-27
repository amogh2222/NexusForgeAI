"""Sample Python project for NexusForge AI E2E testing."""
import asyncio
from dataclasses import dataclass
from typing import List, Optional

@dataclass
class User:
    id: int
    name: str
    email: str
    roles: List[str]

class UserService:
    def __init__(self):
        self._users: dict[int, User] = {}
    
    async def create_user(self, name: str, email: str, roles: Optional[List[str]] = None) -> User:
        user_id = len(self._users) + 1
        user = User(id=user_id, name=name, email=email, roles=roles or ["viewer"])
        self._users[user_id] = user
        return user
    
    async def get_user(self, user_id: int) -> Optional[User]:
        return self._users.get(user_id)
    
    async def list_users(self) -> List[User]:
        return list(self._users.values())

async def main():
    service = UserService()
    await service.create_user("Alice", "alice@example.com", ["admin"])
    await service.create_user("Bob", "bob@example.com")
    users = await service.list_users()
    for u in users:
        print(f"  {u.id}: {u.name} ({u.email}) - {u.roles}")

if __name__ == "__main__":
    asyncio.run(main())
