"""
NexusForge AI — WebSocket Connection Manager
Per-project room-based broadcasting with typed event payloads.
"""
import json
from collections import defaultdict
from typing import Any, Optional
from uuid import UUID

import structlog
from fastapi import WebSocket

log = structlog.get_logger()


class ConnectionManager:
    """
    Manages WebSocket connections grouped by room (project_id + thread_id).
    Supports broadcasting typed events to all clients in a room.
    """

    def __init__(self):
        # room_id -> list of active WebSocket connections
        self._connections: dict[str, list[WebSocket]] = defaultdict(list)
        # websocket -> room_id (reverse lookup for cleanup)
        self._ws_to_room: dict[WebSocket, str] = {}

    def _room_id(self, project_id: str, thread_id: Optional[str] = None) -> str:
        if thread_id:
            return f"{project_id}:{thread_id}"
        return project_id

    async def connect(self, websocket: WebSocket, project_id: str, thread_id: Optional[str] = None):
        """Accept a WebSocket connection and register it in the appropriate room."""
        await websocket.accept()
        room = self._room_id(project_id, thread_id)
        self._connections[room].append(websocket)
        self._ws_to_room[websocket] = room
        log.info("ws.connected", room=room, total=len(self._connections[room]))

    def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection from its room."""
        room = self._ws_to_room.pop(websocket, None)
        if room and websocket in self._connections[room]:
            self._connections[room].remove(websocket)
            if not self._connections[room]:
                del self._connections[room]
        log.info("ws.disconnected", room=room)

    async def send_to_connection(self, websocket: WebSocket, event: dict):
        """Send an event to a single WebSocket connection."""
        try:
            await websocket.send_text(json.dumps(event))
        except Exception as e:
            log.warning("ws.send_failed", error=str(e))
            self.disconnect(websocket)

    async def broadcast_to_room(
        self,
        event: dict,
        project_id: str,
        thread_id: Optional[str] = None,
    ):
        """Broadcast an event to all connections in a room."""
        room = self._room_id(project_id, thread_id)
        connections = self._connections.get(room, [])
        disconnected = []
        for ws in connections:
            try:
                await ws.send_text(json.dumps(event))
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)

    async def broadcast_to_project(self, event: dict, project_id: str):
        """Broadcast to ALL rooms under a project_id (any thread)."""
        prefix = f"{project_id}:"
        rooms = [r for r in self._connections if r == project_id or r.startswith(prefix)]
        for room in rooms:
            connections = list(self._connections.get(room, []))
            for ws in connections:
                try:
                    await ws.send_text(json.dumps(event))
                except Exception:
                    self.disconnect(ws)

    def get_room_count(self, project_id: str) -> int:
        """Get the number of active connections for a project."""
        prefix = f"{project_id}:"
        return sum(
            len(conns)
            for room, conns in self._connections.items()
            if room == project_id or room.startswith(prefix)
        )

    @property
    def total_connections(self) -> int:
        return sum(len(conns) for conns in self._connections.values())


# ─── Singleton ───────────────────────────────────────────────────
manager = ConnectionManager()
