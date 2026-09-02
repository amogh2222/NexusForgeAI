"""
NexusForge AI — Neo4j Knowledge Graph Client

Models code repositories as property graphs for architectural reasoning.
Uses neo4j-rust-ext for 3-10x throughput over the pure-Python driver.

Graph Schema:
  Nodes:         Repository, File, Function, Class, Service, APIEndpoint, DBTable, Package
  Relationships: IMPORTS, CALLS, INHERITS, EXPOSES_API, READS_TABLE, WRITES_TABLE, DEPENDS_ON

Key capabilities:
  - Dependency traversal (what does AuthService depend on?)
  - Blast radius analysis (what breaks if I change this function?)
  - Circular dependency detection
  - Architectural chokepoint identification
  - Shortest path between any two entities
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import structlog

log = structlog.get_logger()


# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class CodeEntity:
    name: str
    entity_type: str    # "Service", "Function", "APIEndpoint", "DBTable", "Class", "Package", "File"
    repo_id: str
    file_path: str = ""
    language: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class CodeRelationship:
    from_name: str
    from_type: str
    to_name: str
    to_type: str
    rel_type: str       # "IMPORTS", "CALLS", "INHERITS", "EXPOSES_API", "READS_TABLE", "WRITES_TABLE", "DEPENDS_ON"
    metadata: dict = field(default_factory=dict)


# ─── Client ───────────────────────────────────────────────────────────────────

class Neo4jClient:
    """
    Async Neo4j client for architectural knowledge graphs.

    Uses AsyncGraphDatabase.driver() — always reuse a single driver instance.
    MERGE semantics everywhere — safe to re-ingest on re-indexing.
    """

    _instance: Optional["Neo4jClient"] = None

    def __init__(self) -> None:
        from backend.core.config import settings
        self._s = settings
        self._driver = None
        self._available = False
        self._init_driver()

    def _init_driver(self) -> None:
        try:
            from neo4j import AsyncGraphDatabase
            self._driver = AsyncGraphDatabase.driver(
                self._s.NEO4J_URI,
                auth=(self._s.NEO4J_USER, self._s.NEO4J_PASSWORD),
                max_connection_pool_size=20,
            )
            self._available = True
            log.info("neo4j.client.initialized", uri=self._s.NEO4J_URI)
        except ImportError:
            log.warning("neo4j.not_installed", hint="pip install neo4j neo4j-rust-ext")
        except Exception as e:
            log.warning("neo4j.init_failed", error=str(e))

    # ─── Schema ──────────────────────────────────────────────────────────────

    async def setup_schema(self) -> None:
        """Create constraints + indexes. Idempotent (IF NOT EXISTS)."""
        if not self._available:
            return

        stmts = [
            "CREATE CONSTRAINT repo_id IF NOT EXISTS FOR (r:Repository) REQUIRE r.id IS UNIQUE",
            "CREATE CONSTRAINT function_fqn IF NOT EXISTS FOR (f:Function) REQUIRE f.fqn IS UNIQUE",
            "CREATE INDEX entity_repo IF NOT EXISTS FOR (n:Service) ON (n.repo_id)",
            "CREATE INDEX entity_file IF NOT EXISTS FOR (n:Function) ON (n.file_path)",
        ]
        async with self._driver.session(database=self._s.NEO4J_DATABASE) as session:
            for stmt in stmts:
                try:
                    await session.run(stmt)
                except Exception as e:
                    log.warning("neo4j.schema_stmt_failed", error=str(e)[:80])
        log.info("neo4j.schema_ready")

    initialize_schema = setup_schema

    async def ingest_entities(self, entities: list[CodeEntity]) -> int:
        """Bulk MERGE entities into the graph. Idempotent."""
        if not self._available or not entities:
            return 0

        async with self._driver.session(database=self._s.NEO4J_DATABASE) as session:
            # Group by entity_type for typed MERGE
            by_type: dict[str, list[dict]] = {}
            for e in entities:
                by_type.setdefault(e.entity_type, []).append({
                    "name": e.name,
                    "repo_id": e.repo_id,
                    "file_path": e.file_path,
                    "language": e.language,
                })

            total = 0
            for entity_type, batch in by_type.items():
                # Use dynamic label via APOC if available, else per-type queries
                try:
                    result = await session.run(
                        f"""
                        UNWIND $batch AS e
                        MERGE (n:{entity_type} {{name: e.name, repo_id: e.repo_id}})
                        SET n.file_path = e.file_path,
                            n.language = e.language,
                            n.updated_at = timestamp()
                        RETURN count(n) AS cnt
                        """,
                        batch=batch,
                    )
                    record = await result.single()
                    total += record["cnt"] if record else len(batch)
                except Exception as ex:
                    log.warning("neo4j.entity_batch_failed", type=entity_type, error=str(ex))

            log.info("neo4j.entities_ingested", total=total)
            return total

    async def ingest_relationships(self, relationships: list[CodeRelationship]) -> int:
        """MERGE relationships between entities."""
        if not self._available or not relationships:
            return 0

        count = 0
        async with self._driver.session(database=self._s.NEO4J_DATABASE) as session:
            for rel in relationships:
                try:
                    await session.run(
                        f"""
                        MATCH (a {{name: $from_name}})
                        MATCH (b {{name: $to_name}})
                        MERGE (a)-[r:{rel.rel_type}]->(b)
                        SET r.updated_at = timestamp()
                        """,
                        from_name=rel.from_name,
                        to_name=rel.to_name,
                    )
                    count += 1
                except Exception as e:
                    log.warning(
                        "neo4j.rel_failed",
                        rel=f"{rel.from_name}->{rel.to_name}",
                        error=str(e)[:60],
                    )

        log.info("neo4j.relationships_ingested", count=count)
        return count

    # ─── Query Operations ────────────────────────────────────────────────────

    async def query_dependencies(
        self, entity_name: str, max_depth: int = 5
    ) -> list[dict]:
        """Get all downstream dependencies of an entity (up to max_depth hops)."""
        if not self._available:
            return []
        async with self._driver.session(database=self._s.NEO4J_DATABASE) as session:
            result = await session.run(
                """
                MATCH (start {name: $name})
                MATCH (start)-[:CALLS|IMPORTS|DEPENDS_ON*1..$depth]->(dep)
                RETURN dep.name AS name,
                       labels(dep)[0] AS type,
                       dep.file_path AS file_path
                LIMIT 50
                """,
                name=entity_name,
                depth=max_depth,
            )
            return [dict(r) async for r in result]

    async def query_shortest_path(
        self, from_name: str, to_name: str
    ) -> list[dict]:
        """Find shortest architectural path between two entities."""
        if not self._available:
            return []
        async with self._driver.session(database=self._s.NEO4J_DATABASE) as session:
            result = await session.run(
                """
                MATCH p = shortestPath(
                    (a {name: $from_name})-[*..10]-(b {name: $to_name})
                )
                RETURN [n IN nodes(p) | {name: n.name, type: labels(n)[0]}] AS path,
                       [r IN relationships(p) | type(r)] AS rels
                """,
                from_name=from_name,
                to_name=to_name,
            )
            record = await result.single()
            if not record:
                return []
            return [{"path": record["path"], "relationships": record["rels"]}]

    async def find_high_impact_entities(self, repo_id: str) -> list[dict]:
        """Architectural chokepoints — entities that many others depend on."""
        if not self._available:
            return []
        async with self._driver.session(database=self._s.NEO4J_DATABASE) as session:
            result = await session.run(
                """
                MATCH (e {repo_id: $repo_id})<-[:CALLS|IMPORTS|DEPENDS_ON]-(caller)
                RETURN e.name AS name,
                       labels(e)[0] AS type,
                       count(caller) AS dependents
                ORDER BY dependents DESC
                LIMIT 20
                """,
                repo_id=repo_id,
            )
            return [dict(r) async for r in result]

    async def find_circular_dependencies(self, repo_id: str) -> list[dict]:
        """Detect circular import/call chains — major architecture smell."""
        if not self._available:
            return []
        async with self._driver.session(database=self._s.NEO4J_DATABASE) as session:
            result = await session.run(
                """
                MATCH p = (s {repo_id: $repo_id})-[:CALLS|IMPORTS*2..8]->(s)
                RETURN [n IN nodes(p) | n.name] AS cycle
                LIMIT 10
                """,
                repo_id=repo_id,
            )
            return [dict(r) async for r in result]

    async def get_api_endpoints(self, repo_id: str) -> list[dict]:
        """Get all detected API endpoints in the repository."""
        if not self._available:
            return []
        async with self._driver.session(database=self._s.NEO4J_DATABASE) as session:
            result = await session.run(
                """
                MATCH (e:APIEndpoint {repo_id: $repo_id})
                OPTIONAL MATCH (f:Function)-[:EXPOSES_API]->(e)
                RETURN e.name AS path,
                       e.method AS method,
                       f.name AS handler,
                       f.file_path AS file_path
                ORDER BY e.name
                """,
                repo_id=repo_id,
            )
            return [dict(r) async for r in result]

    async def get_repo_stats(self, repo_id: str) -> dict:
        """Graph statistics for a repository."""
        if not self._available:
            return {"available": False}
        async with self._driver.session(database=self._s.NEO4J_DATABASE) as session:
            result = await session.run(
                """
                MATCH (n {repo_id: $repo_id})
                RETURN labels(n)[0] AS entity_type, count(n) AS count
                ORDER BY count DESC
                """,
                repo_id=repo_id,
            )
            stats: dict = {"available": True}
            async for r in result:
                stats[r["entity_type"]] = r["count"]
            return stats

    async def delete_repo_graph(self, repo_id: str) -> None:
        """Delete all nodes for a repo — used on re-indexing."""
        if not self._available:
            return
        async with self._driver.session(database=self._s.NEO4J_DATABASE) as session:
            await session.run(
                "MATCH (n {repo_id: $repo_id}) DETACH DELETE n",
                repo_id=repo_id,
            )
        log.info("neo4j.repo_deleted", repo_id=repo_id)

    async def verify_connectivity(self) -> bool:
        if not self._available:
            return False
        try:
            await self._driver.verify_connectivity()
            return True
        except Exception as e:
            log.warning("neo4j.connectivity_check_failed", error=str(e))
            return False

    async def close(self) -> None:
        if self._driver:
            await self._driver.close()

    def is_available(self) -> bool:
        return self._available

    @classmethod
    def get_instance(cls) -> "Neo4jClient":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
