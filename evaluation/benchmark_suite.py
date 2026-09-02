"""
NexusForge AI — Agent Benchmark Suite
Golden test cases for evaluating agent output quality.

Golden cases cover the 5 core agent tasks. Each case defines:
  - Natural language input
  - Required keywords in output (keyword recall check)
  - LLM rubric for quality scoring

Scoring: keyword_recall + rubric_score → pass/fail (threshold: 70/100)
"""
from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Optional

import structlog

log = structlog.get_logger()


# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class BenchmarkCase:
    id: str
    name: str
    task_type: str           # "readme", "bug_fix", "review", "architecture", "explain"
    input_prompt: str
    expected_keywords: list[str]  # must appear in output (case-insensitive)
    rubric_name: str
    timeout_seconds: int = 90


@dataclass
class BenchmarkRun:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    case_id: str = ""
    case_name: str = ""
    agent_output: str = ""
    keyword_recall: float = 0.0     # fraction of expected_keywords found
    rubric_score: float = 0.0       # 0-100 from LLM judge
    overall_score: float = 0.0      # 0.4 * keyword_recall + 0.6 * rubric_score
    latency_ms: float = 0.0
    passed: bool = False            # overall_score >= 70
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class EvaluationReport:
    suite_id: str
    total_cases: int
    passed_cases: int
    pass_rate: float
    mean_score: float
    p95_latency_ms: float
    runs: list[BenchmarkRun]
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Golden Test Cases ───────────────────────────────────────────────────────

GOLDEN_TEST_CASES: list[BenchmarkCase] = [
    BenchmarkCase(
        id="readme-001",
        name="Production README Generation",
        task_type="readme",
        input_prompt=(
            "Generate a production-grade README.md for a FastAPI + PostgreSQL + Redis "
            "microservice called OrderService that handles e-commerce orders. "
            "Include: description, features, prerequisites, installation, environment "
            "variables, API endpoints, running locally, Docker deployment, testing, "
            "and contributing guide."
        ),
        expected_keywords=[
            "installation", "docker", "api", "environment", "postgresql", "redis",
            "testing", "endpoints", "configuration",
        ],
        rubric_name="README_RUBRIC",
        timeout_seconds=90,
    ),
    BenchmarkCase(
        id="bugfix-001",
        name="SQL Injection Bug Fix",
        task_type="bug_fix",
        input_prompt=(
            "Fix this Python code that has a SQL injection vulnerability:\n\n"
            "```python\n"
            "def get_user(username: str):\n"
            "    query = f\"SELECT * FROM users WHERE username = '{username}'\"\n"
            "    return db.execute(query)\n"
            "```\n\n"
            "Explain the vulnerability and provide the fixed version."
        ),
        expected_keywords=[
            "injection", "parameterized", "parameter", "placeholder", "unsafe",
            "vulnerable",
        ],
        rubric_name="BUG_FIX_RUBRIC",
        timeout_seconds=60,
    ),
    BenchmarkCase(
        id="review-001",
        name="Code Review — Async Python",
        task_type="review",
        input_prompt=(
            "Review this async Python code and identify all issues:\n\n"
            "```python\n"
            "import asyncio\n\n"
            "async def process_items(items):\n"
            "    results = []\n"
            "    for item in items:\n"
            "        result = await slow_operation(item)  # runs sequentially!\n"
            "        results.append(result)\n"
            "    return results\n"
            "```\n\n"
            "What are the performance issues and how do you fix them?"
        ),
        expected_keywords=[
            "sequential", "concurrent", "gather", "asyncio.gather", "parallel",
            "performance",
        ],
        rubric_name="CODE_REVIEW_RUBRIC",
        timeout_seconds=60,
    ),
    BenchmarkCase(
        id="arch-001",
        name="Architecture Explanation — CQRS",
        task_type="architecture",
        input_prompt=(
            "Explain the CQRS (Command Query Responsibility Segregation) pattern "
            "and when to use it. Include: core concept, benefits, drawbacks, "
            "when NOT to use it, and a concrete Python/FastAPI implementation example."
        ),
        expected_keywords=[
            "command", "query", "read", "write", "separation", "event", "consistency",
        ],
        rubric_name="ARCHITECTURE_RUBRIC",
        timeout_seconds=90,
    ),
    BenchmarkCase(
        id="sysdesign-001",
        name="System Design — URL Shortener",
        task_type="architecture",
        input_prompt=(
            "Design a URL shortening service (like bit.ly) that handles 100M daily "
            "redirects. Include: API design, database schema, caching strategy, "
            "hash generation algorithm, analytics tracking, and scaling approach. "
            "Target: <10ms redirect latency at 10K RPS."
        ),
        expected_keywords=[
            "cache", "redis", "hash", "redirect", "database", "scale", "cdn",
            "analytics", "10ms",
        ],
        rubric_name="ARCHITECTURE_RUBRIC",
        timeout_seconds=120,
    ),
]

# Index by ID for fast lookup
CASE_INDEX: dict[str, BenchmarkCase] = {c.id: c for c in GOLDEN_TEST_CASES}


# ─── Rubric Scoring ──────────────────────────────────────────────────────────

