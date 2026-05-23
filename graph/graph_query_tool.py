"""
NexusForge AI — Graph Query Tool (LangChain integration)
Wraps Neo4j graph queries as a LangChain StructuredTool for agent use.

Agents call this tool when questions require architectural reasoning:
  "What services depend on AuthService?"
  "How is the Database connected to the API layer?"
  "Are there any circular dependencies?"
"""
from __future__ import annotations

from typing import Literal, Optional

import structlog
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from graph.neo4j_client import Neo4jClient

log = structlog.get_logger()


class GraphQueryInput(BaseModel):
    query_type: Literal["dependencies", "path", "impact", "circular", "endpoints", "summary"] = Field(
        description="Type of graph query to run"
    )
    repo_id: str = Field(description="Repository UUID to query")
    entity_name: Optional[str] = Field(
        default=None,
        description="Name of the entity to query (function, class, service name)",
    )
    target_name: Optional[str] = Field(
        default=None,
        description="Target entity for path queries",
    )
    max_depth: int = Field(default=5, description="Maximum traversal depth")


async def _execute_graph_query(
    query_type: str,
    repo_id: str,
    entity_name: Optional[str] = None,
    target_name: Optional[str] = None,
    max_depth: int = 5,
) -> str:
    """Execute a graph query and return formatted text for LLM context."""
    client = Neo4jClient.get_instance()

    if not client.is_available():
        return "⚠️ Knowledge graph not available. Neo4j connection failed or not configured."

    try:
        match query_type:
            case "dependencies":
                if not entity_name:
                    return "Error: entity_name required for dependencies query"
                results = await client.query_dependencies(entity_name, max_depth)
                if not results:
                    return f"No dependencies found for '{entity_name}'"
                lines = [f"Dependencies of `{entity_name}` (up to {max_depth} hops):"]
                for r in results:
                    lines.append(f"  • [{r.get('type','?')}] {r.get('name','?')} ({r.get('file_path','?')})")
                return "\n".join(lines)

            case "path":
                if not entity_name or not target_name:
                    return "Error: entity_name and target_name required for path query"
                results = await client.query_shortest_path(entity_name, target_name)
                if not results:
                    return f"No path found between '{entity_name}' and '{target_name}'"
                path_info = results[0]
                nodes = " → ".join([n.get("name", "?") for n in path_info.get("path", [])])
                rels = " → ".join(path_info.get("relationships", []))
                return (
                    f"Architectural path: {entity_name} → {target_name}\n"
                    f"  Nodes: {nodes}\n"
                    f"  Via:   {rels}"
                )

            case "impact":
                results = await client.find_high_impact_entities(repo_id)
                if not results:
                    return "No high-impact entities found"
                lines = ["Architectural chokepoints (entities with most dependents):"]
                for r in results[:10]:
                    lines.append(
                        f"  • [{r.get('type','?')}] {r.get('name','?')} — {r.get('dependents', 0)} dependents"
                    )
                return "\n".join(lines)

            case "circular":
                results = await client.find_circular_dependencies(repo_id)
                if not results:
                    return "✅ No circular dependencies detected"
                lines = [f"⚠️ {len(results)} circular dependency chain(s) detected:"]
                for r in results:
                    cycle = " → ".join(r.get("cycle", []))
                    lines.append(f"  • {cycle}")
                return "\n".join(lines)

            case "endpoints":
                results = await client.get_api_endpoints(repo_id)
                if not results:
                    return "No API endpoints found in the knowledge graph"
                lines = ["Detected API endpoints:"]
                for r in results[:20]:
                    lines.append(
                        f"  • {r.get('method','?')} {r.get('path','?')} → {r.get('handler','?')} ({r.get('file_path','?')})"
                    )
                return "\n".join(lines)

            case "summary":
                stats = await client.get_repo_stats(repo_id)
                if not stats.get("available"):
                    return "Graph not yet built for this repository"
                lines = ["Knowledge graph summary:"]
                for entity_type, count in stats.items():
                    if entity_type != "available":
                        lines.append(f"  • {entity_type}: {count} nodes")
                return "\n".join(lines)

            case _:
                return f"Unknown query type: {query_type}"

    except Exception as e:
        log.warning("graph_tool.query_failed", query_type=query_type, error=str(e))
        return f"Graph query failed: {str(e)}"


def create_graph_query_tool() -> StructuredTool:
    """Create and return the graph query LangChain tool."""
    return StructuredTool.from_function(
        coroutine=_execute_graph_query,
        name="query_architecture_graph",
        description=(
            "Query the codebase knowledge graph to understand architectural relationships. "
            "Use this to answer: 'what depends on X?', 'what does Y call?', "
            "'how are A and B connected?', 'are there circular dependencies?', "
            "'what API endpoints exist?'. "
            "Always use this before answering architecture questions."
        ),
        args_schema=GraphQueryInput,
        return_direct=False,
    )
