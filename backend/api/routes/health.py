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
        from rag.vector_store.chroma_store import ChromaStore
        ChromaStore.get_instance().client.heartbeat()
        checks["chromadb"] = "ok"
    except Exception as e:
        checks["chromadb"] = f"error: {str(e)}"

    overall = "healthy" if all(v == "ok" for v in checks.values()) else "degraded"
    return {"status": overall, "checks": checks}
