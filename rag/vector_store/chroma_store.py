"""
NexusForge AI — ChromaDB Vector Store
PersistentClient with HNSW tuning and per-project collection namespacing.
Research-validated: NEVER use EphemeralClient in production.
"""
from typing import Optional

import chromadb
import structlog
from chromadb.config import Settings

log = structlog.get_logger()


class ChromaStore:
    """
    ChromaDB wrapper with:
    - PersistentClient (data survives restarts)
    - Per-project collection namespacing
    - HNSW tuning for optimal recall (M=16, ef_construction=200)
    - Batch operations (never one-by-one inserts)
    - Metadata filtering support
    """

    _instance: Optional["ChromaStore"] = None

    # HNSW tuning from research (balances recall and build time)
    HNSW_SETTINGS = {
        "hnsw:space": "cosine",           # Required for normalized BGE embeddings
        "hnsw:M": 16,                     # Graph connectivity
        "hnsw:ef_construction": 200,       # Build-time recall quality
        "hnsw:ef": 50,                    # Query-time recall (default 10 is too low)
    }

    def __init__(self):
        from backend.core.config import settings

        # Use HTTP client to connect to ChromaDB server (docker-compose)
        try:
            self.client = chromadb.HttpClient(
                host=settings.CHROMA_HOST,
                port=settings.CHROMA_PORT,
                settings=Settings(anonymized_telemetry=False),
            )
            # Test connection
            self.client.heartbeat()
            log.info("chroma.connected", host=settings.CHROMA_HOST, port=settings.CHROMA_PORT)
        except Exception:
            # Fallback to local persistent client
            log.warning("chroma.http_failed_fallback_local", path=settings.CHROMA_PERSIST_PATH)
            self.client = chromadb.PersistentClient(
                path=settings.CHROMA_PERSIST_PATH,
                settings=Settings(anonymized_telemetry=False, allow_reset=False),
            )

        from backend.core.config import settings as s
        self.collection_prefix = s.CHROMA_COLLECTION_PREFIX

    @classmethod
    def get_instance(cls) -> "ChromaStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _collection_name(self, project_id: str) -> str:
        """Generate a safe ChromaDB collection name for a project."""
        safe_id = project_id.replace("-", "_")
        return f"{self.collection_prefix}_{safe_id}"

    def get_or_create_collection(self, project_id: str):
        """Get or create a collection for a project with proper HNSW tuning."""
        name = self._collection_name(project_id)
        collection = self.client.get_or_create_collection(
            name=name,
            metadata=self.HNSW_SETTINGS,
        )
        return collection

    def add_chunks(
        self,
        project_id: str,
        ids: list[str],
        embeddings: list[list[float]],
        documents: list[str],
        metadatas: list[dict],
        batch_size: int = 500,
    ) -> int:
        """
        Batch insert chunks into a project's collection.
        Never inserts one-by-one (10-100x slower).
        Returns number of chunks inserted.
        """
        collection = self.get_or_create_collection(project_id)
        total = 0

        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i:i + batch_size]
            batch_emb = embeddings[i:i + batch_size]
            batch_docs = documents[i:i + batch_size]
            batch_meta = metadatas[i:i + batch_size]

            # Use upsert to handle re-indexing gracefully
            collection.upsert(
                ids=batch_ids,
                embeddings=batch_emb,
                documents=batch_docs,
                metadatas=batch_meta,
            )
            total += len(batch_ids)
            log.info("chroma.batch_inserted", project=project_id, batch=i // batch_size, count=len(batch_ids))

        return total

    def query(
        self,
        project_id: str,
        query_embedding: list[float],
        n_results: int = 10,
        where: Optional[dict] = None,
        where_document: Optional[dict] = None,
    ) -> dict:
        """
        Semantic similarity search with optional metadata filtering.
        Returns results with documents, metadatas, and distances.
        """
        collection = self.get_or_create_collection(project_id)

        kwargs = {
            "query_embeddings": [query_embedding],
            "n_results": min(n_results, collection.count() or n_results),
            "include": ["documents", "metadatas", "distances"],
        }
        if where:
            kwargs["where"] = where
        if where_document:
            kwargs["where_document"] = where_document

        return collection.query(**kwargs)

    def delete_project_collection(self, project_id: str):
        """Delete all vectors for a project (used on re-indexing)."""
        name = self._collection_name(project_id)
        try:
            self.client.delete_collection(name)
            log.info("chroma.collection_deleted", project=project_id)
        except Exception as e:
            log.warning("chroma.collection_delete_failed", project=project_id, error=str(e))

    def get_collection_stats(self, project_id: str) -> dict:
        """Get stats for a project's collection."""
        try:
            collection = self.get_or_create_collection(project_id)
            return {
                "project_id": project_id,
                "total_chunks": collection.count(),
                "collection_name": self._collection_name(project_id),
            }
        except Exception as e:
            return {"project_id": project_id, "error": str(e)}
