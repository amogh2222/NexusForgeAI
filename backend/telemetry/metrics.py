"""NexusForge AI — Prometheus Metrics Setup."""
from fastapi import FastAPI
from prometheus_client import Counter, Gauge, Histogram

# ─── Custom Metrics Declared in README ──────────────────────────

# Agent runs by name + status
agent_executions_total = Counter(
    "nexus_agent_executions_total",
    "Total agent graph executions by agent name and status",
    ["agent", "status"],
)

# RAG retrieval latency
retrieval_latency_seconds = Histogram(
    "nexus_retrieval_latency_seconds",
    "RAG retrieval time across dense, sparse, and rerank stages",
    ["stage"],
    buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)

# Sandbox execution duration
sandbox_runtime_seconds = Histogram(
    "nexus_sandbox_runtime_seconds",
    "Execution duration inside sandbox by runtime",
    ["runtime"],
    buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
)

# Token consumption by model and agent
token_usage_total = Counter(
    "nexus_token_usage_total",
    "Token consumption by model and agent",
    ["model", "agent"],
)

# Live WebSocket connections
active_websocket_connections = Gauge(
    "nexus_active_websocket_connections",
    "Active live WebSocket connections to project channels",
)

# Repo indexing time by language
indexing_duration_seconds = Histogram(
    "nexus_indexing_duration_seconds",
    "Repository indexing duration by detected primary language",
    ["language"],
    buckets=[1.0, 5.0, 10.0, 30.0, 60.0, 120.0],
)


def setup_metrics(app: FastAPI) -> None:
    """Initialize custom Prometheus metrics on FastAPI app state."""
    app.state.metric_agent_executions = agent_executions_total
    app.state.metric_retrieval_latency = retrieval_latency_seconds
    app.state.metric_sandbox_runtime = sandbox_runtime_seconds
    app.state.metric_token_usage = token_usage_total
    app.state.metric_active_websockets = active_websocket_connections
    app.state.metric_indexing_duration = indexing_duration_seconds
