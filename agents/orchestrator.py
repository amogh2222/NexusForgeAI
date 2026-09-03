"""
NexusForge AI — LangGraph Multi-Agent Orchestrator
StateGraph with Supervisor pattern + PostgresSaver checkpoints.
Research-validated: PostgresSaver (NOT MemorySaver) for production.
"""
from typing import Annotated, Optional, TypedDict

import structlog
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph import END, StateGraph, add_messages
from langgraph.graph.state import CompiledStateGraph

from backend.api.websocket.events import AgentEndEvent, AgentStartEvent

log = structlog.get_logger()


# ════════════════════════════════════════════════════════════════════
# SHARED STATE SCHEMA
# Research-validated: Store IDs/refs, not large content blobs,
# to prevent context explosion in graph state.
# ════════════════════════════════════════════════════════════════════
class NexusState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]  # Append-mode reducer
    project_id: str
    thread_id: str
    repository_id: Optional[str]

    # Task tracking
    current_task: str
    task_type: str   # "chat" | "readme" | "review" | "debug" | "codegen" | "infra"

    # RAG context (text summary only, not raw embeddings)
    retrieved_context: str
    context_sources: list[str]  # file paths

    # Agent outputs (populated as pipeline runs)
    plan: Optional[dict]
    generated_code: Optional[dict]
    review_results: Optional[dict]
    infra_bundle: Optional[dict]
    readme_content: Optional[str]
    debug_report: Optional[dict]
    sysdesign_result: Optional[str]
    time_machine_result: Optional[str]

    # Execution
    execution_id: Optional[str]
    execution_result: Optional[dict]

    # Metadata
    agent_history: list[str]
    error: Optional[str]
    total_tokens: int


def create_initial_state(
    project_id: str,
    thread_id: str,
    user_message: str,
    repository_id: Optional[str] = None,
) -> NexusState:
    """Factory for creating a fresh graph state."""
    return {
        "messages": [HumanMessage(content=user_message)],
        "project_id": project_id,
        "thread_id": thread_id,
        "repository_id": repository_id,
        "current_task": user_message,
        "task_type": "chat",
        "retrieved_context": "",
        "context_sources": [],
        "plan": None,
        "generated_code": None,
        "review_results": None,
        "infra_bundle": None,
        "readme_content": None,
        "debug_report": None,
        "sysdesign_result": None,
        "time_machine_result": None,
        "execution_id": None,
        "execution_result": None,
        "agent_history": [],
        "error": None,
        "total_tokens": 0,
    }


