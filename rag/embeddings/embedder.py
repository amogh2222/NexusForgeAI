"""
NexusForge AI — BGE Embedding Service
Singleton pattern: loaded once at startup, never per-task.
Research-validated: normalize_embeddings=True + query prefix required for BGE.
"""
from typing import Optional

import structlog

log = structlog.get_logger()


class EmbeddingService:
    """
    Singleton embedding service using BAAI/bge-base-en-v1.5.

    CRITICAL RULES (from research):
    1. normalize_embeddings=True REQUIRED for cosine similarity
    2. Query prefix REQUIRED for retrieval queries (not for documents)
    3. Model MUST be loaded once at startup, NOT per Celery task
    """

    _instance: Optional["EmbeddingService"] = None
    QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

    def __init__(self, model_name: str = "BAAI/bge-base-en-v1.5", max_seq_length: int = 512):
        self.model_name = model_name
        self.max_seq_length = max_seq_length
        self.model = None
        self.redis_client = None

        try:
            import os
            import redis
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
            self.redis_client = redis.from_url(redis_url)
        except Exception:
            self.redis_client = None

        self._is_fastembed = False
        try:
            from fastembed import TextEmbedding
            log.info("embeddings.loading_fastembed", model=model_name)
            self.model = TextEmbedding(
                model_name=model_name,
                cache_dir="/app/.cache/fastembed",
                threads=2,
                enable_cpu_mem_arena=False,
            )
            self._is_fastembed = True
            log.info("embeddings.loaded_fastembed", model=model_name, dim=768)
        except Exception as fe:
            log.info("embeddings.trying_sentence_transformers", error=str(fe))
            try:
                from sentence_transformers import SentenceTransformer
                log.info("embeddings.loading_st", model=model_name)
                self.model = SentenceTransformer(model_name)
                self.model.max_seq_length = max_seq_length
                log.info("embeddings.loaded_st", model=model_name)
            except Exception as se:
                log.error("embeddings.load_failed", model=model_name, error=str(se))
                raise RuntimeError(f"Failed to load embedding model '{model_name}': {se}") from se

    @classmethod
    def get_instance(cls) -> "EmbeddingService":
        """Get or create the singleton embedding service."""
        if cls._instance is None:
            from backend.core.config import settings
            cls._instance = cls(
                model_name=settings.EMBEDDING_MODEL,
                max_seq_length=settings.EMBEDDING_MAX_SEQ_LENGTH,
            )
        return cls._instance

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """
        Embed a list of documents (code chunks, file contents).
        NO query prefix for documents.
        """
        if not texts:
            return []

        if self.model is None:
            raise RuntimeError("Embedding model is not loaded. Cannot embed documents.")

        log.info("embeddings.embed_documents", count=len(texts), batch_size=batch_size)
        if self._is_fastembed:
            return [e.tolist() for e in self.model.embed(texts, batch_size=batch_size)]
        else:
            embeddings = self.model.encode(
                texts,
                normalize_embeddings=True,   # REQUIRED for cosine similarity with BGE
                batch_size=batch_size,
                show_progress_bar=len(texts) > 100,
                convert_to_numpy=True,
            )
            return embeddings.tolist()

    def embed_query(self, query: str) -> list[float]:
        """
        Embed a single search query.
        BGE REQUIRES the query prefix for proper retrieval behavior.
        """
        if self.model is None:
            raise RuntimeError("Embedding model is not loaded. Cannot embed query.")

        prefixed_query = f"{self.QUERY_PREFIX}{query}"
        cache_key = None
        if self.redis_client:
            import hashlib
            import json
            cache_key = f"embed:{hashlib.sha256(prefixed_query.encode()).hexdigest()}"
            try:
                cached = self.redis_client.get(cache_key)
                if cached:
                    return json.loads(cached)
            except Exception:
                pass

        if self._is_fastembed:
            res = list(self.model.embed([prefixed_query]))[0].tolist()
        else:
            embedding = self.model.encode(
                [prefixed_query],
                normalize_embeddings=True,   # REQUIRED
                convert_to_numpy=True,
            )
            res = embedding[0].tolist()

        if cache_key and self.redis_client:
            try:
                import json
                self.redis_client.set(cache_key, json.dumps(res), ex=86400)
            except Exception:
                pass

        return res

    def embed_queries(self, queries: list[str]) -> list[list[float]]:
        """Embed multiple queries with the required prefix."""
        prefixed = [f"{self.QUERY_PREFIX}{q}" for q in queries]
        embeddings = self.model.encode(
            prefixed,
            normalize_embeddings=True,
            convert_to_numpy=True,
        )
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        """Embedding vector dimension."""
        if self.model is None:
            return 768
        return self.model.get_sentence_embedding_dimension()

    @property
    def model_version(self) -> str:
        """String identifier for embedding versioning in ChromaDB."""
        return self.model_name.replace("/", "--")
