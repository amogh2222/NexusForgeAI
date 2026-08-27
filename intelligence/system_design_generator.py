"""
NexusForge AI — System Design Generator
Generates high-level architecture designs for scaling repositories.

Combines:
  1. RAG context about the current tech stack
  2. Neo4j graph: service topology, API endpoints, DB schema
  3. LLM generation with structured prompting

Output: production HLD document with Mermaid diagram, cost estimate,
database sharding strategy, cache design, and monitoring plan.

Use case: "Design NexusForge AI to handle 10M concurrent users"
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import AsyncIterator, Optional

import structlog

log = structlog.get_logger()


# ─── Scale Targets ───────────────────────────────────────────────────────────

SCALE_PRESETS: dict[str, dict] = {
    "1M_users": {
        "users": "1M",
        "rps": 1_000,
        "latency_p99_ms": 200,
        "data_gb": 500,
        "geo_regions": 1,
        "description": "Regional SaaS (Series A)",
    },
    "10M_users": {
        "users": "10M",
        "rps": 10_000,
        "latency_p99_ms": 100,
        "data_gb": 5_000,
        "geo_regions": 2,
        "description": "Multi-region SaaS (Series B-C)",
    },
    "100M_users": {
        "users": "100M",
        "rps": 100_000,
        "latency_p99_ms": 50,
        "data_gb": 50_000,
        "geo_regions": 4,
        "description": "Global platform (IPO-scale)",
    },
    "1B_users": {
        "users": "1B",
        "rps": 1_000_000,
        "latency_p99_ms": 20,
        "data_gb": 500_000,
        "geo_regions": 6,
        "description": "Hyperscale (FAANG-tier)",
    },
}


@dataclass
class SystemDesignDoc:
    repo_id: str
    scale: str
    users: str
    rps: int
    executive_summary: str
    load_balancing: str
    database_strategy: str
    cache_layer: str
    queue_design: str
    autoscaling: str
    cdn_strategy: str
    monitoring: str
    cost_estimate: str
    mermaid_diagram: str
    generated_at: str


class SystemDesignGenerator:
    """
    Generates production-grade system design documents using LLM + RAG + graph context.
    """

    async def generate(self, repo_id: str, scale: str = "10M_users") -> SystemDesignDoc:
        """Generate a complete system design document."""
        preset = SCALE_PRESETS.get(scale, SCALE_PRESETS["10M_users"])
        context = await self._gather_context(repo_id)
        full_design = await self._generate_sections(repo_id, preset, context)
        return full_design

    async def stream_generation(
        self, repo_id: str, scale: str = "10M_users"
    ) -> AsyncIterator[str]:
        """Stream the system design document token by token."""
        preset = SCALE_PRESETS.get(scale, SCALE_PRESETS["10M_users"])
        context = await self._gather_context(repo_id)
        async for token in self._stream_sections(repo_id, preset, context):
            yield token

    # ─── Context Gathering ────────────────────────────────────────────────────

    async def _gather_context(self, repo_id: str) -> dict:
        """Gather RAG context and graph data about the repository."""
        context: dict = {"rag": "", "graph": "", "api_endpoints": [], "circular_deps": []}

        # RAG: retrieve tech stack context
        try:
            from rag.retrieval.retriever import HybridRetriever
            retriever = HybridRetriever(top_k=5, max_context_tokens=3000)
            rag_context, _ = await retriever.retrieve(
                query="technology stack architecture services database configuration",
                project_id=repo_id,
            )
            context["rag"] = rag_context[:2000]
        except Exception as e:
            log.warning("sysdesign.rag_failed", error=str(e))

        # Graph: get architectural topology
        try:
            from graph.neo4j_client import Neo4jClient
            client = Neo4jClient.get_instance()
            if client.is_available():
                stats = await client.get_repo_stats(repo_id)
                endpoints = await client.get_api_endpoints(repo_id)
                circular = await client.find_circular_dependencies(repo_id)
                impact = await client.find_high_impact_entities(repo_id)
                context["graph"] = json.dumps(stats, indent=2)
                context["api_endpoints"] = endpoints[:10]
                context["circular_deps"] = circular[:3]
                context["impact_entities"] = impact[:5]
        except Exception as e:
            log.warning("sysdesign.graph_failed", error=str(e))

        return context

    async def _generate_sections(
        self, repo_id: str, preset: dict, context: dict
    ) -> SystemDesignDoc:
        """Generate all sections using LLM."""
        from agents.router.model_router import ModelRouter, TaskType

        llm = ModelRouter.get_instance().get_langchain_llm(TaskType.GENERAL)

        prompt = self._build_prompt(preset, context)

        try:
            # Generate full design in one shot
            from langchain_core.messages import HumanMessage
            response = await llm.ainvoke([HumanMessage(content=prompt)])
            raw = response.content if hasattr(response, "content") else str(response)
            if isinstance(raw, list):
                # Gemini returns a list of blocks, extract text
                text_blocks = [b.get("text", "") for b in raw if isinstance(b, dict) and "text" in b]
                raw = "".join(text_blocks) if text_blocks else str(raw)
        except Exception as e:
            log.warning("sysdesign.llm_failed", error=str(e))
            raw = self._fallback_design(preset)

        sections = self._parse_sections(raw)
        
        # Use LLM generated diagram, strip markdown code block backticks if present
        mermaid = sections.get("MERMAID_DIAGRAM", self._generate_mermaid(context, preset))
        if mermaid.startswith("```mermaid"):
            mermaid = mermaid[10:]
        if mermaid.startswith("```"):
            mermaid = mermaid[3:]
        if mermaid.endswith("```"):
            mermaid = mermaid[:-3]
        mermaid = mermaid.strip()
        if not mermaid.startswith("graph"):
            mermaid = "graph TB\n" + mermaid

        return SystemDesignDoc(
            repo_id=repo_id,
            scale=f"{preset['users']}_users",
            users=preset["users"],
            rps=preset["rps"],
            executive_summary=sections.get("EXECUTIVE_SUMMARY", "See full design below."),
            load_balancing=sections.get("LOAD_BALANCING", raw[:500]),
            database_strategy=sections.get("DATABASE_STRATEGY", ""),
            cache_layer=sections.get("CACHE_LAYER", ""),
            queue_design=sections.get("QUEUE_DESIGN", ""),
            autoscaling=sections.get("AUTOSCALING", ""),
            cdn_strategy=sections.get("CDN_STRATEGY", ""),
            monitoring=sections.get("MONITORING", ""),
            cost_estimate=sections.get("COST_ESTIMATE", ""),
            mermaid_diagram=mermaid,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    async def _stream_sections(
        self, repo_id: str, preset: dict, context: dict
    ) -> AsyncIterator[str]:
        """Stream LLM generation token by token."""
        from agents.router.model_router import ModelRouter, TaskType
        from langchain_core.messages import HumanMessage

        llm = ModelRouter.get_instance().get_langchain_llm(TaskType.GENERAL)
        prompt = self._build_prompt(preset, context)

        yield f"# System Design: {preset['users']} Users\n\n"

        try:
            async for chunk in llm.astream([HumanMessage(content=prompt)]):
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content:
                    yield content
        except Exception as e:
            yield f"\n\n⚠️ Generation error: {e}\n"

        yield f"\n\n---\n\n{self._generate_mermaid(context, preset)}"

    # ─── Prompt Building ─────────────────────────────────────────────────────

    def _build_prompt(self, preset: dict, context: dict) -> str:
        endpoints_text = ""
        if context.get("api_endpoints"):
            ep_lines = [
                f"  - {e.get('method','?')} {e.get('path','?')}"
                for e in context["api_endpoints"][:8]
            ]
            endpoints_text = "Detected API endpoints:\n" + "\n".join(ep_lines)

        return f"""You are a principal architect at a leading tech company.
