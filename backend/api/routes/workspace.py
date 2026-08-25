"""
NexusForge AI — Workspace API Routes (IDE backend)
Powers the Monaco IDE frontend: file serving, inline completions,
AI edits, explain, and self-improving code execution.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from backend.core.database import get_db
from backend.core.dependencies import CurrentUser

router = APIRouter(prefix="/workspace", tags=["workspace"])


# ─── Request Models ──────────────────────────────────────────────────────────

class InlineCompleteRequest(BaseModel):
    prefix: str         # last ~500 chars of code before cursor
    language: str = "python"
    project_id: Optional[str] = None


class AIEditRequest(BaseModel):
    code: str
    instruction: str
    language: str = "python"
    file_path: Optional[str] = None
    project_id: Optional[str] = None


class ExplainRequest(BaseModel):
    code: str
    language: str = "python"
    project_id: Optional[str] = None


class SelfImprovingRequest(BaseModel):
    task_description: str
    language: str = "python"
    project_id: str = ""
    test_cases: Optional[list[dict]] = None
    max_retries: int = 3
    stream_events: bool = True


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.get("/file")
async def get_file_content(
    current_user: CurrentUser,
    path: str = Query(..., description="Relative path to file within the indexed project"),
    project_id: str = Query("00000000-0000-0000-0000-000000000000"),
    repo_id: Optional[str] = Query(None, description="Optional repository ID to fetch from"),
    db: AsyncSession = Depends(get_db),
):
    """
    Serve file content for the Monaco IDE file tree.
    Only serves files within the project's indexed repo path.
    """
    from sqlalchemy import select
    from backend.models import Repository, Project
    import uuid

    try:
        project_uuid = uuid.UUID(project_id)
        # Check project belongs to user
        proj_result = await db.execute(
            select(Project).where(Project.id == project_uuid, Project.user_id == current_user.id)
        )
        if not proj_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Project not found")

        # Get repository
        if repo_id:
            repo_uuid = uuid.UUID(repo_id)
            repo_result = await db.execute(
                select(Repository).where(
                    Repository.id == repo_uuid,
                    Repository.project_id == project_uuid
                )
            )
            repo = repo_result.scalars().first()
        else:
            # Find the latest indexed repo first
            repo_result = await db.execute(
                select(Repository)
                .where(Repository.project_id == project_uuid, Repository.indexed_status == 'indexed')
                .order_by(Repository.created_at.desc())
            )
            repo = repo_result.scalars().first()
            if not repo:
                # Fallback to any repo (latest created first)
                repo_result = await db.execute(
                    select(Repository)
                    .where(Repository.project_id == project_uuid)
                    .order_by(Repository.created_at.desc())
                )
                repo = repo_result.scalars().first()

        if not repo or not repo.local_path:
            raise HTTPException(status_code=404, detail="No repository found or not indexed yet")

        # Resolve path relative to repository local_path
        base_dir = Path(repo.local_path).resolve()
        # Resolve the target path ensuring it's relative
        target_path = Path(path)
        if target_path.is_absolute():
            resolved_path = target_path.resolve()
        else:
            resolved_path = (base_dir / target_path).resolve()

        # Prevent Directory Traversal vulnerability
        if not str(resolved_path).startswith(str(base_dir)):
            raise HTTPException(status_code=403, detail="Access denied")

        if not resolved_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        if not resolved_path.is_file():
            raise HTTPException(status_code=400, detail=f"Not a file: {path}")

        content = resolved_path.read_text(encoding="utf-8", errors="replace")
        language = _detect_language(resolved_path.suffix)

        return {
            "path": path,
            "content": content,
            "language": language,
            "size_bytes": resolved_path.stat().st_size,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inline-complete")
async def inline_complete(body: InlineCompleteRequest):
    """
    Ghost text inline completions for Monaco editor.
    Returns a short completion (1-3 lines max) for cursor position.
    Called on debounce (400ms) — must respond fast (<2s).
    """
    from agents.router.model_router import ModelRouter, TaskType
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ModelRouter.get_instance().get_langchain_llm(TaskType.CODEGEN)

    system = (
        "You are a code completion engine. "
        "Complete the code at the cursor. "
        "Return ONLY the completion text (1-3 lines). "
        "No explanation, no markdown, no repetition of existing code."
    )
    user = f"Language: {body.language}\n\nCode so far:\n{body.prefix}"

    try:
        response = await llm.ainvoke([
            SystemMessage(content=system),
            HumanMessage(content=user),
        ])
        completion = response.content if hasattr(response, "content") else str(response)
        # Limit to 3 lines max
        lines = completion.strip().splitlines()
        completion = "\n".join(lines[:3])
        return {"completion": completion}
    except Exception as e:
        return {"completion": "", "error": str(e)}


@router.post("/ai-edit")
async def ai_edit(body: AIEditRequest):
    """
    AI-powered code edit. Streams the replacement code.
    Used by Monaco executeEdits() to replace selected region.
    """
    from agents.router.model_router import ModelRouter, TaskType
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = ModelRouter.get_instance().get_langchain_llm(TaskType.CODEGEN)

    system = (
        f"You are an expert {body.language} developer. "
        "Apply the instruction to the code. "
        "Return ONLY the modified code with no markdown, no explanation."
    )
    user = (
        f"Instruction: {body.instruction}\n\n"
        f"Code:\n{body.code[:3000]}"
    )

    async def _stream():
        try:
            async for chunk in llm.astream([
                SystemMessage(content=system),
                HumanMessage(content=user),
            ]):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content:
                    yield content
        except Exception as e:
            yield f"\n# Error: {e}"

    return StreamingResponse(
        _stream(),
        media_type="text/plain",
        headers={"X-Accel-Buffering": "no"},
    )


@router.post("/explain")
async def explain_code(body: ExplainRequest):
    """
    Explain the given code in plain English.
    Used by Monaco keyboard shortcut Ctrl+Shift+E.
    """
    from agents.router.model_router import ModelRouter, TaskType
    from langchain_core.messages import HumanMessage

    llm = ModelRouter.get_instance().get_langchain_llm(TaskType.DOCS)

    prompt = (
        f"Explain this {body.language} code clearly and concisely (3-5 sentences). "
        f"Focus on what it does and any non-obvious design decisions.\n\n"
        f"```{body.language}\n{body.code[:2000]}\n```"
    )

    try:
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        explanation = response.content if hasattr(response, "content") else str(response)
        return {"explanation": explanation}
    except Exception as e:
        return {"explanation": f"Explanation unavailable: {e}"}


@router.post("/self-improve")
async def self_improving_codegen(body: SelfImprovingRequest):
    """
    Autonomous code generation with self-improvement loop.
    Runs Generate → Execute → Evaluate → Debug → Retry (max 3 cycles).
    Returns final code + execution trace.
    """
    from agents.workflows.self_improving import run_self_improving, stream_self_improving

    import json

    if body.stream_events:
        async def _event_stream():
            async for event in stream_self_improving(
                task_description=body.task_description,
                language=body.language,
                project_id=body.project_id,
                test_cases=body.test_cases,
                max_retries=body.max_retries,
            ):
                yield f"data: {json.dumps(event)}\n\n"
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            _event_stream(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    result = await run_self_improving(
        task_description=body.task_description,
        language=body.language,
        project_id=body.project_id,
        test_cases=body.test_cases,
        max_retries=body.max_retries,
    )

    return {
        "success": result.success,
        "final_code": result.final_code,
        "final_output": result.final_output,
        "total_cycles": result.total_cycles,
        "duration_ms": round(result.duration_ms, 1),
        "error": result.error,
        "events": result.events,
    }


@router.get("/analytics/global-cost")
async def get_global_cost():
    """Real-time cost summary for the IDE cost widget."""
    from backend.services.cost_tracker import CostTracker

    tracker = CostTracker.get_instance()
    summary = await tracker.get_global_summary()
    return {
        "totalCostUsd": summary.get("total_cost_usd", 0),
        "totalTokens": 0,   # aggregate from Redis counters
        "model": "mixed",
        "callsCount": summary.get("total_projects", 0),
        "projects": summary.get("projects", {}),
    }


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _detect_language(suffix: str) -> str:
    return {
        ".py":   "python",
        ".ts":   "typescript",
        ".tsx":  "typescript",
        ".js":   "javascript",
        ".jsx":  "javascript",
        ".json": "json",
        ".yaml": "yaml",
        ".yml":  "yaml",
        ".md":   "markdown",
        ".sql":  "sql",
        ".sh":   "bash",
        ".go":   "go",
        ".rs":   "rust",
        ".java": "java",
        ".cpp":  "cpp",
        ".c":    "c",
    }.get(suffix.lower(), "plaintext")
