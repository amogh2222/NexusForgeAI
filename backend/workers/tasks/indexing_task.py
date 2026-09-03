"""
NexusForge AI — Repository Indexing Celery Task
Chunks, embeds, and stores a repository into ChromaDB.
Streams progress events via Redis pub/sub → WebSocket.
"""
import json
import os
import time
import zipfile
from pathlib import Path
from typing import Optional

import redis
import structlog

from backend.workers.celery_app import celery_app
from backend.core.config import settings

log = structlog.get_logger()

# Files to skip during indexing
SKIP_EXTENSIONS = {
    ".pyc", ".pyo", ".pyd", ".class", ".o", ".so", ".dll", ".exe",
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".ico", ".webp",
    ".mp3", ".mp4", ".avi", ".mov", ".pdf",
    ".lock", ".log", ".bin", ".wasm",
}

SKIP_DIRECTORIES = {
    "node_modules", ".git", "__pycache__", ".pytest_cache", "dist",
    "build", ".next", "venv", ".venv", "env", ".env",
    "vendor", "coverage", ".nyc_output",
}

MAX_FILE_SIZE_BYTES = 200_000  # 200KB per file


def _publish_event(redis_client: redis.Redis, project_id: str, event: dict):
    """Publish event to Redis for WebSocket consumers."""
    try:
        redis_client.publish(f"nexusforge:ws:{project_id}", json.dumps(event))
    except Exception as e:
        log.warning("indexing.publish_failed", error=str(e))


