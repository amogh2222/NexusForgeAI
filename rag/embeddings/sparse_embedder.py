"""
NexusForge AI — BM42 Sparse Embedding Service
Uses fastembed SparseTextEmbedding with Qdrant's BM42 model.

BM42 is NOT classical BM25 — it uses transformer attention weights
for token importance scoring, giving much better retrieval for code.
Model: Qdrant/bm42-all-minilm-l6-v2-attentions (~50MB download)
"""
from __future__ import annotations

import time
from typing import Optional

import structlog

log = structlog.get_logger()


class SparseEmbeddingService:
    """
    Singleton BM42 sparse encoder for Qdrant hybrid search.
    Loaded once at worker startup — never per-task.
    """

    MODEL_NAME = "Qdrant/bm42-all-minilm-l6-v2-attentions"

    _instance: Optional["SparseEmbeddingService"] = None
    _model = None

    def __init__(self) -> None:
        start = time.perf_counter()

        try:
            from fastembed import SparseTextEmbedding

            self._model = SparseTextEmbedding(
                model_name=self.MODEL_NAME,
                cache_dir="/app/.cache/fastembed",
                threads=2,
                enable_cpu_mem_arena=False,
            )
            elapsed = (time.perf_counter() - start) * 1000
            log.info(
                "sparse_embedder.loaded",
                model=self.MODEL_NAME,
                load_time_ms=round(elapsed, 1),
            )
        except ImportError:
            log.warning(
                "sparse_embedder.fastembed_not_installed",
                hint="pip install fastembed",
            )
            self._model = None
        except Exception as e:
            log.warning("sparse_embedder.load_failed", error=str(e))
            self._model = None

    def embed_sparse(self, text: str) -> tuple[list[int], list[float]]:
        """
        Encode a single text to BM42 sparse vector.
        Returns (indices, values) for qdrant_client SparseVector.
        Returns ([], []) if model not available (graceful dense-only fallback).
        """
        if self._model is None:
            return [], []
        try:
            results = list(self._model.embed([text]))
            if not results:
                return [], []
            sparse = results[0]
            return sparse.indices.tolist(), sparse.values.tolist()
        except Exception as e:
            log.warning("sparse_embedder.embed_failed", error=str(e))
            return [], []

    def embed_sparse_batch(
        self, texts: list[str]
    ) -> list[tuple[list[int], list[float]]]:
        """Encode a batch of texts to sparse vectors."""
        if self._model is None:
            return [([], []) for _ in texts]
        try:
            results = list(self._model.embed(texts))
            return [(r.indices.tolist(), r.values.tolist()) for r in results]
        except Exception as e:
            log.warning("sparse_embedder.batch_failed", error=str(e))
            return [([], []) for _ in texts]

    def is_available(self) -> bool:
        return self._model is not None

    @classmethod
    def get_instance(cls) -> "SparseEmbeddingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
