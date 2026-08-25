"""
NexusForge AI — WebSocket Endpoint
Handles real-time bidirectional communication for agent streaming.
"""
import json
from typing import Optional

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError

from backend.api.websocket.hub import manager
from backend.api.websocket.events import ConnectedEvent, ErrorEvent
from backend.core.security import verify_access_token

log = structlog.get_logger()

websocket_router = APIRouter()


@websocket_router.websocket("/ws/{project_id}")
async def websocket_project(
    websocket: WebSocket,
    project_id: str,
    thread_id: Optional[str] = Query(default=None),
    token: Optional[str] = Query(default=None),
):
    """
    WebSocket endpoint for real-time project updates.

    Usage: ws://localhost:8000/ws/{project_id}?thread_id=xxx&token=jwt_token

    Events received from client:
    - {"type": "chat", "content": "...", "thread_id": "..."}
    - {"type": "ping"}

    Events sent to client:
    - All event types from events.py
    """
    # ─── Auth validation ────────────────────────────────────────
    user_id = None
    if token:
        try:
            user_id = verify_access_token(token)
        except JWTError:
            await websocket.accept()
            await websocket.send_text(
                ErrorEvent(message="Invalid authentication token", recoverable=False).model_dump_json()
            )
            await websocket.close(code=4001)
            return

    # ─── Connect ────────────────────────────────────────────────
    await manager.connect(websocket, project_id, thread_id)

    # Send connected confirmation
    await websocket.send_text(
        ConnectedEvent(
            project_id=project_id,
            thread_id=thread_id,
        ).model_dump_json()
    )

    try:
        while True:
            raw_message = await websocket.receive_text()

            try:
                message = json.loads(raw_message)
            except json.JSONDecodeError:
                continue

            msg_type = message.get("type")

            # ─── Ping/Pong keepalive ─────────────────────────────
            if msg_type == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))

            # ─── Chat message → trigger agent pipeline ───────────
            elif msg_type == "chat":
                content = message.get("content", "").strip()
                msg_thread_id = message.get("thread_id", thread_id)
                if content and user_id:
                    from backend.workers.tasks.agent_task import run_agent_pipeline
                    run_agent_pipeline.delay(
                        user_id=user_id,
                        project_id=project_id,
                        thread_id=msg_thread_id,
                        content=content,
                    )

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        log.info("ws.client_disconnected", project_id=project_id)

    except Exception as e:
        log.error("ws.unexpected_error", error=str(e), project_id=project_id)
        manager.disconnect(websocket)
