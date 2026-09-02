"""
NexusForge AI — Evaluation API Routes
Endpoints for RAGAS RAG quality evaluation and agent benchmark suite.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/evaluation", tags=["evaluation"])


# ─── Request / Response Models ───────────────────────────────────────────────

class RAGEvalRequest(BaseModel):
    questions: list[str]
    answers: list[str]
    contexts: list[list[str]]           # List[List[str]] — one list per question
    ground_truths: Optional[list[str]] = None


class BenchmarkRunRequest(BaseModel):
    suite_id: str
    project_id: str
    case_ids: Optional[list[str]] = None    # None = run all golden cases


# ─── Routes ──────────────────────────────────────────────────────────────────

@router.post("/rag")
async def evaluate_rag_quality(body: RAGEvalRequest):
    """
    Evaluate RAG pipeline quality using RAGAS metrics.
    Returns faithfulness, answer_relevancy, context_precision, context_recall.

    Requires: pip install ragas datasets
    Optional: set OPENAI_API_KEY for gpt-4o-mini judge (costs ~$0.001/eval)
    """
    if not (len(body.questions) == len(body.answers) == len(body.contexts)):
        raise HTTPException(
            status_code=400,
            detail="questions, answers, and contexts must all have the same length",
        )

    from evaluation.ragas_evaluator import evaluate_rag

    result = await evaluate_rag(
        questions=body.questions,
        answers=body.answers,
        contexts=body.contexts,
        ground_truths=body.ground_truths,
    )

    return {
        "questions_evaluated": result.questions_evaluated,
        "faithfulness":        round(result.faithfulness, 4),
        "answer_relevancy":    round(result.answer_relevancy, 4),
        "context_precision":   round(result.context_precision, 4),
        "context_recall":      round(result.context_recall, 4) if result.context_recall is not None else None,
        "mean_score":          round(result.mean_score, 4),
        "error":               result.error,
    }


@router.post("/benchmark/run")
async def run_benchmark(body: BenchmarkRunRequest, background_tasks: BackgroundTasks):
    """
    Run golden test cases against the NexusForge AI agent.
    Schedules as a background task — poll /benchmark/status/{suite_id} for results.

    Built-in test cases:
    - readme-001:    Production README generation
    - bugfix-001:    SQL injection detection + fix
    - review-001:    Async Python performance review
    - arch-001:      CQRS architecture explanation
    - sysdesign-001: URL shortener design (10K RPS)
    """
    from evaluation.benchmark_suite import BenchmarkSuite, CASE_INDEX, GOLDEN_TEST_CASES

    # Validate case IDs
    if body.case_ids:
        invalid = [cid for cid in body.case_ids if cid not in CASE_INDEX]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown case IDs: {invalid}. Valid: {list(CASE_INDEX.keys())}",
            )

    available_cases = body.case_ids or [c.id for c in GOLDEN_TEST_CASES]

    async def _run():
        from backend.services.task_manager import TaskResultStore
        suite = BenchmarkSuite()

        # Build agent function from NexusForge workspace chat
        async def agent_fn(prompt: str) -> str:
            try:
                from agents.orchestrator import get_orchestrator
                orch = get_orchestrator()
                state = await orch.arun(
                    project_id=body.project_id,
                    thread_id="eval-thread",
                    user_message=prompt,
                )
                messages = state.get("messages", [])
                if messages:
                    return messages[-1].content
                return str(state)
            except Exception as e:
                import traceback
                return f"Agent error: {e}\n{traceback.format_exc()}"

        async def _on_progress(runs, completed, total):
            try:
                store = TaskResultStore()
                scores = [r.overall_score for r in runs if r.error is None]
                passed = sum(1 for r in runs if r.passed)
                is_done = completed >= total
                latencies = sorted([r.latency_ms for r in runs if r.error is None])
                p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0

                await store.save(body.suite_id, {
                    "suite_id": body.suite_id,
                    "status": "complete" if is_done else "running",
                    "total": total,
                    "completed": completed,
                    "passed": passed,
                    "pass_rate": round(passed / completed, 3) if completed else 0.0,
                    "mean_score": round(sum(scores) / len(scores), 1) if scores else 0.0,
                    "p95_latency_ms": round(p95, 0),
                    "runs": [
                        {
                            "case_id": r.case_id,
                            "case_name": r.case_name,
                            "passed": r.passed,
                            "overall_score": round(r.overall_score, 1),
                            "keyword_recall": round(r.keyword_recall, 3),
                            "rubric_score": round(r.rubric_score, 1),
                            "latency_ms": round(r.latency_ms, 0),
                            "error": r.error,
                            "actual_output": getattr(r, "agent_output", ""),
                        }
                        for r in runs
                    ],
                })
            except Exception:
                pass

        report = await suite.run(
            suite_id=body.suite_id,
            agent_fn=agent_fn,
            case_ids=body.case_ids,
            on_progress=_on_progress,
        )

        # Final store update marked complete
        await _on_progress(report.runs, len(report.runs), len(report.runs))

    background_tasks.add_task(_run)

    return {
        "status": "running",
        "suite_id": body.suite_id,
        "cases_scheduled": len(available_cases),
        "case_ids": available_cases,
        "message": "Benchmark started. Check /evaluation/benchmark/status/{suite_id} for results.",
    }


@router.get("/benchmark/cases")
async def list_benchmark_cases():
    """List all available golden test cases with their metadata."""
    from evaluation.benchmark_suite import GOLDEN_TEST_CASES

    return {
        "total": len(GOLDEN_TEST_CASES),
        "cases": [
            {
                "id": c.id,
                "name": c.name,
                "task_type": c.task_type,
                "expected_keywords": c.expected_keywords,
                "timeout_seconds": c.timeout_seconds,
            }
            for c in GOLDEN_TEST_CASES
        ],
    }


@router.get("/benchmark/status/{suite_id}")
async def get_benchmark_status(suite_id: str):
    """Poll benchmark run results by suite_id."""
    try:
        from backend.services.task_manager import TaskResultStore
        store = TaskResultStore()
        result = await store.get(suite_id)
        if result:
            return result
        return {"status": "running", "suite_id": suite_id, "completed": 0, "runs": []}
    except Exception:
        return {"status": "unknown", "suite_id": suite_id}
