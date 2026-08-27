"""
NexusForge AI — Redis PubSub Listener
Bridges real-time events from Celery/Redis to FastAPI WebSockets.
"""
import asyncio
import json
import structlog
import redis.asyncio as aioredis
from typing import Optional

from backend.core.config import settings
from backend.api.websocket.hub import manager

log = structlog.get_logger()


class RedisListener:
    """Listens to Redis PubSub and forwards events to WebSocket clients."""

    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.pubsub: Optional[aioredis.client.PubSub] = None
        self._task: Optional[asyncio.Task] = None
        self._is_running = False

    async def start(self):
        """Connect to Redis and start listening to the pattern."""
        if self._is_running:
            return

        self._is_running = True
        self.redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        self.pubsub = self.redis.pubsub()

        # We subscribe to the pattern used by Celery tasks: nexusforge:ws:*
        await self.pubsub.psubscribe("nexusforge:ws:*")
        
        self._task = asyncio.create_task(self._listen_loop())
        log.info("redis_listener.started", pattern="nexusforge:ws:*")

    async def stop(self):
        """Stop the listener gracefully."""
        self._is_running = False
        if self.pubsub:
            await self.pubsub.punsubscribe("nexusforge:ws:*")
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("redis_listener.stopped")

    async def _listen_loop(self):
        """Main loop that yields messages from Redis and forwards to WebSockets."""
        try:
            async for message in self.pubsub.listen():
                if not self._is_running:
                    break

                # Ignore subscribe/unsubscribe control messages
                if message["type"] != "pmessage":
                    continue

                channel = message["channel"]  # e.g., nexusforge:ws:<project_id> or nexusforge:ws:<project_id>:<thread_id>
                data_str = message["data"]

                if not channel.startswith("nexusforge:ws:"):
                    continue

                # Extract project_id (first part after prefix)
                parts = channel.replace("nexusforge:ws:", "").split(":")
                project_id = parts[0]

                try:
                    event = json.loads(data_str)
                    # Forward event to the memory ConnectionManager
                    # The manager will broadcast it to all WebSockets connected to this project
                    await manager.broadcast_to_project(event, project_id=project_id)
                except json.JSONDecodeError:
                    log.error("redis_listener.decode_failed", data=data_str)
                except Exception as e:
                    log.error("redis_listener.broadcast_failed", error=str(e), project_id=project_id)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error("redis_listener.fatal_error", error=str(e))
            if self._is_running:
                # Attempt to restart on fatal error after a short delay
                await asyncio.sleep(5)
                self._task = asyncio.create_task(self._listen_loop())


# Singleton instance
redis_listener = RedisListener()
