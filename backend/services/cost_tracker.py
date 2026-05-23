"""
NexusForge AI — Cost & Token Intelligence
Tracks LLM token usage and costs per project, model, and agent task.

Features:
  - Real-time cost accumulation in Redis (fast, no DB writes per request)
  - Daily/weekly/monthly aggregation snapshots in PostgreSQL
  - Per-model pricing table with input/output differentiation
  - Cost efficiency ranking (value per dollar)
  - Budget alerts and model routing recommendations
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Optional

import structlog

log = structlog.get_logger()


# ─── Pricing Table ────────────────────────────────────────────────────────────
# Cost per 1M tokens (input / output)

MODEL_PRICING: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o":        {"input": 2.50,  "output": 10.0},
    "gpt-4o-mini":   {"input": 0.15,  "output": 0.60},
    "gpt-4-turbo":   {"input": 10.0,  "output": 30.0},
    "gpt-3.5-turbo": {"input": 0.50,  "output": 1.50},
    # Anthropic
    "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
    "claude-3-haiku":    {"input": 0.25, "output": 1.25},
    # Local models (compute cost only — approximate)
    "qwen2.5-coder:7b":   {"input": 0.0, "output": 0.0},  # free local
    "llama3.2:3b":        {"input": 0.0, "output": 0.0},
    "nomic-embed-text":   {"input": 0.0, "output": 0.0},
    "default":            {"input": 0.0, "output": 0.0},
}


def get_model_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate USD cost for a model call."""
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["default"])
    return (
        (input_tokens / 1_000_000) * pricing["input"]
        + (output_tokens / 1_000_000) * pricing["output"]
    )


# ─── Token Event ─────────────────────────────────────────────────────────────

@dataclass
class TokenEvent:
    project_id: str
    task_id: str
    agent: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class ProjectCostSummary:
    project_id: str
    total_input_tokens: int
    total_output_tokens: int
    total_cost_usd: float
    calls_by_model: dict[str, int]
    cost_by_model: dict[str, float]
    cost_by_agent: dict[str, float]
    period_start: str
    period_end: str
    cheapest_model: str
    most_used_model: str


# ─── Cost Tracker ─────────────────────────────────────────────────────────────

