import os
import json
import redis.asyncio as redis
from typing import Optional, Dict, Any

class TaskResultStore:
    """Simple Redis-backed store for background task results."""
    
    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.redis = redis.from_url(redis_url)
    
    async def save(self, task_id: str, data: Dict[str, Any], expire_seconds: int = 3600):
        """Store task result as JSON."""
        await self.redis.set(f"task_result:{task_id}", json.dumps(data), ex=expire_seconds)
        
    async def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve task result."""
        data = await self.redis.get(f"task_result:{task_id}")
        if data:
            return json.loads(data)
        return None
