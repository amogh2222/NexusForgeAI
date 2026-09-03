"""NexusForge AI — Health Check + Additional Route Stubs"""
from fastapi import APIRouter
from backend.api.websocket.hub import manager

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint for docker healthcheck and load balancers."""
    return {
        "status": "healthy",
        "service": "nexusforge-ai-backend",
        "active_websockets": manager.total_connections,
    }


@router.get("/health/detailed")
async def detailed_health():
    """Detailed health including dependency status."""
    checks = {"api": "ok"}

    try:
        from backend.core.database import engine
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy", fromlist=["text"]).text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    try:
        import redis
        from backend.core.config import settings
        r = redis.from_url(settings.REDIS_URL)
        r.ping()
        checks["redis"] = "ok"
        r.close()
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    try:
        from rag.vector_store.qdrant_store import QdrantStore
        QdrantStore.get_instance().client.get_collections()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {str(e)}"

    try:
        from graph.neo4j_client import Neo4jClient
        neo = Neo4jClient.get_instance()
        if await neo.verify_connectivity():
            checks["neo4j"] = "ok"
        else:
            checks["neo4j"] = "offline"
    except Exception as e:
        checks["neo4j"] = f"error: {str(e)}"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
