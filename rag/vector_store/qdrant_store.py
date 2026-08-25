"""
NexusForge AI — Qdrant Vector Store
Production-grade vector DB: Rust-backed, billion-scale, named dense+sparse vectors.

Key decisions (research-validated):
- Named Vectors: "dense" (BGE-768, cosine) + "sparse" (BM42, dot product) in ONE collection
- ScalarQuantization(INT8, always_ram=True): 4x memory reduction, quantized vecs in RAM
- on_disk=True for raw dense vectors: saves RAM without hurting query speed (quant vecs used)
- Native hybrid search via Query API (prefetch + FusionQuery.RRF): server-side fusion
- on_disk_payload=True: metadata on disk, frees RAM for vectors
"""
from __future__ import annotations

from typing import Any, Optional

import structlog
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    FusionQuery,
    Fusion,
    HnswConfigDiff,
    KeywordIndexParams,
    KeywordIndexType,
    MatchValue,
    PointStruct,
    Prefetch,
    ScalarQuantization,
    ScalarQuantizationConfig,
    ScalarType,
    SparseIndexParams,
    SparseVector,
    SparseVectorParams,
    VectorParams,
)

log = structlog.get_logger()


class QdrantStore:
    """
    Qdrant wrapper for NexusForge AI.

    Collection per project, named vectors (dense + sparse), INT8 quantization.
    Provides native hybrid retrieval — no manual BM25 or RRF needed.
    """

    DENSE_VECTOR_NAME = "dense"
    SPARSE_VECTOR_NAME = "sparse"
    DENSE_DIM = 768  # BAAI/bge-base-en-v1.5 output dim

    _instance: Optional["QdrantStore"] = None

    def __init__(self) -> None:
        from backend.core.config import settings

        self._prefix = settings.QDRANT_COLLECTION_PREFIX

        kwargs: dict[str, Any] = {
            "host": settings.QDRANT_HOST,
            "port": settings.QDRANT_PORT,
            "prefer_grpc": settings.QDRANT_USE_GRPC,
            "timeout": 30,
        }
        if settings.QDRANT_API_KEY:
            kwargs["api_key"] = settings.QDRANT_API_KEY

        self.client = QdrantClient(**kwargs)
        log.info(
            "qdrant.connected",
            host=settings.QDRANT_HOST,
            port=settings.QDRANT_PORT,
        )

    # ─── Collection Management ────────────────────────────────────────────────

    def _collection_name(self, project_id: str) -> str:
        safe = project_id.replace("-", "_")
        return f"{self._prefix}_{safe}"

    def ensure_collection(self, project_id: str) -> str:
        """Create collection if it doesn't exist. Returns collection name."""
        name = self._collection_name(project_id)
        existing = {c.name for c in self.client.get_collections().collections}
        if name in existing:
            return name

        self.client.create_collection(
            collection_name=name,
            # Dense vector: BGE-768, cosine, raw vectors on disk (saves RAM)
            vectors_config={
                self.DENSE_VECTOR_NAME: VectorParams(
                    size=self.DENSE_DIM,
                    distance=Distance.COSINE,
                    on_disk=True,  # raw on disk; quantized copy stays in RAM
                )
            },
            # Sparse vector: BM42 sparse encoder, dot product
            sparse_vectors_config={
                self.SPARSE_VECTOR_NAME: SparseVectorParams(
                    index=SparseIndexParams(on_disk=False)  # sparse index in RAM
                )
            },
            # INT8 scalar quantization: 4x memory reduction
            quantization_config=ScalarQuantization(
                scalar=ScalarQuantizationConfig(
                    type=ScalarType.INT8,
                    always_ram=True,  # quantized vectors always in RAM for speed
                )
            ),
            # HNSW: m=16 for good connectivity, ef_construct=200 for quality
            hnsw_config=HnswConfigDiff(m=16, ef_construct=200),
            on_disk_payload=True,  # payload (metadata) on disk
        )

        # Payload index for fast project_id filtering
        self.client.create_payload_index(
            collection_name=name,
            field_name="project_id",
            field_schema=KeywordIndexParams(
                type=KeywordIndexType.KEYWORD,
                on_disk=True,
            ),
        )
        # Index for language filter
        self.client.create_payload_index(
            collection_name=name,
            field_name="language",
            field_schema=KeywordIndexParams(
                type=KeywordIndexType.KEYWORD,
                on_disk=True,
            ),
        )

        log.info("qdrant.collection_created", name=name, project_id=project_id)
        return name

    # ─── Write Operations ────────────────────────────────────────────────────

    def upsert_batch(
        self,
        project_id: str,
        ids: list[str],
        dense_vectors: list[list[float]],
        sparse_indices: list[list[int]],
        sparse_values: list[list[float]],
        payloads: list[dict],
        batch_size: int = 100,
    ) -> int:
        """
        Upsert chunks with both dense and sparse vectors.
        Uses batching for performance (never one-by-one).
        Returns number of points upserted.
        """
        name = self.ensure_collection(project_id)
        total = 0

        for i in range(0, len(ids), batch_size):
            batch_ids = ids[i : i + batch_size]
            batch_dense = dense_vectors[i : i + batch_size]
            batch_si = sparse_indices[i : i + batch_size]
            batch_sv = sparse_values[i : i + batch_size]
            batch_payloads = payloads[i : i + batch_size]

            import uuid

            points = []
            for pid, dense, si, sv, payload in zip(
                batch_ids, batch_dense, batch_si, batch_sv, batch_payloads
            ):
                point_id = str(pid)
                try:
                    uuid.UUID(point_id)
                except ValueError:
                    point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, point_id))

                points.append(
                    PointStruct(
                        id=point_id,
                        vector={
                            self.DENSE_VECTOR_NAME: dense,
                            self.SPARSE_VECTOR_NAME: SparseVector(
                                indices=si,
                                values=sv,
                            ),
                        },
                        payload={**payload, "project_id": project_id},
                    )
                )

            self.client.upsert(collection_name=name, points=points, wait=True)
            total += len(points)
            log.info(
                "qdrant.batch_upserted",
                project_id=project_id,
                batch=i // batch_size,
                count=len(points),
            )

        return total

    # ─── Search Operations ───────────────────────────────────────────────────

    def hybrid_search(
        self,
        project_id: str,
        dense_vector: list[float],
        sparse_indices: list[int],
        sparse_values: list[float],
        top_k: int = 10,
        language_filter: Optional[str] = None,
        file_path_filter: Optional[str] = None,
    ) -> list[dict]:
        """
        Native hybrid search: dense + sparse in ONE Qdrant API call.
        Server-side RRF fusion — no manual BM25 or post-processing needed.

        Returns list of dicts with: content, file_path, language, start_line,
        end_line, node_type, score.
        """
        name = self._collection_name(project_id)

        # Build optional filters
        must_conditions = []
        if language_filter:
            must_conditions.append(
                FieldCondition(key="language", match=MatchValue(value=language_filter))
            )
        if file_path_filter:
            must_conditions.append(
                FieldCondition(
                    key="file_path", match=MatchValue(value=file_path_filter)
                )
            )
        query_filter = Filter(must=must_conditions) if must_conditions else None

        try:
            results = self.client.query_points(
                collection_name=name,
                prefetch=[
                    # Dense prefetch: semantic similarity
                    Prefetch(
                        query=dense_vector,
                        using=self.DENSE_VECTOR_NAME,
                        limit=top_k * 2,
                        filter=query_filter,
                    ),
                    # Sparse prefetch: exact token matching (BM42)
                    Prefetch(
                        query=SparseVector(
                            indices=sparse_indices,
                            values=sparse_values,
                        ),
                        using=self.SPARSE_VECTOR_NAME,
                        limit=top_k * 2,
                        filter=query_filter,
                    ),
                ],
                # Server-side Reciprocal Rank Fusion
                query=FusionQuery(fusion=Fusion.RRF),
                limit=top_k,
                with_payload=True,
                with_vectors=False,  # don't return raw vectors
            )
        except Exception as e:
            log.warning("qdrant.search_failed", error=str(e), project_id=project_id)
            return []

        output = []
        for point in results.points:
            payload = point.payload or {}
            output.append(
                {
                    "id": str(point.id),
                    "score": point.score,
                    "content": payload.get("content", ""),
                    "file_path": payload.get("file_path", "unknown"),
                    "language": payload.get("language", ""),
                    "start_line": payload.get("start_line", 0),
                    "end_line": payload.get("end_line", 0),
                    "node_type": payload.get("node_type", ""),
                    "chunk_hash": payload.get("chunk_hash", ""),
                }
            )

        log.info(
            "qdrant.search_complete",
            project_id=project_id,
            top_k=top_k,
            results=len(output),
        )
        return output

    # ─── Collection Management ───────────────────────────────────────────────

    def delete_collection(self, project_id: str) -> None:
        """Delete all vectors for a project (used on re-indexing)."""
        name = self._collection_name(project_id)
        try:
            self.client.delete_collection(name)
            log.info("qdrant.collection_deleted", project_id=project_id)
        except Exception as e:
            log.warning(
                "qdrant.delete_failed", project_id=project_id, error=str(e)
            )

    def get_collection_stats(self, project_id: str) -> dict:
        """Get vector count and index stats for a project collection."""
        name = self._collection_name(project_id)
        try:
            info = self.client.get_collection(name)
            return {
                "project_id": project_id,
                "collection_name": name,
                "vectors_count": info.vectors_count or 0,
                "indexed_vectors_count": info.indexed_vectors_count or 0,
                "points_count": info.points_count or 0,
                "status": info.status.value if info.status else "unknown",
                "disk_data_size_bytes": info.disk_data_size or 0,
                "ram_data_size_bytes": info.ram_data_size or 0,
            }
        except Exception as e:
            return {"project_id": project_id, "error": str(e)}

    def list_all_collections(self) -> list[str]:
        """List all NexusForge collections."""
        return [
            c.name
            for c in self.client.get_collections().collections
            if c.name.startswith(self._prefix)
        ]

    # ─── Singleton ───────────────────────────────────────────────────────────

    @classmethod
    def get_instance(cls) -> "QdrantStore":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
