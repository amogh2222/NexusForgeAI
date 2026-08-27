"""NexusForge AI — Chat, Agents, Memory, and Execution Routes"""

# ──────────────────────────────────────────────────────────────────
# chat.py
# ──────────────────────────────────────────────────────────────────
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from backend.core.dependencies import CurrentUser, DBSession
from fastapi import APIRouter as _APIRouter

chat_router = _APIRouter()
agents_router = _APIRouter()
memory_router = _APIRouter()
executions_router = _APIRouter()

# ─── Chat ──────────────────────────────────────────────────────────


class ChatMessageRequest(BaseModel):
    project_id: str
    thread_id: str
    content: str
    repository_id: Optional[str] = None


class ChatMessageResponse(BaseModel):
    id: UUID
    role: str
    content: str
    agent_name: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


@chat_router.post("/message")
async def send_chat_message(
    request: ChatMessageRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Queue a chat message for agent processing. Response streams via WebSocket."""
    from backend.workers.tasks.agent_task import run_agent_pipeline
    task = run_agent_pipeline.delay(
        user_id=str(current_user.id),
        project_id=request.project_id,
        thread_id=request.thread_id,
        content=request.content,
        repository_id=request.repository_id,
    )
    return {"task_id": task.id, "thread_id": request.thread_id, "status": "queued"}


@chat_router.get("/{thread_id}/history", response_model=List[ChatMessageResponse])
async def get_chat_history(thread_id: str, current_user: CurrentUser, db: DBSession):
    """Get chat history for a thread."""
    from sqlalchemy import select
    from backend.models import Chat
    result = await db.execute(
        select(Chat).where(Chat.thread_id == thread_id).order_by(Chat.created_at.asc()).limit(100)
    )
    return result.scalars().all()


# ─── Agents ────────────────────────────────────────────────────────
@agents_router.get("/logs")
async def get_agent_logs(
    project_id: str,
    current_user: CurrentUser,
    db: DBSession,
    limit: int = 50,
):
    """Get agent activity logs for a project."""
    from sqlalchemy import select
    from backend.models import AgentLog
    result = await db.execute(
        select(AgentLog)
        .where(AgentLog.project_id == project_id)
        .order_by(AgentLog.timestamp.desc())
        .limit(limit)
    )
    logs = result.scalars().all()
    return [
        {
            "id": str(log.id),
            "agent_name": log.agent_name,
            "action": log.action,
            "input_summary": log.input_summary,
            "output_summary": log.output_summary,
            "duration_ms": log.duration_ms,
            "status": log.status,
            "timestamp": log.timestamp.isoformat(),
        }
        for log in logs
    ]


# ─── Memory ────────────────────────────────────────────────────────
@memory_router.get("/retrieve")
async def retrieve_memory(
    project_id: str,
    query: str,
    current_user: CurrentUser,
    top_k: int = 5,
):
    """Semantic retrieval from project's vector memory."""
    from rag.retrieval.retriever import HybridRetriever
    retriever = HybridRetriever(top_k=top_k, rerank_top_k=top_k)
    context, sources = await retriever.retrieve(query=query, project_id=project_id)
    return {"query": query, "context": context, "sources": sources}


@memory_router.get("/stats")
async def memory_stats(project_id: str, current_user: CurrentUser):
    """Get ChromaDB stats for a project."""
    from rag.vector_store.chroma_store import ChromaStore
    return ChromaStore.get_instance().get_collection_stats(project_id)


# ─── Executions ────────────────────────────────────────────────────
class ExecutionRequest(BaseModel):
    project_id: str
    runtime: str  # python | nodejs | go | bash
    code: str
    stdin: Optional[str] = None


@executions_router.post("/")
async def create_execution(
    request: ExecutionRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """Submit code for sandbox execution."""
    import uuid
    from backend.models import Execution, ExecutionStatus

    execution = Execution(
        id=uuid.uuid4(),
        project_id=request.project_id,
        runtime=request.runtime,
        code=request.code,
        stdin=request.stdin,
        status=ExecutionStatus.PENDING,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)

    from backend.workers.tasks.execution_task import execute_code
    task = execute_code.delay(
        execution_id=str(execution.id),
        project_id=request.project_id,
        runtime=request.runtime,
        code=request.code,
        stdin=request.stdin,
    )
    execution.celery_task_id = task.id
    await db.commit()

    return {"execution_id": str(execution.id), "status": "pending"}


@executions_router.get("/{execution_id}")
async def get_execution(execution_id: str, current_user: CurrentUser, db: DBSession):
    """Get execution result."""
    from sqlalchemy import select
    from backend.models import Execution
    result = await db.execute(select(Execution).where(Execution.id == execution_id))
    execution = result.scalar_one_or_none()
    if not execution:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Execution not found")
    return {
        "id": str(execution.id),
        "runtime": execution.runtime,
        "status": execution.status,
        "stdout": execution.stdout,
        "stderr": execution.stderr,
        "exit_code": execution.exit_code,
        "duration_ms": execution.duration_ms,
        "created_at": execution.created_at.isoformat(),
    }
