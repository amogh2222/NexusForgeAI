"""
NexusForge AI — Intelligence API Routes
Endpoints for repository evolution, system design generation,
git commit analysis, and contributor patterns.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.core.database import get_db

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


# ─── Request / Response Models ───────────────────────────────────────────────

class SystemDesignRequest(BaseModel):
    project_id: str
    scale: str = "10M_users"   # "1M_users" | "10M_users" | "100M_users" | "1B_users"
    stream: bool = False


class BugSearchRequest(BaseModel):
    project_id: str
    repo_path: str
    pattern: str                # git pickaxe pattern (e.g. "sql injection", "eval(")
    max_results: int = 10


class GraphQueryRequest(BaseModel):
    repo_id: str
    query_type: str             # "dependencies" | "path" | "impact" | "circular" | "endpoints" | "summary"
    entity_name: Optional[str] = None
    target_name: Optional[str] = None
    max_depth: int = 5


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/evolution/{project_id}")
async def get_repo_evolution(
    project_id: str,
    repo_path: str = Query(..., description="Absolute path to the git repository"),
    max_commits: int = Query(200, ge=10, le=1000),
    db: AsyncSession = Depends(get_db),
):
    """
    Analyze repository commit history.
    Returns per-commit metrics: churn, complexity, bug fixes, refactors.
    """
    from intelligence.git_analyzer import GitAnalyzer

    analyzer = GitAnalyzer(repo_path)
    history = analyzer.analyze_commit_history(max_commits=max_commits)

    if not history:
        return {
            "project_id": project_id,
            "commits": [],
            "warning": "No commits found or PyDriller not installed (pip install pydriller)",
        }

    return {
        "project_id": project_id,
        "total_analyzed": len(history),
        "commits": [
            {
                "hash": c.short_hash,
                "author": c.author,
                "date": c.date.isoformat(),
                "message": c.message[:100],
                "files_changed": c.files_changed,
                "lines_added": c.lines_added,
                "lines_deleted": c.lines_deleted,
                "churn_score": c.churn_score,
                "avg_complexity": round(c.avg_complexity, 2),
                "is_bug_fix": c.is_bug_fix,
                "is_refactor": c.is_refactor,
                "is_feature": c.is_feature,
                "is_security": c.is_security,
            }
            for c in history
        ],
    }


@router.get("/evolution/{project_id}/contributors")
async def get_contributors(
    project_id: str,
    repo_path: str = Query(...),
):
    """
    Contributor pattern analysis.
    Returns per-author: commit counts, owned files, bug-fix rate, busiest hours.
    """
    from intelligence.git_analyzer import GitAnalyzer

    analyzer = GitAnalyzer(repo_path)
    contributors = analyzer.get_contributor_patterns()

    return {
        "project_id": project_id,
        "total_contributors": len(contributors),
        "contributors": [
            {
                "name": c.name,
                "email": c.email,
                "total_commits": c.total_commits,
                "lines_added": c.lines_added,
                "lines_deleted": c.lines_deleted,
                "files_owned": c.files_owned[:10],
                "busiest_hours": c.busiest_hours,
                "avg_commit_size": round(c.avg_commit_size, 1),
                "bug_fix_rate": round(c.bug_fix_rate, 3),
            }
            for c in contributors
        ],
    }


@router.get("/evolution/{project_id}/complexity-timeline")
async def get_complexity_timeline(
    project_id: str,
    repo_path: str = Query(...),
    samples: int = Query(20, ge=5, le=50),
):
    """
    Complexity timeline: sampled data points across repository history.
    Use this for the evolution chart in the frontend.
    """
    from intelligence.git_analyzer import GitAnalyzer

    analyzer = GitAnalyzer(repo_path)
    timeline = analyzer.get_complexity_timeline(n_samples=samples)

    return {
        "project_id": project_id,
        "timeline": [
            {
                "date": pt.date.isoformat(),
                "commit_hash": pt.commit_hash,
                "commit_message": pt.commit_message,
                "avg_complexity": round(pt.avg_complexity, 2),
                "churn": pt.churn,
                "file_count": pt.file_count,
            }
            for pt in timeline
        ],
    }


@router.post("/bug-suspects")
async def find_bug_introduction(body: BugSearchRequest):
    """
    Find commits that introduced a specific code pattern (git pickaxe search).
    Risk-scored by commit size, message quality, and security keywords.
    """
    from intelligence.git_analyzer import GitAnalyzer

    analyzer = GitAnalyzer(body.repo_path)
    suspects = analyzer.find_bug_introduction_commits(
        pattern=body.pattern,
        max_results=body.max_results,
    )

    return {
        "project_id": body.project_id,
        "pattern": body.pattern,
        "suspects": [
            {
                "hash": s.hash,
                "author": s.author,
                "date": s.date.isoformat(),
                "message": s.message,
                "risk_score": round(s.risk_score, 2),
                "files_affected": s.files_affected[:10],
                "diff_snippet": s.diff_snippet[:300],
            }
            for s in suspects
        ],
    }


@router.post("/graph/query")
async def query_architecture_graph(body: GraphQueryRequest):
    """
    Query the Neo4j knowledge graph about repository architecture.
    Supports: dependencies, path, impact, circular, endpoints, summary.
    """
    from graph.graph_query_tool import _execute_graph_query

    result = await _execute_graph_query(
        query_type=body.query_type,
        repo_id=body.repo_id,
        entity_name=body.entity_name,
        target_name=body.target_name,
        max_depth=body.max_depth,
    )
    return {"result": result}


@router.post("/system-design")
async def generate_system_design(body: SystemDesignRequest):
    """
    Generate a production-grade system design document for scaling the repository.
    Combines RAG context + knowledge graph + LLM.
    """
    from intelligence.system_design_generator import SCALE_PRESETS, SystemDesignGenerator

    if body.scale not in SCALE_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scale. Options: {list(SCALE_PRESETS.keys())}",
        )

    if body.stream:
        async def _event_stream():
            generator = SystemDesignGenerator()
            async for token in generator.stream_generation(body.project_id, body.scale):
                yield token

        return StreamingResponse(
            _event_stream(),
            media_type="text/plain",
            headers={"X-Accel-Buffering": "no"},
        )

    generator = SystemDesignGenerator()
    doc = await generator.generate(body.project_id, body.scale)

    return {
        "project_id": doc.repo_id,
        "scale": doc.scale,
        "users": doc.users,
        "rps": doc.rps,
        "executive_summary": doc.executive_summary,
        "load_balancing": doc.load_balancing,
        "database_strategy": doc.database_strategy,
        "cache_layer": doc.cache_layer,
        "queue_design": doc.queue_design,
        "autoscaling": doc.autoscaling,
        "cdn_strategy": doc.cdn_strategy,
        "monitoring": doc.monitoring,
        "cost_estimate": doc.cost_estimate,
        "mermaid_diagram": doc.mermaid_diagram,
        "generated_at": doc.generated_at,
    }