async def _score_with_rubric(rubric_name: str, output: str, prompt: str) -> float:
    """Use LLM as judge to score agent output 0-100."""
    rubric_prompts = {
        "README_RUBRIC": (
            "Score this README 0-100 on: completeness (25pts), technical accuracy (25pts), "
            "code examples (20pts), deployment guide (20pts), clarity (10pts). "
            "Return only a JSON object: {\"score\": <number>, \"reasoning\": \"<brief>\"}"
        ),
        "BUG_FIX_RUBRIC": (
            "Score this bug fix 0-100 on: root cause identified (30pts), fix correctness (40pts), "
            "no regressions introduced (20pts), explanation quality (10pts). "
            "Return only JSON: {\"score\": <number>, \"reasoning\": \"<brief>\"}"
        ),
        "CODE_REVIEW_RUBRIC": (
            "Score this code review 0-100 on: issue severity accuracy (35pts), "
            "actionable suggestions (35pts), missed critical issues penalized (20pts), "
            "false positive rate penalized (10pts). "
            "Return only JSON: {\"score\": <number>, \"reasoning\": \"<brief>\"}"
        ),
        "ARCHITECTURE_RUBRIC": (
            "Score this architecture explanation 0-100 on: technical accuracy (35pts), "
            "depth and completeness (35pts), clarity (20pts), concrete examples (10pts). "
            "Return only JSON: {\"score\": <number>, \"reasoning\": \"<brief>\"}"
        ),
    }

    rubric = rubric_prompts.get(rubric_name, rubric_prompts["ARCHITECTURE_RUBRIC"])
    judge_prompt = (
        f"Task: {prompt[:300]}\n\nAgent output:\n{output[:2000]}\n\n"
        f"Scoring rubric: {rubric}"
    )

    try:
        from backend.core.config import settings
        from langchain_core.messages import HumanMessage

        if settings.OPENAI_API_KEY:
            from langchain_openai import ChatOpenAI
            llm = ChatOpenAI(model="gpt-4o-mini", api_key=settings.OPENAI_API_KEY, temperature=0)
        else:
            from langchain_ollama import ChatOllama
            llm = ChatOllama(model=settings.OLLAMA_MODEL, base_url=settings.OLLAMA_BASE_URL, temperature=0)

        response = await llm.ainvoke([HumanMessage(content=judge_prompt)])
        content = response.content if hasattr(response, "content") else str(response)

        import json
        import re
        json_match = re.search(r'\{[^}]+\}', content)
        if json_match:
            parsed = json.loads(json_match.group())
            return float(parsed.get("score", 50))
        return 50.0
    except Exception as e:
        log.warning("benchmark.rubric_scoring_failed", error=str(e))
        return 50.0  # neutral score on failure


# ─── Benchmark Suite ─────────────────────────────────────────────────────────

class BenchmarkSuite:
    """Runs golden test cases against an agent function and scores the results."""

    PASS_THRESHOLD = 70.0

    async def run(
        self,
        suite_id: str,
        agent_fn: Callable,
        case_ids: Optional[list[str]] = None,
    ) -> EvaluationReport:
        """
        Run benchmark cases against an agent function.

        Args:
            suite_id:  Identifier for this evaluation run
            agent_fn:  Async callable (str) -> str: takes prompt, returns agent output
            case_ids:  Optional list of case IDs to run (default: all cases)
        """
        cases = (
            [CASE_INDEX[cid] for cid in case_ids if cid in CASE_INDEX]
            if case_ids
            else GOLDEN_TEST_CASES
        )

        log.info("benchmark.starting", suite_id=suite_id, cases=len(cases))
        runs: list[BenchmarkRun] = []

        for case in cases:
            run = await self._run_single_case(case, agent_fn)
            runs.append(run)
            log.info(
                "benchmark.case_complete",
                case=case.name,
                score=run.overall_score,
                passed=run.passed,
                latency_ms=run.latency_ms,
            )

        return self._aggregate(suite_id, runs)

    async def _run_single_case(
        self, case: BenchmarkCase, agent_fn: Callable
    ) -> BenchmarkRun:
        run = BenchmarkRun(case_id=case.id, case_name=case.name)
        start = time.perf_counter()

        try:
            # Call agent with timeout
            output = await asyncio.wait_for(
                agent_fn(case.input_prompt),
                timeout=case.timeout_seconds,
            )
            run.agent_output = str(output)[:5000]

        except asyncio.TimeoutError:
            run.error = f"Timeout after {case.timeout_seconds}s"
            run.latency_ms = case.timeout_seconds * 1000
            return run
        except Exception as e:
            run.error = str(e)
            run.latency_ms = (time.perf_counter() - start) * 1000
            return run

        run.latency_ms = (time.perf_counter() - start) * 1000

        # Keyword recall: fraction of expected keywords found
        output_lower = run.agent_output.lower()
        found = sum(1 for kw in case.expected_keywords if kw in output_lower)
        run.keyword_recall = found / len(case.expected_keywords) if case.expected_keywords else 1.0

        # LLM rubric scoring
        run.rubric_score = await _score_with_rubric(
            case.rubric_name, run.agent_output, case.input_prompt
        )

        # Weighted overall: 40% keyword recall + 60% rubric quality
        run.overall_score = (run.keyword_recall * 100 * 0.4) + (run.rubric_score * 0.6)
        run.passed = run.overall_score >= self.PASS_THRESHOLD

        return run

    def _aggregate(self, suite_id: str, runs: list[BenchmarkRun]) -> EvaluationReport:
        passed = sum(1 for r in runs if r.passed)
        scores = [r.overall_score for r in runs if r.error is None]
        latencies = sorted([r.latency_ms for r in runs if r.error is None])
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0.0

        return EvaluationReport(
            suite_id=suite_id,
            total_cases=len(runs),
            passed_cases=passed,
            pass_rate=passed / len(runs) if runs else 0.0,
            mean_score=sum(scores) / len(scores) if scores else 0.0,
            p95_latency_ms=p95,
            runs=runs,
        )