# ════════════════════════════════════════════════════════════════════
# ORCHESTRATOR
# ════════════════════════════════════════════════════════════════════
class NexusOrchestrator:
    """
    Central LangGraph orchestrator managing the 6 specialized agents.
    Uses a Supervisor pattern with conditional routing based on task_type.
    """

    def __init__(self):
        self._graph: Optional[CompiledStateGraph] = None

    async def _build_graph(self) -> CompiledStateGraph:
        """Build and compile the LangGraph StateGraph."""
        from agents.planner.agent import PlannerAgent
        from agents.coder.agent import CoderAgent
        from agents.reviewer.agent import ReviewerAgent
        from agents.infra.agent import InfraAgent
        from agents.docs.agent import DocsAgent
        from agents.debugger.agent import DebuggerAgent
        from agents.sysdesign.agent import SysDesignAgent
        from agents.time_machine.agent import TimeMachineAgent
        from agents.plugin.agent import PluginAgent

        planner = PlannerAgent()
        coder = CoderAgent()
        reviewer = ReviewerAgent()
        infra = InfraAgent()
        docs = DocsAgent()
        debugger = DebuggerAgent()
        sysdesign = SysDesignAgent()
        time_machine = TimeMachineAgent()
        plugin_agent = PluginAgent()

        # ─── Graph Definition ────────────────────────────────────
        graph = StateGraph(NexusState)

        # Add all agent nodes
        graph.add_node("retrieve_context", self._retrieve_context_node)
        graph.add_node("supervisor", self._supervisor_node)
        graph.add_node("planner", planner.run)
        graph.add_node("coder", coder.run)
        graph.add_node("reviewer", reviewer.run)
        graph.add_node("infra", infra.run)
        graph.add_node("docs", docs.run)
        graph.add_node("debugger", debugger.run)
        graph.add_node("sysdesign", sysdesign.run)
        graph.add_node("time_machine", time_machine.run)
        graph.add_node("plugin", plugin_agent.run)
        graph.add_node("finalizer", self._finalizer_node)

        # ─── Entry: always retrieve context first ────────────────
        graph.set_entry_point("retrieve_context")
        graph.add_edge("retrieve_context", "supervisor")

        # ─── Supervisor routes to specialized agents ─────────────
        graph.add_conditional_edges(
            "supervisor",
            self._route_task,
            {
                "planner": "planner",
                "coder": "coder",
                "reviewer": "reviewer",
                "infra": "infra",
                "docs": "docs",
                "debugger": "debugger",
                "sysdesign": "sysdesign",
                "time_machine": "time_machine",
                "plugin": "plugin",
                "finalize": "finalizer",
            },
        )

        # ─── After planning, route to execution ──────────────────
        graph.add_conditional_edges(
            "planner",
            self._route_after_planning,
            {
                "coder": "coder",
                "reviewer": "reviewer",
                "infra": "infra",
                "docs": "docs",
                "finalize": "finalizer",
            },
        )

        # ─── After coding, always review ─────────────────────────
        graph.add_edge("coder", "reviewer")

        # ─── Reviewer can trigger debugger ────────────────────────
        graph.add_conditional_edges(
            "reviewer",
            self._route_after_review,
            {
                "debugger": "debugger",
                "finalize": "finalizer",
            },
        )

        # ─── All terminal nodes go to finalizer ──────────────────
        graph.add_edge("infra", "finalizer")
        graph.add_edge("docs", "finalizer")
        graph.add_edge("debugger", "finalizer")
        graph.add_edge("sysdesign", "finalizer")
        graph.add_edge("time_machine", "finalizer")
        graph.add_edge("plugin", "finalizer")
        graph.add_edge("finalizer", END)

        # ─── Compile with MemorySaver checkpoint ────────────────
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        return graph.compile(checkpointer=checkpointer)

    async def get_graph(self) -> CompiledStateGraph:
        """Lazily build and cache the compiled graph."""
        if self._graph is None:
            self._graph = await self._build_graph()
        return self._graph

    # ─── Nodes ───────────────────────────────────────────────────

    async def _retrieve_context_node(self, state: NexusState) -> dict:
        """RAG retrieval: find relevant code context for the current task."""
        if not state.get("repository_id"):
            return {"retrieved_context": "", "context_sources": []}

        try:
            from rag.retrieval.retriever import HybridRetriever
            retriever = HybridRetriever()
            context, sources = await retriever.retrieve(
                query=state["current_task"],
                project_id=state["project_id"],
            )
            return {
                "retrieved_context": context,
                "context_sources": sources,
            }
        except Exception as e:
            log.warning("orchestrator.retrieval_failed", error=str(e))
            return {"retrieved_context": "", "context_sources": []}

    async def _supervisor_node(self, state: NexusState) -> dict:
        """Classify the task and determine which agent should handle it."""
        task = state["current_task"].lower()

        # Specific domain tasks MUST be checked before generic verbs (generate, write, create)
        if any(kw in task for kw in ["system design", "hld", "scale to", "architect", "architecture", "cqrs", "url shortener", "design a"]):
            task_type = "sysdesign"
        elif any(kw in task for kw in ["readme", "documentation", "generate docs", "document"]):
            task_type = "readme"
        elif any(kw in task for kw in ["review", "audit", "check code", "code review", "security audit"]):
            task_type = "review"
        elif any(kw in task for kw in ["dockerfile", "docker-compose", "deploy", "kubernetes", "ci/cd", "pipeline", "infra"]):
            task_type = "infra"
        elif any(kw in task for kw in ["debug", "error", "fix", "traceback", "exception", "crash", "vulnerability", "bug"]):
            task_type = "debug"
        elif any(kw in task for kw in ["history", "evolution", "time machine", "drift", "commits"]):
            task_type = "time_machine"
        elif any(kw in task for kw in ["pull request", "issue", "kubernetes pod"]):
            task_type = "plugin"
        elif any(kw in task for kw in ["generate", "write", "implement", "create", "code", "function", "class", "script"]):
            task_type = "codegen"
        else:
            task_type = "chat"

        log.info("orchestrator.task_classified", task_type=task_type, task=task[:100])
        return {"task_type": task_type}

    def _route_task(self, state: NexusState) -> str:
        """Route from supervisor to the appropriate agent."""
        routing_map = {
            "debug": "debugger",
            "codegen": "planner",
            "review": "reviewer",
            "infra": "infra",
            "readme": "docs",
            "sysdesign": "sysdesign",
            "time_machine": "time_machine",
            "plugin": "plugin",
            "chat": "docs",  # For general Q&A, docs agent handles it
        }
        return routing_map.get(state["task_type"], "finalize")

    def _route_after_planning(self, state: NexusState) -> str:
        """After planning, route to the appropriate execution agent."""
        plan = state.get("plan", {})
        if not plan:
            return "finalize"
        first_step_agent = plan.get("first_agent", "coder")
        return first_step_agent if first_step_agent in ["coder", "reviewer", "infra", "docs"] else "coder"

    def _route_after_review(self, state: NexusState) -> str:
        """After review, trigger debugger if critical issues found."""
        review = state.get("review_results", {})
        critical_issues = review.get("critical_issues", [])
        if critical_issues and len(critical_issues) > 0:
            return "debugger"
        return "finalize"

    async def _finalizer_node(self, state: NexusState) -> dict:
        """Aggregate all agent outputs into a complete, rich, user-facing response."""
        content_blocks = []

        # 1. README / Documentation Content
        if state.get("readme_content"):
            content_blocks.append(state["readme_content"])

        # 2. System Design Output
        if state.get("sysdesign_result"):
            content_blocks.append(state["sysdesign_result"])

        # 3. Generated Code Content (full files with syntax highlighting)
        if state.get("generated_code"):
            gen = state["generated_code"]
            files = gen.get("files", [])
            if files:
                code_parts = [f"## Generated Implementation: {gen.get('task_description', 'Code Solution')}\n"]
                for f in files:
                    f_path = f.get("path", "file.py")
                    f_lang = f.get("language") or ("python" if f_path.endswith(".py") else "text")
                    f_content = f.get("content", "")
                    f_expl = f.get("explanation", "")
                    code_parts.append(f"### `{f_path}`\n```{f_lang}\n{f_content}\n```")
                    if f_expl:
                        code_parts.append(f"{f_expl}\n")
                if gen.get("dependencies"):
                    code_parts.append(f"**Dependencies**: `{', '.join(gen['dependencies'])}`\n")
                if gen.get("setup_instructions"):
                    code_parts.append(f"**Setup Instructions**:\n{gen['setup_instructions']}\n")
                content_blocks.append("\n".join(code_parts))

            # Auto-save files if repository_id present
            if state.get("repository_id") and files:
                try:
                    from backend.core.database import AsyncSessionLocal
                    from backend.core.file_applier import FileApplier
                    async with AsyncSessionLocal() as db:
                        applier = FileApplier(db)
                        await applier.apply_changes(state["repository_id"], state["generated_code"])
                except Exception as e:
                    log.error("finalizer.file_applier_failed", error=str(e))

        # 4. Debug Report (root cause, explanation, and fixed code)
        if state.get("debug_report"):
            rep = state["debug_report"]
            debug_parts = [
                "## Debug & Fix Report\n",
                f"**Root Cause**: {rep.get('root_cause', 'Unknown')}\n",
                f"**Error Type**: {rep.get('error_type', 'General')}\n",
                f"**Explanation**: {rep.get('explanation', '')}\n",
            ]
            if rep.get("fixed_code"):
                debug_parts.append(f"### Fixed Code\n```python\n{rep['fixed_code']}\n```\n")
            if rep.get("additional_fixes"):
                debug_parts.append("**Recommended Additional Fixes**:\n" + "\n".join(f"- {fix}" for fix in rep["additional_fixes"]) + "\n")
            content_blocks.append("\n".join(debug_parts))

        # 5. Infrastructure Bundle
        if state.get("infra_bundle"):
            infra = state["infra_bundle"]
            infra_parts = ["## Infrastructure Configurations\n"]
            if infra.get("dockerfile"):
                infra_parts.append(f"### Dockerfile\n```dockerfile\n{infra['dockerfile']}\n```\n")
            if infra.get("docker_compose"):
                infra_parts.append(f"### docker-compose.yml\n```yaml\n{infra['docker_compose']}\n```\n")
            if infra.get("ci_cd"):
                infra_parts.append(f"### CI/CD Pipeline\n```yaml\n{infra['ci_cd']}\n```\n")
            if infra.get("setup_instructions"):
                infra_parts.append(f"**Deployment Instructions**:\n{infra['setup_instructions']}\n")
            content_blocks.append("\n".join(infra_parts))

        # 6. Review Results (score, issues, recommendations)
        if state.get("review_results"):
            rev = state["review_results"]
            rev_parts = [
                "## Code Review Report\n",
                f"**Overall Score**: {rev.get('overall_score', 'N/A')}/100\n",
                f"**Summary**: {rev.get('summary', 'Review complete.')}\n",
            ]
            issues = rev.get("issues", [])
            if issues:
                rev_parts.append(f"### Issues Identified ({len(issues)})\n")
                for iss in issues:
                    sev = iss.get('severity', 'info').upper()
                    cat = iss.get('category', 'general')
                    desc = iss.get('description', '')
                    sug = iss.get('suggestion', '')
                    loc = iss.get('location', '')
                    loc_str = f" (`{loc}`)" if loc else ""
                    rev_parts.append(f"- **[{sev}]** {cat}{loc_str}: {desc}")
                    if sug:
                        rev_parts.append(f"  *Fix Suggestion*: {sug}")
            recs = rev.get("recommendations", [])
            if recs:
                rev_parts.append("\n### Recommendations\n" + "\n".join(f"- {r}" for r in recs))
            content_blocks.append("\n".join(rev_parts))

        # 7. Time Machine Result
        if state.get("time_machine_result"):
            content_blocks.append(f"## Time Machine Analysis\n\n{state['time_machine_result']}")

        # 8. Fallback to assistant messages if no specialized block was generated
        if not content_blocks:
            for msg in reversed(state.get("messages", [])):
                if hasattr(msg, "content") and msg.content:
                    msg_type = getattr(msg, "type", "")
                    if msg_type in ["ai", "assistant"]:
                        content_blocks.append(msg.content)
                        break

        # 9. Execution Summary Footer
        meta_items = []
        if state.get("agent_history"):
            agents_chain = " ➔ ".join(state["agent_history"] + ["finalizer"])
            meta_items.append(f"**Agent Pipeline**: `{agents_chain}`")

        if content_blocks:
            final_content = "\n\n---\n\n".join(content_blocks)
        elif state.get("error"):
            final_content = f"⚠️ Pipeline halted with error: {state['error']}"
        else:
            final_content = "⚠️ The agent pipeline concluded without generating output content. Please verify that the selected task matches the input context."
        if meta_items:
            final_content += "\n\n> " + " | ".join(meta_items)

        return {
            "messages": [AIMessage(content=final_content)],
            "agent_history": state["agent_history"] + ["finalizer"],
        }

    # ─── Public API ──────────────────────────────────────────────

    async def arun(
        self,
        project_id: str,
        thread_id: str,
        user_message: str,
        repository_id: Optional[str] = None,
        websocket_broadcaster=None,
    ) -> NexusState:
        """
        Run the agent pipeline for a user message.
        Streams events via websocket_broadcaster if provided.
        """
        graph = await self.get_graph()
        state = create_initial_state(project_id, thread_id, user_message, repository_id)
        config = {"configurable": {"thread_id": thread_id}}

        final_state = None

        # Stream events using astream_events v2 (research-validated)
        async for event in graph.astream_events(state, config=config, version="v2"):
            kind = event["event"]

            if kind == "on_chain_start":
                node = event.get("name", "")
                if node and websocket_broadcaster:
                    await websocket_broadcaster(
                        AgentStartEvent(
                            agent_name=node,
                            action=f"Starting {node}",
                            thread_id=thread_id,
                        ).to_dict(),
                        project_id=project_id,
                        thread_id=thread_id,
                    )
                # Publish to Kafka
                from backend.core.kafka_stream import KafkaEventStream
                await KafkaEventStream.get_instance().publish(
                    topic="nexusforge.agent.events",
                    event_type="agent_start",
                    payload={"project_id": project_id, "thread_id": thread_id, "agent": node}
                )

            elif kind == "on_chat_model_stream":
                content = event["data"]["chunk"].content
                if content and websocket_broadcaster:
                    from backend.api.websocket.events import TokenEvent
                    await websocket_broadcaster(
                        TokenEvent(
                            content=content,
                            thread_id=thread_id,
                        ).to_dict(),
                        project_id=project_id,
                        thread_id=thread_id,
                    )

            elif kind == "on_chain_end":
                node = event.get("name", "")
                if node and websocket_broadcaster:
                    await websocket_broadcaster(
                        AgentEndEvent(
                            agent_name=node,
                            action=f"Completed {node}",
                            thread_id=thread_id,
                        ).to_dict(),
                        project_id=project_id,
                        thread_id=thread_id,
                    )
                # Publish to Kafka
                if node:
                    from backend.core.kafka_stream import KafkaEventStream
                    await KafkaEventStream.get_instance().publish(
                        topic="nexusforge.agent.events",
                        event_type="agent_end",
                        payload={"project_id": project_id, "thread_id": thread_id, "agent": node}
                    )
                final_state = event.get("data", {}).get("output")

        return final_state


# ─── Singleton ───────────────────────────────────────────────────
_orchestrator: Optional[NexusOrchestrator] = None


def get_orchestrator() -> NexusOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = NexusOrchestrator()
    return _orchestrator
