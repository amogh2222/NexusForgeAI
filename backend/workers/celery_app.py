"""
NexusForge AI — Celery Application
Redis broker + result backend. Embedding model loaded at worker startup.
Research-validated: NEVER load embedding models per-task.
"""
from celery import Celery
from celery.signals import worker_ready

from backend.core.config import settings

# ─── App Configuration ───────────────────────────────────────────
celery_app = Celery(
    "nexusforge",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "backend.workers.tasks.indexing_task",
        "backend.workers.tasks.agent_task",
        "backend.workers.tasks.execution_task",
    ],
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timeouts
    task_soft_time_limit=settings.CELERY_TASK_TIMEOUT,
    task_time_limit=settings.CELERY_TASK_TIMEOUT + 30,

    # Retry behavior
    task_max_retries=settings.CELERY_MAX_RETRIES,
    task_acks_late=True,
    task_reject_on_worker_lost=True,

    # Queue configuration
    task_routes={
        "backend.workers.tasks.indexing_task.*": {"queue": "indexing"},
        "backend.workers.tasks.agent_task.*": {"queue": "agents"},
        "backend.workers.tasks.execution_task.*": {"queue": "execution"},
    },

    # Worker settings
    worker_prefetch_multiplier=1,   # Fair scheduling
    worker_max_tasks_per_child=20,  # Prevent memory leaks

    # Results
    result_expires=3600,
    task_track_started=True,
)


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """
    Pre-load embedding model when worker starts.
    CRITICAL: Never load this per-task (10-100x slower).
    """
    import structlog
    log = structlog.get_logger()
    log.info("celery.worker_ready.preloading_models")

    try:
        from rag.embeddings.embedder import EmbeddingService
        EmbeddingService.get_instance()
        log.info("celery.embedding_model_loaded")
    except Exception as e:
        log.error("celery.embedding_model_load_failed", error=str(e))

    try:
        from rag.vector_store.qdrant_store import QdrantStore
        QdrantStore.get_instance()
        log.info("celery.qdrant_connected")
    except Exception as e:
        log.error("celery.qdrant_connect_failed", error=str(e))
