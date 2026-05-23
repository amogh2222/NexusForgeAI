"""
NexusForge AI — Repository Graph Builder
Extracts code entities and relationships from AST chunk metadata
and ingests them into the Neo4j knowledge graph.

Runs AFTER the AST chunking step in the indexing pipeline.
Extracts: functions, classes, services, API endpoints, DB tables,
and their relationships (IMPORTS, CALLS, INHERITS, EXPOSES_API).
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import Any

import structlog

from graph.neo4j_client import CodeEntity, CodeRelationship, Neo4jClient

log = structlog.get_logger()


@dataclass
class GraphBuildResult:
    repo_id: str
    entities_created: int
    relationships_created: int
    duration_ms: float
    errors: list[str] = field(default_factory=list)


class RepoGraphBuilder:
    """
    Builds a Neo4j knowledge graph from AST-chunked repository data.

    Input:  list of chunk dicts (from ast_chunker / text_chunker output)
    Output: entities + relationships persisted to Neo4j
    """

    # FastAPI route decorators → APIEndpoint nodes
    ROUTE_PATTERN = re.compile(
        r'@\w+\.(get|post|put|delete|patch|head|options)\(["\']([^"\']+)["\']',
        re.IGNORECASE,
    )

    # SQLAlchemy table name extraction
    TABLENAME_PATTERN = re.compile(r'__tablename__\s*=\s*["\'](\w+)["\']')

    # Python import patterns
    IMPORT_PATTERN = re.compile(
        r'^(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))',
        re.MULTILINE,
    )

    # Function call pattern (simple heuristic)
    CALL_PATTERN = re.compile(r'\b(\w+)\s*\(')

    # Class inheritance
    CLASS_INHERIT_PATTERN = re.compile(r'class\s+(\w+)\s*\(([^)]+)\)')

    async def build(self, repo_id: str, chunks: list[dict[str, Any]]) -> GraphBuildResult:
        """
        Process all chunks and build the knowledge graph.

        Args:
            repo_id: UUID of the repository
            chunks:  List of dicts with keys: content, file_path, language,
                     node_type, start_line, end_line, metadata
        """
        start = time.perf_counter()
        client = Neo4jClient.get_instance()

        if not client.is_available():
            log.warning("graph_builder.neo4j_unavailable", repo_id=repo_id)
            return GraphBuildResult(
                repo_id=repo_id,
                entities_created=0,
                relationships_created=0,
                duration_ms=0,
                errors=["Neo4j not available"],
            )

        # First pass: collect entities
        entities: list[CodeEntity] = []
        relationships: list[CodeRelationship] = []
        seen_entities: set[str] = set()

        for chunk in chunks:
            meta = chunk.get("metadata", {})
            content = chunk.get("content", "")
            file_path = chunk.get("file_path", meta.get("file_path", ""))
            language = chunk.get("language", meta.get("language", ""))
            node_type = chunk.get("node_type", meta.get("node_type", ""))

            # ── File entity ────────────────────────────────────────────────
            if file_path and file_path not in seen_entities:
                entities.append(CodeEntity(
                    name=file_path,
                    entity_type="File",
                    repo_id=repo_id,
                    file_path=file_path,
                    language=language,
                ))
                seen_entities.add(file_path)

            # ── Function / Class entities ──────────────────────────────────
            if node_type in ("function_definition", "method_definition", "function"):
                func_name = meta.get("name") or self._extract_function_name(content)
                if func_name:
                    fqn = f"{file_path}::{func_name}"
                    if fqn not in seen_entities:
                        entities.append(CodeEntity(
                            name=fqn,
                            entity_type="Function",
                            repo_id=repo_id,
                            file_path=file_path,
                            language=language,
                            metadata={"simple_name": func_name},
                        ))
                        seen_entities.add(fqn)

                    # Link function to file
                    relationships.append(CodeRelationship(
                        from_name=file_path,
                        from_type="File",
                        to_name=fqn,
                        to_type="Function",
                        rel_type="CONTAINS",
                    ))

                    # Detect FastAPI routes
                    for match in self.ROUTE_PATTERN.finditer(content):
                        method = match.group(1).upper()
                        path = match.group(2)
                        endpoint_name = f"{method} {path}"
                        if endpoint_name not in seen_entities:
                            entities.append(CodeEntity(
                                name=endpoint_name,
                                entity_type="APIEndpoint",
                                repo_id=repo_id,
                                file_path=file_path,
                                metadata={"method": method, "path": path},
                            ))
                            seen_entities.add(endpoint_name)
                        relationships.append(CodeRelationship(
                            from_name=fqn,
                            from_type="Function",
                            to_name=endpoint_name,
                            to_type="APIEndpoint",
                            rel_type="EXPOSES_API",
                        ))

            elif node_type in ("class_definition", "class"):
                class_name = meta.get("name") or self._extract_class_name(content)
                if class_name:
                    fqn = f"{file_path}::{class_name}"
                    if fqn not in seen_entities:
                        entities.append(CodeEntity(
                            name=fqn,
                            entity_type="Class",
                            repo_id=repo_id,
                            file_path=file_path,
                            language=language,
                        ))
                        seen_entities.add(fqn)

                    # Detect SQLAlchemy models → DBTable
                    tablename_match = self.TABLENAME_PATTERN.search(content)
                    if tablename_match:
                        table_name = tablename_match.group(1)
                        if table_name not in seen_entities:
                            entities.append(CodeEntity(
                                name=table_name,
                                entity_type="DBTable",
                                repo_id=repo_id,
                                file_path=file_path,
                            ))
                            seen_entities.add(table_name)
                        relationships.append(CodeRelationship(
                            from_name=fqn,
                            from_type="Class",
                            to_name=table_name,
                            to_type="DBTable",
                            rel_type="MAPS_TO",
                        ))

                    # Class inheritance
                    for inherit_match in self.CLASS_INHERIT_PATTERN.finditer(content):
                        parent_names = [p.strip() for p in inherit_match.group(2).split(",")]
                        for parent in parent_names:
                            if parent and parent not in ("object", "ABC", "BaseModel"):
                                relationships.append(CodeRelationship(
                                    from_name=fqn,
                                    from_type="Class",
                                    to_name=parent,
                                    to_type="Class",
                                    rel_type="INHERITS",
                                ))

            # ── Import relationships ───────────────────────────────────────
            if language == "python" and content:
                for imp_match in self.IMPORT_PATTERN.finditer(content):
                    module = imp_match.group(1) or imp_match.group(2)
                    if module and not module.startswith("__"):
                        # Only ingest internal imports (not stdlib/third-party)
                        if "." in module:  # Likely internal relative import
                            relationships.append(CodeRelationship(
                                from_name=file_path,
                                from_type="File",
                                to_name=module,
                                to_type="Package",
                                rel_type="IMPORTS",
                            ))

        # Ingest to Neo4j
        entities_created = await client.ingest_entities(entities)
        relationships_created = await client.ingest_relationships(relationships)

        duration_ms = (time.perf_counter() - start) * 1000
        log.info(
            "graph_builder.complete",
            repo_id=repo_id,
            entities=entities_created,
            relationships=relationships_created,
            duration_ms=round(duration_ms, 1),
        )

        return GraphBuildResult(
            repo_id=repo_id,
            entities_created=entities_created,
            relationships_created=relationships_created,
            duration_ms=duration_ms,
        )

    # ─── Helpers ──────────────────────────────────────────────────────────────

    @staticmethod
    def _extract_function_name(content: str) -> str | None:
        """Extract function name from first line of content."""
        match = re.search(r'(?:def|func|function)\s+(\w+)', content[:200])
        return match.group(1) if match else None

    @staticmethod
    def _extract_class_name(content: str) -> str | None:
        match = re.search(r'class\s+(\w+)', content[:200])
        return match.group(1) if match else None
