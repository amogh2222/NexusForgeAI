"""
NexusForge AI — Hybrid Retriever (Qdrant-native)
Dense (BGE) + Sparse (BM42) hybrid search via Qdrant's built-in RRF fusion.

Upgrade from v1: eliminates manual BM25 + client-side RRF.
Qdrant does server-side fusion in a single API call — faster and more accurate.
"""
from __future__ import annotations

from typing import Optional

import structlog

from rag.embeddings.embedder import EmbeddingService
from rag.embeddings.sparse_embedder import SparseEmbeddingService
from rag.vector_store.qdrant_store import QdrantStore

log = structlog.get_logger()


class HybridRetriever:
    """
    Retrieves relevant code chunks using Qdrant native hybrid search.

    Architecture:
    1. Dense embed query (BGE with mandatory prefix)
    2. Sparse embed query (BM42)
    3. Single Qdrant query_points() call → server-side RRF fusion
    4. Assemble context within token budget
    """

    def __init__(
        self,
        top_k: int = 10,
        rerank_top_k: int = 5,
        max_context_tokens: int = 6000,
    ) -> None:
        self.top_k = top_k
        self.rerank_top_k = rerank_top_k
        self.max_context_tokens = max_context_tokens

    async def retrieve(
        self,
        query: str,
        project_id: str,
        language_filter: Optional[str] = None,
        file_path_filter: Optional[str] = None,
    ) -> tuple[str, list[str]]:
        """
        Retrieve relevant code context using Qdrant hybrid search.

        Args:
            query: Natural language or code query
            project_id: Project to search within
            language_filter: Optional language to restrict search (e.g. "python")
            file_path_filter: Optional file path substring to restrict search

        Returns:
            (context_text, source_file_paths) tuple
        """
        embedder = EmbeddingService.get_instance()
        sparse_embedder = SparseEmbeddingService.get_instance()
        store = QdrantStore.get_instance()

        # ─── Dense Embedding (BGE) ────────────────────────────────────────
        # BGE requires query prefix — research-critical for recall quality
        dense_vector = embedder.embed_query(query)

        # ─── Sparse Embedding (BM42) ──────────────────────────────────────
        # Excels at exact token matching: function names, variable names, identifiers
        sparse_indices, sparse_values = sparse_embedder.embed_sparse(query)

        # ─── Hybrid Search (server-side RRF) ─────────────────────────────
        # Single Qdrant call — no manual BM25, no client-side fusion
        results = store.hybrid_search(
            project_id=project_id,
            dense_vector=dense_vector,
            sparse_indices=sparse_indices,
            sparse_values=sparse_values,
            top_k=self.top_k,
            language_filter=language_filter,
            file_path_filter=file_path_filter,
        )

        if not results:
            log.info("retriever.no_results", query=query[:50], project_id=project_id)
            return "", []

        # ─── Context Assembly (token budget) ─────────────────────────────
        context_parts: list[str] = []
        source_paths: list[str] = []
        total_tokens = 0

        for hit in results[: self.rerank_top_k]:
            content = hit.get("content", "")
            file_path = hit.get("file_path", "unknown")
            start_line = hit.get("start_line", 0)
            language = hit.get("language", "")
            score = hit.get("score", 0.0)

            # Rough token estimate (4 chars ≈ 1 token for code)
            chunk_tokens = len(content) // 4
            if total_tokens + chunk_tokens > self.max_context_tokens:
                log.info(
                    "retriever.token_budget_reached",
                    total=total_tokens,
                    limit=self.max_context_tokens,
                )
                break

            context_parts.append(
                f"### {file_path} (line {start_line}+) [score: {score:.3f}]\n"
                f"```{language}\n{content}\n```"
            )

            if file_path not in source_paths:
                source_paths.append(file_path)

            total_tokens += chunk_tokens

        context = "\n\n".join(context_parts)

        log.info(
            "retriever.complete",
            query=query[:60],
            project_id=project_id,
            chunks_retrieved=len(context_parts),
            total_tokens=total_tokens,
            sources=len(source_paths),
            sparse_available=sparse_embedder.is_available(),
        )

        return context, source_paths
