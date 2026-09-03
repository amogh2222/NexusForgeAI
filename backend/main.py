"""
NexusForge AI — FastAPI Application Entry Point
"""
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncio

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from backend.core.config import settings
from backend.core.database import engine, Base
from backend.api.routes.auth import router as auth_router
from backend.api.routes.projects import router as projects_router
from backend.api.routes.repositories import router as repositories_router
from backend.api.routes.github import router as github_router
from backend.api.routes.github_auth import router as github_auth_router
from backend.api.routes.intelligence import router as intelligence_router
from backend.api.routes.evaluation import router as evaluation_router
from backend.api.routes.workspace import router as workspace_router
from backend.api.routes.health import router as health_router
from backend.api.routes._combined_routes import chat_router, agents_router, memory_router, executions_router
from backend.telemetry.metrics import setup_metrics
from backend.telemetry.tracing import setup_tracing

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan — startup and shutdown events."""
    log.info("nexusforge.startup", version=settings.APP_VERSION, env=settings.APP_ENV)

    # Create database tables (handled by Alembic in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Pre-load embedding model (critical — must not load per-task in Celery)
    from rag.embeddings.embedder import EmbeddingService
    EmbeddingService.get_instance()
    log.info("nexusforge.embeddings_loaded", model=settings.EMBEDDING_MODEL)

    # Initialize Qdrant connection (replaces ChromaDB)
    from rag.vector_store.qdrant_store import QdrantStore
    QdrantStore.get_instance()
    log.info("nexusforge.qdrant_connected", host=settings.QDRANT_HOST)

    # Initialize BM42 sparse embedder
    from rag.embeddings.sparse_embedder import SparseEmbeddingService
    SparseEmbeddingService.get_instance()
    log.info("nexusforge.sparse_embedder_loaded")

    # Start Redis PubSub Listener for WebSockets
    try:
        from backend.api.websocket.redis_listener import redis_listener
        await redis_listener.start()
    except Exception as e:
        log.error("nexusforge.redis_listener_failed", error=str(e))

    # Initialize Neo4j graph schemas
    from graph.neo4j_client import Neo4jClient
    try:
        neo4j_client = Neo4jClient.get_instance()
        await neo4j_client.initialize_schema()
        log.info("nexusforge.neo4j_connected", uri=settings.NEO4J_URI)
    except Exception as e:
        log.error("nexusforge.neo4j_connection_failed", error=str(e))

    # Initialize LLM Router
    from agents.router.model_router import ModelRouter
    ModelRouter.get_instance()
    log.info("model_router.initialized",
             openai=settings.OPENAI_API_KEY is not None,
             ollama=settings.OLLAMA_BASE_URL,
             vllm="disabled")

    # Initialize Kafka Streams
    from backend.core.kafka_stream import KafkaEventStream
    kafka_stream = KafkaEventStream.get_instance()
    await kafka_stream.connect_producer()
    log.info("nexusforge.kafka_connected")

    # Initialize Plugin Registry
    from plugins.registry import PluginRegistry
    plugin_registry = PluginRegistry.get_instance()
    await plugin_registry.initialize_plugins({
        "github": {
            "token": settings.GITHUB_APP_PRIVATE_KEY_PATH, # Or token
            "org": "NexusForge",
            "repo": "demo"
        }
    })
    log.info("nexusforge.plugins_loaded")

    async def process_kafka_event(event_type: str, payload: dict):
        if event_type in ("agent_start", "agent_end"):
            try:
                from backend.core.database import SessionLocal
                from backend.models import AgentLog
                import uuid

                async with SessionLocal() as db:
                    log_entry = AgentLog(
                        project_id=uuid.UUID(payload.get("project_id")),
                        agent_name=payload.get("agent"),
                        action=f"Agent {event_type}",
                        input_summary=payload.get("thread_id", ""),
                        status="success" if event_type == "agent_end" else "in_progress"
                    )
                    db.add(log_entry)
                    await db.commit()
            except Exception as e:
                log.error("kafka.event_processing_error", error=str(e))

    await kafka_stream.connect_consumer("nexusforge.agent.events")
    consumer_task = asyncio.create_task(kafka_stream.consume_loop(process_kafka_event))
    log.info("nexusforge.kafka_consumer_started")

    yield

    # Shutdown
    if consumer_task:
        consumer_task.cancel()
    log.info("nexusforge.shutdown")

    try:
        from backend.api.websocket.redis_listener import redis_listener
        await redis_listener.stop()
    except Exception as e:
        log.error("nexusforge.redis_listener_stop_failed", error=str(e))

    await engine.dispose()
    neo4j_inst = Neo4jClient.get_instance()
    await neo4j_inst.close()


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title="NexusForge AI",
        description="Enterprise Autonomous AI Software Engineering Platform",
        version=settings.APP_VERSION,
        docs_url="/api/docs" if settings.DEBUG else None,
        redoc_url="/api/redoc" if settings.DEBUG else None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ─── Middleware ──────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if not settings.DEBUG:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

    # ─── Prometheus Metrics ──────────────────────────────────────
    Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        should_instrument_requests_inprogress=True,
        excluded_handlers=["/health", "/metrics"],
    ).instrument(app).expose(app, endpoint="/metrics")

    setup_metrics(app)
    setup_tracing(app)

    # ─── Routers ─────────────────────────────────────────────────────────────
    app.include_router(health_router,       tags=["health"])
    app.include_router(auth_router,         prefix="/api/v1/auth",         tags=["auth"])
    app.include_router(projects_router,     prefix="/api/v1/projects",     tags=["projects"])
    app.include_router(repositories_router, prefix="/api/v1/repos",        tags=["repositories"])
    app.include_router(repositories_router, prefix="/api/v1/repositories", tags=["repositories"])
    app.include_router(github_router,       prefix="/api/v1/github",       tags=["github"])
    app.include_router(github_auth_router,  prefix="/api/v1",              tags=["auth"])
    # ─── v2 Routes ───────────────────────────────────────────────────────────
    app.include_router(intelligence_router, prefix="/api/v1",              tags=["intelligence"])
    app.include_router(evaluation_router,   prefix="/api/v1",              tags=["evaluation"])
    app.include_router(workspace_router,    prefix="/api/v1",              tags=["workspace"])
    app.include_router(chat_router,         prefix="/api/v1/chat",         tags=["chat"])
    app.include_router(agents_router,       prefix="/api/v1/agents",       tags=["agents"])
    app.include_router(memory_router,       prefix="/api/v1/memory",       tags=["memory"])
    app.include_router(executions_router,   prefix="/api/v1/executions",   tags=["executions"])
    app.include_router(executions_router,   prefix="/api/v1/execute",      tags=["executions"])

    # ─── WebSocket ───────────────────────────────────────────────────────────
    try:
        from backend.api.websocket.endpoint import websocket_router
        app.include_router(websocket_router)
    except ImportError:
        pass  # WebSocket endpoint not yet created

    # ─── Exception Handlers ─────────────────────────────────────
    @app.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        log.error("nexusforge.unhandled_exception", error=str(exc), path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error", "error": str(exc) if settings.DEBUG else None},
        )

    return app


app = create_app()
