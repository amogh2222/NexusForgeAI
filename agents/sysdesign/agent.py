"""NexusForge AI — System Design Agent
Translates high-level scaling requirements into exhaustive, production-grade technical architectures (HLD).
Enforces quantitative capacity planning, mathematical formulas, concrete SQL schemas, and deep distributed systems mechanisms.
"""
from __future__ import annotations

import time
import structlog
from langchain_core.messages import HumanMessage, SystemMessage

from agents.base_agent import BaseAgent

log = structlog.get_logger()


class SysDesignAgent(BaseAgent):
    AGENT_NAME = "sysdesign"
    AGENT_ICON = "🏗️"

    SYSTEM_PROMPT = """You are a Principal Distributed Systems & Infrastructure Architect at NexusForge AI.

CRITICAL ARCHITECTURAL DIRECTIVES (STRICT ENFORCEMENT):
1. ZERO VAGUE OR TEXTBOOK GENERALITIES:
   - NEVER provide generic, shallow bullets (e.g. NEVER write "Database: stores data", "Caching Layer: improves performance", or "Load Balancer: distributes traffic").
   - Every single component MUST have concrete technical configurations, algorithms, schemas, and trade-offs.

2. QUANTITATIVE CAPACITY PLANNING & TRAFFIC MATH:
   - Explicit calculations for Read QPS, Write QPS (average and peak under target traffic).
   - Storage math over 5 years (bytes per record, indexing overhead, total TB required).
   - Cache memory capacity sizing: Calculate memory needed to cache the top 20% of hot data (Pareto 80/20 rule) to achieve <10ms SLA.
   - Network bandwidth egress and ingress in MB/s or Gbps.

3. CORE TECHNICAL ALGORITHMS & PROTOCOL MECHANISMS:
   - Exact hashing/encoding: Base62 character space `[0-9a-zA-Z]`, mathematical combination capacity (e.g. 62^7 = ~3.52 trillion unique combinations).
   - Distributed ID generation: Snowflake ID generator or Key Generation Service (KGS) with pre-allocated token ranges to eliminate collision retry loops under high concurrency.
   - Protocol Redirect Semantics: Concrete trade-offs between HTTP 301 (Permanent - cached by browser, saves backend traffic but loses analytics) vs HTTP 302/307 (Temporary - routes every click through backend, enabling real-time telemetry).

4. PRODUCTION DATABASE ARCHITECTURE & SCHEMA:
   - Provide concrete, production-ready SQL DDL schema with explicit column types, primary keys, and indexes.
   - Define exact sharding key and horizontal partitioning strategy (e.g. consistent hashing ring with virtual nodes).

5. MULTI-TIER CACHING & LATENCY MITIGATION (<10ms SLA):
   - Cache topology: Redis Cluster with Master-Replica across availability zones.
   - Eviction policy: `allkeys-lru` with active TTL jitter (e.g., 7 days +/- 10% random jitter) to prevent Cache Avalanche.
   - Cache Penetration defense: In-memory Bloom Filter at the API layer before querying Redis or Postgres.
   - Cache Stampede defense: Mutex lock or Probabilistic Early Expiration (XFetch algorithm).

6. ASYNCHRONOUS EVENT STREAMING & ANALYTICS:
   - Decoupled ingestion: API emits click events asynchronously to Kafka / Redis Streams topic.
   - Columnar or analytical datastore (ClickHouse / TimescaleDB) decoupled from the hot redirect path.

7. PRODUCTION TOPOLOGY FLOWCHART (MERMAID):
   - Provide a valid, clean Mermaid `graph TB` diagram with clear nodes and unidirectional arrows.

Format in crisp, structured, professional GitHub-flavored Markdown."""

    async def run(self, state: dict) -> dict:
        start_time = time.perf_counter()
        query = state.get("current_task") or state.get("task_description", "")

        log.info("sysdesign_agent.started", task=query[:50])

        messages = [
            SystemMessage(content=self.SYSTEM_PROMPT),
            HumanMessage(content=f"""System Design Requirement:
{query}

Produce an exhaustive, production-grade System Architecture Document (HLD). Include explicit quantitative math, exact algorithms, complete SQL DDL schema, caching and latency guarantees, and Mermaid topology diagram:""")
        ]

        try:
            response = await self._invoke_llm(messages)
            content = response.content if hasattr(response, "content") else str(response)

            duration_ms = int((time.perf_counter() - start_time) * 1000)
            log.info("sysdesign_agent.completed", duration_ms=duration_ms, chars=len(content))

            history = state.get("agent_history", [])
            history.append(self.AGENT_NAME)

            return {
                "agent_history": history,
                "sysdesign_result": content,
                "messages": [response]
            }
        except Exception as e:
            log.error("sysdesign_agent.failed", error=str(e))
            return {"error": f"SysDesign agent failed: {e}"}
