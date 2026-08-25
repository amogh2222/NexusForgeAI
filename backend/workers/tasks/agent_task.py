"""NexusForge AI — Agent Pipeline Celery Task"""
import asyncio
import json
import time
from typing import Optional

import redis
import structlog

from backend.workers.celery_app import celery_app
from backend.core.config import settings

log = structlog.get_logger()


def _publish_event(redis_client: redis.Redis, project_id: str, thread_id: str, event: dict):
    redis_client.publish(f"nexusforge:ws:{project_id}:{thread_id}", json.dumps(event))


@celery_app.task(
    name="backend.workers.tasks.agent_task.run_agent_pipeline",
    bind=True,
    max_retries=1,
    soft_time_limit=300,
)
def run_agent_pipeline(
    self,
    user_id: str,
    project_id: str,
    thread_id: str,
    content: str,
    repository_id: Optional[str] = None,
):
    """
    Run the LangGraph multi-agent pipeline for a user message.
    Publishes WebSocket events via Redis pub/sub.
    """
    redis_client = redis.from_url(settings.REDIS_URL)
    start_time = time.time()

    async def _run():
        from agents.orchestrator import get_orchestrator

        async def websocket_broadcaster(event: dict, project_id: str, thread_id: str):
            """Broadcast events to all connected WebSocket clients."""
            _publish_event(redis_client, project_id, thread_id, event)

        orchestrator = get_orchestrator()
        final_state = await orchestrator.arun(
            project_id=project_id,
            thread_id=thread_id,
            user_message=content,
            repository_id=repository_id,
            websocket_broadcaster=websocket_broadcaster,
        )

        # Save assistant messages to DB
        if final_state:
            from sqlalchemy import create_engine
            from sqlalchemy.orm import sessionmaker
            from backend.models import Chat
            import uuid as uuid_mod

            sync_engine = create_engine(settings.DATABASE_SYNC_URL)
            Session = sessionmaker(bind=sync_engine)
            with Session() as session:
                # Save user message
                user_chat = Chat(
                    id=uuid_mod.uuid4(),
                    project_id=project_id,
                    thread_id=thread_id,
                    role="user",
                    content=content,
                )
                session.add(user_chat)

                # Save final assistant response
                msgs = final_state.get("messages", [])
                for msg in msgs:
                    if hasattr(msg, "type") and msg.type == "ai":
                        assistant_chat = Chat(
                            id=uuid_mod.uuid4(),
                            project_id=project_id,
                            thread_id=thread_id,
                            role="assistant",
                            content=msg.content,
                        )
                        session.add(assistant_chat)
                session.commit()
            sync_engine.dispose()

        return final_state

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_run())
        loop.close()

        duration_ms = int((time.time() - start_time) * 1000)
        log.info("agent_task.complete", thread_id=thread_id, duration_ms=duration_ms)

        _publish_event(redis_client, project_id, thread_id, {
            "type": "pipeline_complete",
            "thread_id": thread_id,
            "duration_ms": duration_ms,
        })

        return {"status": "success", "thread_id": thread_id, "duration_ms": duration_ms}

    except Exception as e:
        log.error("agent_task.failed", thread_id=thread_id, error=str(e))
        _publish_event(redis_client, project_id, thread_id, {
            "type": "pipeline_error",
            "thread_id": thread_id,
            "error": str(e),
        })
        raise self.retry(exc=e, countdown=5)