Design a production system to scale this application to {preset['users']} users.

Target metrics:
- Users: {preset['users']} ({preset['description']})
- Peak RPS: {preset['rps']:,}
- P99 latency: <{preset['latency_p99_ms']}ms
- Data volume: {preset['data_gb']:,}GB
- Geographic regions: {preset['geo_regions']}

Current codebase context:
{context.get('rag', 'No context available')[:1500]}

{endpoints_text}

Generate a detailed system design with these sections (use these EXACT headers):
## EXECUTIVE_SUMMARY
## LOAD_BALANCING
## DATABASE_STRATEGY
## CACHE_LAYER
## QUEUE_DESIGN
## AUTOSCALING
## CDN_STRATEGY
## MONITORING
## COST_ESTIMATE
## MERMAID_DIAGRAM

For the MERMAID_DIAGRAM section, provide ONLY a valid mermaid graph TB block that models the architecture based on the provided endpoints and codebase context.

Be specific: mention exact technologies (e.g., Aurora PostgreSQL vs CockroachDB),
specific configurations (e.g., Redis Cluster with 6 nodes, 32GB RAM each),
and exact pricing estimates ($X/month at scale).
"""

    def _parse_sections(self, raw: str) -> dict[str, str]:
        """Parse ## SECTION_NAME sections from LLM output."""
        sections: dict[str, str] = {}
        current_key = None
        current_lines: list[str] = []

        for line in raw.splitlines():
            if line.startswith("## ") and line[3:].strip().isupper():
                if current_key and current_lines:
                    sections[current_key] = "\n".join(current_lines).strip()
                current_key = line[3:].strip()
                current_lines = []
            elif current_key:
                current_lines.append(line)

        if current_key and current_lines:
            sections[current_key] = "\n".join(current_lines).strip()

        return sections

    def _generate_mermaid(self, context: dict, preset: dict) -> str:
        """Generate a Mermaid architecture diagram from graph context."""
        endpoints = context.get("api_endpoints", [])
        has_endpoints = bool(endpoints)

        rps = preset.get("rps", 10000)
        cdn = "CloudFront" if rps > 50000 else "CloudFlare"
        db = "Aurora PostgreSQL + Read Replicas" if rps > 10000 else "PostgreSQL"
        cache = "Redis Cluster (6 nodes)" if rps > 50000 else "Redis Sentinel"

        diagram = f"""```mermaid
graph TB
    Client["👤 Users ({preset['users']})"]
    CDN["{cdn} CDN"]
    LB["Load Balancer\\nNGINX / AWS ALB"]
    API1["API Pod 1\\nFastAPI"]
    API2["API Pod 2\\nFastAPI"]
    API3["API Pod N\\nFastAPI (HPA)"]
    Cache["{cache}\\nSession + Query Cache"]
    DB["{db}\\nPrimary + Replicas"]
    Queue["Message Queue\\nRedis Streams / Kafka"]
    Workers["Celery Workers\\nAI Agent Pool (HPA)"]
    Storage["Object Storage\\nS3 / R2"]
    Monitor["Observability\\nGrafana + Prometheus"]

    Client --> CDN
    CDN --> LB
    LB --> API1 & API2 & API3
    API1 & API2 & API3 --> Cache
    API1 & API2 & API3 --> DB
    API1 & API2 & API3 --> Queue
    Queue --> Workers
    Workers --> DB
    Workers --> Storage
    DB --> Monitor
    API1 --> Monitor
```"""
        return diagram

    def _fallback_design(self, preset: dict) -> str:
        return f"""## EXECUTIVE_SUMMARY
Scale to {preset['users']} users using horizontal scaling, CDN, and distributed caching.

## LOAD_BALANCING
Deploy NGINX + AWS ALB with sticky sessions disabled. Use HPA (min 3, max 50 pods).

## DATABASE_STRATEGY
Aurora PostgreSQL with 1 writer + 3 read replicas. Implement read/write splitting.

## CACHE_LAYER
Redis Cluster with 6 nodes. Cache: sessions (30min TTL), queries (5min TTL), embeddings (24h TTL).

## QUEUE_DESIGN
Redis Streams for < 50K RPS. Kafka for > 50K RPS. Topics: task.*, agent.*, result.*.

## AUTOSCALING
Kubernetes HPA based on CPU (70%) and custom metrics (queue depth). Karpenter for node autoscaling.

## CDN_STRATEGY
CloudFront for static assets (S3 origin). Edge caching for API responses with 5min TTL.

## MONITORING
Grafana + Prometheus + OpenTelemetry. SLOs: p99 < {preset['latency_p99_ms']}ms, error rate < 0.1%.

## COST_ESTIMATE
Estimated ${preset['rps'] * 0.05:.0f}/month at {preset['rps']:,} RPS on AWS (compute + DB + network).
"""