class CostTracker:
    """
    Tracks LLM token costs in Redis for real-time dashboards.

    Data structures:
      nexusforge:costs:{project_id}:total_input_tokens  → int (INCRBY)
      nexusforge:costs:{project_id}:total_output_tokens → int (INCRBY)
      nexusforge:costs:{project_id}:total_cost_usd      → float (INCRBYFLOAT)
      nexusforge:costs:{project_id}:by_model:{model}:calls → int
      nexusforge:costs:{project_id}:by_model:{model}:cost  → float
      nexusforge:costs:{project_id}:by_agent:{agent}:cost  → float
      nexusforge:costs:{project_id}:events                 → list of JSON events (LPUSH, capped at 100)
    """

    KEY_PREFIX = "nexusforge:costs"

    _instance: Optional["CostTracker"] = None

    def __init__(self) -> None:
        self._redis = None
        self._connect()

    def _connect(self) -> None:
        try:
            import redis.asyncio as aioredis
            from backend.core.config import settings
            self._redis = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
            )
            log.info("cost_tracker.connected")
        except Exception as e:
            log.warning("cost_tracker.redis_unavailable", error=str(e))

    # ─── Record ──────────────────────────────────────────────────────────────

    async def record(
        self,
        project_id: str,
        task_id: str,
        agent: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float = 0.0,
    ) -> TokenEvent:
        """Record a token usage event. Returns the event for further use."""
        cost = get_model_cost(model, input_tokens, output_tokens)
        event = TokenEvent(
            project_id=project_id,
            task_id=task_id,
            agent=agent,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=latency_ms,
        )

        if self._redis:
            try:
                p = self._redis.pipeline()
                prefix = f"{self.KEY_PREFIX}:{project_id}"
                p.incrby(f"{prefix}:total_input_tokens", input_tokens)
                p.incrby(f"{prefix}:total_output_tokens", output_tokens)
                p.incrbyfloat(f"{prefix}:total_cost_usd", cost)
                p.incr(f"{prefix}:by_model:{model}:calls")
                p.incrbyfloat(f"{prefix}:by_model:{model}:cost", cost)
                p.incrbyfloat(f"{prefix}:by_agent:{agent}:cost", cost)
                # Keep last 100 events
                p.lpush(f"{prefix}:events", json.dumps(asdict(event)))
                p.ltrim(f"{prefix}:events", 0, 99)
                await p.execute()
            except Exception as e:
                log.warning("cost_tracker.record_failed", error=str(e))

        log.info(
            "cost.recorded",
            project=project_id,
            agent=agent,
            model=model,
            tokens=input_tokens + output_tokens,
            cost_usd=round(cost, 6),
        )
        return event

    # ─── Query ───────────────────────────────────────────────────────────────

    async def get_project_summary(self, project_id: str) -> ProjectCostSummary:
        """Get current cost summary for a project."""
        if not self._redis:
            return self._empty_summary(project_id)

        try:
            prefix = f"{self.KEY_PREFIX}:{project_id}"

            # Get totals
            total_input = int(await self._redis.get(f"{prefix}:total_input_tokens") or 0)
            total_output = int(await self._redis.get(f"{prefix}:total_output_tokens") or 0)
            total_cost = float(await self._redis.get(f"{prefix}:total_cost_usd") or 0)

            # Get per-model stats
            calls_by_model: dict[str, int] = {}
            cost_by_model: dict[str, float] = {}
            for model in MODEL_PRICING:
                calls = await self._redis.get(f"{prefix}:by_model:{model}:calls")
                cost = await self._redis.get(f"{prefix}:by_model:{model}:cost")
                if calls:
                    calls_by_model[model] = int(calls)
                    cost_by_model[model] = float(cost or 0)

            # Per-agent costs
            cost_by_agent: dict[str, float] = {}
            for key in await self._redis.keys(f"{prefix}:by_agent:*:cost"):
                agent_name = key.split(":by_agent:")[1].split(":cost")[0]
                cost_by_agent[agent_name] = float(await self._redis.get(key) or 0)

            most_used = max(calls_by_model, key=calls_by_model.get, default="unknown")
            cheapest = min(
                [m for m in cost_by_model if cost_by_model[m] > 0],
                key=lambda m: MODEL_PRICING.get(m, {}).get("input", 0),
                default="local model",
            )

            return ProjectCostSummary(
                project_id=project_id,
                total_input_tokens=total_input,
                total_output_tokens=total_output,
                total_cost_usd=total_cost,
                calls_by_model=calls_by_model,
                cost_by_model=cost_by_model,
                cost_by_agent=cost_by_agent,
                period_start="",
                period_end=datetime.now(timezone.utc).isoformat(),
                cheapest_model=cheapest,
                most_used_model=most_used,
            )

        except Exception as e:
            log.warning("cost_tracker.summary_failed", error=str(e))
            return self._empty_summary(project_id)

    async def get_global_summary(self) -> dict:
        """Get cost summary across all projects."""
        if not self._redis:
            return {"total_cost_usd": 0, "projects": {}}
        try:
            keys = await self._redis.keys(f"{self.KEY_PREFIX}:*:total_cost_usd")
            total = 0.0
            projects = {}
            for key in keys:
                project_id = key.split(":")[2]
                cost = float(await self._redis.get(key) or 0)
                total += cost
                projects[project_id] = cost
            return {
                "total_cost_usd": round(total, 4),
                "total_projects": len(projects),
                "projects": projects,
            }
        except Exception as e:
            return {"error": str(e)}

    async def reset_project(self, project_id: str) -> None:
        """Reset all cost counters for a project."""
        if not self._redis:
            return
        prefix = f"{self.KEY_PREFIX}:{project_id}"
        keys = await self._redis.keys(f"{prefix}:*")
        if keys:
            await self._redis.delete(*keys)
        log.info("cost_tracker.project_reset", project_id=project_id)

    def get_pricing_table(self) -> dict:
        """Return the full model pricing table for the frontend."""
        return {
            model: {
                "input_per_1m": pricing["input"],
                "output_per_1m": pricing["output"],
                "is_local": pricing["input"] == 0.0,
            }
            for model, pricing in MODEL_PRICING.items()
        }

    @staticmethod
    def _empty_summary(project_id: str) -> ProjectCostSummary:
        return ProjectCostSummary(
            project_id=project_id,
            total_input_tokens=0,
            total_output_tokens=0,
            total_cost_usd=0.0,
            calls_by_model={},
            cost_by_model={},
            cost_by_agent={},
            period_start="",
            period_end=datetime.now(timezone.utc).isoformat(),
            cheapest_model="local model",
            most_used_model="unknown",
        )

    @classmethod
    def get_instance(cls) -> "CostTracker":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
