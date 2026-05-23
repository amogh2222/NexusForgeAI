"""
NexusForge AI — WebSocket Event Types
Typed Pydantic event payloads for all real-time events.
"""
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    # ─── Streaming Tokens ───────────────────────────
    TOKEN = "token"
    TOKEN_DONE = "token_done"

    # ─── Agent Lifecycle ────────────────────────────
    AGENT_START = "agent_start"
    AGENT_END = "agent_end"
    AGENT_ERROR = "agent_error"

    # ─── Tool Calls ─────────────────────────────────
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"

    # ─── Indexing ───────────────────────────────────
    INDEXING_START = "indexing_start"
    INDEXING_PROGRESS = "indexing_progress"
    INDEXING_COMPLETE = "indexing_complete"
    INDEXING_ERROR = "indexing_error"

    # ─── Execution ──────────────────────────────────
    EXECUTION_START = "execution_start"
    LOG_LINE = "log_line"
    EXECUTION_COMPLETE = "execution_complete"
    EXECUTION_ERROR = "execution_error"

    # ─── System ─────────────────────────────────────
    CONNECTED = "connected"
    ERROR = "error"
    PING = "ping"
    PONG = "pong"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class BaseEvent(BaseModel):
    type: EventType
    timestamp: str = Field(default_factory=_now_iso)
    thread_id: Optional[str] = None

    def to_dict(self) -> dict:
        return self.model_dump()


class TokenEvent(BaseEvent):
    type: EventType = EventType.TOKEN
    content: str
    agent_name: Optional[str] = None


class TokenDoneEvent(BaseEvent):
    type: EventType = EventType.TOKEN_DONE
    full_content: Optional[str] = None


class AgentStartEvent(BaseEvent):
    type: EventType = EventType.AGENT_START
    agent_name: str
    action: str
    input_summary: Optional[str] = None
    icon: Optional[str] = None


class AgentEndEvent(BaseEvent):
    type: EventType = EventType.AGENT_END
    agent_name: str
    action: str
    output_summary: Optional[str] = None
    duration_ms: Optional[int] = None
    status: str = "success"


class AgentErrorEvent(BaseEvent):
    type: EventType = EventType.AGENT_ERROR
    agent_name: str
    error: str
    recoverable: bool = True


class ToolStartEvent(BaseEvent):
    type: EventType = EventType.TOOL_START
    tool_name: str
    input_preview: Optional[str] = None


class ToolEndEvent(BaseEvent):
    type: EventType = EventType.TOOL_END
    tool_name: str
    output_preview: Optional[str] = None
    duration_ms: Optional[int] = None


class IndexingProgressEvent(BaseEvent):
    type: EventType = EventType.INDEXING_PROGRESS
    repository_id: str
    progress: int  # 0-100
    current_file: Optional[str] = None
    files_processed: int = 0
    total_files: int = 0
    chunks_created: int = 0


class IndexingCompleteEvent(BaseEvent):
    type: EventType = EventType.INDEXING_COMPLETE
    repository_id: str
    total_files: int
    total_chunks: int
    duration_ms: int
    detected_languages: dict = {}


class LogLineEvent(BaseEvent):
    type: EventType = EventType.LOG_LINE
    execution_id: str
    line: str
    stream: str = "stdout"  # stdout | stderr


class ExecutionCompleteEvent(BaseEvent):
    type: EventType = EventType.EXECUTION_COMPLETE
    execution_id: str
    exit_code: int
    duration_ms: int
    status: str


class ErrorEvent(BaseEvent):
    type: EventType = EventType.ERROR
    message: str
    code: Optional[str] = None
    recoverable: bool = True


class ConnectedEvent(BaseEvent):
    type: EventType = EventType.CONNECTED
    project_id: str
    thread_id: Optional[str] = None
    server_time: str = Field(default_factory=_now_iso)