@celery_app.task(
    name="backend.workers.tasks.indexing_task.index_repository",
    bind=True,
    max_retries=2,
    soft_time_limit=600,
)
def index_repository(
    self,
    repository_id: str,
    project_id: str,
    source_path: str,
    source_type: str = "zip",
    branch: str = "main",
    github_url: Optional[str] = None,
    github_token: Optional[str] = None,
):
    """
    Full repository indexing pipeline:
    1. Extract ZIP or clone GitHub repository
    2. Walk files, filter, chunk with AST chunker
    3. Generate BGE embeddings in batches
    4. Store in Qdrant with metadata
    5. Update repository status in PostgreSQL
    6. Publish progress events via Redis
    """
    import torch
    torch.set_num_threads(4)
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    redis_client = redis.from_url(settings.REDIS_URL)
    start_time = time.time()

    log.info("indexing.start", repo_id=repository_id, project_id=project_id)

    try:
        # ─── Step 1: Prepare source directory ────────────────────
        if source_type == "zip":
            extract_dir = source_path.replace(".zip", "_extracted")
            os.makedirs(extract_dir, exist_ok=True)
            with zipfile.ZipFile(source_path, "r") as zf:
                zf.extractall(extract_dir)
            repo_dir = extract_dir
        else:
            repo_dir = source_path
            if github_url:
                if not os.path.exists(repo_dir) or not os.listdir(repo_dir):
                    os.makedirs(repo_dir, exist_ok=True)
                    # Prepare clone URL (inject token if private repo)
                    clone_url = github_url
                    if github_token:
                        if github_url.startswith("https://"):
                            clone_url = github_url.replace("https://", f"https://{github_token}@")
                    try:
                        import subprocess
                        log.info("indexing.cloning", url=github_url, dest=repo_dir, branch=branch)
                        # First try with the specified branch
                        try:
                            subprocess.run(
                                ["git", "clone", "--depth", "1", "--branch", branch, clone_url, repo_dir],
                                capture_output=True,
                                text=True,
                                check=True,
                            )
                        except subprocess.CalledProcessError as e:
                            if "not found" in e.stderr.lower():
                                log.warning("indexing.branch_not_found_fallback", branch=branch, url=github_url)
                                # If branch fails, try cloning the default branch
                                subprocess.run(
                                    ["git", "clone", "--depth", "1", clone_url, repo_dir],
                                    capture_output=True,
                                    text=True,
                                    check=True,
                                )
                            else:
                                raise
                    except subprocess.CalledProcessError as e:
                        log.error("indexing.clone_failed", stdout=e.stdout, stderr=e.stderr)
                        raise ValueError(f"Git clone failed: {e.stderr.strip() if e.stderr else str(e)}")

        _publish_event(redis_client, project_id, {
            "type": "indexing_start",
            "repository_id": repository_id,
            "timestamp": time.time(),
        })

        # ─── Step 2: Walk and collect files ─────────────────────
        all_files = []
        for root, dirs, files in os.walk(repo_dir):
            # Filter directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES]

            for fname in files:
                fpath = os.path.join(root, fname)
                ext = Path(fname).suffix.lower()

                if ext in SKIP_EXTENSIONS:
                    continue
                if os.path.getsize(fpath) > MAX_FILE_SIZE_BYTES:
                    log.debug("indexing.file_skipped_size", file=fname)
                    continue

                rel_path = os.path.relpath(fpath, repo_dir)
                all_files.append((fpath, rel_path, ext))

        total_files = len(all_files)
        log.info("indexing.files_found", count=total_files)

        # Cap repository files to index under CPU constraints to stay responsive
        if total_files > 150:
            log.info("indexing.capping_files", original_count=total_files, capped_count=150)
            # Prioritize Java, Python, TS, JS source code files, and avoid test directories
            CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".rs", ".cpp", ".c"}
            source_files = [f for f in all_files if "test" not in f[1].lower() and f[2] in CODE_EXTENSIONS]
            other_files = [f for f in all_files if f not in source_files]
            all_files = (source_files + other_files)[:150]
            total_files = len(all_files)
            log.info("indexing.files_capped", count=total_files)

        # ─── Step 3: Chunk all files ─────────────────────────────
        from rag.chunking.ast_chunker import ASTChunker
        from rag.chunking.text_chunker import TextChunker

        ast_chunker = ASTChunker(
            max_chunk_tokens=settings.CHUNK_MAX_TOKENS,
            min_chunk_tokens=settings.CHUNK_MIN_TOKENS,
        )
        text_chunker = TextChunker()

        CODE_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".java", ".rs", ".cpp", ".c"}

        all_chunks = []
        detected_languages = {}

        for i, (fpath, rel_path, ext) in enumerate(all_files):
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                if not content.strip():
                    continue

                # Track language stats
                lang = ext.lstrip(".")
                detected_languages[lang] = detected_languages.get(lang, 0) + 1

                # Choose chunker
                if ext in CODE_EXTENSIONS:
                    chunks = ast_chunker.chunk_file(content, rel_path)
                else:
                    chunks = text_chunker.chunk_file(content, rel_path)

                all_chunks.extend(chunks)

                # Publish progress every 10 files
                if i % 10 == 0:
                    progress = int((i / total_files) * 60)  # First 60% = chunking
                    _publish_event(redis_client, project_id, {
                        "type": "indexing_progress",
                        "repository_id": repository_id,
                        "progress": progress,
                        "current_file": rel_path,
                        "files_processed": i,
                        "total_files": total_files,
                        "chunks_created": len(all_chunks),
                    })

            except Exception as e:
                log.warning("indexing.file_error", file=rel_path, error=str(e))

        log.info("indexing.chunking_complete", total_chunks=len(all_chunks))

        # ─── Step 4: Generate embeddings ────────────────────────
        _publish_event(redis_client, project_id, {
            "type": "indexing_progress",
            "repository_id": repository_id,
            "progress": 65,
            "current_file": "Generating embeddings...",
            "chunks_created": len(all_chunks),
        })

        from rag.embeddings.embedder import EmbeddingService
        embedder = EmbeddingService.get_instance()

        chunk_texts = [c.content for c in all_chunks]
        embeddings = embedder.embed_documents(chunk_texts, batch_size=settings.EMBEDDING_BATCH_SIZE)

        _publish_event(redis_client, project_id, {
            "type": "indexing_progress",
            "repository_id": repository_id,
            "progress": 85,
            "current_file": "Storing in vector database...",
        })

        # ─── Step 5: Store in Qdrant ─────────────────────────────
        from rag.vector_store.qdrant_store import QdrantStore
        from rag.embeddings.sparse_embedder import SparseEmbeddingService

        store = QdrantStore.get_instance()
        sparse_embedder = SparseEmbeddingService.get_instance()

        # Delete old collection for this project (re-indexing support)
        store.delete_collection(project_id)

        ids = [c.chunk_id for c in all_chunks]

        # Generate sparse embeddings
        sparse_results = sparse_embedder.embed_sparse_batch(chunk_texts)
        sparse_indices = [r[0] for r in sparse_results]
        sparse_values = [r[1] for r in sparse_results]

        payloads = [
            {
                "content": c.content,
                "file_path": c.file_path,
                "language": c.language,
                "node_type": c.chunk_type,
                "start_line": c.start_line,
                "end_line": c.end_line,
                "chunk_hash": c.chunk_id,
                "parent_name": c.parent_name or "",
                "node_name": c.node_name or "",
            }
            for c in all_chunks
        ]

        total_stored = store.upsert_batch(
            project_id=project_id,
            ids=ids,
            dense_vectors=embeddings,
            sparse_indices=sparse_indices,
            sparse_values=sparse_values,
            payloads=payloads,
        )

        # ─── Step 5b: Build Neo4j Knowledge Graph ─────────────────
        try:
            import asyncio
            from graph.repo_graph_builder import RepoGraphBuilder
            chunk_dicts = [
                {
                    "content": c.content,
                    "file_path": c.file_path,
                    "language": c.language,
                    "node_type": c.chunk_type,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "metadata": {
                        "name": c.node_name,
                        "parent_name": c.parent_name,
                        "file_path": c.file_path,
                        "language": c.language,
                        "node_type": c.chunk_type,
                    }
                }
                for c in all_chunks
            ]
            graph_builder = RepoGraphBuilder()
            graph_res = asyncio.run(graph_builder.build(repository_id, chunk_dicts))
            log.info(
                "indexing.graph_built",
                repo_id=repository_id,
                entities=graph_res.entities_created,
                relationships=graph_res.relationships_created,
            )
        except Exception as ge:
            log.warning("indexing.graph_build_failed", repo_id=repository_id, error=str(ge))

        # ─── Step 6: Update database ─────────────────────────────
        duration_ms = int((time.time() - start_time) * 1000)

        # Sync DB update
        sync_engine = create_engine(settings.DATABASE_SYNC_URL)
        Session = sessionmaker(bind=sync_engine)
        with Session() as session:
            from backend.models import Repository, IndexingStatus
            repo = session.query(Repository).filter_by(id=repository_id).first()
            if repo:
                repo.indexed_status = IndexingStatus.INDEXED
                repo.indexing_progress = 100
                repo.total_files = total_files
                repo.indexed_files = total_files
                repo.total_chunks = total_stored
                repo.detected_languages = detected_languages
                repo.embedding_model_version = embedder.model_version
                session.commit()

        sync_engine.dispose()

        # ─── Complete ────────────────────────────────────────────
        _publish_event(redis_client, project_id, {
            "type": "indexing_complete",
            "repository_id": repository_id,
            "progress": 100,
            "total_files": total_files,
            "total_chunks": total_stored,
            "duration_ms": duration_ms,
            "detected_languages": detected_languages,
        })

        log.info("indexing.complete",
                 repo_id=repository_id,
                 total_files=total_files,
                 total_chunks=total_stored,
                 duration_ms=duration_ms)

        return {
            "status": "success",
            "total_files": total_files,
            "total_chunks": total_stored,
            "duration_ms": duration_ms,
        }

    except Exception as e:
        log.error("indexing.failed", repo_id=repository_id, error=str(e))

        # Update DB status to failed
        try:
            sync_engine = create_engine(settings.DATABASE_SYNC_URL)
            Session = sessionmaker(bind=sync_engine)
            with Session() as session:
                from backend.models import Repository, IndexingStatus
                repo = session.query(Repository).filter_by(id=repository_id).first()
                if repo:
                    repo.indexed_status = IndexingStatus.FAILED
                    session.commit()
            sync_engine.dispose()
        except Exception:
            pass

        _publish_event(redis_client, project_id, {
            "type": "indexing_error",
            "repository_id": repository_id,
            "error": str(e),
        })

        raise self.retry(exc=e, countdown=30)
